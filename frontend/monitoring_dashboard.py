"""系统监控运营面板

实时展示 Prometheus 指标的可视化面板，包含：
- 总查询数、工具调用成功率、响应时间、活跃会话数
- 意图分类分布、工具调用分布、错误趋势
"""

import streamlit as st
import requests
import plotly.graph_objects as go
from prometheus_client.parser import text_string_to_metric_families


def parse_prometheus_metrics(text: str) -> dict:
    """解析 Prometheus 文本格式指标"""
    metrics = {}
    for family in text_string_to_metric_families(text):
        for sample in family.samples:
            key = f"{sample.name}_{','.join(f'{k}={v}' for k, v in sorted(sample.labels.items()))}"
            metrics[key] = sample.value
    return metrics


def fetch_exporter_metrics(exporter_url: str = "http://localhost:8000") -> dict:
    """从 Prometheus Exporter 获取指标"""
    try:
        resp = requests.get(f"{exporter_url}/metrics", timeout=3)
        if resp.status_code == 200:
            return parse_prometheus_metrics(resp.text)
        return {}
    except Exception:
        return {}


def render_monitoring():
    st.header("📊 系统监控运营")
    st.caption("实时监控 Agent 运行状态和性能指标（数据来源：Prometheus Exporter）")

    # 连接状态检测
    exporter_url = "http://localhost:8000"
    metrics = fetch_exporter_metrics(exporter_url)

    if not metrics:
        st.error("⚠️ Prometheus Exporter 未运行，请先启动监控服务")
        st.code("python scripts/start_services.py", language="bash")
        return

    st.success(f"✅ 已连接到 Prometheus Exporter ({exporter_url})")

    # ========== 核心指标卡片 ==========
    st.subheader("核心指标")
    metric_cols = st.columns(4)

    # 1. 总查询数
    with metric_cols[0]:
        query_count = sum(v for k, v in metrics.items() if k.startswith("agent_query_total_"))
        st.metric("总查询数", f"{int(query_count)}")

    # 2. 工具调用成功率
    with metric_cols[1]:
        total_calls = sum(v for k, v in metrics.items() if k.startswith("agent_tool_call_total_"))
        success_calls = sum(v for k, v in metrics.items() if k.startswith("agent_tool_call_success_total_"))
        success_rate = (success_calls / total_calls * 100) if total_calls > 0 else 100.0
        st.metric("工具调用成功率", f"{success_rate:.1f}%", delta="目标 >95%")

    # 3. 平均响应时间
    with metric_cols[2]:
        duration_sum = sum(v for k, v in metrics.items() if k.startswith("agent_query_duration_seconds_sum_"))
        duration_count = sum(v for k, v in metrics.items() if k.startswith("agent_query_duration_seconds_count_"))
        avg_time = (duration_sum / duration_count) if duration_count > 0 else 0.0
        st.metric("平均响应时间", f"{avg_time:.2f}s", delta="目标 <10s")

    # 4. 活跃会话数
    with metric_cols[3]:
        active_count = int(metrics.get("agent_active_sessions_", 0))
        st.metric("活跃会话数", f"{active_count}", delta="实时")

    st.divider()

    # ========== 意图分类分布 ==========
    st.subheader("意图分类分布")
    intent_data = {}
    for key, value in metrics.items():
        if key.startswith("agent_query_total_intent_type="):
            intent = key.split("intent_type=")[1].split(",")[0]
            intent_data[intent] = int(value)

    if intent_data:
        fig_intent = go.Figure(go.Pie(
            labels=list(intent_data.keys()),
            values=list(intent_data.values()),
            hole=0.4,
            marker=dict(colors=["#0d6efd", "#198754", "#fd7e14", "#6f42c1", "#dc3545", "#0dcaf0"])
        ))
        fig_intent.update_layout(height=400)
        st.plotly_chart(fig_intent, use_container_width=True)
    else:
        st.info("暂无意图分类数据")

    # ========== 工具调用分布 ==========
    st.subheader("工具调用分布")
    tool_data = {}
    for key, value in metrics.items():
        if key.startswith("agent_tool_call_total_tool_name="):
            tool = key.split("tool_name=")[1].split(",")[0]
            tool_data[tool] = int(value)

    if tool_data:
        sorted_tools = sorted(tool_data.items(), key=lambda x: x[1], reverse=True)
        tools, counts = zip(*sorted_tools)

        fig_tools = go.Figure(go.Bar(
            x=tools, y=counts,
            marker_color="#6f42c1",
            text=counts,
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

    # ========== 错误统计 ==========
    st.subheader("错误统计")
    col_a, col_b = st.columns(2)

    with col_a:
        query_errors = sum(v for k, v in metrics.items() if k.startswith("agent_query_error_total_"))
        st.metric("查询错误总数", f"{int(query_errors)}")

    with col_b:
        tool_errors = sum(v for k, v in metrics.items() if k.startswith("agent_tool_call_error_total_"))
        st.metric("工具调用失败总数", f"{int(tool_errors)}")

    # ========== 工具调用失败分布 ==========
    tool_error_data = {}
    for key, value in metrics.items():
        if key.startswith("agent_tool_call_error_total_tool_name="):
            tool = key.split("tool_name=")[1].split(",")[0]
            tool_error_data[tool] = int(value)

    if tool_error_data:
        st.subheader("工具调用失败分布")
        tools_err = list(tool_error_data.keys())
        err_counts = list(tool_error_data.values())

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
        st.success("✅ 暂无工具调用失败")

    st.divider()

    # ========== 说明 ==========
    st.info("""
    **说明：** 当前展示累计指标（Counter），如需查看趋势图（时间序列）和更多高级功能，请安装 Docker 并启动完整监控栈：

    ```bash
    cd docker
    docker-compose up -d
    ```

    启动后访问：
    - **Grafana 面板**：http://localhost:3000 (admin/admin123)
    - **Prometheus**：http://localhost:9090
    """)
