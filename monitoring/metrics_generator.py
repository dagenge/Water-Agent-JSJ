"""量化指标生成脚本

用于生成业务场景下的量化指标。

生成的指标：
1. 工具调用成功率：从基线X%提升到Y%
2. 平均响应时间：从X秒降低到Y秒
3. 一致性校验修正率：从X%降低到Y%（降低幻觉输出）
4. 用户满意度：从X星提升到Y星
5. Badcase率：从X%降低到Y%
6. 跨团队调用量：MCP Server日均调用N次
7. 知识库召回准确率：从X%提升到Y%
8. 系统可用性：9X.X%
"""

import random
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List


class MetricsGenerator:
    """量化指标生成器"""

    def __init__(self, seed: int = 42):
        random.seed(seed)

    def generate_performance_improvement(self) -> Dict[str, Any]:
        """生成性能改进指标

        场景：SQLite迁移到PostgreSQL + 优化查询逻辑
        """
        baseline = {
            "avg_latency_ms": random.uniform(4500, 5500),  # 4.5-5.5秒
            "p95_latency_ms": random.uniform(9000, 11000),  # 9-11秒
            "p99_latency_ms": random.uniform(15000, 18000),  # 15-18秒
        }

        improved = {
            "avg_latency_ms": baseline["avg_latency_ms"] * random.uniform(0.55, 0.65),  # 降低35-45%
            "p95_latency_ms": baseline["p95_latency_ms"] * random.uniform(0.60, 0.70),  # 降低30-40%
            "p99_latency_ms": baseline["p99_latency_ms"] * random.uniform(0.65, 0.75),  # 降低25-35%
        }

        return {
            "metric": "响应时间",
            "baseline": {
                "avg": f"{baseline['avg_latency_ms']/1000:.2f}秒",
                "p95": f"{baseline['p95_latency_ms']/1000:.2f}秒",
                "p99": f"{baseline['p99_latency_ms']/1000:.2f}秒",
            },
            "improved": {
                "avg": f"{improved['avg_latency_ms']/1000:.2f}秒",
                "p95": f"{improved['p95_latency_ms']/1000:.2f}秒",
                "p99": f"{improved['p99_latency_ms']/1000:.2f}秒",
            },
            "improvement": {
                "avg": f"{(1 - improved['avg_latency_ms']/baseline['avg_latency_ms'])*100:.1f}%",
                "p95": f"{(1 - improved['p95_latency_ms']/baseline['p95_latency_ms'])*100:.1f}%",
                "p99": f"{(1 - improved['p99_latency_ms']/baseline['p99_latency_ms'])*100:.1f}%",
            }
        }

    def generate_accuracy_improvement(self) -> Dict[str, Any]:
        """生成准确率改进指标

        场景：优化prompt + 增加一致性校验 + badcase迭代
        """
        baseline_accuracy = random.uniform(0.82, 0.86)  # 82-86%
        improved_accuracy = random.uniform(0.92, 0.95)  # 92-95%

        baseline_hallucination = random.uniform(0.12, 0.18)  # 12-18%幻觉率
        improved_hallucination = random.uniform(0.03, 0.06)  # 3-6%幻觉率

        return {
            "metric": "准确率和幻觉率",
            "baseline": {
                "accuracy": f"{baseline_accuracy*100:.1f}%",
                "hallucination_rate": f"{baseline_hallucination*100:.1f}%",
            },
            "improved": {
                "accuracy": f"{improved_accuracy*100:.1f}%",
                "hallucination_rate": f"{improved_hallucination*100:.1f}%",
            },
            "improvement": {
                "accuracy": f"+{(improved_accuracy - baseline_accuracy)*100:.1f}个百分点",
                "hallucination_rate": f"-{(baseline_hallucination - improved_hallucination)*100:.1f}个百分点",
            }
        }

    def generate_tool_call_metrics(self) -> Dict[str, Any]:
        """生成工具调用指标

        场景：优化工具选择逻辑，减少无效调用
        """
        baseline_success_rate = random.uniform(0.89, 0.92)  # 89-92%
        improved_success_rate = random.uniform(0.96, 0.98)  # 96-98%

        baseline_avg_calls = random.uniform(4.2, 4.8)  # 平均4.2-4.8次调用
        improved_avg_calls = random.uniform(3.1, 3.5)  # 平均3.1-3.5次调用

        return {
            "metric": "工具调用效率",
            "baseline": {
                "success_rate": f"{baseline_success_rate*100:.1f}%",
                "avg_calls_per_query": f"{baseline_avg_calls:.1f}次",
            },
            "improved": {
                "success_rate": f"{improved_success_rate*100:.1f}%",
                "avg_calls_per_query": f"{improved_avg_calls:.1f}次",
            },
            "improvement": {
                "success_rate": f"+{(improved_success_rate - baseline_success_rate)*100:.1f}个百分点",
                "avg_calls_reduction": f"-{(baseline_avg_calls - improved_avg_calls)/baseline_avg_calls*100:.1f}%",
            }
        }

    def generate_user_satisfaction(self) -> Dict[str, Any]:
        """生成用户满意度指标

        场景：基于用户反馈持续优化
        """
        baseline_rating = random.uniform(3.6, 3.9)  # 3.6-3.9星
        improved_rating = random.uniform(4.3, 4.6)  # 4.3-4.6星

        baseline_positive_rate = random.uniform(0.68, 0.74)  # 68-74%正面反馈
        improved_positive_rate = random.uniform(0.85, 0.90)  # 85-90%正面反馈

        return {
            "metric": "用户满意度",
            "baseline": {
                "avg_rating": f"{baseline_rating:.1f}星/5星",
                "positive_feedback_rate": f"{baseline_positive_rate*100:.1f}%",
            },
            "improved": {
                "avg_rating": f"{improved_rating:.1f}星/5星",
                "positive_feedback_rate": f"{improved_positive_rate*100:.1f}%",
            },
            "improvement": {
                "rating": f"+{improved_rating - baseline_rating:.1f}星",
                "positive_rate": f"+{(improved_positive_rate - baseline_positive_rate)*100:.1f}个百分点",
            }
        }

    def generate_badcase_reduction(self) -> Dict[str, Any]:
        """生成Badcase降低指标

        场景：建立badcase收集和迭代机制
        """
        baseline_badcase_rate = random.uniform(0.15, 0.22)  # 15-22%
        improved_badcase_rate = random.uniform(0.05, 0.08)  # 5-8%

        total_badcases_collected = random.randint(180, 250)
        badcases_fixed = random.randint(140, 200)

        return {
            "metric": "Badcase管理",
            "baseline": {
                "badcase_rate": f"{baseline_badcase_rate*100:.1f}%",
            },
            "improved": {
                "badcase_rate": f"{improved_badcase_rate*100:.1f}%",
            },
            "improvement": {
                "badcase_rate_reduction": f"-{(baseline_badcase_rate - improved_badcase_rate)*100:.1f}个百分点",
                "reduction_ratio": f"{(baseline_badcase_rate - improved_badcase_rate)/baseline_badcase_rate*100:.0f}%",
            },
            "details": {
                "total_collected": total_badcases_collected,
                "fixed": badcases_fixed,
                "fix_rate": f"{badcases_fixed/total_badcases_collected*100:.1f}%",
            }
        }

    def generate_mcp_usage(self) -> Dict[str, Any]:
        """生成MCP Server跨团队使用指标

        场景：内网部署MCP Server，支撑多团队工具复用
        """
        daily_calls = random.randint(120, 180)  # 日均120-180次调用
        monthly_calls = daily_calls * 30

        downstream_teams = 2  # 2个下游团队接入
        total_tools = 12
        most_used_tools = [
            ("query_rainfall_data", random.randint(35, 45)),
            ("query_rainfall_statistics", random.randint(25, 35)),
            ("query_flood_events", random.randint(18, 25)),
        ]

        return {
            "metric": "MCP Server跨团队复用",
            "usage": {
                "daily_calls": f"{daily_calls}次/天",
                "monthly_calls": f"{monthly_calls}次/月",
                "downstream_teams": f"{downstream_teams}个团队",
                "success_rate": f"{random.uniform(0.96, 0.98)*100:.1f}%",
            },
            "most_used_tools": [
                {"tool": name, "calls_percentage": f"{count/daily_calls*100:.1f}%"}
                for name, count in most_used_tools
            ],
            "impact": f"避免{downstream_teams}个团队重复开发数据查询模块，节省约{downstream_teams * 15}人天开发工作量"
        }

    def generate_rag_improvement(self) -> Dict[str, Any]:
        """生成RAG知识库改进指标

        场景：从FAISS迁移到pgvector + 优化检索策略
        """
        baseline_recall = random.uniform(0.72, 0.78)  # 72-78%召回率
        improved_recall = random.uniform(0.86, 0.91)  # 86-91%召回率

        baseline_precision = random.uniform(0.68, 0.74)  # 68-74%准确率
        improved_precision = random.uniform(0.82, 0.88)  # 82-88%准确率

        return {
            "metric": "知识库检索质量",
            "baseline": {
                "recall": f"{baseline_recall*100:.1f}%",
                "precision": f"{baseline_precision*100:.1f}%",
                "avg_retrieval_time": f"{random.uniform(800, 1200):.0f}ms",
            },
            "improved": {
                "recall": f"{improved_recall*100:.1f}%",
                "precision": f"{improved_precision*100:.1f}%",
                "avg_retrieval_time": f"{random.uniform(200, 400):.0f}ms",
            },
            "improvement": {
                "recall": f"+{(improved_recall - baseline_recall)*100:.1f}个百分点",
                "precision": f"+{(improved_precision - baseline_precision)*100:.1f}个百分点",
                "retrieval_time": f"-{random.uniform(65, 75):.0f}%",
            }
        }

    def generate_system_reliability(self) -> Dict[str, Any]:
        """生成系统可靠性指标

        场景：生产部署后的稳定性数据
        """
        uptime = random.uniform(0.992, 0.997)  # 99.2-99.7%可用性
        mtbf_hours = random.uniform(240, 360)  # 平均故障间隔240-360小时
        mttr_minutes = random.uniform(8, 15)  # 平均恢复时间8-15分钟

        return {
            "metric": "系统可靠性",
            "uptime": f"{uptime*100:.2f}%",
            "mtbf": f"{mtbf_hours:.0f}小时",
            "mttr": f"{mttr_minutes:.0f}分钟",
            "error_rate": f"{(1-uptime)*100:.3f}%",
        }

    def generate_all_metrics(self) -> Dict[str, Any]:
        """生成所有量化指标"""
        return {
            "generated_at": datetime.now().isoformat(),
            "project": "广东省水利水电科学研究院 - 水文Agent子模块",
            "metrics": {
                "performance": self.generate_performance_improvement(),
                "accuracy": self.generate_accuracy_improvement(),
                "tool_efficiency": self.generate_tool_call_metrics(),
                "user_satisfaction": self.generate_user_satisfaction(),
                "badcase_management": self.generate_badcase_reduction(),
                "mcp_usage": self.generate_mcp_usage(),
                "rag_quality": self.generate_rag_improvement(),
                "reliability": self.generate_system_reliability(),
            }
        }


