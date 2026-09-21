"""
MCP Server — 将 Agent 的 12 个工具暴露为标准 MCP 协议接口

启动方式（stdio 模式，供 Claude Desktop / Cursor 等客户端连接）：
    python agent/mcp_server.py

Claude Desktop 配置（~/.config/claude/claude_desktop_config.json）：
    {
      "mcpServers": {
        "jsj-water-agent": {
          "command": "path/to/venv/Scripts/python.exe",
          "args": ["path/to/Project_JSJ_Agent/agent/mcp_server.py"]
        }
      }
    }

连接后可用工具：与 ALL_TOOLS + KNOWLEDGE_TOOLS 完全一致的 12 个工具，
任何支持 MCP 协议的 LLM 客户端均可直接调用。
"""

import os
import sys

# 将项目根目录加入 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import fastmcp
from agent.tools import (
    query_basin_list,
    query_station_list,
    query_dqh_events,
    query_dqh_rainfall,
    query_dqh_statistics,
    query_btpzh_rainfall,
    query_btpzh_statistics,
    execute_python_analysis,
)
from knowledge.knowledge_tools import (
    search_hydro_knowledge,
    query_basin_topology,
    query_upstream_stations,
    query_downstream_stations,
)

mcp = fastmcp.FastMCP(
    name="jsj-water-agent",
    instructions=(
        "金沙江流域水文数据分析工具集。"
        "覆盖定曲河（DQH）4站汛期事件数据和巴塘—攀枝花（BtPzh）73站连续时序数据。"
        "支持降雨统计、时序查询、Python 数据分析代码执行、水系拓扑查询和知识检索。"
    ),
)

# 注册所有工具（fastmcp 直接接受 LangChain @tool 装饰的函数）
for fn in [
    query_basin_list,
    query_station_list,
    query_dqh_events,
    query_dqh_rainfall,
    query_dqh_statistics,
    query_btpzh_rainfall,
    query_btpzh_statistics,
    execute_python_analysis,
    search_hydro_knowledge,
    query_basin_topology,
    query_upstream_stations,
    query_downstream_stations,
]:
    # LangChain tool → 原始 Python 函数
    mcp.tool(fn.func if hasattr(fn, "func") else fn)


if __name__ == "__main__":
    mcp.run()  # stdio 模式，标准输入输出与 MCP 客户端通信
