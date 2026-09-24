"""Streamlit 前端大屏 — 金沙江流域水文智能 Agent"""

import json
import os
import re
import sys
from datetime import datetime, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import geopandas as gpd
from shapely import simplify as shapely_simplify

from agent.executor import run_agent
from agent.tools import _safe_query, query_dqh_events, query_dqh_rainfall, query_dqh_statistics, query_btpzh_rainfall, query_btpzh_statistics
from knowledge.knowledge_tools import query_basin_topology
from agent.config import BTPZH_SHP, DQH_SHP, ANALYSIS_OUTPUT_DIR, GUANGDONG_BASINS

st.set_page_config(
    page_title="流域水文智能 Agent",
    page_icon="🏔",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASIN_COLORS = {
    "定曲河": "#0d6efd",
    "巴塘—攀枝花": "#198754",
    "布吉河": "#dc3545",
    "棠荆": "#fd7e14",
    "尖山": "#6f42c1",
    "河子口": "#20c997",
    "白盆珠水库": "#0dcaf0",
}
BASIN_ID_MAP = {
    "定曲河": "dqh",
    "巴塘—攀枝花": "btpzh",
    "布吉河": "bjh",
    "棠荆": "tj",
    "尖山": "js",
    "河子口": "hzk",
    "白盆珠水库": "bpz",
}


# ─── 工具函数 ────────────────────────────────────────────────

@st.cache_resource
def load_geojson(shp_path: str) -> dict | None:
    if not shp_path or not os.path.exists(shp_path):
        return None
    try:
        gdf = gpd.read_file(shp_path).to_crs("EPSG:4326")
        geom = gdf.geometry.union_all()
        simplified = shapely_simplify(geom, tolerance=0.001, preserve_topology=True)
        return simplified.__geo_interface__
    except Exception as e:
        st.warning(f"SHP 加载失败: {e}")
        return None


def parse_md_table(text: str) -> pd.DataFrame | None:
    lines = [l.strip() for l in text.splitlines() if l.strip().startswith("|") and not l.strip().startswith("|--")]
    if len(lines) < 2:
        return None
    try:
        rows = [[c.strip() for c in l.strip("|").split("|")] for l in lines]
        return pd.DataFrame(rows[1:], columns=rows[0])
    except Exception:
        return None


# ─── Tab 1：流域总览 + 地图 ──────────────────────────────────

def render_overview():
    st.header("🏔 流域总览")

    # 金沙江流域
    st.subheader("金沙江流域")
    cols = st.columns(2)
    jsj_meta = {
        "定曲河": {"id": "dqh", "type": "山区源头支流", "stations": 4, "hourly_events": 11, "daily_events": 15, "period": "2008–2024（汛期）"},
        "巴塘—攀枝花": {"id": "btpzh", "type": "金沙江干流区间", "stations": 73, "hourly_events": "连续小时", "daily_events": "连续日", "period": "2010-12 ~ 2024-08"},
    }
    for i, (name, info) in enumerate(jsj_meta.items()):
        color = BASIN_COLORS[name]
        with cols[i]:
            st.markdown(f"""
            <div style="padding:14px;border-radius:8px;border-left:5px solid {color};background:#f8f9fa;">
                <strong style="color:{color};font-size:16px">{name}</strong><br>
                <small>📌 {info['type']}</small><br>
                <small>📡 {info['stations']} 站 &nbsp;|&nbsp; ⏱ 小时: {info['hourly_events']} &nbsp;|&nbsp; 📅 日: {info['daily_events']}</small><br>
                <small>🗓 {info['period']}</small>
            </div>""", unsafe_allow_html=True)

    # 广东流域
    st.subheader("广东流域")
    gd_names = ["布吉河", "棠荆", "尖山", "河子口", "白盆珠水库"]
    gd_cols = st.columns(5)
    for i, name in enumerate(gd_names):
        bid = BASIN_ID_MAP[name]
        color = BASIN_COLORS[name]
        stations = _safe_query("SELECT COUNT(*) as cnt FROM station_metadata WHERE basin_id=?", (bid,))
        station_count = stations[0]["cnt"] if stations else 0
        with gd_cols[i]:
            st.markdown(f"""
            <div style="padding:12px;border-radius:8px;border-left:4px solid {color};background:#f8f9fa;">
                <strong style="color:{color};font-size:14px">{name}</strong><br>
                <small>📡 {station_count} 站</small>
            </div>""", unsafe_allow_html=True)

    st.divider()

    selected = st.multiselect("选择流域显示（可多选）", list(BASIN_ID_MAP.keys()), default=["定曲河"])
    if not selected:
        return

    shp_map = {"定曲河": DQH_SHP, "巴塘—攀枝花": BTPZH_SHP}
    for basin_name in ["布吉河", "棠荆", "尖山", "河子口", "白盆珠水库"]:
        bid = BASIN_ID_MAP[basin_name]
        shp_map[basin_name] = GUANGDONG_BASINS[bid]["watershed_shp"]

    geo_layers, marker_js, all_lats, all_lons = [], [], [], []

    for name in selected:
        bid = BASIN_ID_MAP[name]
        gj = load_geojson(shp_map[name])
        if gj:
            geo_layers.append({"name": name, "geojson": gj, "color": BASIN_COLORS[name]})
        stations = _safe_query(
            "SELECT station_id, name_cn, lat, lon FROM station_metadata WHERE basin_id=? AND lat IS NOT NULL",
            (bid,),
        )
        for s in stations:
            if s["lat"] and s["lon"]:
                color = BASIN_COLORS[name]
                marker_js.append(
                    f'L.circleMarker([{s["lat"]:.5f},{s["lon"]:.5f}],'
                    f'{{radius:5,color:"{color}",fillColor:"{color}",fillOpacity:0.85}})'
                    f'.addTo(map).bindTooltip("{s["station_id"]}: {s["name_cn"]}")'
                )
                all_lats.append(s["lat"])
                all_lons.append(s["lon"])

    if not geo_layers and not marker_js:
        st.info("SHP 文件未找到，仅显示站点标记（坐标为近似值，等待用户更新）。")

    static = Path(__file__).parent / "static"
    leaflet_css = (static / "leaflet.css").read_text(encoding="utf-8")
    leaflet_js = (static / "leaflet.js").read_text(encoding="utf-8")

    center_lat = sum(all_lats) / len(all_lats) if all_lats else 28.0
    center_lon = sum(all_lons) / len(all_lons) if all_lons else 99.5

    layers_js_blocks = []
    for gl in geo_layers:
        layers_js_blocks.append(f"""
(function(){{
  var gj={json.dumps(gl["geojson"])};
  var lyr=L.geoJSON(gj,{{style:function(){{return{{color:'{gl["color"]}',weight:2,fillColor:'{gl["color"]}',fillOpacity:0.12}}}}}}).addTo(map);
  lyr.bindPopup('<b>{gl["name"]}</b>');
  allLayers.push(lyr);
}})();""")

    html = f"""<!DOCTYPE html><html>
<head>
<style>body{{margin:0}}#map{{width:100%;height:680px}}</style>
<style>{leaflet_css}</style>
</head><body>
<div id="map"></div>
<script>{leaflet_js}</script>
<script>
var map=L.map('map').setView([{center_lat:.4f},{center_lon:.4f}],8);
L.tileLayer('https://webst0{{s}}.is.autonavi.com/appmaptile?style=6&x={{x}}&y={{y}}&z={{z}}',
  {{subdomains:'1234',attribution:'高德卫星'}}).addTo(map);
var allLayers=[];
{"".join(layers_js_blocks)}
{";".join(marker_js)};
if(allLayers.length>0){{map.fitBounds(L.featureGroup(allLayers).getBounds().pad(0.1));}}
</script></body></html>"""

    import streamlit.components.v1 as components
    components.html(html, height=700, scrolling=False)


# ─── Tab 2：智能对话 ─────────────────────────────────────────

def render_chat():
    st.header("💬 智能对话")
    st.caption("支持：降雨查询 · 统计分析 · 相关性计算 · Python 代码分析 · 水文知识问答")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("输入水文分析问题……")
    if not user_input:
        return

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        status_box = st.empty()

        def update_status(stage, detail):
            icons = {"intent": "🔍", "plan": "📋", "tools": "🔧", "correct": "✅"}
            status_box.info(f"{icons.get(stage, '⏳')} {detail}")

        # 传递对话历史（不含当前轮）
        history = st.session_state.messages[:-1]
        result = run_agent(user_input, chat_history=history, status_callback=update_status)
        status_box.empty()

        output = result["output"]
        st.markdown(output)

        # 如果输出中含图片路径，自动显示
        for fig_path in re.findall(r"\[FIGURE\]\s*(.+\.png)", output):
            if os.path.exists(fig_path.strip()):
                st.image(fig_path.strip())

        with st.expander("🔍 调试信息"):
            st.json({
                "意图": result["intent"],
                "执行计划": result.get("plan", []),
                "工具调用数": len(result.get("intermediate_steps", [])),
                "已自校验": result["corrected"],
            })

    st.session_state.messages.append({"role": "assistant", "content": output})


# ─── Tab 3：流域历史事件查询 ─────────────────────────────────────

def render_dqh():
    st.header("📊 流域历史事件查询")

    c1, c2, c3 = st.columns(3)
    with c1:
        # 流域选择
        basin_opts = ["定曲河 (dqh)", "布吉河 (bjh)", "棠荆 (tj)", "尖山 (js)", "白盆珠水库 (bpz)"]
        basin_sel = st.selectbox("选择流域", basin_opts)
        basin_id = basin_sel.split("(")[1].strip(")")

    with c2:
        resolution = st.selectbox("时间分辨率", ["hourly", "daily"])

    with c3:
        # 根据流域动态查询事件
        if basin_id == "dqh":
            events_raw = query_dqh_events.invoke({"resolution": resolution})
            event_codes = re.findall(r"\b(\d{8,12})\b", events_raw)
        else:
            # 广东流域：列出Flood目录下的CSV文件
            flood_dir = GUANGDONG_BASINS[basin_id]["station_csv"].replace("StationProperty.csv", "Flood")
            if os.path.exists(flood_dir):
                event_codes = sorted([f.replace(".csv", "") for f in os.listdir(flood_dir) if f.endswith(".csv") and re.match(r"\d{10}", f[:10])])
            else:
                event_codes = []

        event_code = st.selectbox("汛期事件", event_codes if event_codes else ["—"])

    # 站点选择
    stations = _safe_query("SELECT station_id, name_cn FROM station_metadata WHERE basin_id=?", (basin_id,))
    st_opts = ["全部"] + [f"{s['station_id']} {s['name_cn']}" for s in stations]
    st_sel = st.selectbox("站点", st_opts)

    if st.button("查询", type="primary"):
        sid = "" if st_sel == "全部" else st_sel.split()[0]
        st.session_state["event_query"] = {
            "basin_id": basin_id,
            "event_code": event_code,
            "resolution": resolution,
            "sid": sid,
        }

    if "event_query" in st.session_state and isinstance(st.session_state["event_query"], dict):
        q = st.session_state["event_query"]
        tab_rain, tab_stat = st.tabs(["时序数据", "降雨统计"])

        with tab_rain:
            # 查询时序数据
            if q["basin_id"] == "dqh":
                raw = query_dqh_rainfall.invoke({
                    "event_code": q["event_code"], "resolution": q["resolution"],
                    "station_id": q["sid"], "limit": 2000,
                })
            else:
                # 广东流域：读取CSV文件
                flood_csv = GUANGDONG_BASINS[q["basin_id"]]["station_csv"].replace("StationProperty.csv", f"Flood/{q['event_code']}.csv")
                if os.path.exists(flood_csv):
                    df_raw = pd.read_csv(flood_csv, encoding="utf-8")
                    raw = f"## {GUANGDONG_BASINS[q['basin_id']]['name']} {q['event_code']} 事件数据\n" + df_raw.head(200).to_markdown(index=False)
                else:
                    raw = f"未找到事件 {q['event_code']} 的数据文件"

            # 表格展开/收起
            df = parse_md_table(raw)
            if df is not None and len(df) > 20:
                show_full = st.checkbox("展开完整表格", value=False)
                if show_full:
                    st.markdown(raw)
                else:
                    st.markdown(raw[:1500] + "\n\n_（表格已截断，勾选上方复选框查看完整数据）_")
            else:
                st.markdown(raw[:3000])

            # 降雨过程线
            if df is not None:
                # DQH 流域有 TIME 列，广东流域只有 ID 列
                x_col = "TIME" if "TIME" in df.columns else "ID"
                rain_cols = [c for c in df.columns if c not in [x_col, "Q"]]

                if rain_cols:
                    fig = make_subplots(specs=[[{"secondary_y": True}]])
                    for col in rain_cols:
                        vals = pd.to_numeric(df[col], errors="coerce")
                        fig.add_trace(go.Bar(x=df[x_col], y=vals, name=col, opacity=0.7), secondary_y=True)

                    basin_name = GUANGDONG_BASINS.get(q['basin_id'], {}).get('name', '定曲河') if q['basin_id'] != 'dqh' else '定曲河'
                    fig.update_layout(
                        title=f"{basin_name} {q['event_code']} 降雨过程线",
                        height=380,
                        barmode="stack",
                        hovermode="x unified"
                    )
                    fig.update_xaxes(title_text="时间步" if x_col == "ID" else "时间")
                    fig.update_yaxes(title_text="降雨 (mm)", secondary_y=True, autorange="reversed")
                    st.plotly_chart(fig, use_container_width=True)

        with tab_stat:
            if q["basin_id"] == "dqh":
                raw2 = query_dqh_statistics.invoke({"event_code": q["event_code"], "resolution": q["resolution"]})
            else:
                # 广东流域：计算统计
                if os.path.exists(flood_csv):
                    df_raw = pd.read_csv(flood_csv, encoding="utf-8")
                    rain_cols = [c for c in df_raw.columns if c not in ["ID", "Q", "TIME"]]
                    stats = []
                    for col in rain_cols:
                        vals = pd.to_numeric(df_raw[col], errors="coerce")
                        stats.append({
                            "站点": col,
                            "累计雨量(mm)": vals.sum(),
                            "最大时段雨量(mm)": vals.max(),
                            "有雨时次": (vals > 0).sum()
                        })
                    raw2 = f"## {GUANGDONG_BASINS[q['basin_id']]['name']} {q['event_code']} 降雨统计\n" + pd.DataFrame(stats).to_markdown(index=False)
                else:
                    raw2 = "数据文件不存在"

            st.markdown(raw2)
            df2 = parse_md_table(raw2)
            if df2 is not None and "累计雨量(mm)" in df2.columns:
                vals = pd.to_numeric(df2["累计雨量(mm)"], errors="coerce")
                fig2 = go.Figure(go.Bar(x=df2.iloc[:, 0], y=vals, marker_color="#0d6efd"))
                fig2.update_layout(height=320, xaxis_title="站点", yaxis_title="累计雨量 (mm)")
                st.plotly_chart(fig2, use_container_width=True)


# ─── Tab 4：BtPzh 时序查询 ──────────────────────────────────

def render_btpzh():
    st.header("📈 巴塘—攀枝花时序查询")

    c1, c2, c3 = st.columns(3)
    with c1:
        resolution = st.selectbox("分辨率", ["daily", "hourly"], key="btpzh_res")
    with c2:
        start = st.date_input("起始日期", value=date(2015, 6, 1), key="btpzh_s")
    with c3:
        end = st.date_input("结束日期", value=date(2015, 8, 31), key="btpzh_e")

    # 站点选择（多选）
    all_stations = _safe_query("SELECT name_cn FROM station_metadata WHERE basin_id='btpzh' ORDER BY station_id")
    st_names = [s["name_cn"] for s in all_stations]
    sel_stations = st.multiselect("选择站点（留空=全部，全部时仅返回前200行）", st_names,
                                  default=["奔子栏", "石鼓", "阿海水文站"])

    if st.button("查询", type="primary", key="btpzh_query_btn"):
        st.session_state["btpzh_query_data"] = {
            "start": str(start), "end": str(end),
            "resolution": resolution,
            "station_str": ",".join(sel_stations),
        }

    if "btpzh_query_data" in st.session_state and isinstance(st.session_state["btpzh_query_data"], dict):
        q = st.session_state["btpzh_query_data"]
        tab_ts, tab_stat = st.tabs(["时序数据", "统计"])

        with tab_ts:
            raw = query_btpzh_rainfall.invoke({
                "start_date": q["start"], "end_date": q["end"],
                "resolution": q["resolution"], "station_names": q["station_str"], "limit": 300,
            })
            st.markdown(raw[:3000])
            df = parse_md_table(raw)
            if df is not None and "TIME" in df.columns and len(df) > 1:
                rain_cols = [c for c in df.columns if c != "TIME"]
                fig = go.Figure()
                for col in rain_cols:
                    vals = pd.to_numeric(df[col], errors="coerce")
                    fig.add_trace(go.Scatter(x=df["TIME"], y=vals, name=col, mode="lines"))
                fig.update_layout(title=f"BtPzh {q['start']}~{q['end']} 降雨过程（{q['resolution']}）",
                                  height=400, hovermode="x unified",
                                  xaxis_title="时间", yaxis_title="降雨 (mm)")
                st.plotly_chart(fig, use_container_width=True)

        with tab_stat:
            raw2 = query_btpzh_statistics.invoke({
                "start_date": q["start"], "end_date": q["end"],
                "resolution": q["resolution"], "station_names": q["station_str"],
            })
            st.markdown(raw2)
            df2 = parse_md_table(raw2)
            if df2 is not None and "累计雨量(mm)" in df2.columns:
                vals = pd.to_numeric(df2["累计雨量(mm)"], errors="coerce")
                fig2 = go.Figure(go.Bar(x=df2["站点名"], y=vals, marker_color="#198754"))
                fig2.update_layout(height=360, xaxis_title="站点", yaxis_title="累计雨量 (mm)")
                st.plotly_chart(fig2, use_container_width=True)


# ─── Tab 5：代码分析沙盒 ─────────────────────────────────────

def render_sandbox():
    st.header("🧪 Python 分析沙盒")
    st.caption("直接编写 pandas/matplotlib 代码操作数据库，Agent 将在安全隔离进程中执行。")

    default_code = '''\
# 示例：计算定曲河 2009 年汛期各站点降雨统计
conn = get_conn()
df = pd.read_sql("SELECT * FROM dqh_hourly_2009050100", conn)
conn.close()

rain_cols = ['古学', '得荣', '热打', '乡城']
stats = df[rain_cols].agg(['sum', 'max', 'mean']).T
stats.columns = ['累计(mm)', '最大时段(mm)', '均值(mm/h)']
print(stats.round(2).to_string())

# 绘制面雨量过程线
area_rain = df[rain_cols].mean(axis=1)
plt.figure(figsize=(10, 4))
plt.bar(df.index, area_rain, color='steelblue', alpha=0.7, label='面平均雨量')
plt.gca().invert_yaxis()
plt.xlabel('时间步')
plt.ylabel('面平均雨量 (mm/h)')
plt.title('定曲河 2009年汛期 面雨量过程线')
plt.legend()
save_fig('dqh_2009_areal_rain.png')
'''
    code = st.text_area("Python 代码", value=default_code, height=320)

    if st.button("▶ 运行", type="primary"):
        from agent.tools import execute_python_analysis
        with st.spinner("执行中…"):
            output = execute_python_analysis.invoke({"code": code})
        st.subheader("执行结果")
        # 分离文本输出和图片
        text_lines, fig_paths = [], []
        for line in output.splitlines():
            if line.startswith("[FIGURE]"):
                fig_paths.append(line.replace("[FIGURE]", "").strip())
            else:
                text_lines.append(line)
        if text_lines:
            st.code("\n".join(text_lines), language="text")
        for fp in fig_paths:
            if os.path.exists(fp):
                st.image(fp, caption=os.path.basename(fp))
            else:
                st.warning(f"图片未找到: {fp}")


# ─── 主入口 ──────────────────────────────────────────────────

def main():
    st.title("🏔 流域水文智能 Agent")
    st.caption(
        f"基座模型: DeepSeek | 框架: LangChain + LangGraph | "
        f"RAG: BGE-small-zh + BM25 + RRF | 流域: DQH + BtPzh + GD | "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

    tabs = st.tabs(["🌏 流域总览", "💬 智能对话", "📊 流域历史事件", "📈 BtPzh 时序", "🧪 代码沙盒"])
    with tabs[0]:
        render_overview()
    with tabs[1]:
        render_chat()
    with tabs[2]:
        render_dqh()
    with tabs[3]:
        render_btpzh()
    with tabs[4]:
        render_sandbox()


if __name__ == "__main__":
    main()
