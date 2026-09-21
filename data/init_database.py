"""
数据库初始化脚本：将 DQH + BtPzh 原始数据导入 SQLite

运行方式：
    python data/init_database.py

说明：
  - DQH 小时/日尺度：基于汛期事件 CSV，每场次独立建表
  - BtPzh 小时/日尺度：连续时间序列，各建一张宽表
  - 站点坐标在 STATION_COORDS 中定义；
    等用户提供真实坐标后直接修改该 dict 即可，is_approximate 字段标记近似坐标
"""

import os
import sys
import sqlite3
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from agent.config import (
    DATABASE_PATH,
    DQH_HOURLY_DIR,
    DQH_DAILY_DIR,
    BTPZH_HOURLY_XLSX,
    BTPZH_DAILY_XLSX,
)

# ─────────────────────────────────────────────────────────
# 站点坐标（WGS84）
# TODO: 用实测坐标替换下列近似值，并将 is_approximate 改为 0
# ─────────────────────────────────────────────────────────
STATION_COORDS: dict[str, tuple[float, float, int]] = {
    # DQH — (lat, lon, is_approximate)
    "dqh_C1": (29.10, 99.75, 1),   # 古学
    "dqh_C2": (28.71, 99.29, 1),   # 得荣
    "dqh_C3": (28.98, 99.62, 1),   # 热打
    "dqh_C4": (29.18, 99.80, 1),   # 乡城
    # BtPzh — 按金沙江沿线地名近似，后续替换
    "btpzh_C01": (29.00, 99.11, 1),  # 三台
    "btpzh_C02": (28.88, 99.25, 1),  # 东山
    "btpzh_C03": (28.80, 99.40, 1),  # 使跨丁
    "btpzh_C04": (28.70, 99.55, 1),  # 倒流箐
    "btpzh_C05": (26.62, 101.35, 1), # 华坪
    "btpzh_C06": (26.50, 101.10, 1), # 团山
    "btpzh_C07": (27.75, 99.45, 1),  # 塔城
    "btpzh_C08": (27.60, 99.50, 1),  # 大东
    "btpzh_C09": (27.10, 99.68, 1),  # 天申堂
    "btpzh_C10": (27.05, 100.12, 1), # 宏地
    "btpzh_C11": (25.97, 100.59, 1), # 宾川
    "btpzh_C12": (26.70, 100.42, 1), # 总管田
    "btpzh_C13": (26.08, 101.22, 1), # 拉乌
    "btpzh_C14": (25.72, 101.34, 1), # 排营
    "btpzh_C15": (27.30, 99.52, 1),  # 新文
    "btpzh_C16": (27.20, 99.60, 1),  # 昔丙
    "btpzh_C17": (27.18, 99.65, 1),  # 期钠
    "btpzh_C18": (26.92, 100.05, 1), # 永兴
    "btpzh_C19": (26.68, 100.75, 1), # 永胜
    "btpzh_C20": (26.50, 101.40, 1), # 河口
    "btpzh_C21": (27.18, 99.72, 1),  # 石洞
    "btpzh_C22": (26.02, 100.43, 1), # 石羊
    "btpzh_C23": (26.38, 101.25, 1), # 石龙坝
    "btpzh_C24": (25.62, 100.45, 1), # 米甸
    "btpzh_C25": (28.42, 99.20, 1),  # 茨拉
    "btpzh_C26": (27.35, 99.47, 1),  # 西川
    "btpzh_C27": (26.88, 99.98, 1),  # 西邑
    "btpzh_C28": (28.18, 99.18, 1),  # 过拉地
    "btpzh_C29": (27.55, 100.88, 1), # 通达
    "btpzh_C30": (26.42, 101.05, 1), # 金棉
    "btpzh_C31": (26.95, 100.22, 1), # 顺州
    "btpzh_C32": (26.12, 100.68, 1), # 马游
    "btpzh_C33": (26.68, 100.28, 1), # 鲁地拉水文站
    "btpzh_C34": (26.55, 100.18, 1), # 鹤庆
    "btpzh_C35": (28.40, 99.05, 1),  # 中咱
    "btpzh_C36": (28.95, 99.80, 1),  # 乡城
    "btpzh_C37": (29.10, 99.75, 1),  # 古学
    "btpzh_C38": (27.95, 99.33, 1),  # 奔子栏
    "btpzh_C39": (28.71, 99.29, 1),  # 得荣
    "btpzh_C40": (28.98, 99.62, 1),  # 热打
    "btpzh_C41": (28.50, 99.45, 1),  # 贡波
    "btpzh_C42": (29.08, 99.10, 1),  # 邦达
    "btpzh_C43": (28.12, 99.25, 1),  # 上桥头
    "btpzh_C44": (28.05, 99.35, 1),  # 尼西
    "btpzh_C45": (27.78, 99.62, 1),  # 巨甸
    "btpzh_C46": (28.60, 99.70, 1),  # 格咱
    "btpzh_C47": (26.88, 99.55, 1),  # 石鼓
    "btpzh_C48": (28.25, 99.30, 1),  # 茨卡桶
    "btpzh_C49": (28.22, 99.42, 1),  # 霞若
    "btpzh_C50": (28.38, 99.52, 1),  # 鲁甸
    "btpzh_C51": (27.72, 99.48, 1),  # 黎明
    "btpzh_C52": (27.65, 99.52, 1),  # 下桥头
    "btpzh_C53": (27.58, 99.48, 1),  # 后箐
    "btpzh_C54": (27.50, 99.58, 1),  # 土官
    "btpzh_C55": (27.42, 99.55, 1),  # 大具二级气象站
    "btpzh_C56": (27.82, 99.70, 1),  # 小中甸
    "btpzh_C57": (26.78, 99.72, 1),  # 梨园变电站气象站
    "btpzh_C58": (26.72, 99.75, 1),  # 梨园气象站
    "btpzh_C59": (27.32, 99.48, 1),  # 永壳
    "btpzh_C60": (27.15, 99.62, 1),  # 白地
    "btpzh_C61": (27.82, 99.72, 1),  # 香格里拉
    "btpzh_C62": (27.68, 99.58, 1),  # 龙蟠
    "btpzh_C63": (27.05, 99.90, 1),  # 三江口雨量站
    "btpzh_C64": (26.95, 99.85, 1),  # 仲扎
    "btpzh_C65": (26.88, 99.80, 1),  # 关田
    "btpzh_C66": (26.82, 99.75, 1),  # 吉尔仲堆
    "btpzh_C67": (26.78, 99.82, 1),  # 奉科一级气象站
    "btpzh_C68": (26.72, 99.88, 1),  # 宁朗
    "btpzh_C69": (26.68, 99.92, 1),  # 日瓦
    "btpzh_C70": (26.62, 99.95, 1),  # 洛吉
    "btpzh_C71": (26.58, 99.98, 1),  # 阿海牛克夕气象站
    "btpzh_C72": (27.05, 101.55, 1), # 稻城
    "btpzh_C73": (26.62, 99.98, 1),  # 阿海水文站
}

