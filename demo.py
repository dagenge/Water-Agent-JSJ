"""Project_JSJ_Agent 演示脚本

展示核心功能：
1. 多流域站点查询
2. 降雨统计分析
3. 代码分析沙盒
4. RAG 知识问答
"""

import sys
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from agent.executor import run_agent


def demo_basin_query():
    """演示1: 多流域站点查询（金沙江 + 广东 7 流域）"""
    print("=" * 60)
    print("演示1: 多流域站点查询")
    print("=" * 60)

    queries = [
        "定曲河流域有哪些站点",
        "查询棠荆有哪些水文站",
        "布吉河流域有多少个站点",
    ]

    for query in queries:
        print(f"\n【用户输入】: {query}")
        result = run_agent(query, session_id="demo_basin")
        print(f"\n【Agent回答】:\n{result['output'][:300]}...")
        print(f"【意图识别】: {result['intent']['intent']} (置信度: {result['intent']['confidence']})")
        print(f"【工具调用】: {len(result['intermediate_steps'])} 次")
        print("-" * 60)


def demo_rainfall_stats():
    """演示2: 降雨与流量统计分析（DQH + BtPzh + 广东流域）"""
    print("\n" + "=" * 60)
    print("演示2: 降雨与流量统计分析")
    print("=" * 60)

    queries = [
        "查询定曲河 2009050100 事件的降雨统计",
        "巴塘到攀枝花 2015年6月奔子栏站的累计降雨是多少",
        "查询棠荆流域历史事件最大流量",
    ]

    for query in queries:
        print(f"\n【用户输入】: {query}")
        result = run_agent(query, session_id="demo_stats")
        print(f"\n【Agent回答】:\n{result['output'][:500]}...")
        print(f"\n【意图识别】: {result['intent']['intent']}")
        print(f"【工具调用】: {[step['tool'] for step in result['intermediate_steps']]}")
        print("-" * 60)


def demo_code_sandbox():
    """演示3: 代码分析沙盒"""
    print("\n" + "=" * 60)
    print("演示3: 代码分析沙盒")
    print("=" * 60)

    query = "计算定曲河 2009050100 事件各站点的面平均降雨，并绘制过程线"

    print(f"\n【用户输入】: {query}")
    result = run_agent(query, session_id="demo_code")
    print(f"\n【Agent回答】:\n{result['output']}")
    print(f"\n【意图识别】: {result['intent']['intent']}")
    print(f"【工具调用】: {[step['tool'] for step in result['intermediate_steps']]}")
    print("-" * 60)


def demo_rag_knowledge():
    """演示4: RAG 知识问答"""
    print("\n" + "=" * 60)
    print("演示4: RAG 知识问答")
    print("=" * 60)

    queries = [
        "暴雨强度公式的参数怎么确定?",
        "什么是汇流时间?",
    ]

    for query in queries:
        print(f"\n【用户输入】: {query}")
        result = run_agent(query, session_id="demo_rag")
        print(f"\n【Agent回答】:\n{result['output'][:400]}...")
        print(f"\n【意图识别】: {result['intent']['intent']}")
        print("-" * 60)


def demo_monitoring_metrics():
    """演示5: 监控指标验证"""
    print("\n" + "=" * 60)
    print("演示5: 监控指标验证")
    print("=" * 60)

    import requests
    import re

    try:
        print("\n正在查询 Prometheus Exporter (http://localhost:8000/metrics)...")
        resp = requests.get("http://localhost:8000/metrics", timeout=3)

        if resp.status_code == 200:
            content = resp.text

            # 提取关键指标
            query_total = re.findall(r'agent_query_total\{[^}]+\}\s+([\d.]+)', content)
            tool_total = re.findall(r'agent_tool_call_total\{[^}]+\}\s+([\d.]+)', content)

            total_queries = sum(float(x) for x in query_total)
            total_tools = sum(float(x) for x in tool_total)

            print(f"\n✓ 监控系统正常运行")
            print(f"  累计查询数: {int(total_queries)}")
            print(f"  累计工具调用: {int(total_tools)}")
            print(f"\n访问监控面板: http://localhost:8501 → 系统监控 Tab")
        else:
            print(f"\n⚠ Exporter 响应异常: HTTP {resp.status_code}")
    except requests.exceptions.ConnectionError:
        print("\n⚠ Prometheus Exporter 未启动")
        print("  启动命令: python scripts/start_services.py")
    except Exception as e:
        print(f"\n✗ 监控验证失败: {e}")

    print("-" * 60)


def main():
    print("\n🌊 Project_JSJ_Agent 功能演示")
    print("=" * 60)
    print("本脚本将演示 Agent 的核心功能：")
    print("1. 多流域站点查询（金沙江 + 广东 7 个流域）")
    print("2. 降雨与流量统计分析（DQH + BtPzh + 广东流域）")
    print("3. 代码分析沙盒（隔离进程执行 Python 代码）")
    print("4. RAG 知识问答（BGE + BM25 + RRF 混合检索）")
    print("5. 监控指标验证（Prometheus + Grafana 栈）")
    print("=" * 60)

    try:
        # 运行演示
        demo_basin_query()
        demo_rainfall_stats()
        demo_code_sandbox()
        demo_rag_knowledge()
        demo_monitoring_metrics()

        print("\n" + "=" * 60)
        print("✅ 所有演示完成！")
        print("=" * 60)
        print("\n访问 Streamlit UI 体验完整功能: http://localhost:8501")
        print("查看实时监控指标: http://localhost:8000/metrics")
        print("监控可视化面板: http://localhost:8501 → 系统监控 Tab")

    except KeyboardInterrupt:
        print("\n\n⚠️ 演示被用户中断")
    except Exception as e:
        print(f"\n\n❌ 演示出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
