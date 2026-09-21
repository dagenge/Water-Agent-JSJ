"""初始化 PostgreSQL 数据库"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from config import init_database, engine
from sqlalchemy import text

def create_database():
    """创建数据库（如果不存在）"""
    from sqlalchemy import create_engine
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
    DB_NAME = os.getenv("DB_NAME", "water_agent")
    
    # 连接到 postgres 默认数据库
    admin_url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    
    with admin_engine.connect() as conn:
        # 检查数据库是否存在
        result = conn.execute(text(
            f"SELECT 1 FROM pg_database WHERE datname='{DB_NAME}'"
        ))
        exists = result.scalar()
        
        if not exists:
            conn.execute(text(f"CREATE DATABASE {DB_NAME}"))
            print(f"[OK] Database {DB_NAME} created")
        else:
            print(f"[INFO] Database {DB_NAME} already exists")
    
    admin_engine.dispose()

def install_pgvector():
    """安装 pgvector 扩展"""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
        print("[OK] pgvector extension installed")

if __name__ == "__main__":
    print("=" * 50)
    print("PostgreSQL Database Initialization")
    print("=" * 50)

    # 1. 创建数据库
    create_database()

    # 2. 安装 pgvector 扩展
    try:
        install_pgvector()
    except Exception as e:
        print(f"[WARN] pgvector extension failed: {e}")
        print("   Manual: CREATE EXTENSION vector;")

    # 3. 创建表
    init_database()

    print("=" * 50)
    print("[OK] Database initialization completed")
    print("=" * 50)
