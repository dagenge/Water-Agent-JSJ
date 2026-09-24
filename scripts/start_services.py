"""启动脚本：同时运行 Prometheus Exporter 和 Streamlit

使用方式：
    python scripts/start_services.py
"""

import os
import sys
import subprocess
import time
from pathlib import Path
from dotenv import load_dotenv

# 设置控制台编码为 UTF-8
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载 .env 文件
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(env_path)
    print(f"Loaded .env from: {env_path}")


def check_port_available(port: int) -> bool:
    """检查端口是否可用"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) != 0


def kill_process_on_port(port: int):
    """杀死占用指定端口的进程"""
    try:
        # 查找占用端口的进程
        result = subprocess.run(
            f'netstat -ano | findstr ":{port}"',
            shell=True,
            capture_output=True,
            text=True
        )
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if 'LISTENING' in line:
                    parts = line.split()
                    pid = parts[-1]
                    # 杀死进程
                    subprocess.run(f'taskkill /F /PID {pid} /T', shell=True, capture_output=True)
                    print(f"   已终止占用端口 {port} 的进程 (PID: {pid})")
                    time.sleep(1)
                    return True
    except Exception as e:
        print(f"   清理端口 {port} 失败: {e}")
    return False


def main():
    print("=" * 60)
    print("流域水文智能 Agent - 服务启动")
    print("=" * 60)

    # 检查环境变量
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key or api_key == "your-api-key-here":
        print("\n[错误] DEEPSEEK_API_KEY 未配置")
        print("\n请在 .env 文件中设置 DEEPSEEK_API_KEY")
        print("示例: DEEPSEEK_API_KEY=sk-your-actual-key")
        return 1

    # 检查数据库配置
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    print(f"\n[数据库配置] {db_host}:{db_port}")

    # 检查并清理端口占用
    ports = {
        8000: "Prometheus Exporter",
        8501: "Streamlit"
    }

    for port, service in ports.items():
        if not check_port_available(port):
            print(f"\n[警告] 端口 {port} ({service}) 已被占用，正在清理...")
            kill_process_on_port(port)

    print("\n[启动服务]...")

    # 启动 Prometheus Exporter（后台运行）
    print("\n1. 启动 Prometheus Exporter (端口 8000)...")
    exporter_process = subprocess.Popen(
        [sys.executable, "monitoring/exporter.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(project_root),
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    )
    time.sleep(2)  # 等待启动

    # 验证端口是否启动成功
    if check_port_available(8000):
        print("   [错误] Prometheus Exporter 启动失败")
        exporter_process.terminate()
        return 1

    print("   [成功] Prometheus Exporter 已启动")
    print(f"   指标端点: http://localhost:8000/metrics")

    # 启动 Streamlit（后台运行）
    print("\n2. 启动 Streamlit 前端 (端口 8501)...")
    streamlit_process = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run",
            "frontend/streamlit_app.py",
            "--server.port=8501",
            "--server.address=0.0.0.0"
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(project_root),
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    )
    time.sleep(3)  # 等待启动

    # 验证端口是否启动成功
    if check_port_available(8501):
        print("   [错误] Streamlit 启动失败")
        exporter_process.terminate()
        streamlit_process.terminate()
        return 1

    print("   [成功] Streamlit 前端已启动")

    print("\n" + "=" * 60)
    print("[成功] 所有服务启动成功！")
    print("=" * 60)
    print("\n访问地址:")
    print("  Streamlit UI:        http://localhost:8501")
    print("  Prometheus Metrics:  http://localhost:8000/metrics")
    print("  Health Check:        http://localhost:8000/health")
    print("\n提示：服务已在后台运行，关闭此窗口不影响服务")
    print("      如需停止服务，请使用任务管理器终止进程")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
