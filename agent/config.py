"""Agent 配置：LLM 工厂、路径常量、流域元数据"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Streamlit Cloud Secrets 兼容：优先读取 st.secrets，回退到环境变量
try:
    import streamlit as st
    DEEPSEEK_API_KEY = st.secrets.get("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
except (ImportError, FileNotFoundError):
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

DATABASE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "database", "jsj_agent.db"
)
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")

# 用于代码执行工具的输出目录
ANALYSIS_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "analysis_output")
os.makedirs(ANALYSIS_OUTPUT_DIR, exist_ok=True)

BASIN_NAME_MAP = {
    "dqh": "定曲河",
    "btpzh": "巴塘—攀枝花",
}

# 原始数据路径（初始化数据库时使用）
DQH_HOURLY_DIR = r"H:\LMScore\lms-core\resources\Biye\DQH\Flood_hourly2"
DQH_DAILY_DIR = r"H:\LMScore\lms-core\resources\Biye\DQH\Flood_daily"
BTPZH_HOURLY_XLSX = r"H:\LMScore\lms-core\resources\Biye\BtPzh\降雨数据_巴塘到攀枝花.xlsx"
BTPZH_DAILY_XLSX = r"H:\LMScore\lms-core\resources\Biye\BtPzh\降雨数据_巴塘到攀枝花_日尺度(小时求和).xlsx"
DQH_SHP = r"H:\JSJ\研二下项目\工程文件\DQHshp.shp"
BTPZH_SHP = r"H:\LMScore\lms-core\resources\Biye\ArcGIS数据\BtPzh.shp"


def build_llm(temperature: float = 0.1, max_tokens: int = 4096) -> ChatOpenAI:
    if not DEEPSEEK_API_KEY:
        raise ValueError(
            "⚠️ DeepSeek API Key 未配置\n\n"
            "本地运行：复制 .env.example 为 .env 并填入密钥\n"
            "Streamlit Cloud：在 App Settings → Secrets 中配置 DEEPSEEK_API_KEY"
        )
    return ChatOpenAI(
        model=DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=LLM_TIMEOUT,
        max_retries=LLM_MAX_RETRIES,
    )
