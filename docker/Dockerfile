FROM python:3.9-slim

LABEL maintainer="Water Agent Team"
LABEL description="流域水文智能 Agent - Docker 镜像"

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY agent/ ./agent/
COPY config/ ./config/
COPY knowledge/ ./knowledge/
COPY monitoring/ ./monitoring/
COPY streamlit_demo.py .
COPY docker/docker-entrypoint.sh /docker-entrypoint.sh

# 设置执行权限
RUN chmod +x /docker-entrypoint.sh

# 暴露端口
EXPOSE 8501 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动脚本
ENTRYPOINT ["/docker-entrypoint.sh"]
