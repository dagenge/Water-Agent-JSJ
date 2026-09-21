"""Water Agent 一键启动脚本"""
import subprocess
import time
import webbrowser
import os
import sys

def main():
    print("=" * 60)
    print("🌊 金沙江流域水文智能 Agent")
    print("=" * 60)

    # 设置环境
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"

    print("\n🚀 [1/3] 启动后端服务...")
    backend = subprocess.Popen(
        [sys.executable, "backend/server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    )

    time.sleep(3)
    print("✅ 后端服务已启动 (http://localhost:8765)")

    print("\n🚀 [2/3] 启动前端界面...")
    frontend = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run",
         "frontend/streamlit_app.py",
         "--server.port", "8501",
         "--server.headless", "true"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    )

    time.sleep(6)
    print("✅ 前端界面已启动 (http://localhost:8501)")

    print("\n🚀 [3/3] 打开浏览器...")
    webbrowser.open("http://localhost:8501")

    print("\n" + "=" * 60)
    print("✨ Water Agent 已成功启动！")
    print("📱 访问地址: http://localhost:8501")
    print("⚠️  关闭此窗口将停止 Agent 服务")
    print("=" * 60)

    try:
        # 保持运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 正在关闭服务...")
        backend.terminate()
        frontend.terminate()
        print("👋 Water Agent 已关闭")

if __name__ == "__main__":
    main()
