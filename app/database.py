"""
数据库模型
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()

class User(Base):
    """管理员用户表"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class APIKey(Base):
    """API 密钥表"""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    rate_limit = Column(Integer, default=100)  # 每小时请求限制
    created_by = Column(Integer, nullable=False)  # user_id
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

class TranslationLog(Base):
    """翻译日志表"""
    __tablename__ = "translation_logs"

    id = Column(Integer, primary_key=True, index=True)
    api_key_id = Column(Integer, nullable=True)  # 关联的 API Key
    source_lang = Column(String, nullable=False)
    target_lang = Column(String, nullable=False)
    model_used = Column(String, nullable=False)
    char_count = Column(Integer, nullable=False)  # 字符数
    success = Column(Boolean, nullable=False)
    error_message = Column(String, nullable=True)
    response_time = Column(Float, nullable=False)  # 响应时间（秒）
    model_backend = Column(String, nullable=True)
    actual_model_name = Column(String, nullable=True)
    model_load_time = Column(Float, nullable=True, default=0.0)
    inference_time = Column(Float, nullable=True, default=0.0)
    format_time = Column(Float, nullable=True, default=0.0)
    segment_count = Column(Integer, nullable=True, default=0)
    batch_count = Column(Integer, nullable=True, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SystemConfig(Base):
    """系统配置表"""
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    value = Column(String, nullable=False)
    description = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
