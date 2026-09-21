"""SQLite 迁移到 PostgreSQL 脚本"""

import os
import sys
import sqlite3
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import pandas as pd

# PostgreSQL 连接配置
PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT = os.getenv("POSTGRES_PORT", "5432")
PG_DB = os.getenv("POSTGRES_DB", "water_agent")
PG_USER = os.getenv("POSTGRES_USER", "postgres")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "admin123")

DATABASE_URL = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"

# SQLite 数据库路径
SQLITE_DB_JSJ = r"H:\Work\项目经历\Project_JSJ_Agent\data\database\jsj_agent.db"
SQLITE_DB_AGENT = r"H:\Work\项目经历\Project_Agent\data\database\water_agent.db"


def check_postgres_connection():
    """检查 PostgreSQL 连接"""
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ PostgreSQL 连接成功: {version}")
            return engine
    except Exception as e:
        print(f"❌ PostgreSQL 连接失败: {e}")
        sys.exit(1)


def create_tables(engine):
    """创建 PostgreSQL 表结构"""
    print("\n创建表结构...")

    sql = """
    -- 启用 pgvector 扩展
    CREATE EXTENSION IF NOT EXISTS vector;

    -- 流域元数据
    CREATE TABLE IF NOT EXISTS basin_metadata (
        basin_id VARCHAR(20) PRIMARY KEY,
        basin_name VARCHAR(100) NOT NULL,
        province VARCHAR(50) DEFAULT '广东省',
        basin_type VARCHAR(50),
        area_km2 FLOAT,
        description TEXT
    );

    -- 站点元数据
    CREATE TABLE IF NOT EXISTS station_metadata (
        station_id VARCHAR(50) PRIMARY KEY,
        basin_id VARCHAR(20) REFERENCES basin_metadata(basin_id),
        sid VARCHAR(20) NOT NULL,
        name_cn VARCHAR(100),
        name_en VARCHAR(100),
        x_coord FLOAT,
        y_coord FLOAT,
        lon FLOAT,
        lat FLOAT
    );
    CREATE INDEX IF NOT EXISTS idx_station_basin ON station_metadata(basin_id);

    -- 洪水场次元数据
    CREATE TABLE IF NOT EXISTS flood_event_metadata (
        event_id VARCHAR(100) PRIMARY KEY,
        basin_id VARCHAR(20) REFERENCES basin_metadata(basin_id),
        event_code VARCHAR(50) NOT NULL,
        event_name VARCHAR(200),
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        timesteps INTEGER
    );
    CREATE INDEX IF NOT EXISTS idx_flood_basin ON flood_event_metadata(basin_id);
    CREATE INDEX IF NOT EXISTS idx_flood_code ON flood_event_metadata(event_code);

    -- 雨量数据字典
    CREATE TABLE IF NOT EXISTS rainfall_data_dict (
        id SERIAL PRIMARY KEY,
        basin_id VARCHAR(20) NOT NULL,
        event_code VARCHAR(50) NOT NULL,
        column_index INTEGER NOT NULL,
        column_name VARCHAR(100) NOT NULL,
        station_id VARCHAR(50) REFERENCES station_metadata(station_id),
        data_type VARCHAR(20) DEFAULT 'rainfall',
        unit VARCHAR(20) DEFAULT 'mm'
    );
    CREATE INDEX IF NOT EXISTS idx_data_dict_basin_event ON rainfall_data_dict(basin_id, event_code);

    -- 知识库文档（pgvector）
    CREATE TABLE IF NOT EXISTS knowledge_documents (
        id SERIAL PRIMARY KEY,
        basin_id VARCHAR(20) REFERENCES basin_metadata(basin_id),
        content TEXT NOT NULL,
        source VARCHAR(200),
        chunk_id INTEGER,
        embedding vector(384),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_knowledge_basin ON knowledge_documents(basin_id);

    -- Agent 会话记录
    CREATE TABLE IF NOT EXISTS agent_sessions (
        id SERIAL PRIMARY KEY,
        session_id VARCHAR(100) UNIQUE NOT NULL,
        user_input TEXT NOT NULL,
        intent_type VARCHAR(50),
        intent_details JSONB,
        output TEXT,
        tool_calls JSONB,
        execution_time_ms FLOAT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_session_id ON agent_sessions(session_id);
    CREATE INDEX IF NOT EXISTS idx_session_created ON agent_sessions(created_at);
    """

    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    print("✅ 表结构创建完成")


def migrate_sqlite_data(engine, sqlite_path, basin_prefix):
    """从 SQLite 迁移数据到 PostgreSQL"""
    if not os.path.exists(sqlite_path):
        print(f"⚠️  SQLite 文件不存在: {sqlite_path}")
        return

    print(f"\n迁移数据: {sqlite_path} (流域前缀: {basin_prefix})")

    sqlite_conn = sqlite3.connect(sqlite_path)

    # 获取所有表
    tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", sqlite_conn)
    print(f"发现 {len(tables)} 个表: {', '.join(tables['name'].tolist())}")

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        for table_name in tables['name']:
            if table_name.startswith('sqlite_'):
                continue

            print(f"  迁移表: {table_name}")
            df = pd.read_sql(f"SELECT * FROM {table_name}", sqlite_conn)

            if len(df) > 0:
                # 使用 pandas to_sql 批量插入
                df.to_sql(table_name, engine, if_exists='append', index=False, method='multi')
                print(f"    ✅ 迁移 {len(df)} 条记录")
            else:
                print(f"    ⚠️  表为空")

        session.commit()
        print(f"✅ {sqlite_path} 迁移完成")

    except Exception as e:
        session.rollback()
        print(f"❌ 迁移失败: {e}")
    finally:
        session.close()
        sqlite_conn.close()


def main():
    """主函数"""
    print("=" * 60)
    print("SQLite → PostgreSQL 迁移工具")
    print("=" * 60)

    # 检查连接
    engine = check_postgres_connection()

    # 创建表结构
    create_tables(engine)

    # 迁移 JSJ_Agent 数据（btpzh/dqh 流域）
    migrate_sqlite_data(engine, SQLITE_DB_JSJ, "jsj")

    # 迁移 Project_Agent 数据（BJH/BPZ/HZK/JS/TJ 流域）
    migrate_sqlite_data(engine, SQLITE_DB_AGENT, "agent")

    print("\n" + "=" * 60)
    print("✅ 迁移完成！")
    print("=" * 60)

    # 验证数据
    print("\n数据统计:")
    with engine.connect() as conn:
        for table in ["basin_metadata", "station_metadata", "flood_event_metadata"]:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.fetchone()[0]
            print(f"  {table}: {count} 条")


if __name__ == "__main__":
    main()

