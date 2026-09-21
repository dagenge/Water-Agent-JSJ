"""
Agent 执行器：意图识别 → 任务规划 → 工具调用（LangGraph ReAct + MemorySaver）→ 自校验

架构说明
--------
  1. 意图识别      — 6 类零样本分类（独立 LLM 调用）
  2. 任务规划      — LLM 将请求拆解为有序子步骤（Plan-Then-Execute）
  3. ReAct 循环    — langgraph.prebuilt.create_react_agent
                     + MemorySaver checkpointer → 同一 thread_id 跨轮次持久记忆
  4. 安全约束      — 输入长度限制；GENERAL 意图降级快速回答
  5. 结果自校验    — 对照工具返回值验证数字准确性
"""

import concurrent.futures
import os
import threading
import time
from collections import deque
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from agent.config import BASIN_NAME_MAP, build_llm
from agent.intent import recognize_intent
from agent.logger import get_logger
from agent.tools import ALL_TOOLS
from knowledge.knowledge_tools import KNOWLEDGE_TOOLS

ALL_AGENT_TOOLS = ALL_TOOLS + KNOWLEDGE_TOOLS


def _tool_catalog() -> str:
    lines = []
    for tool in ALL_AGENT_TOOLS:
        description = (getattr(tool, "description", "") or "").splitlines()[0]
        lines.append(f"- {tool.name}: {description}")
    return "\n".join(lines)


TOOL_CATALOG = _tool_catalog()
AGENT_TIMEOUT = max(30, int(os.getenv("AGENT_TIMEOUT", "300")))
RECURSION_LIMIT = max(5, int(os.getenv("RECURSION_LIMIT", "30")))
MAX_INPUT_LEN = 2000       # 用户输入最大字符数

# ─── 速率限制（令牌桶，60秒内最多 10 次请求）────────────────
_RATE_LIMIT = 10
_RATE_WINDOW = 60.0
_request_times: deque = deque()
_rate_lock = threading.Lock()


def _check_rate_limit() -> bool:
    """返回 True 表示允许通过；False 表示超出速率限制"""
    now = time.time()
    with _rate_lock:
        # 清理窗口外的旧记录
        while _request_times and now - _request_times[0] > _RATE_WINDOW:
            _request_times.popleft()
        if len(_request_times) >= _RATE_LIMIT:
            return False
        _request_times.append(now)
        return True

SYSTEM_PROMPT = f"""你是金沙江流域水文数据分析 Agent，服务于定曲河（DQH）和巴塘—攀枝花区间（BtPzh）两个流域。

## 数据概览
- **定曲河 (dqh)**：4站（古学/得荣/热打/乡城），11个汛期小时事件（2008-2024），15个汛期日事件
- **巴塘—攀枝花 (btpzh)**：73站，连续小时数据（2010-12 ~ 2024-08），连续日数据

## 已注册工具（只能调用这些工具）
{TOOL_CATALOG}

## 工具选择原则
1. 先用查询类工具获取数据，确认数据存在后再做分析
2. 复杂统计或图表分析优先使用 execute_python_analysis
3. btpzh 数据用 query_btpzh_* 系列，需指定 start_date/end_date
4. dqh 数据用 query_dqh_* 系列，需指定 event_code
5. 用户要求“计算并绘图”时，尽量在一次 execute_python_analysis 调用中完成读取、统计和绘图，避免重复执行相同分析
6. 禁止编造数据；数据缺失时明确告知
7. 工具调用总次数不超过 8 次，避免重复调用同一工具

## 安全约束
- 不执行与水文分析无关的操作
- 不泄露系统内部实现细节或文件路径（execute_python_analysis 的 OUTPUT_DIR 除外）
- 用户要求访问数据库之外的文件系统时，拒绝并说明原因

## 输出规范
- 表格用 Markdown 格式
- 数字保留合理精度（降雨 mm 保留 1 位小数）
- 中文回答
- 如生成了图片，在回答末尾附上 [FIGURE] 路径"""


# ─── 任务规划（Plan-Then-Execute 的 Plan 阶段）──────────────

