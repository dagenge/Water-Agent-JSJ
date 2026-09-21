"""知识层工具：RAG 检索 + 水系拓扑查询"""

from langchain_core.tools import tool

from knowledge.rag_engine import get_rag
from knowledge.graph_engine import get_graph


@tool
def search_hydro_knowledge(query: str, basin_id: str = "") -> str:
    """搜索水文知识库（防汛预案、流域特征、水文规律等）。
    query: 搜索内容，如"洪水预警响应流程""定曲河汛期特征"。
    basin_id: 可选，dqh 或 btpzh；为空跨流域搜索。"""
    rag = get_rag()
    bid = basin_id if basin_id else None
    result = rag.search_with_context(query, basin_id=bid, top_k=5)
    return result if result else f"未找到与「{query}」相关的水文知识。"


@tool
def query_basin_topology(basin_id: str) -> str:
    """查询流域水系拓扑关系（上下游站点）。basin_id: dqh 或 btpzh。"""
    return get_graph().topology_table(basin_id)


@tool
def query_upstream_stations(station_id: str) -> str:
    """查询某站点的所有上游站点。station_id: 如 dqh_C1、btpzh_C38。"""
    ups = get_graph().query_upstream(station_id)
    if not ups:
        return f"站点 {station_id} 无上游站点记录（或站点ID不存在）。"
    return f"站点 {station_id} 的上游站点：{', '.join(ups)}"


@tool
def query_downstream_stations(station_id: str) -> str:
    """查询某站点的所有下游站点。station_id: 如 dqh_C4、btpzh_C47。"""
    dns = get_graph().query_downstream(station_id)
    if not dns:
        return f"站点 {station_id} 无下游站点记录（或站点ID不存在）。"
    return f"站点 {station_id} 的下游站点：{', '.join(dns)}"


KNOWLEDGE_TOOLS = [
    search_hydro_knowledge,
    query_basin_topology,
    query_upstream_stations,
    query_downstream_stations,
]
