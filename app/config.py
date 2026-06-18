"""
配置文件
"""
import os
from typing import Dict, List
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config:
    # 安全配置
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

    # 数据库配置
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./translation_api.db")

    # 管理员配置
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")

    # API配置
    API_TITLE = "本地翻译API"
    API_VERSION = "2.0.0"
    API_DESCRIPTION = "整合 Argos、MarianMT、M2M100、NLLB 的安全本地翻译服务"
    API_RATE_LIMIT = int(os.getenv("API_RATE_LIMIT", "100"))
    API_RATE_LIMIT_PERIOD = int(os.getenv("API_RATE_LIMIT_PERIOD", "3600"))

    # 模型配置
    AVAILABLE_MODELS = ["argos", "marian", "m2m100", "m2m100_1_2b", "nllb"]
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "argos")

    # 支持的语言对
    SUPPORTED_LANGUAGE_PAIRS = {
        "argos": {
            "en-zh": True,
            "zh-en": True,
            "en-ja": True,
            "ja-en": True,
        },
        "marian": {
            "en-zh": True,
            "zh-en": True,
        },
        "m2m100": {
            "en-zh": True,
            "zh-en": True,
            "en-ja": True,
            "ja-en": True,
        },
        "m2m100_1_2b": {
            "en-zh": True,
            "zh-en": True,
            "en-ja": True,
            "ja-en": True,
        },
        "nllb": {
            "en-zh": True,
            "zh-en": True,
            "en-ja": True,
            "ja-en": True,
        }
    }

    # MarianMT 模型映射
    MARIAN_MODELS = {
        "en-zh": "Helsinki-NLP/opus-mt-en-zh",
        "zh-en": "Helsinki-NLP/opus-mt-zh-en",
    }

    # M2M100 模型路径
    M2M100_MODEL = "facebook/m2m100_418M"
    M2M100_LARGE_MODEL = os.getenv("M2M100_LARGE_MODEL", "facebook/m2m100_1.2B")

    # NLLB 模型路径。默认使用相对更适合本地部署的 distilled 版本。
    NLLB_MODEL = os.getenv("NLLB_MODEL", "facebook/nllb-200-distilled-600M")

    # 设备配置
    DEVICE = os.getenv("DEVICE", "cpu")

    # 启动时预热的 Argos 语言对，避免首个客户请求承担初始化成本
    ARGOS_WARMUP_PAIRS = [
        pair.strip()
        for pair in os.getenv("ARGOS_WARMUP_PAIRS", "en-zh,zh-en").split(",")
        if pair.strip()
    ]

config = Config()