# DQH 站点名称到 station_id 的映射（列名顺序固定）
DQH_STATION_COLS = ["古学", "得荣", "热打", "乡城"]
DQH_STATION_IDS  = ["dqh_C1", "dqh_C2", "dqh_C3", "dqh_C4"]

# 舍弃的汛期事件（调蓄影响严重，不导入）
DQH_ABANDONED = {"2017060100", "2018060100", "2020060100", "2021060100", "2022060100", "2023060100"}


def create_tables(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS basin_metadata (
        basin_id   TEXT PRIMARY KEY,
        basin_name TEXT NOT NULL,
        basin_type TEXT,
        river      TEXT,
        description TEXT,
        area_km2   REAL
    );

    CREATE TABLE IF NOT EXISTS station_metadata (
        station_id      TEXT PRIMARY KEY,
        basin_id        TEXT NOT NULL,
        name_cn         TEXT NOT NULL,
        lat             REAL,
        lon             REAL,
        is_approximate  INTEGER DEFAULT 1,
        FOREIGN KEY (basin_id) REFERENCES basin_metadata(basin_id)
    );

    CREATE TABLE IF NOT EXISTS dqh_event_metadata (
        event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        basin_id    TEXT DEFAULT 'dqh',
        event_code  TEXT NOT NULL UNIQUE,
        resolution  TEXT NOT NULL,  -- 'hourly' or 'daily'
        start_time  TEXT,
        end_time    TEXT,
        timesteps   INTEGER
    );

    CREATE TABLE IF NOT EXISTS rainfall_data_dict (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        basin_id    TEXT NOT NULL,
        table_name  TEXT NOT NULL,
        column_name TEXT NOT NULL,
        data_type   TEXT NOT NULL,  -- 'rainfall' or 'flow'
        station_id  TEXT
    );
    """)
    conn.commit()


def insert_basin_metadata(conn: sqlite3.Connection) -> None:
    rows = [
        ("dqh",   "定曲河",       "山区源头",  "金沙江",
         "定曲河流域，位于四川省甘孜州，金沙江一级支流，面积约 6,000 km²。拥有古学、得荣、热打、乡城共 4 个雨量/流量站。",
         6000.0),
        ("btpzh", "巴塘—攀枝花区间", "干流区间",  "金沙江",
         "金沙江中游巴塘至攀枝花区间，跨川滇两省，共 73 个雨量站，小时数据时段 2010-12-16 至 2024-08-10。",
         None),
    ]
    conn.executemany(
        "INSERT OR REPLACE INTO basin_metadata VALUES (?,?,?,?,?,?)", rows
    )
    conn.commit()


def insert_station_metadata(conn: sqlite3.Connection) -> None:
    # DQH stations
    dqh_names = dict(zip(DQH_STATION_IDS, DQH_STATION_COLS))
    # BtPzh station names（顺序与 Excel 列顺序一致）
    btpzh_names = [
        "三台","东山","使跨丁","倒流箐","华坪","团山","塔城","大东","天申堂","宏地",
        "宾川","总管田","拉乌","排营","新文","昔丙","期钠","永兴","永胜","河口",
        "石洞","石羊","石龙坝","米甸","茨拉","西川","西邑","过拉地","通达","金棉",
        "顺州","马游","鲁地拉水文站","鹤庆","中咱","乡城","古学","奔子栏","得荣","热打",
        "贡波","邦达","上桥头","尼西","巨甸","格咱","石鼓","茨卡桶","霞若","鲁甸",
        "黎明","下桥头","后箐","土官","大具二级气象站","小中甸","梨园变电站气象站","梨园气象站",
        "永壳","白地","香格里拉","龙蟠","三江口雨量站","仲扎","关田","吉尔仲堆",
        "奉科一级气象站","宁朗","日瓦","洛吉","阿海牛克夕气象站","稻城","阿海水文站",
    ]
    rows = []
    for sid, name in dqh_names.items():
        lat, lon, approx = STATION_COORDS.get(sid, (None, None, 1))
        rows.append((sid, "dqh", name, lat, lon, approx))
    for i, name in enumerate(btpzh_names, start=1):
        sid = f"btpzh_C{i:02d}"
        lat, lon, approx = STATION_COORDS.get(sid, (None, None, 1))
        rows.append((sid, "btpzh", name, lat, lon, approx))
    conn.executemany(
        "INSERT OR REPLACE INTO station_metadata VALUES (?,?,?,?,?,?)", rows
    )
    conn.commit()


def _load_dqh_event(
    conn: sqlite3.Connection,
    csv_path: str,
    event_code: str,
    resolution: str,
) -> None:
    """读取单个 DQH CSV，建表并插入数据，同时更新元数据表"""
    # Flood_hourly2 已统一为 UTF-8；Flood_daily 原始文件为 GBK
    for enc in ("utf-8", "gb18030"):
        try:
            df = pd.read_csv(csv_path, encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"无法解码 {csv_path}")
    df.columns = ["TIME", "Q", "古学", "得荣", "热打", "乡城"]
    df["TIME"] = pd.to_datetime(df["TIME"])

    table = f"dqh_{resolution}_{event_code}"
    df.to_sql(table, conn, if_exists="replace", index=False)

    # 写事件元数据
    conn.execute(
        "INSERT OR REPLACE INTO dqh_event_metadata "
        "(basin_id, event_code, resolution, start_time, end_time, timesteps) "
        "VALUES ('dqh', ?, ?, ?, ?, ?)",
        (event_code, resolution,
         str(df["TIME"].iloc[0]), str(df["TIME"].iloc[-1]), len(df)),
    )
    # 写数据字典
    for col, sid in zip(DQH_STATION_COLS, DQH_STATION_IDS):
        conn.execute(
            "INSERT INTO rainfall_data_dict (basin_id, table_name, column_name, data_type, station_id) "
            "VALUES (?,?,?,?,?)",
            ("dqh", table, col, "rainfall", sid),
        )
    conn.execute(
        "INSERT INTO rainfall_data_dict (basin_id, table_name, column_name, data_type, station_id) "
        "VALUES (?,?,?,?,?)",
        ("dqh", table, "Q", "flow", None),
    )
    conn.commit()
    print(f"  [{table}] {len(df)} rows")


def load_dqh_hourly(conn: sqlite3.Connection) -> None:
    print("Loading DQH hourly events...")
    for fname in sorted(os.listdir(DQH_HOURLY_DIR)):
        if not fname.endswith(".csv"):
            continue
        event_code = fname.replace(".csv", "")
        if event_code in DQH_ABANDONED:
            print(f"  [SKIP] {event_code} (abandoned)")
            continue
        _load_dqh_event(conn, os.path.join(DQH_HOURLY_DIR, fname), event_code, "hourly")


def load_dqh_daily(conn: sqlite3.Connection) -> None:
    print("Loading DQH daily events...")
    for fname in sorted(os.listdir(DQH_DAILY_DIR)):
        if not fname.endswith(".csv") or fname == "Flood_daily_summary.csv":
            continue
        event_code = fname.replace(".csv", "")
        _load_dqh_event(conn, os.path.join(DQH_DAILY_DIR, fname), event_code, "daily")


def load_btpzh(conn: sqlite3.Connection) -> None:
    """读取 BtPzh 小时 / 日 Excel，建两张宽表"""
    for resolution, xlsx_path, table_name in [
        ("hourly", BTPZH_HOURLY_XLSX, "btpzh_hourly"),
        ("daily",  BTPZH_DAILY_XLSX,  "btpzh_daily"),
    ]:
        print(f"Loading BtPzh {resolution} from {xlsx_path} ...")
        df = pd.read_excel(xlsx_path, engine="openpyxl")
        df.rename(columns={"TIME": "TIME"}, inplace=True)
        df["TIME"] = pd.to_datetime(df["TIME"])

        # 写宽表
        df.to_sql(table_name, conn, if_exists="replace", index=False, chunksize=5000)

        # 写数据字典
        station_cols = [c for c in df.columns if c != "TIME"]
        station_meta = {
            row[2]: row[0]  # name_cn -> station_id
            for row in conn.execute(
                "SELECT station_id, basin_id, name_cn FROM station_metadata WHERE basin_id='btpzh'"
            )
        }
        for col in station_cols:
            sid = station_meta.get(col)
            conn.execute(
                "INSERT INTO rainfall_data_dict (basin_id, table_name, column_name, data_type, station_id) "
                "VALUES (?,?,?,?,?)",
                ("btpzh", table_name, col, "rainfall", sid),
            )
        conn.commit()
        print(f"  [{table_name}] {len(df)} rows × {len(df.columns)} cols")


def create_indexes(conn: sqlite3.Connection) -> None:
    """在 BtPzh 宽表的 TIME 列上建索引，加速时间范围查询"""
    for tbl in ("btpzh_hourly", "btpzh_daily"):
        try:
            conn.execute(f'CREATE INDEX IF NOT EXISTS idx_{tbl}_time ON "{tbl}"("TIME")')
        except Exception:
            pass
    conn.commit()
    print("Indexes created.")


def main() -> None:
    db_dir = os.path.dirname(DATABASE_PATH)
    os.makedirs(db_dir, exist_ok=True)

    if os.path.exists(DATABASE_PATH):
        os.remove(DATABASE_PATH)
        print(f"Existing database removed: {DATABASE_PATH}")

    conn = sqlite3.connect(DATABASE_PATH)
    try:
        create_tables(conn)
        insert_basin_metadata(conn)
        insert_station_metadata(conn)
        load_dqh_hourly(conn)
        load_dqh_daily(conn)
        load_btpzh(conn)
        create_indexes(conn)
        print(f"\nDatabase initialized: {DATABASE_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
