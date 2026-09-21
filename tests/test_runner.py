"""测试用例管理和回归测试模块

功能：
1. 测试用例管理（CRUD）
2. 回归测试执行
3. 准确率评估
4. 测试报告生成
"""

import sys
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.orm import Session
from config.postgres.database import SessionLocal
from config.postgres.models import TestCase, AgentSession


class TestCaseManager:
    """测试用例管理器"""

    def __init__(self, db: Optional[Session] = None):
        self.db = db or SessionLocal()
        self.own_db = db is None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.own_db:
            self.db.close()

    def create_test_case(self, test_id: str, user_input: str,
                        expected_intent: str,
                        expected_tools: List[str],
                        expected_output_keywords: List[str],
                        expected_data_points: Optional[Dict] = None,
                        category: str = "basic_query",
                        priority: str = "medium") -> TestCase:
        """创建测试用例"""
        test_case = TestCase(
            test_id=test_id,
            user_input=user_input,
            expected_intent=expected_intent,
            expected_tools=expected_tools,
            expected_output_keywords=expected_output_keywords,
            expected_data_points=expected_data_points,
            category=category,
            priority=priority,
        )

        self.db.add(test_case)
        self.db.commit()
        self.db.refresh(test_case)

        return test_case

    def get_test_cases(self, category: Optional[str] = None,
                      priority: Optional[str] = None,
                      is_active: bool = True) -> List[TestCase]:
        """获取测试用例"""
        query = self.db.query(TestCase)

        if category:
            query = query.filter(TestCase.category == category)
        if priority:
            query = query.filter(TestCase.priority == priority)
        if is_active is not None:
            query = query.filter(TestCase.is_active == is_active)

        return query.order_by(TestCase.created_at.desc()).all()

    def run_test_case(self, test_case: TestCase, agent_executor) -> Dict[str, Any]:
        """运行单个测试用例

        Args:
            test_case: 测试用例
            agent_executor: Agent执行器（run_agent函数）

        Returns:
            测试结果
        """
        from agent.executor import run_agent

        # 执行Agent
        result = run_agent(test_case.user_input, session_id=f"test_{test_case.test_id}")

        # 检查意图
        intent_match = result["intent"]["intent"] == test_case.expected_intent

        # 检查工具调用
        called_tools = [tc["tool"] for tc in result.get("intermediate_steps", [])]
        tools_match = set(test_case.expected_tools).issubset(set(called_tools))

        # 检查输出关键词
        output = result["output"]
        keywords_match = all(kw in output for kw in test_case.expected_output_keywords)

        # 检查数据点（如果有）
        data_points_match = True
        if test_case.expected_data_points:
            # 这里需要根据实际情况解析输出并验证数据点
            # 简化处理：检查数据点的key是否在输出中
            for key in test_case.expected_data_points.keys():
                if key not in output:
                    data_points_match = False
                    break

        # 综合判断
        passed = intent_match and tools_match and keywords_match and data_points_match

        return {
            "test_id": test_case.test_id,
            "passed": passed,
            "intent_match": intent_match,
            "tools_match": tools_match,
            "keywords_match": keywords_match,
            "data_points_match": data_points_match,
            "called_tools": called_tools,
            "output": output,
            "execution_time_ms": result.get("execution_time_ms", 0),
        }

    def run_test_suite(self, category: Optional[str] = None,
                      priority: Optional[str] = None) -> Dict[str, Any]:
        """运行测试套件

        Args:
            category: 测试类别过滤
            priority: 优先级过滤

        Returns:
            测试报告
        """
        test_cases = self.get_test_cases(category=category, priority=priority)

        if not test_cases:
            return {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "pass_rate": 0,
                "results": [],
            }

        results = []
        passed_count = 0

        for tc in test_cases:
            print(f"运行测试: {tc.test_id}...", end=" ")
            try:
                result = self.run_test_case(tc)
                if result["passed"]:
                    passed_count += 1
                    print("✓")
                else:
                    print("✗")

                results.append(result)

                # 更新测试用例状态
                tc.last_pass = result["passed"]
                tc.last_run_at = datetime.now()
                self.db.commit()

            except Exception as e:
                print(f"✗ (异常: {e})")
                results.append({
                    "test_id": tc.test_id,
                    "passed": False,
                    "error": str(e),
                })

        return {
            "total": len(test_cases),
            "passed": passed_count,
            "failed": len(test_cases) - passed_count,
            "pass_rate": passed_count / len(test_cases) if test_cases else 0,
            "results": results,
            "timestamp": datetime.now().isoformat(),
        }


