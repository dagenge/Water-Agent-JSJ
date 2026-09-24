"""Prometheus监控指标导出器

监控指标：
1. agent_query_total: 总查询数（按intent_type分类）
2. agent_query_duration_seconds: 查询响应时间分布
3. agent_tool_call_total: 工具调用次数（按tool_name分类）
4. agent_tool_call_duration_seconds: 工具调用耗时
5. agent_tool_call_success_rate: 工具调用成功率
6. agent_consistency_check_corrections: 一致性校验修正次数
7. agent_feedback_total: 用户反馈数（按feedback_type分类）
8. agent_badcase_total: Badcase总数（按category分类）
"""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
from prometheus_client.core import CollectorRegistry
import time
from typing import Optional

# 使用全局默认 REGISTRY，确保所有进程共享同一套metrics
registry = REGISTRY

# ====== 查询相关指标 ======
query_total = Counter(
    'agent_query_total',
    'Total number of agent queries',
    ['intent_type', 'version'],
    registry=registry
)

query_duration = Histogram(
    'agent_query_duration_seconds',
    'Agent query duration in seconds',
    ['intent_type', 'version'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
    registry=registry
)

query_success_total = Counter(
    'agent_query_success_total',
    'Total number of successful queries',
    ['intent_type', 'version'],
    registry=registry
)

query_error_total = Counter(
    'agent_query_error_total',
    'Total number of failed queries',
    ['intent_type', 'error_type', 'version'],
    registry=registry
)

# ====== 工具调用指标 ======
tool_call_total = Counter(
    'agent_tool_call_total',
    'Total number of tool calls',
    ['tool_name', 'version'],
    registry=registry
)

tool_call_duration = Histogram(
    'agent_tool_call_duration_seconds',
    'Tool call duration in seconds',
    ['tool_name'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
    registry=registry
)

tool_call_success_total = Counter(
    'agent_tool_call_success_total',
    'Total number of successful tool calls',
    ['tool_name'],
    registry=registry
)

tool_call_error_total = Counter(
    'agent_tool_call_error_total',
    'Total number of failed tool calls',
    ['tool_name', 'error_type'],
    registry=registry
)

# ====== 一致性校验指标 ======
consistency_check_corrections = Counter(
    'agent_consistency_check_corrections',
    'Number of corrections made by consistency check',
    ['intent_type'],
    registry=registry
)

consistency_check_failures = Counter(
    'agent_consistency_check_failures',
    'Number of consistency check failures',
    ['failure_type'],
    registry=registry
)

# ====== 用户反馈指标 ======
feedback_total = Counter(
    'agent_feedback_total',
    'Total user feedback count',
    ['feedback_type', 'rating'],
    registry=registry
)

badcase_total = Counter(
    'agent_badcase_total',
    'Total badcase count',
    ['category'],
    registry=registry
)

# ====== 实时状态指标 ======
active_sessions = Gauge(
    'agent_active_sessions',
    'Number of currently active sessions',
    registry=registry
)

avg_tool_calls_per_query = Gauge(
    'agent_avg_tool_calls_per_query',
    'Average number of tool calls per query',
    registry=registry
)


class MetricsCollector:
    """监控指标收集器"""

    def __init__(self):
        self.version = "v1.0.0"  # 当前版本

    def record_query_start(self, intent_type: str, version: Optional[str] = None):
        """记录查询开始"""
        v = version or self.version
        query_total.labels(intent_type=intent_type, version=v).inc()
        active_sessions.inc()

    def record_query_end(self, intent_type: str, duration_ms: float, success: bool = True,
                        error_type: Optional[str] = None, version: Optional[str] = None):
        """记录查询结束"""
        v = version or self.version
        duration_s = duration_ms / 1000.0

        query_duration.labels(intent_type=intent_type, version=v).observe(duration_s)

        if success:
            query_success_total.labels(intent_type=intent_type, version=v).inc()
        else:
            query_error_total.labels(
                intent_type=intent_type,
                error_type=error_type or "unknown",
                version=v
            ).inc()

        active_sessions.dec()

    def record_tool_call(self, tool_name: str, duration_ms: float, success: bool = True,
                        error_type: Optional[str] = None, version: Optional[str] = None):
        """记录工具调用"""
        v = version or self.version
        duration_s = duration_ms / 1000.0

        tool_call_total.labels(tool_name=tool_name, version=v).inc()
        tool_call_duration.labels(tool_name=tool_name).observe(duration_s)

        if success:
            tool_call_success_total.labels(tool_name=tool_name).inc()
        else:
            tool_call_error_total.labels(
                tool_name=tool_name,
                error_type=error_type or "unknown"
            ).inc()

    def record_consistency_check(self, intent_type: str, corrected: bool,
                                 failure_type: Optional[str] = None):
        """记录一致性校验"""
        if corrected:
            consistency_check_corrections.labels(intent_type=intent_type).inc()

        if failure_type:
            consistency_check_failures.labels(failure_type=failure_type).inc()

    def record_feedback(self, feedback_type: str, rating: Optional[int] = None,
                       is_badcase: bool = False, badcase_category: Optional[str] = None):
        """记录用户反馈"""
        rating_str = str(rating) if rating else "none"
        feedback_total.labels(feedback_type=feedback_type, rating=rating_str).inc()

        if is_badcase and badcase_category:
            badcase_total.labels(category=badcase_category).inc()

    def update_avg_tool_calls(self, avg_count: float):
        """更新平均工具调用次数"""
        avg_tool_calls_per_query.set(avg_count)

    def get_metrics(self) -> bytes:
        """获取Prometheus格式的指标"""
        return generate_latest(registry)


# 全局实例
metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """获取全局指标收集器"""
    return metrics_collector
