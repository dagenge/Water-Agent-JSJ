"""MCP Server实现：标准化工具协议

MCP (Model Context Protocol) 是Anthropic推出的标准化工具协议，类似LSP之于代码编辑器。

功能：
1. 将水文Agent的12个工具暴露为MCP Server
2. 定义标准化的工具schema（name, description, parameters）
3. 处理下游团队的工具调用请求
4. 记录调用日志和性能指标

实际应用场景：
- 研究院内部3个LLM应用团队都需要查询水文数据
- 通过MCP Server实现工具复用，避免重复开发
- 下游团队通过MCP Client调用，无需关心数据库细节
"""

import sys
import os
import json
from typing import Any, Dict, List, Optional
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastmcp import FastMCP
from agent.tools import (
    query_basin_list,
    query_station_list,
    query_flood_events,
    query_rainfall_data,
    query_rainfall_statistics,
    query_peak_flow,
    query_data_dict,
)
from knowledge.knowledge_tools import (
    search_flood_prevention_knowledge,
    check_rainfall_warning_compliance,
    query_basin_topology,
    query_upstream_stations,
    query_downstream_stations,
)

# 初始化MCP Server
mcp = FastMCP("water-agent-mcp")

# MCP调用日志
MCP_LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs", "mcp_calls")
os.makedirs(MCP_LOG_DIR, exist_ok=True)


