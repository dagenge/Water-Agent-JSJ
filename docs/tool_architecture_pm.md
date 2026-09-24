# Agent 工具架构与数据流程（产品经理视角）

## 一、工具定义：从代码到 Schema

### 1.1 工具是如何定义的？

**核心机制：Python 类型提示 → JSON Schema**

```python
from langchain_core.tools import tool

@tool
def query_station_list(basin_id: str = "") -> str:
    """查询站点列表。
    basin_id: 可选，dqh 或 btpzh；为空返回全部。
    返回站点ID、中文名、经纬度（含近似标记）。"""
    # 实际查询逻辑
    rows = _safe_query("SELECT * FROM station_metadata WHERE basin_id=?", (basin_id,))
    return _to_md_table(rows)
```

**关键要素拆解：**

| 组成部分 | 作用 | 示例 |
|---------|------|------|
| `@tool` 装饰器 | 将普通函数转为 LangChain 工具，自动生成 Schema | LangChain 框架提供 |
| 函数名 | 工具的唯一标识符，LLM 通过此名称调用 | `query_station_list` |
| 参数类型提示 | 定义参数类型和默认值，生成 JSON Schema | `basin_id: str = ""` |
| Docstring | 工具功能说明，LLM 依此判断何时使用 | `"""查询站点列表..."""` |
| 返回类型 | 工具输出格式 | `-> str`（Markdown 表格） |

### 1.2 Schema 自动生成机制

**Python 类型提示 → JSON Schema 转换：**

```python
# Python 函数定义
def query_btpzh_rainfall(
    start_date: str,
    end_date: str,
    resolution: str = "daily",
    station_names: str = "",
    limit: int = 200,
) -> str:
```

**自动转换为 JSON Schema（LLM 可理解的格式）：**

```json
{
  "name": "query_btpzh_rainfall",
  "description": "查询巴塘—攀枝花（BtPzh）连续时序降雨数据...",
  "parameters": {
    "type": "object",
    "properties": {
      "start_date": {"type": "string", "description": "起始日期，格式 YYYY-MM-DD"},
      "end_date": {"type": "string", "description": "结束日期"},
      "resolution": {"type": "string", "default": "daily"},
      "station_names": {"type": "string", "default": ""},
      "limit": {"type": "integer", "default": 200}
    },
    "required": ["start_date", "end_date"]
  }
}
```

**关键点：**
- LangChain 的 `@tool` 装饰器在运行时自动解析类型提示
- LLM 接收的是 JSON Schema，而非 Python 代码
- 参数有默认值 → Schema 中 `required` 字段不包含该参数

---

## 二、完整数据流程（端到端）

### 2.1 流程图

```
用户提问："查询武汉站最近一周水位"
    ↓
[Streamlit 前端]
    接收输入，生成 session_id
    ↓
executor.py :: run_agent(user_input, session_id)
    ↓
[构建消息] {"messages": [{"role": "user", "content": "查询武汉站..."}]}
    ↓
[Agent 调用] agent.invoke(messages, config={"thread_id": session_id})
    ↓
┌─────────────────────────────────────────────────┐
│ LangGraph ReAct Agent（create_react_agent）     │
│                                                 │
│  [消息列表传入]                                  │
│  messages = [                                   │
│    HumanMessage("查询武汉站最近一周水位")          │
│  ]                                              │
│                                                 │
│  ┌──────────────────────────────┐              │
│  │ LLM 节点（决策中心）            │              │
│  │  - 接收: messages列表          │              │
│  │  - 分析: System Prompt +      │              │
│  │          工具Schema列表 +      │              │
│  │          对话历史              │              │
│  │  - 输出: AIMessage             │              │
│  │    · 纯文本 → 最终回复          │              │
│  │    · tool_calls → 调用工具     │              │
│  └──────────────────────────────┘              │
│           ↓                                     │
│  【判断】AIMessage 包含 tool_calls？             │
│           ↓                                     │
│       是  │  否 → 结束，返回文本                  │
│           ↓                                     │
│  ┌──────────────────────────────┐              │
│  │ Tools 节点（工具执行层）        │              │
│  │  - 接收: AIMessage.tool_calls │              │
│  │  - 执行: Python 函数调用       │              │
│  │  - 输出: ToolMessage          │              │
│  └──────────────────────────────┘              │
│           ↓                                     │
│  messages.append(ToolMessage)                   │
│           ↓                                     │
│  【循环】回到 LLM 节点分析工具结果                  │
│                                                 │
└─────────────────────────────────────────────────┘
    ↓
[返回结果] {"output": "武汉站水位 15.32 米...", ...}
    ↓
[Streamlit 展示]
```

### 2.2 关键节点详解

#### 节点 1：LLM 决策节点

