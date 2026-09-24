"""共享指标注册表，供多进程访问

问题：Prometheus metrics 注册在 REGISTRY 中，但 Streamlit 和 Exporter 是独立进程，
     executor.py 中记录的 metrics 只存在于 Streamlit 进程的 REGISTRY，
     Exporter 进程无法读取。

解决方案：使用文件系统作为进程间共享存储，定期将 metrics 写入文件，Exporter 读取并暴露。

文件格式：Prometheus text format
存储路径：data/metrics/current_metrics.txt
"""

import os
import threading
import time
from pathlib import Path

# metrics 文件路径
METRICS_FILE = Path(__file__).parent.parent / "data" / "metrics" / "current_metrics.txt"
METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)

# 全局锁
_file_lock = threading.Lock()


def write_metrics(metrics_text: str):
    """将 metrics 文本写入共享文件"""
    with _file_lock:
        METRICS_FILE.write_text(metrics_text, encoding="utf-8")


def read_metrics() -> str:
    """从共享文件读取 metrics 文本"""
    with _file_lock:
        if METRICS_FILE.exists():
            return METRICS_FILE.read_text(encoding="utf-8")
        return ""


class MetricsWriter:
    """后台线程定期将 REGISTRY 导出到文件"""

    def __init__(self, interval: float = 2.0):
        self.interval = interval
        self.running = False
        self.thread = None

    def start(self):
        """启动后台写入线程"""
        if self.running:
            return

        from prometheus_client import REGISTRY, generate_latest

        self.running = True

        def _worker():
            while self.running:
                try:
                    metrics_text = generate_latest(REGISTRY).decode("utf-8")
                    write_metrics(metrics_text)
                except Exception:
                    pass
                time.sleep(self.interval)

        self.thread = threading.Thread(target=_worker, daemon=True)
        self.thread.start()

    def stop(self):
        """停止后台写入"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)


# 全局实例
_metrics_writer = MetricsWriter()


def start_metrics_writer():
    """启动 metrics 写入器（在 Streamlit 进程中调用）"""
    _metrics_writer.start()
