#!/bin/bash
set -e

echo "=========================================="
echo "流域水文智能 Agent - Docker 启动"
echo "=========================================="

# 等待 PostgreSQL 就绪
echo "等待 PostgreSQL 就绪..."
until nc -z postgres 5432; do
    echo "  PostgreSQL 未就绪，等待中..."
    sleep 2
done
echo "✅ PostgreSQL 已就绪"

# 初始化数据库表结构
echo "初始化数据库表结构..."
python -c "
from config.models import Base
from config.database import engine
Base.metadata.create_all(bind=engine)
print('✅ 数据库表结构已创建')
"

# 启动 Prometheus Exporter (后台运行)
echo "启动 Prometheus Exporter (端口 8000)..."
python monitoring/exporter.py &
EXPORTER_PID=$!
echo "  PID: $EXPORTER_PID"

# 等待 Exporter 启动
sleep 3
if ! curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "⚠️  警告: Prometheus Exporter 健康检查失败"
fi

# 启动 Streamlit (前台运行)
echo "启动 Streamlit (端口 8501)..."
echo "=========================================="
exec streamlit run streamlit_demo.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.fileWatcherType=none
