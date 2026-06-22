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
    API_RATE_LIMIT = 100
    API_RATE_LIMIT_PERIOD = 3600
    API_BASE_URL = os.getenv("API_BASE_URL", "").strip().rstrip("/")

    # 模型配置
    AVAILABLE_MODELS = [
        "argos",
        "marian",
        "m2m100",
        "m2m100_1_2b",
        "nllb",
        "qwen3_1_7b",
        "gemma3_1b",
        "qwen2_5_0_5b",
    ]
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "argos")
    MODEL_ENABLED = {model_name: True for model_name in AVAILABLE_MODELS}

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
        },
        "qwen3_1_7b": {
            "en-zh": True,
            "zh-en": True,
            "en-ja": True,
            "ja-en": True,
        },
        "gemma3_1b": {
            "en-zh": True,
            "zh-en": True,
            "en-ja": True,
            "ja-en": True,
        },
        "qwen2_5_0_5b": {
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
    M2M100_MODEL = os.getenv("M2M100_MODEL", "facebook/m2m100_418M")
    M2M100_LARGE_MODEL = os.getenv("M2M100_LARGE_MODEL", "facebook/m2m100_1.2B")
    M2M100_BACKEND = os.getenv("M2M100_BACKEND", "auto").lower()

    # NLLB 模型路径。默认使用相对更适合本地部署的 distilled 版本。
    NLLB_MODEL = os.getenv("NLLB_MODEL", "facebook/nllb-200-distilled-600M")
    NLLB_BACKEND = os.getenv("NLLB_BACKEND", "auto").lower()

    # 通用大语言模型翻译后端。默认使用指令/聊天模型，翻译时只从本地缓存加载。
    QWEN3_MODEL = os.getenv("QWEN3_MODEL", "Qwen/Qwen3-1.7B")
    GEMMA3_MODEL = os.getenv("GEMMA3_MODEL", "google/gemma-3-1b-it")
    QWEN2_5_MODEL = os.getenv("QWEN2_5_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")
    CAUSAL_LM_MODELS = {
        "qwen3_1_7b": {
            "model_name": QWEN3_MODEL,
            "display_name": "Qwen3 1.7B",
            "size": "~3.5GB",
            "requires_auth": False,
        },
        "gemma3_1b": {
            "model_name": GEMMA3_MODEL,
            "display_name": "Gemma 3 1B",
            "size": "~2GB",
            "requires_auth": True,
        },
        "qwen2_5_0_5b": {
            "model_name": QWEN2_5_MODEL,
            "display_name": "Qwen2.5 0.5B",
            "size": "~1GB",
            "requires_auth": False,
        },
    }

    # 设备配置
    DEVICE = os.getenv("DEVICE", "cpu")
    TRANSLATION_MAX_NEW_TOKENS = int(os.getenv("TRANSLATION_MAX_NEW_TOKENS", "128"))
    TRANSLATION_BATCH_SIZE = int(os.getenv("TRANSLATION_BATCH_SIZE", "8"))
    LLM_MAX_INPUT_TOKENS = int(os.getenv("LLM_MAX_INPUT_TOKENS", "1024"))
    LLM_TRANSLATION_MAX_NEW_TOKENS = int(os.getenv("LLM_TRANSLATION_MAX_NEW_TOKENS", "512"))
    LLM_TRANSLATION_BATCH_SIZE = int(os.getenv("LLM_TRANSLATION_BATCH_SIZE", "0"))
    TORCH_CPU_THREADS = int(os.getenv("TORCH_CPU_THREADS", "0"))
    MODEL_WARMUP_ENABLED = os.getenv("MODEL_WARMUP_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    TRANSFORMER_WARMUP_MODELS = [
        model.strip()
        for model in os.getenv("TRANSFORMER_WARMUP_MODELS", "marian").split(",")
        if model.strip()
    ]
    TRANSFORMER_WARMUP_PAIRS = [
        pair.strip()
        for pair in os.getenv("TRANSFORMER_WARMUP_PAIRS", "zh-en,en-zh").split(",")
        if pair.strip()
    ]
    MARIAN_BACKEND = os.getenv("MARIAN_BACKEND", "auto").lower()
    CTRANSLATE2_MODELS_DIR = os.getenv("CTRANSLATE2_MODELS_DIR", "./models/ctranslate2")
    MARIAN_CT2_COMPUTE_TYPE = os.getenv("MARIAN_CT2_COMPUTE_TYPE", "int8")
    MARIAN_CT2_INTER_THREADS = int(os.getenv("MARIAN_CT2_INTER_THREADS", "1"))
    MARIAN_CT2_INTRA_THREADS = int(os.getenv("MARIAN_CT2_INTRA_THREADS", "0"))
    MARIAN_CT2_MAX_QUEUED_BATCHES = int(os.getenv("MARIAN_CT2_MAX_QUEUED_BATCHES", "0"))
    M2M100_CT2_COMPUTE_TYPE = os.getenv("M2M100_CT2_COMPUTE_TYPE", "int8")
    M2M100_CT2_INTER_THREADS = int(os.getenv("M2M100_CT2_INTER_THREADS", "1"))
    M2M100_CT2_INTRA_THREADS = int(os.getenv("M2M100_CT2_INTRA_THREADS", "0"))
    M2M100_CT2_MAX_QUEUED_BATCHES = int(os.getenv("M2M100_CT2_MAX_QUEUED_BATCHES", "0"))
    NLLB_CT2_COMPUTE_TYPE = os.getenv("NLLB_CT2_COMPUTE_TYPE", "int8")
    NLLB_CT2_INTER_THREADS = int(os.getenv("NLLB_CT2_INTER_THREADS", "1"))
    NLLB_CT2_INTRA_THREADS = int(os.getenv("NLLB_CT2_INTRA_THREADS", "0"))
    NLLB_CT2_MAX_QUEUED_BATCHES = int(os.getenv("NLLB_CT2_MAX_QUEUED_BATCHES", "0"))

    # 启动时预热的 Argos 语言对，避免首个客户请求承担初始化成本
    ARGOS_WARMUP_PAIRS = [
        pair.strip()
        for pair in os.getenv("ARGOS_WARMUP_PAIRS", "en-zh,zh-en").split(",")
        if pair.strip()
    ]

config = Config()
