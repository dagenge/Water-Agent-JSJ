"""PostgreSQL数据模型定义

新增表：
- AgentSession: 会话记录，用于追踪每次查询的完整执行链路
- UserFeedback: 用户反馈，用于badcase收集
- ToolCallMetric: 工具调用监控，用于分析工具成功率和性能
- SystemMetric: 系统级指标，用于Prometheus导出
- AgentVersion: 版本管理，用于A/B测试和灰度发布
- TestCase: 测试用例集，用于回归测试
"""

from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, DateTime, Boolean, JSON, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from config.postgres.database import Base


class BasinMetadata(Base):
    """流域元数据"""
    __tablename__ = "basin_metadata"

    basin_id = Column(String(20), primary_key=True)
    basin_name = Column(String(100), nullable=False)
    province = Column(String(50), default="广东省")
    basin_type = Column(String(50))
    area_km2 = Column(Float)
    description = Column(Text)

    stations = relationship("StationMetadata", back_populates="basin")
    flood_events = relationship("FloodEventMetadata", back_populates="basin")


class StationMetadata(Base):
    """站点元数据"""
    __tablename__ = "station_metadata"

    station_id = Column(String(50), primary_key=True)
    basin_id = Column(String(20), ForeignKey("basin_metadata.basin_id"), nullable=False)
    sid = Column(String(20), nullable=False)
    name_cn = Column(String(100))
    name_en = Column(String(100))
    x_coord = Column(Float)
    y_coord = Column(Float)
    lon = Column(Float)
    lat = Column(Float)

    basin = relationship("BasinMetadata", back_populates="stations")

    __table_args__ = (
        Index("idx_station_basin", "basin_id"),
    )


class FloodEventMetadata(Base):
    """洪水场次元数据"""
    __tablename__ = "flood_event_metadata"

    event_id = Column(String(100), primary_key=True)
    basin_id = Column(String(20), ForeignKey("basin_metadata.basin_id"), nullable=False)
    event_code = Column(String(50), nullable=False)
    event_name = Column(String(200))
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    timesteps = Column(Integer)

    basin = relationship("BasinMetadata", back_populates="flood_events")

    __table_args__ = (
        Index("idx_flood_basin", "basin_id"),
        Index("idx_flood_code", "event_code"),
    )


class RainfallDataDict(Base):
    """雨量数据字典：记录每个流域每场洪水的表结构"""
    __tablename__ = "rainfall_data_dict"

    id = Column(Integer, primary_key=True, autoincrement=True)
    basin_id = Column(String(20), nullable=False)
    event_code = Column(String(50), nullable=False)
    column_index = Column(Integer, nullable=False)
    column_name = Column(String(100), nullable=False)
    station_id = Column(String(50), ForeignKey("station_metadata.station_id"))
    data_type = Column(String(20), default="rainfall")
    unit = Column(String(20), default="mm")

    __table_args__ = (
        Index("idx_data_dict_basin_event", "basin_id", "event_code"),
    )


class KnowledgeDocument(Base):
    """知识库文档 + pgvector向量存储

    相比FAISS文件存储的优势：
    1. 向量和元数据在同一数据库，保证一致性
    2. 支持SQL条件过滤 + 向量相似度组合查询
    3. 支持增量更新，无需重建整个索引
    4. IVFFlat索引加速向量检索
    """
    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    basin_id = Column(String(20), ForeignKey("basin_metadata.basin_id"))
    content = Column(Text, nullable=False)
    source = Column(String(200))
    chunk_id = Column(Integer)
    embedding = Column(Vector(384))  # pgvector类型，384维向量
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_knowledge_basin", "basin_id"),
        # IVFFlat 向量索引：将向量空间分成多个聚类，加速检索
        Index("idx_knowledge_embedding", "embedding", postgresql_using="ivfflat", postgresql_ops={"embedding": "vector_cosine_ops"}),
    )


class AgentSession(Base):
    """Agent会话记录：追踪每次查询的完整执行链路

    用于：
    1. 问题复现：根据session_id回放完整执行过程
    2. 性能分析：统计平均执行时间、工具调用次数
    3. 意图分布：分析用户最常问的问题类型
    """
    __tablename__ = "agent_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    user_input = Column(Text, nullable=False)
    intent_type = Column(String(50))
    intent_details = Column(JSON)
    output = Column(Text)
    corrected_output = Column(Text)
    is_corrected = Column(Boolean, default=False)
    tool_calls = Column(JSON)  # 工具调用序列 [{tool, input, output, latency_ms}]
    tool_call_count = Column(Integer, default=0)
    execution_time_ms = Column(Float)
    version = Column(String(50))  # Agent版本号
    created_at = Column(DateTime, server_default=func.now())

    feedbacks = relationship("UserFeedback", back_populates="session")

    __table_args__ = (
        Index("idx_session_created", "created_at"),
        Index("idx_session_intent", "intent_type"),
        Index("idx_session_version", "version"),
    )