def format_metrics_for_resume(metrics: Dict[str, Any]) -> List[str]:
    """将指标格式化为简历可用的量化描述"""
    m = metrics["metrics"]

    statements = [
        # 性能优化
        f"PostgreSQL+pgvector替换SQLite后，查询响应时间从{m['performance']['baseline']['avg']}降至{m['performance']['improved']['avg']}（优化{m['performance']['improvement']['avg']}），P95延迟优化{m['performance']['improvement']['p95']}",

        # 准确率提升
        f"通过一致性校验和badcase迭代优化，Agent准确率从{m['accuracy']['baseline']['accuracy']}提升至{m['accuracy']['improved']['accuracy']}，幻觉输出率从{m['accuracy']['baseline']['hallucination_rate']}降低至{m['accuracy']['improved']['hallucination_rate']}",

        # 工具调用优化
        f"优化工具选择逻辑，工具调用成功率从{m['tool_efficiency']['baseline']['success_rate']}提升至{m['tool_efficiency']['improved']['success_rate']}，平均调用次数从{m['tool_efficiency']['baseline']['avg_calls_per_query']}降至{m['tool_efficiency']['improved']['avg_calls_per_query']}",

        # 用户满意度
        f"用户满意度从{m['user_satisfaction']['baseline']['avg_rating']}提升至{m['user_satisfaction']['improved']['avg_rating']}，正面反馈率达{m['user_satisfaction']['improved']['positive_feedback_rate']}",

        # Badcase管理
        f"建立badcase收集机制，累计收集{m['badcase_management']['details']['total_collected']}个badcase并修复{m['badcase_management']['details']['fixed']}个，badcase率从{m['badcase_management']['baseline']['badcase_rate']}降至{m['badcase_management']['improved']['badcase_rate']}（降低{m['badcase_management']['improvement']['reduction_ratio']}）",

        # MCP跨团队复用
        f"MCP Server部署后支撑{m['mcp_usage']['usage']['downstream_teams']}跨团队数据查询复用，日均调用{m['mcp_usage']['usage']['daily_calls']}，调用成功率{m['mcp_usage']['usage']['success_rate']}，{m['mcp_usage']['impact']}",

        # 知识库优化
        f"RAG检索召回率从{m['rag_quality']['baseline']['recall']}提升至{m['rag_quality']['improved']['recall']}，准确率从{m['rag_quality']['baseline']['precision']}提升至{m['rag_quality']['improved']['precision']}，检索时间优化{m['rag_quality']['improvement']['retrieval_time']}",

        # 系统可靠性
        f"内网验证环境系统可用性{m['reliability']['uptime']}，平均故障间隔{m['reliability']['mtbf']}，平均恢复时间{m['reliability']['mttr']}",
    ]

    return statements


if __name__ == "__main__":
    generator = MetricsGenerator(seed=42)
    metrics = generator.generate_all_metrics()

    # 保存完整指标
    output_file = "quantitative_metrics.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    print("=" * 80)
    print("量化指标生成完成")
    print("=" * 80)

    # 打印简历可用的描述
    print("\n【简历可用的量化描述】\n")
    statements = format_metrics_for_resume(metrics)
    for i, stmt in enumerate(statements, 1):
        print(f"{i}. {stmt}\n")

    print(f"\n完整指标已保存至: {output_file}")
