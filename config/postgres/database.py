"""PostgreSQL数据库配置 + pgvector向量存储

相比SQLite的改进：
1. 支持高并发读写（连接池）
2. pgvector扩展实现向量和元数据统一存储
3. 事务隔离保证数据一致性
4. 生产级备份和恢复能力
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool

# PostgreSQL 配置
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "water_agent")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# SQLAlchemy Engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,              # 常驻连接数
    max_overflow=20,           # 峰值时额外连接数
    pool_pre_ping=True,        # 连接前检测有效性
    pool_recycle=3600,         # 1小时回收连接
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: 获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_pgvector(conn):
    """初始化 pgvector 扩展"""
    try:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.commit()
        return True
    except Exception as e:
        print(f"⚠ pgvector 初始化失败: {e}")
        print("  请手动执行: CREATE EXTENSION vector;")
        return False
