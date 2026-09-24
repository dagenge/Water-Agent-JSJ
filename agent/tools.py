"""
Agent 工具集 — 数据库查询工具 + Python 代码执行工具

工具清单（11个）：
  数据查询（10）：
    query_basin_list           — 列出所有流域
    query_station_list         — 查询站点列表
    query_dqh_events           — 查询 DQH 汛期事件
    query_dqh_rainfall         — 查询 DQH 事件降雨时序
    query_dqh_statistics       — 查询 DQH 事件降雨统计
    query_btpzh_rainfall       — 按时间范围查询 BtPzh 降雨
    query_btpzh_statistics     — BtPzh 时段统计（累计/极值）
    query_guangdong_events     — 查询广东流域汛期事件列表
    query_guangdong_rainfall   — 查询广东流域事件降雨时序（含流量Q）
    query_guangdong_statistics — 查询广东流域事件降雨和流量统计

  代码执行（1）：
    execute_python_analysis    — 执行 pandas/matplotlib 数据分析代码，
                                 返回 stdout 及生成文件路径（让 Agent 真正"干活"）
"""

import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import time
from typing import Any

from langchain_core.tools import tool

from agent.config import DATABASE_PATH, BASIN_NAME_MAP, ANALYSIS_OUTPUT_DIR, GUANGDONG_BASINS


# ─── 安全约束常量 ─────────────────────────────────────────────

# SQL 查询 allowlist：只允许这些 basin_id / resolution 值拼入表名
VALID_BASINS = {"dqh", "btpzh", "bjh", "tj", "js", "hzk", "bpz"}
VALID_RESOLUTIONS = {"hourly", "daily"}
# event_code 只允许纯数字（8~12 位）
_EVENT_CODE_RE = re.compile(r"^\d{8,12}$")

# execute_python_analysis 中禁止出现的高危操作
_BANNED_PATTERNS = [
    r"\bos\.system\b",
    r"\bsubprocess\b",
    r"\bshutil\.rmtree\b",
    r"\bshutil\.move\b",
    r"\bopen\s*\(.+['\"]w['\"]",   # 写文件（save_fig 已白名单内）
    r"\b__import__\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\bimportlib\b",
    r"\bctypes\b",
    r"\bsocket\b",
    r"\brequests?\b",
    r"\burllib\b",
]
_BANNED_RE = re.compile("|".join(_BANNED_PATTERNS), re.IGNORECASE)


def _validate_basin_id(basin_id: str) -> str | None:
    """返回清洗后的 basin_id；非法则返回 None"""
    v = basin_id.strip().lower()
    return v if v in VALID_BASINS else None


def _validate_resolution(resolution: str) -> str | None:
    v = resolution.strip().lower()
    return v if v in VALID_RESOLUTIONS else None


def _validate_event_code(event_code: str) -> str | None:
    v = event_code.strip()
    return v if _EVENT_CODE_RE.match(v) else None


# ─── 内部工具函数 ────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _safe_query(sql: str, params: tuple = ()) -> list[dict]:
    """只读查询，返回 dict 列表"""
    conn = _get_conn()
    try:
        cur = conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _to_md_table(rows: list[dict]) -> str:
    if not rows:
        return "_无数据_"
    headers = list(rows[0].keys())
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join(["------"] * len(headers)) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(h, "")) for h in headers) + " |")
    return "\n".join(lines)


# ─── 数据查询工具 ────────────────────────────────────────────

@tool
def query_basin_list() -> str:
    """查询所有流域的基本信息（流域ID、名称、类型、河流、面积）"""
    rows = _safe_query(
        "SELECT basin_id, basin_name, basin_type, river, area_km2 FROM basin_metadata"
    )
    return _to_md_table(rows)


@tool
def query_station_list(basin_id: str = "") -> str:
    """查询站点列表。
    basin_id: 可选，dqh 或 btpzh；为空返回全部。
    返回站点ID、中文名、经纬度（含近似标记）。"""
    if basin_id:
        rows = _safe_query(
            "SELECT station_id, name_cn, lat, lon, is_approximate "
            "FROM station_metadata WHERE basin_id=? ORDER BY station_id",
            (basin_id,),
        )
    else:
        rows = _safe_query(
            "SELECT station_id, basin_id, name_cn, lat, lon FROM station_metadata "
            "ORDER BY basin_id, station_id"
        )
    return _to_md_table(rows)