**输入格式（messages 列表）：**
```python
[
    HumanMessage(content="查询武汉站水位"),
    AIMessage(content="", tool_calls=[{
        "name": "query_station_list",
        "args": {"basin_id": "btpzh"},
        "id": "call_abc123"
    }]),
    ToolMessage(content="| station_id | name_cn | ... |...", tool_call_id="call_abc123"),
    AIMessage(content="我将查询武汉站数据...")
]
```

**LLM 接收的完整上下文：**
1. **System Prompt**（executor.py 中的 `SYSTEM_PROMPT`）
2. **工具 Schema 列表**（8个工具的 JSON Schema）
3. **历史消息**（HumanMessage + AIMessage + ToolMessage）

**LLM 输出决策：**
- **方式1：直接回复** → `AIMessage(content="武汉站水位...")`
- **方式2：调用工具** → `AIMessage(content="", tool_calls=[...])`

**关键：tool_calls 的数据结构**
```python
AIMessage(
    content="",  # 调用工具时内容为空
    tool_calls=[
        {
            "name": "query_btpzh_rainfall",  # 工具名
            "args": {  # 工具参数，dict格式
                "start_date": "2024-07-08",
                "end_date": "2024-07-15",
                "resolution": "daily"
            },
            "id": "call_xyz789"  # 调用ID，用于追踪
        }
    ]
)
```

#### 节点 2：Tools 执行节点

**工具调用流程：**

```python
# 1. LangGraph 从 AIMessage.tool_calls 提取调用信息
tool_name = "query_btpzh_rainfall"
tool_args = {"start_date": "2024-07-08", "end_date": "2024-07-15"}

# 2. 查找对应的 Python 函数（通过工具注册表）
tool_func = ALL_TOOLS[tool_name]  # 实际是 query_btpzh_rainfall 函数对象

# 3. **直接调用 Python 函数**，参数以 **关键字参数** 形式传入
result = tool_func(**tool_args)
# 等价于: query_btpzh_rainfall(start_date="2024-07-08", end_date="2024-07-15")

# 4. 封装为 ToolMessage
tool_message = ToolMessage(
    content=result,  # 工具返回的字符串（Markdown表格）
    tool_call_id="call_xyz789",  # 对应 AIMessage 中的 id
    name="query_btpzh_rainfall"
)

# 5. 追加到消息列表
messages.append(tool_message)
```

**数据格式转换链：**
```
LLM输出(JSON Schema格式)
   ↓ LangGraph 解析
Python dict: {"start_date": "...", "end_date": "..."}
   ↓ 作为关键字参数传递
Python 函数调用: query_btpzh_rainfall(start_date="...", end_date="...")
   ↓ 函数内部：SQL查询 + 结果格式化
返回字符串: "## 巴塘—攀枝花...\n| TIME | 站点A | ...\n|..."
   ↓ 封装为 ToolMessage
ToolMessage(content="...")
   ↓ 回到 LLM 节点
```

---

## 三、用户问题逐一解答

### Q1: Schema 是如何实现的？
**A:** Python 类型提示 → `@tool` 装饰器解析 → 自动生成 JSON Schema → LLM 可理解

### Q2: 哪个 Node 负责工具调用？
**A:** `create_react_agent` 内部有两个关键节点：
- **LLM 节点**：分析意图，决定是否调用工具
- **Tools 节点**：执行工具，返回 ToolMessage

LangGraph 自动处理节点间的路由，开发者只需提供工具列表。

### Q3: LangGraph 如何传输"意图 → 工具调用"信息？
**A:** 通过 **messages 列表**：
1. LLM 输出 `AIMessage.tool_calls`（包含工具名和参数）
2. LangGraph 自动路由到 Tools 节点
3. Tools 节点解析 `tool_calls`，执行对应 Python 函数
4. 结果封装为 `ToolMessage`，追加到 messages

**关键数据结构：**
```python
messages = [
    HumanMessage(...),
    AIMessage(tool_calls=[...]),  # ← 意图传递
    ToolMessage(...),             # ← 结果返回
]
```

### Q4: 工具接收的入参格式？
**A:** **Python dict**（字典），而非 JSON 字符串
- LLM 输出 JSON Schema 格式的 `tool_calls`
- LangGraph 自动解析为 Python dict
- 作为 `**kwargs` 传递给工具函数

```python
# 工具接收到的参数（开发者视角）
def query_btpzh_rainfall(start_date: str, end_date: str, ...):
    # start_date 是 Python str 对象，不是 JSON 字符串
    print(type(start_date))  # <class 'str'>
```

### Q5: 工具调用结果的格式？
**A:** **Markdown 格式的字符串**
- 所有查询工具返回 Markdown 表格
- `execute_python_analysis` 返回代码执行的 stdout
- 封装为 `ToolMessage.content`

```python
result = query_station_list(basin_id="dqh")
# result = "| station_id | name_cn | lat | lon |\n|---|---|---|---|\n| dqh_C1 | ... |"
```