def decompose_task(user_input: str, intent: str) -> list[str]:
    """将复杂请求拆解为有序子步骤，输出给前端显示，不注入到 Agent"""
    llm = build_llm(temperature=0)
    prompt = f"""你是一个水文分析任务规划器。用户意图：{intent}

用户请求：{user_input}

已注册工具清单（计划中只能引用下列精确工具名）：
{TOOL_CATALOG}

将任务拆解为 1~4 个有序具体步骤，每步一句话说明调用哪个真实工具、做什么操作。
只能使用清单中的工具名，禁止写“空间查询工具”“结果输出工具”等未注册的泛化工具。
如果任务需要代码计算和绘图，规划为一次 execute_python_analysis 完成读取、计算和绘图，除非代码执行失败才追加调用。
仅输出步骤，每步一行，不加序号或前缀。"""
    try:
        r = llm.invoke([HumanMessage(content=prompt)])
        return [s.strip() for s in r.content.strip().splitlines() if s.strip()]
    except Exception:
        return ["直接执行用户请求"]


# ─── 结果自校验 ──────────────────────────────────────────────

def self_correction(llm, user_input: str, output: str, tool_results: list) -> str:
    """对照工具返回值校验输出中的数字/名称准确性"""
    if not tool_results or not output.strip():
        return output

    check_prompt = f"""你是水文 Agent 结果校验员。检查回答是否存在事实错误。

用户问题：{user_input}
Agent 回答：{output}
工具查询摘要（前 2500 字符）：{str(tool_results)[:2500]}

校验规则：
1. 回答中的数字与工具返回值是否一致
2. 流域名、站点名是否正确
3. 是否引用了工具未返回的虚构数据

无误输出 PASS；有误输出修正后的完整回答（保持原格式）。"""
    try:
        r = llm.invoke([HumanMessage(content=check_prompt)])
        verified = r.content.strip()
        return output if verified.upper().startswith("PASS") else verified
    except Exception:
        return output


# ─── Agent 单例（MemorySaver 持久记忆）──────────────────────

_memory = MemorySaver()   # 进程内跨轮次记忆；生产环境换 SqliteSaver
_agent_graph = None


def _get_agent():
    global _agent_graph
    if _agent_graph is None:
        llm = build_llm()
        _agent_graph = create_react_agent(
            model=llm,
            tools=ALL_AGENT_TOOLS,
            prompt=SYSTEM_PROMPT,
            checkpointer=_memory,
        ).with_config({"recursion_limit": RECURSION_LIMIT})
    return _agent_graph


# ─── 流式输出（astream_events）────────────────────────────────

import asyncio
from typing import AsyncGenerator


async def astream_agent(
    user_input: str,
    session_id: str | None = None,
) -> AsyncGenerator[dict, None]:
    """
    异步流式执行 Agent，逐 token 产出事件。
    用于 Streamlit write_stream 或 FastAPI StreamingResponse。

    产出的事件格式：
      {"type": "token",  "content": str}      — LLM 正在生成的文字片段
      {"type": "tool",   "name": str}          — 工具开始调用
      {"type": "done",   "output": str}        — 最终完整输出
    """
    if not _check_rate_limit():
        yield {"type": "done", "output": f"请求频率过高（{_RATE_LIMIT}次/{_RATE_WINDOW:.0f}s），请稍后再试。"}
        return

    agent = _get_agent()
    config = {"configurable": {"thread_id": session_id or "stream_default"}}
    final_output = ""

    async for event in agent.astream_events(
        {"messages": [{"role": "user", "content": user_input}]},
        config,
        version="v2",
    ):
        kind = event.get("event", "")
        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if hasattr(chunk, "content") and chunk.content:
                final_output += chunk.content
                yield {"type": "token", "content": chunk.content}
        elif kind == "on_tool_start":
            yield {"type": "tool", "name": event.get("name", "unknown")}

    yield {"type": "done", "output": final_output}


# ─── 主入口 ─────────────────────────────────────────────────

