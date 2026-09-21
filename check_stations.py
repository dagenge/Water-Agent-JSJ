import sqlite3

conn = sqlite3.connect('data/database/jsj_agent.db')
cursor = conn.execute('SELECT station_id, name_cn, basin_id, lat, lon FROM station_metadata LIMIT 10')

print('Station ID | Name | Basin | Latitude | Longitude')
print('-' * 70)
for row in cursor.fetchall():
    print(f'{row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]}')

cursor = conn.execute('SELECT COUNT(*) FROM station_metadata WHERE basin_id = "btpzh"')
print(f'\nBTPZH stations: {cursor.fetchone()[0]}')

cursor = conn.execute('SELECT COUNT(*) FROM station_metadata WHERE basin_id = "dqh"')
print(f'DQH stations: {cursor.fetchone()[0]}')

cursor = conn.execute('SELECT COUNT(*) FROM station_metadata')
print(f'Total stations: {cursor.fetchone()[0]}')

conn.close()
