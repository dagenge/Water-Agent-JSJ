"""SQLite 数据迁移到 PostgreSQL + pgvector

迁移内容：
1. 流域元数据、站点元数据、洪水场次元数据、数据字典
2. 洪水时序数据（动态表）
3. 知识库向量化数据从FAISS迁移到pgvector

优势：
- 向量和元数据统一存储，保证一致性
- 支持SQL条件过滤 + 向量相似度组合查询
- 增量更新无需重建整个索引
- 生产级备份恢复能力
"""

import sqlite3
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text, Table, Column, Float, MetaData, Integer
from config.postgres.database import engine, SessionLocal, init_pgvector
from config.postgres.models import (
    Base, BasinMetadata, StationMetadata, FloodEventMetadata,
    RainfallDataDict, KnowledgeDocument
)

SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "database", "water_agent.db")


def migrate_metadata():
    """迁移元数据表"""
    print("\n=== 迁移元数据表 ===")

    if not os.path.exists(SQLITE_DB_PATH):
        print(f"  ⚠ SQLite数据库不存在: {SQLITE_DB_PATH}")
        return

    sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
    sqlite_conn.row_factory = sqlite3.Row

    db = SessionLocal()

    try:
        # 1. 流域元数据
        print("  - 流域元数据...")
        cursor = sqlite_conn.execute("SELECT * FROM basin_metadata")
        basins = []
        for row in cursor.fetchall():
            basin = BasinMetadata(
                basin_id=row["basin_id"],
                basin_name=row["basin_name"],
                province=row.get("province", "广东省"),
                basin_type=row["basin_type"],
                area_km2=row.get("area_km2"),
                description=row["description"],
            )
            basins.append(basin)

        if basins:
            db.bulk_save_objects(basins)
            db.commit()
            print(f"    ✓ 导入 {len(basins)} 个流域")

        # 2. 站点元数据
        print("  - 站点元数据...")
        cursor = sqlite_conn.execute("SELECT * FROM station_metadata")
        stations = []
        for row in cursor.fetchall():
            station = StationMetadata(
                station_id=row["station_id"],
                basin_id=row["basin_id"],
                sid=row["sid"],
                name_cn=row.get("name_cn"),
                name_en=row.get("name_en"),
                x_coord=row.get("x_coord"),
                y_coord=row.get("y_coord"),
                lon=row.get("lon"),
                lat=row.get("lat"),
            )
            stations.append(station)

        if stations:
            db.bulk_save_objects(stations)
            db.commit()
            print(f"    ✓ 导入 {len(stations)} 个站点")

        # 3. 洪水场次元数据
        print("  - 洪水场次元数据...")
        cursor = sqlite_conn.execute("SELECT * FROM flood_event_metadata")
        events = []
        for row in cursor.fetchall():
            event = FloodEventMetadata(
                event_id=row["event_id"],
                basin_id=row["basin_id"],
                event_code=row["event_code"],
                event_name=row.get("event_name"),
                start_time=row.get("start_time"),
                end_time=row.get("end_time"),
                timesteps=row.get("timesteps"),
            )
            events.append(event)

        if events:
            db.bulk_save_objects(events)
            db.commit()
            print(f"    ✓ 导入 {len(events)} 个洪水场次")

        # 4. 数据字典
        print("  - 数据字典...")
        cursor = sqlite_conn.execute("SELECT * FROM rainfall_data_dict")
        dict_entries = []
        for row in cursor.fetchall():
            entry = RainfallDataDict(
                basin_id=row["basin_id"],
                event_code=row["event_code"],
                column_index=row["column_index"],
                column_name=row["column_name"],
                station_id=row.get("station_id"),
                data_type=row.get("data_type", "rainfall"),
                unit=row.get("unit", "mm"),
            )
            dict_entries.append(entry)

        if dict_entries:
            db.bulk_save_objects(dict_entries)
            db.commit()
            print(f"    ✓ 导入 {len(dict_entries)} 条数据字典")

    except Exception as e:
        print(f"  ✗ 迁移失败: {e}")
        db.rollback()
    finally:
        db.close()
        sqlite_conn.close()


