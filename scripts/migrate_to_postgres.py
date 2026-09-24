"""SQLite 数据迁移到 PostgreSQL

将现有 SQLite 数据库中的对话历史和用户反馈迁移到 PostgreSQL。
已有的元数据（basin/station/flood/observation）在 PostgreSQL 中通过初始化脚本加载。

使用方式：
    python scripts/migrate_to_postgres.py
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
from datetime import datetime
from config.database import SessionLocal
from config.models import ConversationHistory, UserFeedback


def migrate_conversation_history(sqlite_path: str):
    """迁移对话历史"""
    if not os.path.exists(sqlite_path):
        print(f"SQLite 文件不存在: {sqlite_path}")
        return 0

    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()

    # 检查表是否存在
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='conversation_history'
    """)
    if not cursor.fetchone():
        print("SQLite 中未找到 conversation_history 表")
        conn.close()
        return 0

    # 读取 SQLite 数据
    cursor.execute("SELECT * FROM conversation_history")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("conversation_history 表为空")
        return 0

    # 写入 PostgreSQL
    session = SessionLocal()
    migrated = 0
    try:
        for row in rows:
            # SQLite 表结构: id, session_id, user_input, agent_output, intent, created_at
            record = ConversationHistory(
                session_id=row[1],
                user_input=row[2],
                agent_output=row[3],
                intent=row[4],
                created_at=datetime.fromisoformat(row[5]) if row[5] else datetime.now()
            )
            session.add(record)
            migrated += 1

        session.commit()
        print(f"✅ 成功迁移 {migrated} 条对话记录")
    except Exception as e:
        session.rollback()
        print(f"❌ 迁移对话记录失败: {e}")
        migrated = 0
    finally:
        session.close()

    return migrated


def migrate_user_feedback(sqlite_path: str):
    """迁移用户反馈"""
    if not os.path.exists(sqlite_path):
        return 0

    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='user_feedback'
    """)
    if not cursor.fetchone():
        print("SQLite 中未找到 user_feedback 表")
        conn.close()
        return 0

    cursor.execute("SELECT * FROM user_feedback")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("user_feedback 表为空")
        return 0

    session = SessionLocal()
    migrated = 0
    try:
        for row in rows:
            # SQLite 表结构: id, session_id, query, rating, comment, created_at
            record = UserFeedback(
                session_id=row[1],
                query=row[2],
                rating=row[3],
                comment=row[4] if len(row) > 4 else None,
                created_at=datetime.fromisoformat(row[5]) if len(row) > 5 and row[5] else datetime.now()
            )
            session.add(record)
            migrated += 1

        session.commit()
        print(f"✅ 成功迁移 {migrated} 条反馈记录")
    except Exception as e:
        session.rollback()
        print(f"❌ 迁移反馈记录失败: {e}")
        migrated = 0
    finally:
        session.close()

    return migrated


def main():
    print("=" * 60)
    print("SQLite → PostgreSQL 数据迁移工具")
    print("=" * 60)

    # 查找 SQLite 数据库文件
    possible_paths = [
        "data/database/jsj_agent.db",
        "data/agent.db",
        "data/water_agent.db",
        "../data/agent.db",
    ]

    sqlite_path = None
    for path in possible_paths:
        if os.path.exists(path):
            sqlite_path = path
            break

    if not sqlite_path:
        print("⚠️  未找到 SQLite 数据库文件，可能的路径：")
        for p in possible_paths:
            print(f"   - {p}")
        print("\n如需迁移，请手动指定 SQLite 文件路径。")
        return

    print(f"\n📁 SQLite 数据库: {sqlite_path}")
    print(f"🎯 目标 PostgreSQL: {os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}\n")

    # 执行迁移
    conv_count = migrate_conversation_history(sqlite_path)
    feedback_count = migrate_user_feedback(sqlite_path)

    print("\n" + "=" * 60)
    print(f"迁移完成！")
    print(f"  对话记录: {conv_count} 条")
    print(f"  用户反馈: {feedback_count} 条")
    print("=" * 60)


if __name__ == "__main__":
    main()
