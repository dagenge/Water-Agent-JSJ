"""Prometheus 指标导出 HTTP 服务器

启动独立的 HTTP 服务器，暴露 /metrics 端点供 Prometheus 抓取。
默认端口: 8000

使用方式:
    python monitoring/exporter.py
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from monitoring.prometheus_metrics import metrics_collector
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

logger = logging.getLogger(__name__)


class MetricsHandler(BaseHTTPRequestHandler):
    """处理 Prometheus 指标请求"""

    def do_GET(self):
        if self.path == '/metrics':
            metrics_data = metrics_collector.get_metrics()
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; version=0.0.4; charset=utf-8')
            self.end_headers()
            self.wfile.write(metrics_data)
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