def log_mcp_call(tool_name: str, input_data: Dict, output: str, latency_ms: float, success: bool):
    """记录MCP工具调用日志"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "tool_name": tool_name,
        "input": input_data,
        "output": output[:500] if success else output,  # 成功时截断，失败时保留完整错误
        "latency_ms": latency_ms,
        "success": success,
    }

    log_file = os.path.join(MCP_LOG_DIR, f"mcp_calls_{datetime.now().strftime('%Y%m%d')}.jsonl")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


# ============================================================
# 数据查询工具（8个）
# ============================================================

@mcp.tool()
def mcp_query_basin_list() -> str:
    """查询所有流域的基本信息（流域ID、名称、类型、描述）

    返回格式：Markdown表格
    """
    import time
    start = time.time()
    try:
        result = query_basin_list.invoke({})
        latency_ms = (time.time() - start) * 1000
        log_mcp_call("query_basin_list", {}, result, latency_ms, True)
        return result
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        error_msg = str(e)
        log_mcp_call("query_basin_list", {}, error_msg, latency_ms, False)
        raise


@mcp.tool()
def mcp_query_station_list(basin_id: str = "") -> str:
    """查询指定流域的站点列表

    Args:
        basin_id: 流域ID，可选值: hzk/bpz/js/tj/bjh，为空则查全部

    返回格式：Markdown表格
    """
    import time
    start = time.time()
    input_data = {"basin_id": basin_id}
    try:
        result = query_station_list.invoke(input_data)
        latency_ms = (time.time() - start) * 1000
        log_mcp_call("query_station_list", input_data, result, latency_ms, True)
        return result
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        error_msg = str(e)
        log_mcp_call("query_station_list", input_data, error_msg, latency_ms, False)
        raise


@mcp.tool()
def mcp_query_flood_events(basin_id: str = "") -> str:
    """查询洪水场次列表

    Args:
        basin_id: 流域ID，可选，为空则查全部

    返回格式：Markdown表格，包含场次编号、时间步数等
    """
    import time
    start = time.time()
    input_data = {"basin_id": basin_id}
    try:
        result = query_flood_events.invoke(input_data)
        latency_ms = (time.time() - start) * 1000
        log_mcp_call("query_flood_events", input_data, result, latency_ms, True)
        return result
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        error_msg = str(e)
        log_mcp_call("query_flood_events", input_data, error_msg, latency_ms, False)
        raise


@mcp.tool()
def mcp_query_rainfall_data(basin_id: str, event_code: str, station_id: str = "", limit: int = 200) -> str:
    """查询指定流域、指定洪水场次的降雨/流量数据

    Args:
        basin_id: 流域ID (hzk/bpz/js/tj/bjh)
        event_code: 场次编号 (如 20050610)
        station_id: 可选，指定站点ID (如 hzk_C1)，为空返回所有列
        limit: 返回行数限制，默认200

    返回格式：Markdown表格，包含时间步和各站点降雨量
    """
    import time
    start = time.time()
    input_data = {"basin_id": basin_id, "event_code": event_code, "station_id": station_id, "limit": limit}
    try:
        result = query_rainfall_data.invoke(input_data)
        latency_ms = (time.time() - start) * 1000
        log_mcp_call("query_rainfall_data", input_data, result, latency_ms, True)
        return result
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        error_msg = str(e)
        log_mcp_call("query_rainfall_data", input_data, error_msg, latency_ms, False)
        raise


@mcp.tool()
def mcp_query_rainfall_statistics(basin_id: str, event_code: str) -> str:
    """计算指定洪水场次的降雨统计：各站点累计雨量、最大小时雨量、面平均雨量

    Args:
        basin_id: 流域ID (hzk/bpz/js/tj/bjh)
        event_code: 场次编号

    返回格式：Markdown表格
    """
    import time
    start = time.time()
    input_data = {"basin_id": basin_id, "event_code": event_code}
    try:
        result = query_rainfall_statistics.invoke(input_data)
        latency_ms = (time.time() - start) * 1000
        log_mcp_call("query_rainfall_statistics", input_data, result, latency_ms, True)
        return result
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        error_msg = str(e)
        log_mcp_call("query_rainfall_statistics", input_data, error_msg, latency_ms, False)
        raise


@mcp.tool()
def mcp_query_peak_flow(basin_id: str, event_code: str) -> str:
    """查询指定洪水场次的洪峰流量及发生时间

    Args:
        basin_id: 流域ID (hzk/bpz/js/tj/bjh)
        event_code: 场次编号

    返回格式：Markdown格式，包含洪峰流量和发生时间步
    """
    import time
    start = time.time()
    input_data = {"basin_id": basin_id, "event_code": event_code}
    try:
        result = query_peak_flow.invoke(input_data)
        latency_ms = (time.time() - start) * 1000
        log_mcp_call("query_peak_flow", input_data, result, latency_ms, True)
        return result
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        error_msg = str(e)
        log_mcp_call("query_peak_flow", input_data, error_msg, latency_ms, False)
        raise


@mcp.tool()
def mcp_query_data_dict(basin_id: str) -> str:
    """查询指定流域的数据字典：列名到站点的映射关系

    Args:
        basin_id: 流域ID

    返回格式：Markdown表格，展示数据结构和站点映射
    """
    import time
    start = time.time()
    input_data = {"basin_id": basin_id}
    try:
        result = query_data_dict.invoke(input_data)
        latency_ms = (time.time() - start) * 1000
        log_mcp_call("query_data_dict", input_data, result, latency_ms, True)
        return result
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        error_msg = str(e)
        log_mcp_call("query_data_dict", input_data, error_msg, latency_ms, False)
        raise


# ============================================================
# 知识库检索工具（4个）
# ============================================================

@mcp.tool()
def mcp_search_knowledge(query: str, basin_id: str = "") -> str:
    """检索防汛知识库

    Args:
        query: 查询问题
        basin_id: 可选，指定流域ID过滤

    返回格式：相关文档片段（Markdown格式）
    """
    import time
    start = time.time()
    input_data = {"query": query, "basin_id": basin_id}
    try:
        result = search_flood_prevention_knowledge.invoke(input_data)
        latency_ms = (time.time() - start) * 1000
        log_mcp_call("search_knowledge", input_data, result, latency_ms, True)
        return result
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        error_msg = str(e)
        log_mcp_call("search_knowledge", input_data, error_msg, latency_ms, False)
        raise


@mcp.tool()
def mcp_check_warning(basin_id: str, rainfall_1h: float, rainfall_3h: float, rainfall_24h: float) -> str:
    """检查降雨是否达到预警标准

    Args:
        basin_id: 流域ID
        rainfall_1h: 1小时累计雨量(mm)
        rainfall_3h: 3小时累计雨量(mm)
        rainfall_24h: 24小时累计雨量(mm)

    返回格式：预警等级和建议
    """
    import time
    start = time.time()
    input_data = {
        "basin_id": basin_id,
        "rainfall_1h": rainfall_1h,
        "rainfall_3h": rainfall_3h,
        "rainfall_24h": rainfall_24h
    }
    try:
        result = check_rainfall_warning_compliance.invoke(input_data)
        latency_ms = (time.time() - start) * 1000
        log_mcp_call("check_warning", input_data, result, latency_ms, True)
        return result
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        error_msg = str(e)
        log_mcp_call("check_warning", input_data, error_msg, latency_ms, False)
        raise


@mcp.tool()
def mcp_query_topology(basin_id: str) -> str:
    """查询流域水系拓扑结构

    Args:
        basin_id: 流域ID

    返回格式：站点连接关系（Markdown格式）
    """
    import time
    start = time.time()
    input_data = {"basin_id": basin_id}
    try:
        result = query_basin_topology.invoke(input_data)
        latency_ms = (time.time() - start) * 1000
        log_mcp_call("query_topology", input_data, result, latency_ms, True)
        return result
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        error_msg = str(e)
        log_mcp_call("query_topology", input_data, error_msg, latency_ms, False)
        raise


@mcp.tool()
def mcp_query_upstream(station_id: str) -> str:
    """查询指定站点的上游站点

    Args:
        station_id: 站点ID

    返回格式：上游站点列表（Markdown格式）
    """
    import time
    start = time.time()
    input_data = {"station_id": station_id}
    try:
        result = query_upstream_stations.invoke(input_data)
        latency_ms = (time.time() - start) * 1000
        log_mcp_call("query_upstream", input_data, result, latency_ms, True)
        return result
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        error_msg = str(e)
        log_mcp_call("query_upstream", input_data, error_msg, latency_ms, False)
        raise


@mcp.tool()
def mcp_query_downstream(station_id: str) -> str:
    """查询指定站点的下游站点

    Args:
        station_id: 站点ID

    返回格式：下游站点列表（Markdown格式）
    """
    import time
    start = time.time()
    input_data = {"station_id": station_id}
    try:
        result = query_downstream_stations.invoke(input_data)
        latency_ms = (time.time() - start) * 1000
        log_mcp_call("query_downstream", input_data, result, latency_ms, True)
        return result
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        error_msg = str(e)
        log_mcp_call("query_downstream", input_data, error_msg, latency_ms, False)
        raise


# ============================================================
# MCP Server 启动
# ============================================================

def start_server(transport: str = "stdio", host: str = "localhost", port: int = 8766):
    """启动MCP Server

    Args:
        transport: 传输协议，'stdio' 或 'http'
        host: HTTP模式下的监听地址
        port: HTTP模式下的监听端口

    使用场景：
    1. stdio模式：适合本地进程间通信，下游通过子进程调用
    2. http模式：适合内网服务调用，下游通过HTTP请求调用
    """
    print("=" * 60)
    print("水文Agent MCP Server")
    print("=" * 60)
    print(f"传输协议: {transport}")
    if transport == "http":
        print(f"监听地址: {host}:{port}")
    print(f"工具数量: 12")
    print("  - 数据查询: 7个")
    print("  - 知识检索: 1个")
    print("  - 拓扑查询: 3个")
    print("  - 预警检查: 1个")
    print(f"日志目录: {MCP_LOG_DIR}")
    print("=" * 60)

    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport == "http":
        mcp.run(transport="http", host=host, port=port)
    else:
        raise ValueError(f"不支持的传输协议: {transport}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="水文Agent MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio",
                       help="传输协议 (默认: stdio)")
    parser.add_argument("--host", default="localhost", help="HTTP监听地址 (默认: localhost)")
    parser.add_argument("--port", type=int, default=8766, help="HTTP监听端口 (默认: 8766)")

    args = parser.parse_args()

    start_server(transport=args.transport, host=args.host, port=args.port)
