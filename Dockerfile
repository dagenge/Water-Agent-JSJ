# 基础镜像：Python 3.9
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 暴露端口
EXPOSE 8765 8501

# 启动命令
CMD ["bash", "-c", "python backend/server.py & streamlit run frontend/streamlit_app.py --server.port 8501 --server.address 0.0.0.0"]
