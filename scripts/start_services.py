"""启动脚本：同时运行 Prometheus Exporter 和 Streamlit

使用方式：
    python scripts/start_services.py
"""

import os
import sys
import subprocess
import time
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_port_available(port: int) -> bool:
    """检查端口是否可用"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) != 0


def main():
    print("=" * 60)
    print("流域水文智能 Agent - 服务启动")
    print("=" * 60)

    # 检查环境变量
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key or api_key == "your-api-key-here":
        print("\n❌ 错误: DEEPSEEK_API_KEY 未配置")
        print("\n请在 .env 文件中设置 DEEPSEEK_API_KEY")
        print("示例: DEEPSEEK_API_KEY=sk-your-actual-key")
        return 1

    # 检查数据库配置
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    print(f"\n📊 数据库配置: {db_host}:{db_port}")

    # 检查端口占用
    ports = {
        8000: "Prometheus Exporter",
        8501: "Streamlit"
    }

    for port, service in ports.items():
        if not check_port_available(port):
            print(f"\n⚠️  警告: 端口 {port} ({service}) 已被占用")
            print(f"   请先停止占用该端口的进程，或修改配置使用其他端口")

    print("\n🚀 启动服务...")

    # 启动 Prometheus Exporter
    print("\n1. 启动 Prometheus Exporter (端口 8000)...")
    exporter_process = subprocess.Popen(
        [sys.executable, "monitoring/exporter.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(2)  # 等待启动

    if exporter_process.poll() is not None:
        print("   ❌ Prometheus Exporter 启动失败")
        _, stderr = exporter_process.communicate()
        print(f"   错误: {stderr.decode('utf-8', errors='ignore')}")
        return 1

    print("   ✅ Prometheus Exporter 已启动")
    print(f"   指标端点: http://localhost:8000/metrics")

    # 启动 Streamlit
    print("\n2. 启动 Streamlit (端口 8501)...")
    streamlit_process = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run",
            "streamlit_demo.py",
            "--server.port=8501",
            "--server.address=0.0.0.0"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(3)  # 等待启动

    if streamlit_process.poll() is not None:
        print("   ❌ Streamlit 启动失败")
        exporter_process.terminate()
        _, stderr = streamlit_process.communicate()
        print(f"   错误: {stderr.decode('utf-8', errors='ignore')}")
        return 1

    print("   ✅ Streamlit 已启动")

    print("\n" + "=" * 60)
    print("✅ 所有服务启动成功！")
    print("=" * 60)
    print("\n访问地址:")
    print("  🌐 Streamlit UI:        http://localhost:8501")
    print("  📊 Prometheus Metrics:  http://localhost:8000/metrics")
    print("  💚 Health Check:        http://localhost:8000/health")
    print("\n按 Ctrl+C 停止所有服务")
    print("=" * 60)

    try:
        # 保持运行直到用户中断
        while True:
            time.sleep(1)
            # 检查进程是否意外退出
            if exporter_process.poll() is not None:
                print("\n⚠️  Prometheus Exporter 意外退出")
                break
            if streamlit_process.poll() is not None:
                print("\n⚠️  Streamlit 意外退出")
                break
    except KeyboardInterrupt:
        print("\n\n正在停止服务...")
        exporter_process.terminate()
        streamlit_process.terminate()
        exporter_process.wait()
        streamlit_process.wait()
        print("✅ 所有服务已停止")

    return 0


if __name__ == "__main__":
    sys.exit(main())
