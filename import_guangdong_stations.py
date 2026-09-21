"""导入广东省流域站点数据到 SQLite 和 PostgreSQL"""

import sqlite3
import pandas as pd
from pyproj import Transformer

# 投影坐标转经纬度（广东省使用 CGCS2000 / 3-degree Gauss-Kruger CM 114E）
transformer = Transformer.from_crs("EPSG:4547", "EPSG:4326", always_xy=True)

def convert_coords(x, y):
    """投影坐标 -> WGS84 经纬度"""
    lon, lat = transformer.transform(x, y)
    return lat, lon

# 读取站点数据
stations = []

# BJH 流域（布吉河）
bjh = pd.read_csv(r"H:\Biye\Data\Model\BJH\modelfile\Stationproperty.csv")
for _, row in bjh.iterrows():
    lat, lon = convert_coords(row['X'], row['Y'])
    stations.append({
        'station_id': f"bjh_{row['SID']}",
        'basin_id': 'bjh',
        'name_cn': row['NAME'],
        'lat': lat,
        'lon': lon,
        'is_approximate': 0
    })

# BPZ 流域（白盆珠）
bpz = pd.read_csv(r"H:\Biye\Data\Model\BPZ\modelfile\Stationproperty.csv")
for _, row in bpz.iterrows():
    lat, lon = convert_coords(row['X'], row['Y'])
    stations.append({
        'station_id': f"bpz_{row['SID']}",
        'basin_id': 'bpz',
        'name_cn': row['NAME'],
        'lat': lat,
        'lon': lon,
        'is_approximate': 0
    })

# JS 流域（鉴江）
js = pd.read_csv(r"H:\Biye\Data\Model\JS\modelfile\Stationproperty.csv")
for _, row in js.iterrows():
    lat, lon = convert_coords(row['X'], row['Y'])
    stations.append({
        'station_id': f"js_{row['SID']}",
        'basin_id': 'js',
        'name_cn': row['NAME'],
        'lat': lat,
        'lon': lon,
        'is_approximate': 0
    })

# TJ 流域（潭江）
tj = pd.read_csv(r"H:\Biye\Data\Model\TJ\modelfile\Stationproperty.csv", encoding='gbk')
for _, row in tj.iterrows():
    lat, lon = convert_coords(row['X'], row['Y'])
    stations.append({
        'station_id': f"tj_{row['SID']}",
        'basin_id': 'tj',
        'name_cn': row['NAME'],
        'lat': lat,
        'lon': lon,
        'is_approximate': 0
    })

print(f"Total Guangdong stations: {len(stations)}")

# 插入到 SQLite
conn = sqlite3.connect('data/database/jsj_agent.db')
cursor = conn.cursor()

# 插入流域元数据
basins = [
    ('bjh', '布吉河流域'),
    ('bpz', '白盆珠流域'),
    ('js', '鉴江流域'),
    ('tj', '潭江流域')
]

for basin in basins:
    cursor.execute('''
        INSERT OR IGNORE INTO basin_metadata (basin_id, basin_name)
        VALUES (?, ?)
    ''', basin)

# 插入站点
for station in stations:
    cursor.execute('''
        INSERT OR REPLACE INTO station_metadata
        (station_id, basin_id, name_cn, lat, lon, is_approximate)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        station['station_id'],
        station['basin_id'],
        station['name_cn'],
        station['lat'],
        station['lon'],
        station['is_approximate']
    ))

conn.commit()

# 验证
cursor.execute('SELECT basin_id, COUNT(*) FROM station_metadata GROUP BY basin_id')
for row in cursor.fetchall():
    print(f"{row[0]}: {row[1]} stations")

conn.close()

print("\nSQLite import completed!")
print("Next: Run init_db.py to sync to PostgreSQL")
