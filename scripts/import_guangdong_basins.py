"""导入广东流域站点数据到数据库

从 H:\Biye\Data\Model 下的各流域文件夹读取 StationProperty.csv，
将站点信息导入到 jsj_agent.db 的 station_metadata 表中。

坐标系转换：WGS84 UTM Zone 50N (EPSG:32650) → WGS84 经纬度 (EPSG:4326)
"""

import os
import sys
import sqlite3
import pandas as pd
from pathlib import Path
from pyproj import Transformer

# 设置控制台编码为 UTF-8
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agent.config import DATABASE_PATH, GUANGDONG_BASINS

# 坐标转换器：UTM Zone 50N → WGS84 经纬度（广东流域使用 EPSG:32650）
transformer = Transformer.from_crs('EPSG:32650', 'EPSG:4326', always_xy=True)


def import_basin_stations(basin_id: str, basin_config: dict, conn: sqlite3.Connection):
    """导入单个流域的站点数据"""
    csv_path = basin_config["station_csv"]
    basin_name = basin_config["name"]

    if not os.path.exists(csv_path):
        print(f"  ⚠️  {basin_name} 站点CSV不存在: {csv_path}")
        return 0

    # 尝试多种编码读取CSV
    df = None
    for encoding in ['utf-8', 'gbk', 'gb2312', 'latin1']:
        try:
            df = pd.read_csv(csv_path, encoding=encoding)
            break
        except (UnicodeDecodeError, Exception):
            continue

    if df is None:
        print(f"  ⚠️  {basin_name} 站点CSV编码无法识别: {csv_path}")
        return 0

    print(f"  📄 读取 {basin_name} 站点CSV: {len(df)} 条记录")

    cursor = conn.cursor()
    inserted = 0

    for _, row in df.iterrows():
        station_id = f"{basin_id}_{row['SID']}"
        name_cn = row['NAME']
        x_utm, y_utm = row['X'], row['Y']

        # UTM → 经纬度
        lon, lat = transformer.transform(x_utm, y_utm)

        # 检查是否已存在
        cursor.execute(
            "SELECT COUNT(*) FROM station_metadata WHERE station_id=?",
            (station_id,)
        )
        if cursor.fetchone()[0] > 0:
            print(f"    - {station_id} 已存在，跳过")
            continue

        # 插入数据库
        cursor.execute("""
            INSERT INTO station_metadata (station_id, basin_id, name_cn, lat, lon, is_approximate)
            VALUES (?, ?, ?, ?, ?, 0)
        """, (station_id, basin_id, name_cn, lat, lon))

        inserted += 1
        print(f"    ✓ {station_id}: {name_cn} ({lat:.6f}, {lon:.6f})")

    conn.commit()
    return inserted


def main():
    print("=" * 60)
    print("导入广东流域站点数据")
    print("=" * 60)

    if not os.path.exists(DATABASE_PATH):
        print(f"\n❌ 数据库文件不存在: {DATABASE_PATH}")
        return 1

    conn = sqlite3.connect(DATABASE_PATH)

    total_inserted = 0
    for basin_id, config in GUANGDONG_BASINS.items():
        print(f"\n[{basin_id}] {config['name']}")
        count = import_basin_stations(basin_id, config, conn)
        total_inserted += count

    conn.close()

    print("\n" + "=" * 60)
    print(f"✅ 完成！共导入 {total_inserted} 个站点")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
