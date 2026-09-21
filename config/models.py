"""PostgreSQL 数据库模型"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from config.database import Base


class BasinMetadata(Base):
    """流域元数据"""
    __tablename__ = "basin_metadata"

    basin_id = Column(String(50), primary_key=True)
    basin_name = Column(String(100), nullable=False)
    basin_area = Column(Float)
    main_river = Column(String(100))
    province = Column(String(50))
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    # 关联
    stations = relationship("StationMetadata", back_populates="basin")
    floods = relationship("FloodEventMetadata", back_populates="basin")


class StationMetadata(Base):
    """测站元数据"""
    __tablename__ = "station_metadata"

    station_id = Column(String(50), primary_key=True)
    station_name = Column(String(100), nullable=False)
    basin_id = Column(String(50), ForeignKey("basin_metadata.basin_id"))
    station_type = Column(String(50))
    longitude = Column(Float)
    latitude = Column(Float)
    elevation = Column(Float)
    drainage_area = Column(Float)
    warning_water_level = Column(Float)
    guarantee_water_level = Column(Float)
    created_at = Column(DateTime, default=datetime.now)

    # 关联
    basin = relationship("BasinMetadata", back_populates="stations")
    observations = relationship("WaterObservation", back_populates="station")

    __table_args__ = (
        Index("idx_station_basin", "basin_id"),
    )


class FloodEventMetadata(Base):
    """洪水事件元数据"""
    __tablename__ = "flood_event_metadata"

    event_id = Column(Integer, primary_key=True, autoincrement=True)
    basin_id = Column(String(50), ForeignKey("basin_metadata.basin_id"))
    event_name = Column(String(200), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime)
    peak_discharge = Column(Float)
    peak_water_level = Column(Float)
    affected_stations = Column(JSON)
    severity = Column(String(50))
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    # 关联
    basin = relationship("BasinMetadata", back_populates="floods")

    __table_args__ = (
        Index("idx_flood_basin", "basin_id"),
        Index("idx_flood_date", "start_date"),
    )


class WaterObservation(Base):
    """水文观测数据"""
    __tablename__ = "water_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(String(50), ForeignKey("station_metadata.station_id"), nullable=False)
    obs_time = Column(DateTime, nullable=False)
    water_level = Column(Float)
    discharge = Column(Float)
    rainfall = Column(Float)
    temperature = Column(Float)
    data_source = Column(String(50))
    quality_flag = Column(String(10))
    created_at = Column(DateTime, default=datetime.now)

    # 关联
    station = relationship("StationMetadata", back_populates="observations")

    __table_args__ = (
        Index("idx_obs_station_time", "station_id", "obs_time"),
    )


class ConversationHistory(Base):
    """对话历史"""
    __tablename__ = "conversation_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=False)
    user_input = Column(Text, nullable=False)
    agent_response = Column(Text, nullable=False)
    intent = Column(String(50))
    tools_used = Column(JSON)
    execution_time = Column(Float)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("idx_conv_session", "session_id"),
        Index("idx_conv_time", "created_at"),
    )


class UserFeedback(Base):
    """用户反馈"""
    __tablename__ = "user_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversation_history.id"))
    rating = Column(Integer)  # 1-5
    feedback_text = Column(Text)
    issue_type = Column(String(50))
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("idx_feedback_session", "session_id"),
    )
