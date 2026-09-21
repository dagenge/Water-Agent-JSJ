"""Badcase收集和管理模块

功能：
1. 自动检测潜在badcase（工具调用失败、一致性校验失败、异常响应时间）
2. 用户反馈收集
3. Badcase分类和标注
4. 测试集生成
"""

import os
import sys
from typing import Optional, Dict, Any, List
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.orm import Session
from config.postgres.database import SessionLocal
from config.postgres.models import AgentSession, UserFeedback, TestCase


class BadcaseCategory:
    """Badcase分类"""
    TOOL_SELECTION = "tool_selection"          # 工具选择错误
    PARAMETER_ERROR = "parameter_error"        # 参数错误
    RESULT_INTERPRETATION = "result_interpretation"  # 结果解读错误
    KNOWLEDGE_ERROR = "knowledge_error"        # 知识检索错误
    TIMEOUT = "timeout"                        # 超时
    TOOL_FAILURE = "tool_failure"             # 工具执行失败


class BadcaseDetector:
    """Badcase自动检测器"""

    @staticmethod
    def detect_from_session(session_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """从会话数据中检测潜在badcase

        检测规则：
        1. 工具调用失败
        2. 一致性校验触发修正
        3. 响应时间超过阈值
        4. 工具调用次数异常（太多或太少）
        5. 输出包含"未找到""无数据"等关键词但用户可能期望有数据

        Returns:
            如果检测到badcase，返回 {category, reason, confidence}
            否则返回 None
        """
        issues = []

        # 1. 检查工具调用失败
        tool_calls = session_data.get("tool_calls", [])
        failed_tools = [tc for tc in tool_calls if not tc.get("success", True)]
        if failed_tools:
            issues.append({
                "category": BadcaseCategory.TOOL_FAILURE,
                "reason": f"{len(failed_tools)}个工具调用失败: {[t['tool'] for t in failed_tools]}",
                "confidence": 0.9
            })

        # 2. 检查一致性校验
        if session_data.get("is_corrected", False):
            issues.append({
                "category": BadcaseCategory.RESULT_INTERPRETATION,
                "reason": "一致性校验触发修正，原始输出与工具结果不一致",
                "confidence": 0.8
            })

        # 3. 检查响应时间
        execution_time = session_data.get("execution_time_ms", 0)
        if execution_time > 60000:  # 超过60秒
            issues.append({
                "category": BadcaseCategory.TIMEOUT,
                "reason": f"响应时间过长: {execution_time/1000:.1f}秒",
                "confidence": 0.7
            })

        # 4. 检查工具调用次数
        tool_count = len(tool_calls)
        if tool_count > 8:
            issues.append({
                "category": BadcaseCategory.TOOL_SELECTION,
                "reason": f"工具调用次数过多: {tool_count}次，可能存在重复调用或选择错误",
                "confidence": 0.6
            })
        elif tool_count == 0 and session_data.get("intent_type") != "greeting":
            issues.append({
                "category": BadcaseCategory.TOOL_SELECTION,
                "reason": "未调用任何工具，可能是意图识别或工具选择错误",
                "confidence": 0.7
            })

        # 5. 检查输出内容
        output = session_data.get("output", "")
        if any(keyword in output for keyword in ["未找到", "无数据", "不存在", "查询失败"]):
            # 进一步判断是否真的没有数据，还是查询条件错误
            user_input = session_data.get("user_input", "")
            if any(keyword in user_input for keyword in ["2024", "2023", "2022", "去年", "今年"]):
                # 用户明确问了时间范围，但返回"无数据"，可能是参数错误
                issues.append({
                    "category": BadcaseCategory.PARAMETER_ERROR,
                    "reason": "用户问了具体时间范围，但返回'无数据'，可能是参数传递错误",
                    "confidence": 0.5
                })

        # 返回置信度最高的issue
        if issues:
            return max(issues, key=lambda x: x["confidence"])
        return None


class BadcaseManager:
    """Badcase管理器"""

    def __init__(self, db: Optional[Session] = None):
        self.db = db or SessionLocal()
        self.own_db = db is None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.own_db:
            self.db.close()

    def record_feedback(self, session_id: str, feedback_type: str,
                       rating: Optional[int] = None,
                       feedback_text: Optional[str] = None) -> UserFeedback:
        """记录用户反馈"""
        # 获取session数据
        session = self.db.query(AgentSession).filter(
            AgentSession.session_id == session_id
        ).first()

        if not session:
            raise ValueError(f"Session不存在: {session_id}")

        # 自动检测是否为badcase
        is_badcase = False
        badcase_category = None

        session_data = {
            "user_input": session.user_input,
            "intent_type": session.intent_type,
            "output": session.output,
            "is_corrected": session.is_corrected,
            "tool_calls": session.tool_calls or [],
            "execution_time_ms": session.execution_time_ms,
        }

        # 如果是负面反馈，自动检测badcase
        if feedback_type in ["negative", "incorrect", "incomplete"]:
            detection_result = BadcaseDetector.detect_from_session(session_data)
            if detection_result:
                is_badcase = True
                badcase_category = detection_result["category"]

        # 创建反馈记录
        feedback = UserFeedback(
            session_id=session_id,
            rating=rating,
            feedback_type=feedback_type,
            feedback_text=feedback_text,
            is_badcase=is_badcase,
            badcase_category=badcase_category,
        )

        self.db.add(feedback)
        self.db.commit()
        self.db.refresh(feedback)

        return feedback

    def annotate_badcase(self, feedback_id: int, category: str,
                        annotation_notes: str) -> UserFeedback:
        """人工标注badcase"""
        feedback = self.db.query(UserFeedback).filter(
            UserFeedback.id == feedback_id
        ).first()

        if not feedback:
            raise ValueError(f"Feedback不存在: {feedback_id}")

        feedback.is_badcase = True
        feedback.badcase_category = category
        feedback.annotated = True
        feedback.annotation_notes = annotation_notes

        self.db.commit()
        self.db.refresh(feedback)

        return feedback

    def get_unannotated_badcases(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取未标注的badcase"""
        feedbacks = self.db.query(UserFeedback).filter(
            UserFeedback.is_badcase == True,
            UserFeedback.annotated == False
        ).order_by(UserFeedback.created_at.desc()).limit(limit).all()

        results = []
        for fb in feedbacks:
            session = self.db.query(AgentSession).filter(
                AgentSession.session_id == fb.session_id
            ).first()

            if session:
                results.append({
                    "feedback_id": fb.id,
                    "session_id": fb.session_id,
                    "user_input": session.user_input,
                    "output": session.output,
                    "intent_type": session.intent_type,
                    "tool_calls": session.tool_calls,
                    "feedback_type": fb.feedback_type,
                    "feedback_text": fb.feedback_text,
                    "badcase_category": fb.badcase_category,
                    "created_at": fb.created_at,
                })

        return results

    def create_test_case_from_badcase(self, feedback_id: int,
                                     expected_intent: str,
                                     expected_tools: List[str],
                                     expected_output_keywords: List[str],
                                     category: str = "regression") -> TestCase:
        """从badcase创建测试用例"""
        feedback = self.db.query(UserFeedback).filter(
            UserFeedback.id == feedback_id
        ).first()

        if not feedback:
            raise ValueError(f"Feedback不存在: {feedback_id}")

        session = self.db.query(AgentSession).filter(
            AgentSession.session_id == feedback.session_id
        ).first()

        if not session:
            raise ValueError(f"Session不存在: {feedback.session_id}")

        # 生成test_id
        test_id = f"badcase_{feedback_id}_{datetime.now().strftime('%Y%m%d')}"

        test_case = TestCase(
            test_id=test_id,
            user_input=session.user_input,
            expected_intent=expected_intent,
            expected_tools=expected_tools,
            expected_output_keywords=expected_output_keywords,
            category=category,
            priority="high",  # badcase修复后的测试优先级高
        )

        self.db.add(test_case)
        self.db.commit()
        self.db.refresh(test_case)

        return test_case

    def get_badcase_statistics(self) -> Dict[str, Any]:
        """获取badcase统计"""
        from sqlalchemy import func

        total = self.db.query(UserFeedback).filter(
            UserFeedback.is_badcase == True
        ).count()

        annotated = self.db.query(UserFeedback).filter(
            UserFeedback.is_badcase == True,
            UserFeedback.annotated == True
        ).count()

        # 按类别统计
        by_category = self.db.query(
            UserFeedback.badcase_category,
            func.count(UserFeedback.id)
        ).filter(
            UserFeedback.is_badcase == True
        ).group_by(UserFeedback.badcase_category).all()

        category_stats = {cat: count for cat, count in by_category if cat}

        return {
            "total_badcases": total,
            "annotated": annotated,
            "unannotated": total - annotated,
            "by_category": category_stats,
        }


def auto_detect_badcases_batch(limit: int = 100) -> List[int]:
    """批量检测最近的会话中的潜在badcase

    Returns:
        检测到的badcase的feedback_id列表
    """
    db = SessionLocal()
    detected_ids = []

    try:
        # 获取最近的会话（还没有反馈的）
        sessions = db.query(AgentSession).outerjoin(
            UserFeedback,
            AgentSession.session_id == UserFeedback.session_id
        ).filter(
            UserFeedback.id == None  # 没有反馈记录
        ).order_by(AgentSession.created_at.desc()).limit(limit).all()

        for session in sessions:
            session_data = {
                "user_input": session.user_input,
                "intent_type": session.intent_type,
                "output": session.output,
                "is_corrected": session.is_corrected,
                "tool_calls": session.tool_calls or [],
                "execution_time_ms": session.execution_time_ms,
            }

            detection_result = BadcaseDetector.detect_from_session(session_data)

            if detection_result and detection_result["confidence"] >= 0.7:
                # 自动创建badcase记录
                feedback = UserFeedback(
                    session_id=session.session_id,
                    feedback_type="auto_detected",
                    is_badcase=True,
                    badcase_category=detection_result["category"],
                    feedback_text=f"自动检测: {detection_result['reason']}",
                )
                db.add(feedback)
                db.commit()
                db.refresh(feedback)
                detected_ids.append(feedback.id)

    finally:
        db.close()

    return detected_ids