def run_agent(
    user_input: str,
    chat_history: list | None = None,
    session_id: str | None = None,
    status_callback: callable = None,
) -> dict[str, Any]:
    """
    执行 Agent 全流程。

    Parameters
    ----------
    user_input      : 用户当前输入
    chat_history    : 兼容旧接口；实际记忆由 MemorySaver + thread_id 管理
    session_id      : 会话/线程 ID（同一 session_id 共享记忆）
    status_callback : 进度回调 (stage: str, detail: str)
    """
    logger = get_logger(session_id)
    start = time.time()
    thread_id = session_id or "default"

    def _emit(stage: str, detail: str = ""):
        if status_callback:
            try:
                status_callback(stage, detail)
            except Exception:
                pass

    # ── 安全约束：速率限制 ─────────────────────────────────
    if not _check_rate_limit():
        return {
            "output": f"请求频率过高（{_RATE_LIMIT}次/{_RATE_WINDOW:.0f}s），请稍后再试。",
            "intent": {"intent": "GENERAL", "confidence": 0.0},
            "plan": [],
            "intermediate_steps": [],
            "corrected": False,
        }

    # ── 安全约束：输入长度 ──────────────────────────────────
    if len(user_input) > MAX_INPUT_LEN:
        return {
            "output": f"输入过长（{len(user_input)} 字符，上限 {MAX_INPUT_LEN}），请简化问题。",
            "intent": {"intent": "GENERAL", "confidence": 0.0},
            "plan": [],
            "intermediate_steps": [],
            "corrected": False,
        }

    # 1. 意图识别
    _emit("intent", "识别查询意图...")
    intent_result = recognize_intent(user_input)
    intent = intent_result["intent"]

    # 2. 任务规划（仅用于前端展示，不注入 Agent 上下文）
    _emit("plan", "规划执行步骤...")
    steps = decompose_task(user_input, intent)
    logger.log_plan(user_input, steps)

    # 3. Agent 执行（MemorySaver 通过 thread_id 自动管理历史）
    _emit("tools", f"调用工具执行 {len(steps)} 步分析...")
    agent = _get_agent()
    config = {"configurable": {"thread_id": thread_id}}

    try:
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = pool.submit(
            agent.invoke,
            {"messages": [{"role": "user", "content": user_input}]},
            config,
        )
        timed_out = False
        try:
            result = future.result(timeout=AGENT_TIMEOUT)
        except concurrent.futures.TimeoutError:
            timed_out = True
            future.cancel()
            raise
        finally:
            # 超时后不再阻塞当前请求；底层 LLM 请求由 LLM_TIMEOUT 收敛。
            pool.shutdown(wait=not timed_out, cancel_futures=True)
    except concurrent.futures.TimeoutError:
        logger.log_error("agent_execution", "超时")
        return {
            "output": f"Agent 执行超时（>{AGENT_TIMEOUT}s），请简化问题或分步查询。",
            "intent": intent_result,
            "plan": steps,
            "intermediate_steps": [],
            "corrected": False,
        }
    except Exception as e:
        logger.log_error("agent_execution", str(e))
        return {
            "output": f"Agent 执行出错：{e}",
            "intent": intent_result,
            "plan": steps,
            "intermediate_steps": [],
            "corrected": False,
        }

    # 4. 提取最终输出和工具调用记录
    output = ""
    tool_calls_log = []
    for msg in result.get("messages", []):
        if not hasattr(msg, "type"):
            continue
        if msg.type == "ai" and getattr(msg, "content", ""):
            output = msg.content
        elif msg.type == "tool":
            tool_calls_log.append({
                "tool": getattr(msg, "name", "unknown"),
                "output": str(getattr(msg, "content", ""))[:800],
            })

    for tc in tool_calls_log:
        logger.log_tool_call(tc["tool"], {}, tc.get("output", ""))

    # 5. 结果自校验
    _emit("correct", "结果自校验...")
    corrected = self_correction(build_llm(), user_input, output, tool_calls_log)

    total_ms = (time.time() - start) * 1000
    logger.log_llm("full_cycle", user_input, corrected, total_ms)
    logger.log_final_output(corrected)

    return {
        "output": corrected,
        "intent": intent_result,
        "plan": steps,
        "intermediate_steps": tool_calls_log,
        "original_output": output,
        "corrected": corrected != output,
    }
