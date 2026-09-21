"""意图识别：将用户输入分类到水文分析业务意图"""

from langchain_core.messages import SystemMessage, HumanMessage
from agent.config import build_llm
from agent.logger import get_logger

INTENT_PROMPT = """你是金沙江流域水文数据分析助手的意图识别模块。根据用户输入判断其意图。

可选意图（只返回代码，不解释）：
- RAIN_QUERY      : 查询时序降雨数据（如"查2015年6月奔子栏的降雨"）
- STAT_ANALYSIS   : 降雨统计分析（累计、均值、极值、面雨量、频率等）
- CORRELATION     : 站点间/上下游降雨相关性、空间分布分析
- REPORT_GEN      : 生成分析报告或摘要文档
- BASIN_QUERY     : 查询流域/站点基本信息
- GENERAL         : 通用水文知识问答或其他

只返回意图代码。"""

VALID_INTENTS = {"RAIN_QUERY", "STAT_ANALYSIS", "CORRELATION", "REPORT_GEN", "BASIN_QUERY", "GENERAL"}


def recognize_intent(user_input: str) -> dict:
    """识别用户意图，返回 {intent: str, confidence: float}"""
    llm = build_llm(temperature=0)
    logger = get_logger()

    response = llm.invoke([
        SystemMessage(content=INTENT_PROMPT),
        HumanMessage(content=user_input),
    ])
    raw = response.content.strip().upper()
    intent = raw if raw in VALID_INTENTS else "GENERAL"
    confidence = 1.0 if raw in VALID_INTENTS else 0.5
    logger.log_intent(user_input, intent, confidence)
    return {"intent": intent, "confidence": confidence}