def migrate_flood_timeseries():
    """迁移洪水时序数据（动态表）"""
    print("\n=== 迁移洪水时序数据 ===")

    if not os.path.exists(SQLITE_DB_PATH):
        print(f"  ⚠ SQLite数据库不存在，跳过")
        return

    sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
    sqlite_conn.row_factory = sqlite3.Row

    # 获取所有洪水表名
    cursor = sqlite_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'flood_%'"
    )
    tables = [row[0] for row in cursor.fetchall()]

    print(f"  发现 {len(tables)} 个洪水时序表")

    metadata = MetaData()

    for i, table_name in enumerate(tables, 1):
        print(f"  [{i}/{len(tables)}] {table_name}...", end=" ")

        try:
            # 获取表结构
            cursor = sqlite_conn.execute(f'PRAGMA table_info("{table_name}")')
            columns = cursor.fetchall()

            # 动态创建 PostgreSQL 表
            cols = []
            for col in columns:
                col_name = col[1]

                if col_name == "ID":
                    cols.append(Column("ID", Integer, primary_key=True))
                else:
                    # 其他列都是浮点数（降雨量、流量）
                    cols.append(Column(col_name, Float))

            table = Table(table_name, metadata, *cols, extend_existing=True)
            table.create(engine, checkfirst=True)

            # 批量导入数据
            cursor = sqlite_conn.execute(f'SELECT * FROM "{table_name}"')
            rows = cursor.fetchall()

            if rows:
                # 转换为字典列表
                data = []
                for row in rows:
                    row_dict = {}
                    for col in columns:
                        col_name = col[1]
                        value = row[col_name]
                        # 转换为适当的类型
                        if col_name == "ID":
                            row_dict[col_name] = int(value) if value is not None else None
                        else:
                            row_dict[col_name] = float(value) if value is not None else None
                    data.append(row_dict)

                # 批量插入
                with engine.connect() as conn:
                    conn.execute(table.insert(), data)
                    conn.commit()

                print(f"✓ {len(rows)} 行")
            else:
                print("(空表)")

        except Exception as e:
            print(f"✗ {e}")

    sqlite_conn.close()


def migrate_knowledge_vectors():
    """迁移知识库向量到 pgvector

    从FAISS文件 + BM25 pickle 迁移到 PostgreSQL + pgvector
    优势：向量和元数据统一存储，支持SQL条件过滤 + 向量检索组合
    """
    print("\n=== 迁移知识库向量到 pgvector ===")

    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from knowledge.rag_engine import get_rag, BASIN_NAME_MAP
    except ImportError as e:
        print(f"  ⚠ 无法导入RAG模块: {e}")
        print("  跳过向量迁移")
        return

    try:
        rag = get_rag(force_rebuild=False)
    except Exception as e:
        print(f"  ⚠ RAG加载失败: {e}")
        print("  跳过向量迁移")
        return

    db = SessionLocal()

    try:
        total_docs = 0
        for basin_id, basin_name in BASIN_NAME_MAP.items():
            print(f"  - {basin_name} ({basin_id})...", end=" ")

            kb = rag.basins.get(basin_id)
            if not kb or not kb.documents:
                print("无文档")
                continue

            docs_to_insert = []
            for doc in kb.documents:
                # 获取向量
                embedding = kb.embeddings.embed_query(doc.page_content)

                doc_obj = KnowledgeDocument(
                    basin_id=basin_id,
                    content=doc.page_content,
                    source=doc.metadata.get("source", ""),
                    chunk_id=doc.metadata.get("chunk_id", 0),
                    embedding=embedding,
                )
                docs_to_insert.append(doc_obj)

            if docs_to_insert:
                db.bulk_save_objects(docs_to_insert)
                db.commit()
                total_docs += len(docs_to_insert)
                print(f"✓ {len(docs_to_insert)} 个文档片段")

        print(f"\n  总计: {total_docs} 个文档片段")

    except Exception as e:
        print(f"  ✗ 向量迁移失败: {e}")
        db.rollback()
    finally:
        db.close()