@tool
def query_dqh_events(resolution: str = "") -> str:
    """查询定曲河（DQH）汛期事件列表。
    resolution: 可选，hourly（小时）或 daily（日），为空返回全部。
    返回事件代码、时间分辨率、开始/结束时间、时间步数。"""
    sql = ("SELECT event_code, resolution, start_time, end_time, timesteps "
           "FROM dqh_event_metadata")
    params: tuple = ()
    if resolution:
        sql += " WHERE resolution=?"
        params = (resolution,)
    sql += " ORDER BY resolution, event_code"
    rows = _safe_query(sql, params)
    return _to_md_table(rows)


@tool
def query_dqh_rainfall(
    event_code: str,
    resolution: str = "hourly",
    station_id: str = "",
    limit: int = 200,
) -> str:
    """查询 DQH 指定汛期事件的降雨时序数据（不含流量Q）。
    event_code: 事件代码，如 2009050100。
    resolution: hourly（默认）或 daily。
    station_id: 可选，指定站点ID（dqh_C1~dqh_C4），为空返回全部站点。
    limit: 最多返回行数，默认 200，最大 2000。"""
    ec = _validate_event_code(event_code)
    res = _validate_resolution(resolution)
    if not ec:
        return f"event_code 格式无效（需 8~12 位纯数字）：{event_code}"
    if not res:
        return f"resolution 无效（仅接受 hourly / daily）：{resolution}"
    table = f"dqh_{res}_{ec}"

    # 确认表存在
    exists = _safe_query(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    if not exists:
        return f"未找到事件 {ec}（resolution={res}），请先用 query_dqh_events 确认。"

    # 从数据字典取降雨列
    dict_rows = _safe_query(
        "SELECT column_name, station_id FROM rainfall_data_dict "
        "WHERE table_name=? AND data_type='rainfall' ORDER BY id",
        (table,),
    )
    if station_id:
        rain_cols = [r["column_name"] for r in dict_rows if r["station_id"] == station_id]
    else:
        rain_cols = [r["column_name"] for r in dict_rows]

    if not rain_cols:
        return f"站点 {station_id} 在事件 {event_code} 中无降雨数据。"

    quoted = ", ".join(f'"{c}"' for c in rain_cols)
    sql = f'SELECT TIME, {quoted} FROM "{table}" LIMIT {min(limit, 2000)}'
    rows = _safe_query(sql)
    header = f"## 定曲河 {event_code}（{resolution}）降雨时序\n"
    return header + _to_md_table(rows)


@tool
def query_dqh_statistics(event_code: str, resolution: str = "hourly") -> str:
    """计算 DQH 指定汛期事件各站点降雨统计：累计雨量、最大小时雨量、有雨时次。
    event_code: 事件代码。
    resolution: hourly（默认）或 daily。"""
    ec = _validate_event_code(event_code)
    res = _validate_resolution(resolution)
    if not ec:
        return f"event_code 格式无效：{event_code}"
    if not res:
        return f"resolution 无效：{resolution}"
    table = f"dqh_{res}_{ec}"
    exists = _safe_query(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    if not exists:
        return f"未找到事件 {ec}（resolution={res}）。"

    dict_rows = _safe_query(
        "SELECT column_name, station_id FROM rainfall_data_dict "
        "WHERE table_name=? AND data_type='rainfall' ORDER BY id",
        (table,),
    )
    lines = [
        f"## 定曲河 {ec}（{res}）降雨统计",
        "| 站点ID | 站点名 | 累计雨量(mm) | 最大时段雨量(mm) | 有雨时次 |",
        "|--------|--------|-------------|----------------|----------|",
    ]
    for d in dict_rows:
        col, sid = d["column_name"], d["station_id"] or "—"
        row = _safe_query(
            f'SELECT SUM("{col}") as total, MAX("{col}") as mx, '
            f'SUM(CASE WHEN "{col}">0 THEN 1 ELSE 0 END) as cnt '
            f'FROM "{table}"'
        )
        if row and row[0]["total"] is not None:
            r = row[0]
            lines.append(
                f"| {sid} | {col} | {r['total']:.1f} | {r['mx']:.1f} | {r['cnt']} |"
            )
    return "\n".join(lines)


@tool
def query_btpzh_rainfall(
    start_date: str,
    end_date: str,
    resolution: str = "daily",
    station_names: str = "",
    limit: int = 200,
) -> str:
    """查询巴塘—攀枝花（BtPzh）连续时序降雨数据。
    start_date: 起始日期，格式 YYYY-MM-DD 或 YYYY-MM-DD HH:MM。
    end_date:   结束日期，同上格式。
    resolution: daily（日，默认）或 hourly（小时）。
    station_names: 逗号分隔的中文站点名，如 '奔子栏,石鼓,阿海水文站'；为空返回全部。
    limit: 最多返回行数，默认 200，最大 500。"""
    res = _validate_resolution(resolution)
    if not res:
        return f"resolution 无效（仅接受 hourly / daily）：{resolution}"
    table = "btpzh_hourly" if res == "hourly" else "btpzh_daily"

    if station_names.strip():
        names = [n.strip() for n in station_names.split(",") if n.strip()]
        quoted = ", ".join(f'"{n}"' for n in names)
        col_clause = f"TIME, {quoted}"
    else:
        col_clause = "*"

    sql = (
        f'SELECT {col_clause} FROM "{table}" '
        f'WHERE TIME >= ? AND TIME <= ? '
        f'ORDER BY TIME LIMIT {min(limit, 500)}'
    )
    rows = _safe_query(sql, (start_date, end_date))
    if not rows:
        return f"时段 {start_date}~{end_date} 无数据（{resolution}）。请检查日期范围，BtPzh 数据覆盖 2010-12 至 2024-08。"
    header = f"## 巴塘—攀枝花 {start_date}~{end_date}（{resolution}）\n"
    return header + _to_md_table(rows)


@tool
def query_btpzh_statistics(
    start_date: str,
    end_date: str,
    resolution: str = "daily",
    station_names: str = "",
) -> str:
    """计算 BtPzh 指定时段各站点降雨统计：累计雨量、最大时段雨量。
    start_date / end_date: 格式 YYYY-MM-DD。
    resolution: daily（默认）或 hourly。
    station_names: 逗号分隔中文站名；为空统计全部站点（较慢）。"""
    res = _validate_resolution(resolution)
    if not res:
        return f"resolution 无效：{resolution}"
    table = "btpzh_hourly" if res == "hourly" else "btpzh_daily"

    if station_names.strip():
        names = [n.strip() for n in station_names.split(",") if n.strip()]
    else:
        # 从数据字典取所有站点列名
        dict_rows = _safe_query(
            "SELECT DISTINCT column_name FROM rainfall_data_dict "
            "WHERE basin_id='btpzh' AND table_name=? AND data_type='rainfall'",
            (table,),
        )
        names = [r["column_name"] for r in dict_rows]

    lines = [
        f"## 巴塘—攀枝花 {start_date}~{end_date}（{res}）统计",
        "| 站点名 | 累计雨量(mm) | 最大时段雨量(mm) | 有效时次 |",
        "|--------|-------------|----------------|---------|",
    ]
    for name in names:
        row = _safe_query(
            f'SELECT SUM("{name}") as total, MAX("{name}") as mx, '
            f'SUM(CASE WHEN "{name}">0 THEN 1 ELSE 0 END) as cnt '
            f'FROM "{table}" WHERE TIME>=? AND TIME<=?',
            (start_date, end_date),
        )
        if row and row[0]["total"] is not None:
            r = row[0]
            lines.append(f"| {name} | {r['total']:.1f} | {r['mx']:.1f} | {r['cnt']} |")
    return "\n".join(lines)


@tool
def query_guangdong_events(basin_id: str) -> str:
    """查询广东流域（布吉河、棠荆、尖山、河子口、白盆珠水库）的汛期事件列表。
    basin_id: bjh, tj, js, hzk, bpz 之一。
    返回该流域所有事件代码列表。"""
    if basin_id not in GUANGDONG_BASINS:
        return f"basin_id 无效：{basin_id}，仅支持 {', '.join(GUANGDONG_BASINS.keys())}"

    flood_dir = GUANGDONG_BASINS[basin_id].get("flood_dir", "")
    if not flood_dir or not os.path.exists(flood_dir):
        return f"{GUANGDONG_BASINS[basin_id]['name']} 的 Flood 目录不存在：{flood_dir}"

    try:
        files = [f for f in os.listdir(flood_dir) if f.endswith(".csv")]
        event_codes = sorted([f.replace(".csv", "") for f in files if re.match(r"\d{10}", f[:10])])

        if not event_codes:
            return f"{GUANGDONG_BASINS[basin_id]['name']} 暂无汛期事件数据。"

        lines = [
            f"## {GUANGDONG_BASINS[basin_id]['name']} 汛期事件列表",
            f"共 {len(event_codes)} 个事件：",
            "",
            "| 序号 | 事件代码 | 年份 |",
            "|------|---------|------|",
        ]
        for idx, code in enumerate(event_codes, 1):
            year = code[:4] if len(code) >= 4 else "—"
            lines.append(f"| {idx} | {code} | {year} |")

        return "\n".join(lines)
    except Exception as e:
        return f"读取事件列表失败：{e}"


@tool
def query_guangdong_rainfall(basin_id: str, event_code: str, limit: int = 200) -> str:
    """查询广东流域指定汛期事件的降雨时序数据（含流量Q列）。
    basin_id: bjh, tj, js, hzk, bpz 之一。
    event_code: 事件代码，如 2003091505。
    limit: 最多返回行数，默认 200。
    返回时序表格，包含 ID、Q（流量）、各站点降雨列、Z列。"""
    if basin_id not in GUANGDONG_BASINS:
        return f"basin_id 无效：{basin_id}"

    flood_dir = GUANGDONG_BASINS[basin_id].get("flood_dir", "")
    csv_path = os.path.join(flood_dir, f"{event_code}.csv")

    if not os.path.exists(csv_path):
        return f"事件 {event_code} 的数据文件不存在：{csv_path}"

    try:
        import pandas as pd
        df = pd.read_csv(csv_path, encoding="utf-8")

        if len(df) > limit:
            df = df.head(limit)
            truncated = True
        else:
            truncated = False

        lines = [
            f"## {GUANGDONG_BASINS[basin_id]['name']} {event_code} 事件时序数据",
            df.to_markdown(index=False),
        ]
        if truncated:
            lines.append(f"\n_（表格已截断，仅显示前 {limit} 行）_")

        return "\n".join(lines)
    except Exception as e:
        return f"读取事件数据失败：{e}"


@tool
def query_guangdong_statistics(basin_id: str, event_code: str) -> str:
    """查询广东流域指定汛期事件的降雨和流量统计。
    basin_id: bjh, tj, js, hzk, bpz 之一。
    event_code: 事件代码。
    返回各站点累计雨量、最大时段雨量、有雨时次，以及流量Q的最大值和平均值。"""
    if basin_id not in GUANGDONG_BASINS:
        return f"basin_id 无效：{basin_id}"

    flood_dir = GUANGDONG_BASINS[basin_id].get("flood_dir", "")
    csv_path = os.path.join(flood_dir, f"{event_code}.csv")

    if not os.path.exists(csv_path):
        return f"事件 {event_code} 的数据文件不存在"

    try:
        import pandas as pd
        df = pd.read_csv(csv_path, encoding="utf-8")

        # 排除 ID, Z 列，提取 Q 和降雨列
        exclude_cols = ["ID", "Z"]
        data_cols = [c for c in df.columns if c not in exclude_cols]

        lines = [
            f"## {GUANGDONG_BASINS[basin_id]['name']} {event_code} 统计",
            "",
            "### 降雨统计",
            "| 站点 | 累计雨量(mm) | 最大时段雨量(mm) | 有雨时次 |",
            "|------|-------------|----------------|----------|",
        ]

        rain_cols = [c for c in data_cols if c != "Q"]
        for col in rain_cols:
            vals = pd.to_numeric(df[col], errors="coerce")
            total = vals.sum()
            mx = vals.max()
            cnt = (vals > 0).sum()
            lines.append(f"| {col} | {total:.1f} | {mx:.1f} | {cnt} |")

        # 流量统计
        if "Q" in df.columns:
            q_vals = pd.to_numeric(df["Q"], errors="coerce")
            q_max = q_vals.max()
            q_mean = q_vals.mean()
            q_records = len(q_vals.dropna())
            lines.extend([
                "",
                "### 流量统计",
                f"- 最大流量：{q_max:.2f} m³/s",
                f"- 平均流量：{q_mean:.2f} m³/s",
                f"- 有效记录数：{q_records}",
            ])

        return "\n".join(lines)
    except Exception as e:
        return f"统计计算失败：{e}"


# ─── 代码执行工具 ────────────────────────────────────────────

_EXEC_PRELUDE = '''
import os, sys, warnings
warnings.filterwarnings("ignore")
import sqlite3
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 自动寻找中文字体（Windows / Linux）
_cjk_font_paths = [
    r"C:\\Windows\\Fonts\\msyh.ttc",
    r"C:\\Windows\\Fonts\\simhei.ttf",
    r"C:\\Windows\\Fonts\\simsun.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]
for _font_path in _cjk_font_paths:
    if os.path.exists(_font_path):
        _font_name = fm.FontProperties(fname=_font_path).get_name()
        plt.rcParams["font.sans-serif"] = [_font_name] + plt.rcParams["font.sans-serif"]
        break
else:
    _cjk_fonts = [f.name for f in fm.fontManager.ttflist
                  if any(k in f.name for k in ("SimHei", "Microsoft YaHei", "SimSun", "WenQuanYi", "Noto"))]
    if _cjk_fonts:
        plt.rcParams["font.sans-serif"] = _cjk_fonts + plt.rcParams["font.sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

DB_PATH = r"{db_path}"
OUTPUT_DIR = r"{output_dir}"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def save_fig(name="figure.png"):
    path = os.path.join(OUTPUT_DIR, name)
    plt.savefig(path, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"[FIGURE] {{path}}")
    return path
'''


@tool
def execute_python_analysis(code: str) -> str:
    """执行 Python 数据分析代码，可操作 SQLite 数据库、生成图表和统计结果。
    适用场景：复杂的统计分析、相关性计算、可视化图表生成、多站点对比等。

    可用资源：
      - pandas, numpy, matplotlib（中文字体自动配置）
      - DB_PATH: SQLite 数据库路径
      - get_conn(): 获取数据库连接
      - save_fig(name): 保存当前 matplotlib 图形，返回文件路径（name 用英文）
      - OUTPUT_DIR: 分析结果输出目录

    使用 print() 输出分析结果；生成图表用 save_fig() 保存。
    输出路径中含 [FIGURE] 前缀的行表示已生成图片文件。

    示例（面雨量计算）：
        conn = get_conn()
        df = pd.read_sql("SELECT * FROM dqh_hourly_2009050100", conn)
        area_rain = df[['古学','得荣','热打','乡城']].mean(axis=1)
        print(area_rain.describe())
    """
    # 安全约束：拦截高危操作关键字
    if _BANNED_RE.search(code):
        hits = _BANNED_RE.findall(code)
        return f"[SECURITY] 代码包含禁止操作：{hits}。仅允许 pandas / numpy / matplotlib 数据分析操作。"

    # 代码长度限制（防止超长注入）
    if len(code) > 8000:
        return "[SECURITY] 代码过长（上限 8000 字符），请简化后重试。"

    prelude = _EXEC_PRELUDE.format(
        db_path=DATABASE_PATH.replace("\\", "\\\\"),
        output_dir=ANALYSIS_OUTPUT_DIR.replace("\\", "\\\\"),
    )
    full_code = prelude + "\n\n" + textwrap.dedent(code)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", encoding="utf-8", delete=False
    ) as f:
        f.write(full_code)
        tmp_path = f.name

    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            timeout=60,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        duration_ms = (time.time() - start) * 1000

        output_parts = []
        if stdout:
            output_parts.append(stdout)
        if stderr:
            # 过滤掉无关的 UserWarning
            filtered = "\n".join(
                l for l in stderr.splitlines()
                if not l.startswith("Traceback") or "Error" in l
            )
            if filtered:
                output_parts.append(f"[STDERR]\n{filtered}")
        if result.returncode != 0 and not output_parts:
            output_parts.append(f"[EXIT {result.returncode}] {stderr[:500]}")

        return "\n".join(output_parts) or "(代码执行完毕，无输出)"
    except subprocess.TimeoutExpired:
        return "[TIMEOUT] 代码执行超时（>60秒），请简化分析逻辑或缩小数据范围。"
    except Exception as e:
        return f"[ERROR] 代码执行出错: {e}"
    finally:
        os.unlink(tmp_path)


# ─── 工具列表（供 executor 使用）───────────────────────────

ALL_TOOLS = [
    query_basin_list,
    query_station_list,
    query_dqh_events,
    query_dqh_rainfall,
    query_dqh_statistics,
    query_btpzh_rainfall,
    query_btpzh_statistics,
    query_guangdong_events,
    query_guangdong_rainfall,
    query_guangdong_statistics,
    execute_python_analysis,
]