def create_baseline_test_suite():
    """创建基线测试套件

    包含5大类典型查询：
    1. 基础查询：流域、站点、场次信息
    2. 数据查询：降雨、流量数据
    3. 统计分析：统计指标计算
    4. 知识检索：防汛知识查询
    5. 拓扑查询：上下游关系
    """
    with TestCaseManager() as tcm:
        test_cases = [
            # 1. 基础查询
            {
                "test_id": "basic_001",
                "user_input": "查询所有流域信息",
                "expected_intent": "basin_query",
                "expected_tools": ["query_basin_list"],
                "expected_output_keywords": ["河子口", "白盆珠", "布吉河"],
                "category": "basic_query",
                "priority": "high",
            },
            {
                "test_id": "basic_002",
                "user_input": "河子口流域有哪些站点？",
                "expected_intent": "station_query",
                "expected_tools": ["query_station_list"],
                "expected_output_keywords": ["hzk", "站点"],
                "category": "basic_query",
                "priority": "high",
            },
            {
                "test_id": "basic_003",
                "user_input": "白盆珠流域有哪些洪水场次？",
                "expected_intent": "flood_event_query",
                "expected_tools": ["query_flood_events"],
                "expected_output_keywords": ["bpz", "场次"],
                "category": "basic_query",
                "priority": "high",
            },

            # 2. 数据查询
            {
                "test_id": "data_001",
                "user_input": "查询河子口流域20050610场次的降雨数据",
                "expected_intent": "rainfall_query",
                "expected_tools": ["query_flood_events", "query_rainfall_data"],
                "expected_output_keywords": ["20050610", "降雨"],
                "category": "data_query",
                "priority": "high",
            },
            {
                "test_id": "data_002",
                "user_input": "白盆珠20060712场次的洪峰是多少？",
                "expected_intent": "peak_flow_query",
                "expected_tools": ["query_peak_flow"],
                "expected_output_keywords": ["洪峰", "m³/s"],
                "category": "data_query",
                "priority": "high",
            },

            # 3. 统计分析
            {
                "test_id": "stats_001",
                "user_input": "统计河子口20050610场次各站点累计雨量",
                "expected_intent": "rainfall_statistics",
                "expected_tools": ["query_rainfall_statistics"],
                "expected_output_keywords": ["累计雨量", "mm"],
                "category": "statistics",
                "priority": "medium",
            },

            # 4. 知识检索
            {
                "test_id": "knowledge_001",
                "user_input": "河子口流域的暴雨预警标准是什么？",
                "expected_intent": "knowledge_query",
                "expected_tools": ["search_flood_prevention_knowledge"],
                "expected_output_keywords": ["预警", "标准"],
                "category": "knowledge",
                "priority": "medium",
            },

            # 5. 拓扑查询
            {
                "test_id": "topology_001",
                "user_input": "查询河子口流域的水系拓扑结构",
                "expected_intent": "topology_query",
                "expected_tools": ["query_basin_topology"],
                "expected_output_keywords": ["拓扑", "上游", "下游"],
                "category": "topology",
                "priority": "medium",
            },
        ]

        created_count = 0
        for tc_data in test_cases:
            try:
                tcm.create_test_case(**tc_data)
                created_count += 1
                print(f"✓ 创建测试用例: {tc_data['test_id']}")
            except Exception as e:
                print(f"✗ 创建失败 {tc_data['test_id']}: {e}")

        print(f"\n总计创建 {created_count}/{len(test_cases)} 个测试用例")


if __name__ == "__main__":
    print("=== 创建基线测试套件 ===\n")
    create_baseline_test_suite()

    print("\n=== 运行测试套件 ===\n")
    with TestCaseManager() as tcm:
        report = tcm.run_test_suite()
        print(f"\n测试报告:")
        print(f"  总数: {report['total']}")
        print(f"  通过: {report['passed']}")
        print(f"  失败: {report['failed']}")
        print(f"  通过率: {report['pass_rate']*100:.1f}%")