def create_views():
    """创建统一查询视图"""
    print("\n=== 创建视图 ===")

    with engine.connect() as conn:
        try:
            # 洪水事件总览视图
            conn.execute(text("""
                CREATE OR REPLACE VIEW v_all_flood_events AS
                SELECT fem.*, bm.basin_name, bm.basin_type
                FROM flood_event_metadata fem
                JOIN basin_metadata bm ON fem.basin_id = bm.basin_id
            """))

            # 站点总览视图
            conn.execute(text("""
                CREATE OR REPLACE VIEW v_all_stations AS
                SELECT sm.*, bm.basin_name, bm.basin_type
                FROM station_metadata sm
                JOIN basin_metadata bm ON sm.basin_id = bm.basin_id
            """))

            # 数据字典总览视图
            conn.execute(text("""
                CREATE OR REPLACE VIEW v_all_data_dict AS
                SELECT rdd.*, bm.basin_name, sm.name_cn as station_name
                FROM rainfall_data_dict rdd
                JOIN basin_metadata bm ON rdd.basin_id = bm.basin_id
                LEFT JOIN station_metadata sm ON rdd.station_id = sm.station_id
            """))

            conn.commit()
            print("  ✓ 视图创建完成")

        except Exception as e:
            print(f"  ✗ 视图创建失败: {e}")


def create_indexes():
    """创建性能优化索引"""
    print("\n=== 创建索引 ===")

    with engine.connect() as conn:
        try:
            # pgvector IVFFlat索引需要先有数据才能训练
            # 检查knowledge_documents表是否有数据
            result = conn.execute(text("SELECT COUNT(*) FROM knowledge_documents"))
            count = result.scalar()

            if count > 0:
                print(f"  - 为 {count} 条知识库记录创建向量索引...")
                # IVFFlat索引：设置lists参数（聚类数），建议为rows/1000
                lists = max(10, count // 1000)
                conn.execute(text(f"""
                    CREATE INDEX IF NOT EXISTS idx_knowledge_embedding_ivfflat
                    ON knowledge_documents
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = {lists})
                """))
                print(f"    ✓ 向量索引创建完成 (lists={lists})")
            else:
                print("  ⚠ 知识库表为空，跳过向量索引创建")

            conn.commit()

        except Exception as e:
            print(f"  ✗ 索引创建失败: {e}")


def main():
    start_time = time.time()
    print("=" * 60)
    print("SQLite → PostgreSQL + pgvector 数据迁移")
    print("=" * 60)

    # 1. 初始化 PostgreSQL
    print("\n[1/7] 初始化 PostgreSQL...")
    with engine.connect() as conn:
        if init_pgvector(conn):
            print("  ✓ pgvector 扩展已启用")
        else:
            print("  ⚠ pgvector 扩展启用失败，向量功能将不可用")

    # 2. 创建所有表
    print("\n[2/7] 创建表结构...")
    try:
        Base.metadata.create_all(engine)
        print("  ✓ 表结构创建完成")
    except Exception as e:
        print(f"  ✗ 表结构创建失败: {e}")
        return

    # 3. 迁移元数据
    print("\n[3/7] 迁移元数据...")
    migrate_metadata()

    # 4. 迁移时序数据
    print("\n[4/7] 迁移时序数据...")
    migrate_flood_timeseries()

    # 5. 迁移知识库向量
    print("\n[5/7] 迁移知识库向量...")
    migrate_knowledge_vectors()

    # 6. 创建视图
    print("\n[6/7] 创建视图...")
    create_views()

    # 7. 创建索引
    print("\n[7/7] 创建索引...")
    create_indexes()

    # 统计
    print("\n" + "=" * 60)
    print("迁移完成统计")
    print("=" * 60)

    db = SessionLocal()
    try:
        basin_count = db.query(BasinMetadata).count()
        station_count = db.query(StationMetadata).count()
        event_count = db.query(FloodEventMetadata).count()
        doc_count = db.query(KnowledgeDocument).count()

        print(f"  - 流域数: {basin_count}")
        print(f"  - 站点数: {station_count}")
        print(f"  - 洪水场次: {event_count}")
        print(f"  - 知识库文档: {doc_count}")
        print(f"  - 耗时: {time.time() - start_time:.2f} 秒")
    finally:
        db.close()

    print("\n下一步:")
    print("  1. 更新 .env 文件中的数据库配置")
    print("  2. 修改 agent/tools.py 和 knowledge/rag_engine.py 使用 PostgreSQL")
    print("  3. 启动服务并测试查询功能")


if __name__ == "__main__":
    main()