### Q6: Agent 如何组装工具结果给 LLM？
**A:** **不需要手动组装**，LangGraph 自动管理 messages 列表
1. 工具执行完毕 → 自动生成 `ToolMessage`
2. `ToolMessage` 追加到 messages 列表
3. 整个 messages 列表传回 LLM 节点
4. LLM 看到完整对话历史（包括工具调用记录）

**MemorySaver 的作用：**
- 持久化 messages 列表到内存
- 下次调用时加载历史记录
- 实现跨轮次的上下文记忆

### Q7: 谁决定何时输出最终答案？
**A:** **LLM 自己决定**
- 每次 LLM 节点执行，LLM 判断：
  - 信息足够 → 输出 `AIMessage(content="最终答案")`
  - 需要更多数据 → 输出 `AIMessage(tool_calls=[...])`
- LangGraph 根据 `AIMessage` 是否包含 `tool_calls` 自动路由

**ReAct 循环终止条件：**
```python
# LangGraph 内部逻辑（简化）
while True:
    ai_msg = llm_node(messages)
    if ai_msg.tool_calls:
        tool_msg = tools_node(ai_msg.tool_calls)
        messages.append(tool_msg)
        continue  # 继续循环
    else:
        return ai_msg.content  # 结束，返回最终答案
```

---

## 四、技术架构总结

### 4.1 三层架构

```
┌─────────────────────────────────────┐
│ 应用层（Streamlit）                  │
│  - 用户交互界面                      │
│  - session_id 生成                  │
└─────────────────────────────────────┘
            ↓
┌─────────────────────────────────────┐
│ 编排层（LangGraph ReAct Agent）      │
│  - LLM 节点：意图理解 + 决策         │
│  - Tools 节点：工具执行              │
│  - MemorySaver：对话记忆             │
└─────────────────────────────────────┘
            ↓
┌─────────────────────────────────────┐
│ 工具层（8个 @tool 函数）             │
│  - 数据库查询（7个）                 │
│  - Python代码执行（1个）             │
└─────────────────────────────────────┘
            ↓
┌─────────────────────────────────────┐
│ 数据层（SQLite）                     │
│  - 流域元数据                        │
│  - 站点元数据                        │
│  - 降雨时序数据                      │
└─────────────────────────────────────┘
```

### 4.2 数据格式流转

| 阶段 | 数据格式 | 示例 |
|-----|---------|-----|
| 用户输入 | 自然语言字符串 | "查询武汉站水位" |
| Streamlit → executor | Python dict | `{"user_input": "...", "session_id": "..."}` |
| executor → LangGraph | messages 列表 | `[HumanMessage(...)]` |
| LLM 输出工具调用 | AIMessage.tool_calls | `[{"name": "...", "args": {...}}]` |
| 工具函数接收参数 | Python 关键字参数 | `query_station_list(basin_id="dqh")` |
| 工具函数返回结果 | Markdown 字符串 | `"| col1 | col2 |\n|..."` |
| 封装为消息 | ToolMessage | `ToolMessage(content="...")` |
| LLM 最终输出 | AIMessage.content | "武汉站当前水位 15.32 米" |
| Streamlit 展示 | Markdown 渲染 | UI 上显示格式化文本 |

---

## 五、关键设计决策

### 5.1 为什么工具返回 Markdown 字符串？

**优势：**
- LLM 易于理解表格结构
- 前端直接渲染，无需二次格式化
- 人类可读，便于调试

**劣势：**
- 无法在 LLM 侧直接计算（需 execute_python_analysis）
- 大表格消耗更多 tokens

### 5.2 为什么使用 MemorySaver 而非数据库？

**当前方案（进程内存）：**
- 优势：零配置，开发简单
- 劣势：重启丢失，无法跨进程

**生产方案（SqliteSaver / PostgresSaver）：**
- 持久化存储
- 支持分布式部署
- 可审计、可回溯

### 5.3 为什么用 ReAct 而非 Function Calling？

**ReAct（当前）：**
- 可见的推理过程
- 支持多轮工具调用
- 更好的容错性

**Pure Function Calling：**
- 更快（一次调用）
- 适合简单查询
- 缺乏推理透明度

---

## 六、核心代码位置索引

| 功能 | 文件 | 行号 | 说明 |
|-----|------|------|------|
| 工具定义 | `agent/tools.py` | 108-467 | 8个工具的完整实现 |
| Schema 转换 | LangChain 框架 | N/A | `@tool` 装饰器自动处理 |
| Agent 创建 | `agent/executor.py` | 148-162 | `create_react_agent` 调用 |
| MemorySaver 绑定 | `agent/executor.py` | 160 | `checkpointer=_memory` |
| 工具调用入口 | `agent/executor.py` | 270-272 | `agent.invoke(messages, config)` |
| 前端集成 | `streamlit_demo.py` | 182-186 | `run_agent` 调用 |

---

**文档版本：** v1.0  
**更新时间：** 2025-01-XX  
**适用范围：** 产品经理、技术经理、新人开发者
