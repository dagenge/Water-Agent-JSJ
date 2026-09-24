"""Prometheus 指标导出 HTTP 服务器

启动独立的 HTTP 服务器，暴露 /metrics 端点供 Prometheus 抓取。
默认端口: 8000

使用方式:
    python monitoring/exporter.py
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from http.server import HTTPServer, BaseHTTPRequestHandler
from prometheus_client import generate_latest, REGISTRY
import logging

# 导入共享 metrics 读取器
from monitoring.shared_metrics import read_metrics

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

logger = logging.getLogger(__name__)


class MetricsHandler(BaseHTTPRequestHandler):
    """处理 Prometheus 指标请求"""

    def do_GET(self):
        if self.path == '/metrics':
            # 从共享文件读取 metrics（由 Streamlit 进程写入）
            metrics_text = read_metrics()

            # 如果文件为空，回退到本进程的 REGISTRY（仅包含基础 Python metrics）
            if not metrics_text:
                metrics_text = generate_latest(REGISTRY).decode('utf-8')

            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; version=0.0.4; charset=utf-8')
            self.end_headers()
            self.wfile.write(metrics_text.encode('utf-8'))
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')

    def log_message(self, format, *args):
        """抑制默认访问日志"""
        pass


def start_exporter(port: int = 8000):
    """启动 Prometheus 指标导出服务器"""
    server = HTTPServer(('0.0.0.0', port), MetricsHandler)
    logger.info(f"Prometheus exporter 启动成功，监听端口: {port}")
    logger.info(f"指标端点: http://0.0.0.0:{port}/metrics")
    logger.info(f"健康检查: http://0.0.0.0:{port}/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Prometheus exporter 已停止")
        server.shutdown()


if __name__ == "__main__":
    start_exporter()