class UserFeedback(Base):
    """用户反馈记录：badcase收集和标注

    工作流：
    1. 用户点击反馈按钮 → 记录feedback_type和rating
    2. 自动检测潜在badcase（一致性校验失败、工具调用失败）→ is_badcase=True
    3. 研究员定期标注 → 填写badcase_category和annotation_notes
    4. 加入测试集 → 用于回归测试
    """
    __tablename__ = "user_feedbacks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), ForeignKey("agent_sessions.session_id"), nullable=False)
    rating = Column(Integer)  # 1-5星评分
    feedback_type = Column(String(50))  # positive/negative/incorrect/incomplete/tool_error
    feedback_text = Column(Text)
    is_badcase = Column(Boolean, default=False)
    badcase_category = Column(String(50))  # tool_selection/parameter_error/result_interpretation/knowledge_error
    annotated = Column(Boolean, default=False)
    annotation_notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    session = relationship("AgentSession", back_populates="feedbacks")

    __table_args__ = (
        Index("idx_feedback_session", "session_id"),
        Index("idx_feedback_badcase", "is_badcase"),
        Index("idx_feedback_annotated", "annotated"),
        Index("idx_feedback_created", "created_at"),
    )


class ToolCallMetric(Base):
    """工具调用监控指标

    用于分析：
    1. 哪些工具最常被调用？
    2. 哪些工具成功率低？
    3. 哪些工具响应慢？
    4. 错误类型分布（参数错误、数据不存在、超时）
    """
    __tablename__ = "tool_call_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100))
    tool_name = Column(String(100), nullable=False)
    tool_input = Column(JSON)
    tool_output_summary = Column(Text)
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    latency_ms = Column(Float)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_tool_name", "tool_name"),
        Index("idx_tool_created", "created_at"),
        Index("idx_tool_success", "success"),
        Index("idx_tool_name_success", "tool_name", "success"),
    )


class SystemMetric(Base):
    """系统级监控指标：用于Prometheus导出

    指标示例：
    - agent_query_total: 总查询数
    - agent_query_success_rate: 查询成功率
    - agent_avg_latency_ms: 平均响应时间
    - tool_call_success_rate{tool_name}: 各工具成功率
    - consistency_check_failure_rate: 一致性校验失败率
    """
    __tablename__ = "system_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Float, nullable=False)
    labels = Column(JSON)  # 附加标签（如basin_id, tool_name等）
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_metric_name_created", "metric_name", "created_at"),
    )


class AgentVersion(Base):
    """Agent版本管理：支持A/B测试和灰度发布

    发布流程：
    1. 创建新版本 → is_active=False, ab_test_ratio=0.0
    2. 灰度测试 → ab_test_ratio=0.1（10%流量）
    3. 观察指标 → 对比新旧版本的成功率、latency、用户满意度
    4. 全量上线 → is_active=True, ab_test_ratio=1.0
    5. 回滚机制 → 激活上一版本
    """
    __tablename__ = "agent_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    system_prompt_hash = Column(String(64))  # system prompt的MD5
    tool_schema_hash = Column(String(64))  # 工具schema的MD5
    is_active = Column(Boolean, default=False)
    ab_test_ratio = Column(Float, default=0.0)  # A/B测试流量比例 0.0-1.0
    performance_summary = Column(JSON)  # {success_rate, avg_latency_ms, user_satisfaction}
    created_at = Column(DateTime, server_default=func.now())
    activated_at = Column(DateTime)
    deactivated_at = Column(DateTime)

    __table_args__ = (
        Index("idx_version_active", "is_active"),
    )


class TestCase(Base):
    """测试用例集：用于回归测试和准确率评估

    来源：
    1. 人工编写的典型查询
    2. 从badcase中提取
    3. 用户高频查询

    用途：
    1. 版本升级前回归测试
    2. 准确率基准评估
    3. CI/CD自动化测试
    """
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    test_id = Column(String(100), unique=True, nullable=False)
    user_input = Column(Text, nullable=False)
    expected_intent = Column(String(50))
    expected_tools = Column(JSON)  # 期望调用的工具序列
    expected_output_keywords = Column(JSON)  # 期望输出包含的关键词
    expected_data_points = Column(JSON)  # 期望输出的数据点（用于校验准确性）
    category = Column(String(50))  # 测试类别：basic_query/statistics/topology/knowledge
    priority = Column(String(20), default="medium")  # high/medium/low
    is_active = Column(Boolean, default=True)
    last_pass = Column(Boolean)
    last_run_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_test_category", "category"),
        Index("idx_test_active", "is_active"),
        Index("idx_test_priority", "priority"),
    )
