"""系统监控运营面板

实时展示 Prometheus 指标的可视化面板，包含：
- 总查询数、工具调用成功率、响应时间、活跃会话数
- 意图分类分布、工具调用分布、错误趋势
"""

import streamlit as st
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta


def fetch_prometheus_metric(query: str, prometheus_url: str = "http://localhost:9090") -> dict:
    """查询 Prometheus 指标"""
    try:
        resp = requests.get(f"{prometheus_url}/api/v1/query", params={"query": query}, timeout=5)
        if resp.status_code == 200:
            return resp.json().get("data", {}).get("result", [])
        return []
    except Exception:
        return []


def fetch_prometheus_range(query: str, start: datetime, end: datetime,
                          step: str = "1m", prometheus_url: str = "http://localhost:9090") -> dict:
    """查询 Prometheus 时间范围指标"""
    try:
        resp = requests.get(
            f"{prometheus_url}/api/v1/query_range",
            params={
                "query": query,
                "start": int(start.timestamp()),
                "end": int(end.timestamp()),
                "step": step,
            },
            timeout=5
        )
        if resp.status_code == 200:
            return resp.json().get("data", {}).get("result", [])
        return []
    except Exception:
        return []


def render_monitoring():
    st.header("📊 系统监控运营")
    st.caption("实时监控 Agent 运行状态和性能指标（数据来源：Prometheus）")

    # 连接状态检测
    prometheus_url = "http://localhost:9090"
    try:
        health = requests.get(f"{prometheus_url}/-/healthy", timeout=2)
        if health.status_code != 200:
            st.error("⚠️ Prometheus 未运行，请先启动监控服务：`python scripts/start_services.py`")
            return
    except Exception:
        st.warning("⚠️ 无法连接 Prometheus（http://localhost:9090），指标数据不可用")
        st.info("启动监控：`python scripts/start_services.py`")
        return

    # 时间范围选择
    col1, col2 = st.columns([3, 1])
    with col1:
        time_range = st.selectbox(
            "时间范围",
            ["最近 15 分钟", "最近 1 小时", "最近 6 小时", "最近 24 小时"],
            index=1
        )
    with col2:
        auto_refresh = st.checkbox("自动刷新", value=False)
        if auto_refresh:
            st.rerun()

    # 解析时间范围
    time_map = {
        "最近 15 分钟": 15,
        "最近 1 小时": 60,
        "最近 6 小时": 360,
        "最近 24 小时": 1440,
    }
    minutes = time_map[time_range]
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=minutes)

    # ========== 核心指标卡片 ==========
    st.subheader("核心指标")
    metric_cols = st.columns(4)

    # 1. 总查询数
    with metric_cols[0]:
        query_count_result = fetch_prometheus_metric(f"sum(increase(agent_query_total[{minutes}m]))")
        total_queries = int(query_count_result[0]["value"][1]) if query_count_result else 0
        st.metric("总查询数", f"{total_queries}", delta=f"{minutes}分钟")

    # 2. 工具调用成功率
    with metric_cols[1]:
        success_rate_query = f"(sum(rate(agent_tool_call_success_total[{minutes}m])) / sum(rate(agent_tool_call_total[{minutes}m]))) * 100"
        success_rate_result = fetch_prometheus_metric(success_rate_query)
        success_rate = float(success_rate_result[0]["value"][1]) if success_rate_result else 0.0
        st.metric("工具调用成功率", f"{success_rate:.1f}%", delta="目标 >95%")

    # 3. P95 响应时间
    with metric_cols[2]:
        p95_query = f"histogram_quantile(0.95, rate(agent_query_duration_seconds_bucket[{minutes}m]))"
        p95_result = fetch_prometheus_metric(p95_query)
        p95_time = float(p95_result[0]["value"][1]) if p95_result else 0.0
        st.metric("P95 响应时间", f"{p95_time:.2f}s", delta="目标 <10s")

    # 4. 活跃会话数
    with metric_cols[3]:
        active_sessions_result = fetch_prometheus_metric("agent_active_sessions")
        active_count = int(active_sessions_result[0]["value"][1]) if active_sessions_result else 0
        st.metric("活跃会话数", f"{active_count}", delta="实时")

    st.divider()

    # ========== 趋势图表 ==========
    chart_tab1, chart_tab2, chart_tab3 = st.tabs(["📈 查询与响应", "🔧 工具调用", "❌ 错误分析"])

    with chart_tab1:
        # 查询趋势图
        st.subheader("查询趋势")
        query_rate_data = fetch_prometheus_range(
            "sum(rate(agent_query_total[1m]))",
            start_time, end_time, step="1m"
        )

        if query_rate_data:
            timestamps = [datetime.fromtimestamp(t) for t, _ in query_rate_data[0]["values"]]
            values = [float(v) for _, v in query_rate_data[0]["values"]]

            fig_query = go.Figure()
            fig_query.add_trace(go.Scatter(
                x=timestamps, y=values,
                mode="lines", name="QPS",
                line=dict(color="#0d6efd", width=2),
                fill="tozeroy", fillcolor="rgba(13, 110, 253, 0.1)"
            ))
            fig_query.update_layout(
                height=320,
                xaxis_title="时间",
                yaxis_title="每秒查询数 (QPS)",
                hovermode="x unified",
                template="plotly_white"
            )
            st.plotly_chart(fig_query, use_container_width=True)
        else:
            st.info("暂无查询数据")

        # 响应时间分布
        st.subheader("响应时间分布 (P50 / P95 / P99)")
        quantiles = ["0.5", "0.95", "0.99"]
        quantile_names = ["P50", "P95", "P99"]
        quantile_colors = ["#198754", "#fd7e14", "#dc3545"]

        fig_latency = go.Figure()
        for q, name, color in zip(quantiles, quantile_names, quantile_colors):
            latency_data = fetch_prometheus_range(
                f"histogram_quantile({q}, rate(agent_query_duration_seconds_bucket[1m]))",
                start_time, end_time, step="1m"
            )
            if latency_data:
                ts = [datetime.fromtimestamp(t) for t, _ in latency_data[0]["values"]]
                vals = [float(v) for _, v in latency_data[0]["values"]]
                fig_latency.add_trace(go.Scatter(
                    x=ts, y=vals, mode="lines", name=name,
                    line=dict(color=color, width=2)
                ))

        fig_latency.update_layout(
            height=320,
            xaxis_title="时间",
            yaxis_title="响应时间 (秒)",
            hovermode="x unified",
            template="plotly_white"
        )
        st.plotly_chart(fig_latency, use_container_width=True)

    with chart_tab2:
        # 工具调用分布
        st.subheader("工具调用分布")
        tool_dist_data = fetch_prometheus_metric(f"sum by (tool_name) (increase(agent_tool_call_total[{minutes}m]))")

        if tool_dist_data:
            tool_names = [item["metric"]["tool_name"] for item in tool_dist_data]
            tool_counts = [int(float(item["value"][1])) for item in tool_dist_data]

            fig_tools = go.Figure(go.Bar(
                x=tool_names, y=tool_counts,
                marker_color="#6f42c1",
                text=tool_counts,
                textposition="auto"
            ))
            fig_tools.update_layout(
                height=360,
                xaxis_title="工具名称",
                yaxis_title="调用次数",
                template="plotly_white"
            )
            st.plotly_chart(fig_tools, use_container_width=True)
        else:
            st.info("暂无工具调用数据")

        # 工具调用耗时
        st.subheader("工具平均耗时 (Top 5)")
        tool_duration_data = fetch_prometheus_metric(
            f"topk(5, avg by (tool_name) (rate(agent_tool_call_duration_seconds_sum[{minutes}m]) / rate(agent_tool_call_duration_seconds_count[{minutes}m])))"
        )

        if tool_duration_data:
            tools = [item["metric"]["tool_name"] for item in tool_duration_data]
            durations = [float(item["value"][1]) * 1000 for item in tool_duration_data]  # 转换为毫秒

            fig_duration = go.Figure(go.Bar(
                y=tools, x=durations,
                orientation="h",
                marker_color="#0dcaf0",
                text=[f"{d:.0f}ms" for d in durations],
                textposition="auto"
            ))
            fig_duration.update_layout(
                height=280,
                xaxis_title="平均耗时 (毫秒)",
                yaxis_title="工具名称",
                template="plotly_white"
            )
            st.plotly_chart(fig_duration, use_container_width=True)
        else:
            st.info("暂无工具耗时数据")

    with chart_tab3:
        # 错误趋势
        st.subheader("查询错误趋势")
        error_rate_data = fetch_prometheus_range(
            "sum(rate(agent_query_error_total[1m]))",
            start_time, end_time, step="1m"
        )

        if error_rate_data:
            ts = [datetime.fromtimestamp(t) for t, _ in error_rate_data[0]["values"]]
            vals = [float(v) for _, v in error_rate_data[0]["values"]]

            fig_errors = go.Figure()
            fig_errors.add_trace(go.Scatter(
                x=ts, y=vals,
                mode="lines+markers", name="错误率",
                line=dict(color="#dc3545", width=2),
                marker=dict(size=4)
            ))
            fig_errors.update_layout(
                height=300,
                xaxis_title="时间",
                yaxis_title="错误数/秒",
                hovermode="x unified",
                template="plotly_white"
            )
            st.plotly_chart(fig_errors, use_container_width=True)
        else:
            st.info("暂无错误数据")

        # 工具调用失败分布
        st.subheader("工具调用失败分布")
        tool_error_data = fetch_prometheus_metric(
            f"sum by (tool_name) (increase(agent_tool_call_error_total[{minutes}m]))"
        )

        if tool_error_data:
            tools_err = [item["metric"]["tool_name"] for item in tool_error_data]
            err_counts = [int(float(item["value"][1])) for item in tool_error_data]

            fig_tool_errors = go.Figure(go.Bar(
                x=tools_err, y=err_counts,
                marker_color="#dc3545",
                text=err_counts,
                textposition="auto"
            ))
            fig_tool_errors.update_layout(
                height=280,
                xaxis_title="工具名称",
                yaxis_title="失败次数",
                template="plotly_white"
            )
            st.plotly_chart(fig_tool_errors, use_container_width=True)
        else:
            st.info("✅ 暂无工具调用失败")

    st.divider()

    # ========== 意图分类分布 ==========
    st.subheader("意图分类分布")
    intent_dist_data = fetch_prometheus_metric(f"sum by (intent_type) (increase(agent_query_total[{minutes}m]))")

    if intent_dist_data:
        intents = [item["metric"]["intent_type"] for item in intent_dist_data]
        counts = [int(float(item["value"][1])) for item in intent_dist_data]

        fig_intent = go.Figure(go.Pie(
            labels=intents, values=counts,
            hole=0.4,
            marker=dict(colors=["#0d6efd", "#198754", "#fd7e14", "#6f42c1", "#dc3545", "#0dcaf0"])
        ))
        fig_intent.update_layout(height=400)
        st.plotly_chart(fig_intent, use_container_width=True)
    else:
        st.info("暂无意图分类数据")

    # ========== Grafana 和 Prometheus 入口 ==========
    st.divider()
    st.subheader("🔗 外部监控入口")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("### Grafana 面板")
        st.markdown("完整监控面板，包含告警配置和历史数据")
        st.markdown("[打开 Grafana →](http://localhost:3000) (admin/admin123)")
    with col_b:
        st.markdown("### Prometheus 查询")
        st.markdown("原始指标查询和 PromQL 调试")
        st.markdown("[打开 Prometheus →](http://localhost:9090)")

