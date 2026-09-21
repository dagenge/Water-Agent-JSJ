"""Agent版本管理和A/B测试模块

功能：
1. 版本创建和激活
2. A/B测试流量分配
3. 版本性能对比
4. 灰度发布和回滚
"""

import hashlib
import random
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.postgres.database import SessionLocal
from config.postgres.models import AgentVersion, AgentSession


class VersionManager:
    """Agent版本管理器"""

    def __init__(self, db: Optional[Session] = None):
        self.db = db or SessionLocal()
        self.own_db = db is None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.own_db:
            self.db.close()

    def create_version(self, version: str, description: str,
                      system_prompt: str, tool_schema: str) -> AgentVersion:
        """创建新版本

        Args:
            version: 版本号，如 v1.1.0
            description: 版本描述，说明改动内容
            system_prompt: 系统提示词
            tool_schema: 工具schema的JSON字符串

        Returns:
            创建的版本对象
        """
        # 计算hash
        system_prompt_hash = hashlib.md5(system_prompt.encode()).hexdigest()
        tool_schema_hash = hashlib.md5(tool_schema.encode()).hexdigest()

        # 检查版本是否已存在
        existing = self.db.query(AgentVersion).filter(
            AgentVersion.version == version
        ).first()

        if existing:
            raise ValueError(f"版本已存在: {version}")

        agent_version = AgentVersion(
            version=version,
            description=description,
            system_prompt_hash=system_prompt_hash,
            tool_schema_hash=tool_schema_hash,
            is_active=False,
            ab_test_ratio=0.0,
        )

        self.db.add(agent_version)
        self.db.commit()
        self.db.refresh(agent_version)

        return agent_version

    def activate_version(self, version: str, ab_test_ratio: float = 1.0) -> AgentVersion:
        """激活版本

        Args:
            version: 版本号
            ab_test_ratio: A/B测试流量比例，0.0-1.0
                          0.1表示10%流量，1.0表示全量

        Returns:
            激活的版本对象
        """
        agent_version = self.db.query(AgentVersion).filter(
            AgentVersion.version == version
        ).first()

        if not agent_version:
            raise ValueError(f"版本不存在: {version}")

        # 如果是全量上线，先停用其他版本
        if ab_test_ratio == 1.0:
            self.db.query(AgentVersion).filter(
                AgentVersion.is_active == True
            ).update({
                "is_active": False,
                "deactivated_at": datetime.now(),
            })

        agent_version.is_active = True
        agent_version.ab_test_ratio = ab_test_ratio
        agent_version.activated_at = datetime.now()

        self.db.commit()
        self.db.refresh(agent_version)

        return agent_version

    def deactivate_version(self, version: str) -> AgentVersion:
        """停用版本"""
        agent_version = self.db.query(AgentVersion).filter(
            AgentVersion.version == version
        ).first()

        if not agent_version:
            raise ValueError(f"版本不存在: {version}")

        agent_version.is_active = False
        agent_version.deactivated_at = datetime.now()

        self.db.commit()
        self.db.refresh(agent_version)

        return agent_version

    def get_active_version(self, session_id: Optional[str] = None) -> str:
        """获取当前应使用的版本

        支持A/B测试：根据session_id的hash值和ab_test_ratio决定使用哪个版本

        Args:
            session_id: 会话ID，用于一致性hash分流

        Returns:
            版本号
        """
        active_versions = self.db.query(AgentVersion).filter(
            AgentVersion.is_active == True
        ).order_by(AgentVersion.activated_at.desc()).all()

        if not active_versions:
            return "v1.0.0"  # 默认版本

        # 如果只有一个激活版本，直接返回
        if len(active_versions) == 1:
            return active_versions[0].version

        # 多版本A/B测试
        # 使用session_id的hash值确保同一用户始终分配到同一版本
        if session_id:
            hash_val = int(hashlib.md5(session_id.encode()).hexdigest(), 16)
            ratio = (hash_val % 10000) / 10000.0
        else:
            ratio = random.random()

        cumulative = 0.0
        for v in active_versions:
            cumulative += v.ab_test_ratio
            if ratio < cumulative:
                return v.version

        return active_versions[0].version

    def compare_versions(self, version_a: str, version_b: str,
                        days: int = 7) -> Dict[str, Any]:
        """对比两个版本的性能

        对比指标：
        1. 查询成功率
        2. 平均响应时间
        3. 平均工具调用次数
        4. 一致性校验修正率
        5. 用户满意度（基于反馈）

        Args:
            version_a: 版本A
            version_b: 版本B
            days: 统计最近N天的数据

        Returns:
            对比结果字典
        """
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=days)

        def get_stats(version: str) -> Dict[str, Any]:
            sessions = self.db.query(AgentSession).filter(
                AgentSession.version == version,
                AgentSession.created_at >= cutoff_date
            ).all()

            if not sessions:
                return {
                    "total_queries": 0,
                    "avg_latency_ms": 0,
                    "avg_tool_calls": 0,
                    "correction_rate": 0,
                    "success_rate": 0,
                }

            total = len(sessions)
            total_latency = sum(s.execution_time_ms or 0 for s in sessions)
            total_tool_calls = sum(s.tool_call_count or 0 for s in sessions)
            corrections = sum(1 for s in sessions if s.is_corrected)

            # 统计用户反馈
            from config.postgres.models import UserFeedback
            positive_feedbacks = self.db.query(UserFeedback).join(
                AgentSession, UserFeedback.session_id == AgentSession.session_id
            ).filter(
                AgentSession.version == version,
                AgentSession.created_at >= cutoff_date,
                UserFeedback.feedback_type == "positive"
            ).count()

            total_feedbacks = self.db.query(UserFeedback).join(
                AgentSession, UserFeedback.session_id == AgentSession.session_id
            ).filter(
                AgentSession.version == version,
                AgentSession.created_at >= cutoff_date
            ).count()

            return {
                "total_queries": total,
                "avg_latency_ms": total_latency / total if total > 0 else 0,
                "avg_tool_calls": total_tool_calls / total if total > 0 else 0,
                "correction_rate": corrections / total if total > 0 else 0,
                "positive_feedback_rate": positive_feedbacks / total_feedbacks if total_feedbacks > 0 else 0,
            }

        stats_a = get_stats(version_a)
        stats_b = get_stats(version_b)

        return {
            "version_a": version_a,
            "version_b": version_b,
            "comparison_days": days,
            "stats_a": stats_a,
            "stats_b": stats_b,
            "winner": self._determine_winner(stats_a, stats_b),
        }

    def _determine_winner(self, stats_a: Dict, stats_b: Dict) -> str:
        """根据统计数据判断哪个版本更好

        综合评分 = 0.3*正反馈率 + 0.3*(1-修正率) + 0.2*(1-归一化延迟) + 0.2*(1-归一化工具调用)
        """
        if stats_a["total_queries"] == 0 and stats_b["total_queries"] == 0:
            return "insufficient_data"

        if stats_a["total_queries"] == 0:
            return "version_b"
        if stats_b["total_queries"] == 0:
            return "version_a"

        # 归一化延迟和工具调用次数
        max_latency = max(stats_a["avg_latency_ms"], stats_b["avg_latency_ms"])
        max_tools = max(stats_a["avg_tool_calls"], stats_b["avg_tool_calls"])

        score_a = (
            0.3 * stats_a["positive_feedback_rate"] +
            0.3 * (1 - stats_a["correction_rate"]) +
            0.2 * (1 - stats_a["avg_latency_ms"] / max_latency if max_latency > 0 else 0) +
            0.2 * (1 - stats_a["avg_tool_calls"] / max_tools if max_tools > 0 else 0)
        )

        score_b = (
            0.3 * stats_b["positive_feedback_rate"] +
            0.3 * (1 - stats_b["correction_rate"]) +
            0.2 * (1 - stats_b["avg_latency_ms"] / max_latency if max_latency > 0 else 0) +
            0.2 * (1 - stats_b["avg_tool_calls"] / max_tools if max_tools > 0 else 0)
        )

        if abs(score_a - score_b) < 0.05:
            return "tie"
        elif score_a > score_b:
            return "version_a"
        else:
            return "version_b"

    def list_versions(self) -> List[Dict[str, Any]]:
        """列出所有版本"""
        versions = self.db.query(AgentVersion).order_by(
            AgentVersion.created_at.desc()
        ).all()

        return [{
            "version": v.version,
            "description": v.description,
            "is_active": v.is_active,
            "ab_test_ratio": v.ab_test_ratio,
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "activated_at": v.activated_at.isoformat() if v.activated_at else None,
            "performance_summary": v.performance_summary,
        } for v in versions]


def gradual_rollout(version: str, initial_ratio: float = 0.1,
                   steps: List[float] = [0.1, 0.3, 0.5, 1.0],
                   comparison_baseline: str = "v1.0.0") -> Dict[str, Any]:
    """灰度发布：逐步增加新版本流量

    Args:
        version: 要发布的版本
        initial_ratio: 初始流量比例
        steps: 流量增长步骤
        comparison_baseline: 对比基线版本

    Returns:
        发布计划
    """
    with VersionManager() as vm:
        # 激活版本，设置初始流量
        vm.activate_version(version, ab_test_ratio=initial_ratio)

        plan = {
            "version": version,
            "baseline": comparison_baseline,
            "steps": [],
        }

        for ratio in steps:
            plan["steps"].append({
                "ratio": ratio,
                "status": "pending" if ratio > initial_ratio else "active",
                "instruction": f"观察指标，确认无异常后手动执行: version_manager.activate_version('{version}', {ratio})"
            })

        return plan
