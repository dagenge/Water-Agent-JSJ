"""金沙江水系拓扑图谱：DQH + BtPzh 上下游关系"""

import networkx as nx

BASIN_NAME_MAP = {"dqh": "定曲河", "btpzh": "巴塘—攀枝花"}


class JSJTopologyGraph:
    """
    金沙江水系拓扑图，基于 NetworkX DiGraph。
    边方向：上游节点 → 下游节点（relation='upstream_of'）
    """

    def __init__(self):
        self.graph = nx.DiGraph()
        self._build()

    def _build(self) -> None:
        G = self.graph

        # ── 定曲河（DQH）── 4 站，乡城最上游，乡城→热打→古学→出口
        G.add_node("dqh_outlet", name="定曲河出口", basin="dqh", type="outlet")
        for sid, name in [("dqh_C1","古学"),("dqh_C2","得荣"),("dqh_C3","热打"),("dqh_C4","乡城")]:
            G.add_node(sid, name=name, basin="dqh", type="rain_station")
        G.add_edge("dqh_C4", "dqh_C3", relation="upstream_of")   # 乡城 → 热打
        G.add_edge("dqh_C3", "dqh_C1", relation="upstream_of")   # 热打 → 古学
        G.add_edge("dqh_C2", "dqh_C3", relation="upstream_of")   # 得荣 → 热打（支流）
        G.add_edge("dqh_C1", "dqh_outlet", relation="upstream_of")

        # ── 巴塘—攀枝花（BtPzh）── 金沙江干流由北向南
        # 选取主干代表节点，实际 73 站全部汇入金沙江干流
        G.add_node("btpzh_outlet", name="攀枝花站", basin="btpzh", type="outlet")
        # 主干：巴塘 → 奔子栏 → 石鼓 → 梨园 → 阿海 → 攀枝花
        mainline = [
            ("btpzh_C42","邦达"),("btpzh_C35","中咱"),("btpzh_C38","奔子栏"),
            ("btpzh_C47","石鼓"),("btpzh_C58","梨园气象站"),("btpzh_C73","阿海水文站"),
        ]
        for sid, name in mainline:
            if sid not in G.nodes:
                G.add_node(sid, name=name, basin="btpzh", type="rain_station")
        for i in range(len(mainline) - 1):
            G.add_edge(mainline[i][0], mainline[i+1][0], relation="upstream_of")
        G.add_edge(mainline[-1][0], "btpzh_outlet", relation="upstream_of")

        # 其余 67 站直连到流域出口（拓扑简化，实际位置由坐标体现）
        known = {s for s, _ in mainline}
        for i in range(1, 74):
            sid = f"btpzh_C{i:02d}"
            if sid not in G.nodes:
                G.add_node(sid, name=f"站点{i}", basin="btpzh", type="rain_station")
            if sid not in known:
                G.add_edge(sid, "btpzh_outlet", relation="upstream_of")

    def query_upstream(self, node_id: str) -> list[str]:
        if node_id not in self.graph:
            return []
        result = []
        for pred in self.graph.predecessors(node_id):
            if self.graph.edges[pred, node_id].get("relation") == "upstream_of":
                result.append(pred)
                result.extend(self.query_upstream(pred))
        return result

    def query_downstream(self, node_id: str) -> list[str]:
        if node_id not in self.graph:
            return []
        result = []
        for succ in self.graph.successors(node_id):
            if self.graph.edges[node_id, succ].get("relation") == "upstream_of":
                result.append(succ)
                result.extend(self.query_downstream(succ))
        return result

    def topology_table(self, basin_id: str) -> str:
        lines = [
            f"## {BASIN_NAME_MAP.get(basin_id, basin_id)} 水系拓扑",
            "| 节点ID | 名称 | 类型 | 直接上游 | 直接下游 |",
            "|--------|------|------|----------|----------|",
        ]
        for n, data in self.graph.nodes(data=True):
            if data.get("basin") != basin_id:
                continue
            ups = [p for p in self.graph.predecessors(n)
                   if self.graph.edges[p, n].get("relation") == "upstream_of"]
            dns = [s for s in self.graph.successors(n)
                   if self.graph.edges[n, s].get("relation") == "upstream_of"]
            lines.append(
                f"| {n} | {data.get('name', n)} | {data.get('type','')} "
                f"| {', '.join(ups) or '—'} | {', '.join(dns) or '—'} |"
            )
        return "\n".join(lines)


_graph_instance: JSJTopologyGraph | None = None


def get_graph() -> JSJTopologyGraph:
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = JSJTopologyGraph()
    return _graph_instance
