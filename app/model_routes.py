"""
模型管理相关接口
"""
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from threading import Event, Lock, Thread
from typing import Optional
from uuid import uuid4
import importlib.util
import os
import re
import shutil
import time

from .auth import get_current_user_from_token, security
from .config import config
from .database import SystemConfig
from .db_session import get_db
from .models.ct2_utils import get_ct2_model_dir, get_huggingface_snapshot_path, has_ct2_model_files

router = APIRouter()
download_tasks = {}
download_tasks_lock = Lock()

MODEL_SIZE_HINTS = {
    "facebook/m2m100_418M": 1_250_000_000,
    "facebook/m2m100_1.2B": 4_500_000_000,
    "facebook/nllb-200-distilled-600M": 2_500_000_000,
    "facebook/nllb-200-1.3B": 5_500_000_000,
    "facebook/nllb-200-3.3B": 13_000_000_000,
}
DEFAULT_MARIAN_SIZE_HINT = 320_000_000
MULTILINGUAL_UI_LANGS = ["zh", "en", "ja", "ko", "fr", "de", "es", "ru"]


def build_all_language_pairs(languages):
    return [
        f"{source}-{target}"
        for source in languages
        for target in languages
        if source != target
    ]

def has_huggingface_model_files(model_name: str) -> bool:
    """Check whether a HuggingFace model cache contains actual weight files."""
    cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
    model_dir_name = model_name.replace("/", "--")
    model_path = os.path.join(cache_dir, f"models--{model_dir_name}")

    if not os.path.isdir(model_path):
        return False

    no_exist_marker = f"{os.sep}.no_exist{os.sep}"

    for root, _, files in os.walk(model_path):
        if no_exist_marker in root:
            continue

        if any(
            file_name in {"pytorch_model.bin", "model.safetensors"}
            or file_name.endswith(".safetensors")
            for file_name in files
        ):
            return True

    return False

def has_huggingface_cache_dir(model_name: str) -> bool:
    """Check whether any HuggingFace cache directory exists for a model."""
    cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
    model_dir_name = model_name.replace("/", "--")
    model_path = os.path.join(cache_dir, f"models--{model_dir_name}")
    return os.path.isdir(model_path)

def get_huggingface_model_cache_path(model_name: str) -> str:
    cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
    model_dir_name = model_name.replace("/", "--")
    return os.path.join(cache_dir, f"models--{model_dir_name}")

def get_directory_size(path: str) -> int:
    total = 0
    if not os.path.isdir(path):
        return total

    for root, _, files in os.walk(path):
        if f"{os.sep}.no_exist{os.sep}" in root:
            continue

        for file_name in files:
            try:
                total += os.path.getsize(os.path.join(root, file_name))
            except OSError:
                pass

    return total

def create_download_task(kind: str, label: str) -> str:
    task_id = str(uuid4())
    now = time.time()
    with download_tasks_lock:
        download_tasks[task_id] = {
            "task_id": task_id,
            "kind": kind,
            "label": label,
            "status": "queued",
            "percent": 0,
            "message": "等待开始...",
            "error": None,
            "started_at": now,
            "updated_at": now,
            "finished_at": None,
        }
    return task_id

def update_download_task(task_id: str, **updates):
    with download_tasks_lock:
        task = download_tasks.get(task_id)
        if not task:
            return

        task.update(updates)
        task["updated_at"] = time.time()

def finish_download_task(task_id: str, message: str):
    update_download_task(
        task_id,
        status="completed",
        percent=100,
        message=message,
        error=None,
        finished_at=time.time(),
    )

def fail_download_task(task_id: str, error: str):
    update_download_task(
        task_id,
        status="failed",
        message="下载失败",
        error=error,
        finished_at=time.time(),
    )

def monitor_huggingface_cache(
    task_id: str,
    model_name: str,
    start_percent: int,
    end_percent: int,
    total_bytes_hint: int,
    stop_event: Event
):
    """Estimate download progress by watching HuggingFace cache size."""
    cache_path = get_huggingface_model_cache_path(model_name)

    while not stop_event.is_set():
        current_size = get_directory_size(cache_path)
        if total_bytes_hint > 0:
            ratio = min(current_size / total_bytes_hint, 1)
            percent = min(end_percent - 1, int(start_percent + ratio * (end_percent - start_percent)))
            update_download_task(
                task_id,
                percent=max(start_percent, percent),
                downloaded_bytes=current_size,
                total_bytes_hint=total_bytes_hint,
            )
        time.sleep(1)

def run_threaded_download(target, *args):
    Thread(target=target, args=args, daemon=True).start()

class InstallRequest(BaseModel):
    source_lang: str
    target_lang: str

class ModelConfigRequest(BaseModel):
    use_gpu: bool
    default_model: Optional[str] = None

async def require_admin_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db)
):
    """Require a valid admin JWT for model management endpoints."""
    return await get_current_user_from_token(credentials.credentials, db)

async def upsert_config(
    db: AsyncSession,
    key: str,
    value: str,
    description: str
):
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    item = result.scalar_one_or_none()
    if item:
        item.value = value
        item.description = description
    else:
        db.add(SystemConfig(key=key, value=value, description=description))

@router.get("/admin/models/downloads/{task_id}")
async def get_download_task_status(
    task_id: str,
    current_user=Depends(require_admin_user)
):
    """获取模型/语言包下载任务进度"""
    with download_tasks_lock:
        task = download_tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="下载任务不存在")
        return dict(task)

@router.get("/admin/models/config")
async def get_model_config(
    current_user=Depends(require_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取模型配置"""
    result = await db.execute(select(SystemConfig).where(SystemConfig.key.in_([
        "device",
        "default_model",
    ])))
    rows = {row.key: row.value for row in result.scalars().all()}
    device = rows.get("device", config.DEVICE)
    default_model = rows.get("default_model", config.DEFAULT_MODEL)

    return {
        "device": device,
        "use_gpu": device == "cuda",
        "default_model": default_model,
        "available_models": config.AVAILABLE_MODELS,
        "restart_required": False,
    }

@router.post("/admin/models/config")
async def save_model_config(
    request: ModelConfigRequest,
    current_user=Depends(require_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """保存模型配置，重启服务后对模型实例生效"""
    device = "cuda" if request.use_gpu else "cpu"

    if request.default_model and request.default_model not in config.AVAILABLE_MODELS:
        raise HTTPException(status_code=400, detail=f"不支持的默认模型: {request.default_model}")

    await upsert_config(db, "device", device, "Model inference device: cpu or cuda")

    if request.default_model:
        await upsert_config(db, "default_model", request.default_model, "Default translation model")
        config.DEFAULT_MODEL = request.default_model

    await db.commit()
    config.DEVICE = device

    return {
        "success": True,
        "message": "模型配置已保存，重启服务后对已初始化模型生效",
        "device": device,
        "use_gpu": request.use_gpu,
        "default_model": request.default_model or config.DEFAULT_MODEL,
        "restart_required": True,
    }

@router.get("/admin/models/status")
async def get_models_status(current_user=Depends(require_admin_user)):
    """获取所有模型状态和已下载的模型"""
    argos_available = importlib.util.find_spec("argostranslate") is not None
    transformers_available = importlib.util.find_spec("transformers") is not None
    ctranslate2_available = importlib.util.find_spec("ctranslate2") is not None

    # 检查 Argos 已安装的包
    argos_packages = []
    argos_ready_pairs = []
    if argos_available:
        try:
            import argostranslate.package
            installed = argostranslate.package.get_installed_packages()
            for pkg in installed:
                argos_packages.append(f"{pkg.from_code}→{pkg.to_code}")
                argos_ready_pairs.append(f"{pkg.from_code}-{pkg.to_code}")
        except Exception:
            argos_available = False

    # 检查 HuggingFace 缓存的模型
    huggingface_models = []
    cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
    if os.path.exists(cache_dir):
        try:
            models = [d for d in os.listdir(cache_dir) if d.startswith("models--")]
            for m in models:
                # 提取模型名称
                model_name = m.replace("models--", "").replace("--", "/")
                huggingface_models.append(model_name)
        except:
            pass

    # 判断各模型的下载状态。目录存在不代表模型完整，必须有权重文件。
    marian_models = [
        m for m in huggingface_models
        if ("Helsinki-NLP" in m or "opus-mt" in m) and has_huggingface_model_files(m)
    ]
    marian_cache_models = [
        m for m in huggingface_models
        if "Helsinki-NLP" in m or "opus-mt" in m
    ]
    m2m100_models = [
        m for m in huggingface_models
        if m == config.M2M100_MODEL and has_huggingface_model_files(m)
    ]
    m2m100_cache_models = [
        m for m in huggingface_models
        if m == config.M2M100_MODEL
    ]
    m2m100_large_models = [
        m for m in huggingface_models
        if m == config.M2M100_LARGE_MODEL and has_huggingface_model_files(m)
    ]
    m2m100_large_cache_models = [
        m for m in huggingface_models
        if m == config.M2M100_LARGE_MODEL
    ]
    nllb_models = [
        m for m in huggingface_models
        if m == config.NLLB_MODEL and has_huggingface_model_files(m)
    ]
    nllb_cache_models = [
        m for m in huggingface_models
        if m == config.NLLB_MODEL
    ]
    marian_downloaded = len(marian_models) > 0
    m2m100_downloaded = len(m2m100_models) > 0
    m2m100_large_downloaded = len(m2m100_large_models) > 0
    nllb_downloaded = len(nllb_models) > 0
    marian_ready_pairs = []
    marian_ct2_models = [
        model for model in marian_models
        if has_ct2_model_files(model)
    ]
    for model in marian_models:
        name = model.split("/")[-1]
        if name.startswith("opus-mt-"):
            parts = name.replace("opus-mt-", "").split("-")
            if len(parts) >= 2:
                marian_ready_pairs.append(f"{parts[0]}-{parts[1]}")

    m2m100_ready_pairs = build_all_language_pairs(MULTILINGUAL_UI_LANGS) if m2m100_downloaded else []
    m2m100_large_ready_pairs = build_all_language_pairs(MULTILINGUAL_UI_LANGS) if m2m100_large_downloaded else []
    nllb_ready_pairs = build_all_language_pairs(MULTILINGUAL_UI_LANGS) if nllb_downloaded else []
    m2m100_ct2_models = [
        model for model in m2m100_models
        if has_ct2_model_files(model)
    ]
    m2m100_large_ct2_models = [
        model for model in m2m100_large_models
        if has_ct2_model_files(model)
    ]

    return {
        "argos": {
            "loaded": argos_available,
            "type": "offline",
            "size": "50-100MB/package",
            "downloaded_packages": argos_packages,
            "ready_pairs": sorted(argos_ready_pairs),
            "has_downloads": len(argos_packages) > 0
        },
        "marian": {
            "loaded": transformers_available and marian_downloaded,
            "type": "neural",
            "size": "200-300MB",
            "downloaded_models": marian_models,
            "cached_models": marian_cache_models,
            "ctranslate2_available": ctranslate2_available,
            "ctranslate2_models": marian_ct2_models,
            "backend": config.MARIAN_BACKEND,
            "cache_incomplete": len(marian_cache_models) > len(marian_models),
            "ready_pairs": sorted(marian_ready_pairs),
            "has_downloads": marian_downloaded
        },
        "m2m100": {
            "loaded": transformers_available and m2m100_downloaded,
            "type": "multilingual",
            "size": "1.2GB",
            "downloaded_models": m2m100_models,
            "cached_models": m2m100_cache_models,
            "ctranslate2_available": ctranslate2_available,
            "ctranslate2_models": m2m100_ct2_models,
            "backend": config.M2M100_BACKEND,
            "cache_incomplete": len(m2m100_cache_models) > len(m2m100_models),
            "ready_pairs": sorted(m2m100_ready_pairs),
            "has_downloads": m2m100_downloaded
        },
        "m2m100_1_2b": {
            "loaded": transformers_available and m2m100_large_downloaded,
            "type": "multilingual",
            "size": "4.5GB",
            "downloaded_models": m2m100_large_models,
            "cached_models": m2m100_large_cache_models,
            "ctranslate2_available": ctranslate2_available,
            "ctranslate2_models": m2m100_large_ct2_models,
            "backend": config.M2M100_BACKEND,
            "cache_incomplete": len(m2m100_large_cache_models) > len(m2m100_large_models),
            "ready_pairs": sorted(m2m100_large_ready_pairs),
            "has_downloads": m2m100_large_downloaded
        },
        "nllb": {
            "loaded": transformers_available and nllb_downloaded,
            "type": "multilingual",
            "size": "2.5GB+",
            "downloaded_models": nllb_models,
            "cached_models": nllb_cache_models,
            "cache_incomplete": len(nllb_cache_models) > len(nllb_models),
            "ready_pairs": sorted(nllb_ready_pairs),
            "has_downloads": nllb_downloaded
        }
    }

@router.get("/admin/models/marian/available")
async def list_available_marian_models(current_user=Depends(require_admin_user)):
    """列出可用的 MarianMT 模型"""
    # 常用的 MarianMT 模型列表
    models = [
        {
            "model_name": "Helsinki-NLP/opus-mt-en-zh",
            "from_lang": "en",
            "to_lang": "zh",
            "from_name": "English",
            "to_name": "Chinese",
            "size": "~300MB",
            "quality": "high"
        },
        {
            "model_name": "Helsinki-NLP/opus-mt-zh-en",
            "from_lang": "zh",
            "to_lang": "en",
            "from_name": "Chinese",
            "to_name": "English",
            "size": "~300MB",
            "quality": "high"
        },
        {
            "model_name": "Helsinki-NLP/opus-mt-en-ja",
            "from_lang": "en",
            "to_lang": "ja",
            "from_name": "English",
            "to_name": "Japanese",
            "size": "~300MB",
            "quality": "high"
        },
        {
            "model_name": "Helsinki-NLP/opus-mt-ja-en",
            "from_lang": "ja",
            "to_lang": "en",
            "from_name": "Japanese",
            "to_name": "English",
            "size": "~300MB",
            "quality": "high"
        },
        {
            "model_name": "Helsinki-NLP/opus-mt-en-fr",
            "from_lang": "en",
            "to_lang": "fr",
            "from_name": "English",
            "to_name": "French",
            "size": "~300MB",
            "quality": "high"
        },
        {
            "model_name": "Helsinki-NLP/opus-mt-en-de",
            "from_lang": "en",
            "to_lang": "de",
            "from_name": "English",
            "to_name": "German",
            "size": "~300MB",
            "quality": "high"
        },
        {
            "model_name": "Helsinki-NLP/opus-mt-en-es",
            "from_lang": "en",
            "to_lang": "es",
            "from_name": "English",
            "to_name": "Spanish",
            "size": "~300MB",
            "quality": "high"
        },
        {
            "model_name": "Helsinki-NLP/opus-mt-en-ru",
            "from_lang": "en",
            "to_lang": "ru",
            "from_name": "English",
            "to_name": "Russian",
            "size": "~300MB",
            "quality": "high"
        }
    ]

    # 检查哪些模型已下载
    try:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        import os
        cache_dir = os.path.expanduser("~/.cache/huggingface/hub")

        for model in models:
            # 简单检查：看缓存目录是否存在该模型
            model_dir_name = model["model_name"].replace("/", "--")
            model["downloaded"] = has_huggingface_model_files(model["model_name"])
            model["ctranslate2_converted"] = has_ct2_model_files(model["model_name"])
    except:
        # 如果检查失败，都标记为未下载
        for model in models:
            model["downloaded"] = False
            model["ctranslate2_converted"] = False

    return {"models": models}

@router.post("/admin/models/marian/download")
async def download_marian_model(
    model_name: str,
    current_user=Depends(require_admin_user)
):
    """下载 MarianMT 模型"""
    available_models = {
        model["model_name"]
        for model in (await list_available_marian_models(current_user))["models"]
    }
    is_valid_opus_model = re.fullmatch(r"Helsinki-NLP/opus-mt-[A-Za-z0-9_-]+", model_name)
    if model_name not in available_models and not is_valid_opus_model:
        raise HTTPException(status_code=400, detail=f"不允许下载未知模型: {model_name}")

    task_id = create_download_task("marian", model_name)
    run_threaded_download(download_marian_model_task, task_id, model_name)

    return {
        "success": True,
        "task_id": task_id,
        "message": f"模型 {model_name} 下载任务已开始"
    }

def download_marian_model_task(task_id: str, model_name: str):
    stop_event = Event()
    monitor = Thread(
        target=monitor_huggingface_cache,
        args=(task_id, model_name, 20, 95, DEFAULT_MARIAN_SIZE_HINT, stop_event),
        daemon=True
    )

    try:
        from transformers import MarianMTModel, MarianTokenizer

        update_download_task(task_id, status="running", percent=5, message="准备下载 MarianMT 模型...")
        monitor.start()

        update_download_task(task_id, percent=15, message="下载分词器文件...")
        MarianTokenizer.from_pretrained(model_name)

        update_download_task(task_id, percent=30, message="下载模型权重文件...")
        MarianMTModel.from_pretrained(model_name)

        stop_event.set()
        if not has_huggingface_model_files(model_name):
            raise RuntimeError("模型下载结束，但未检测到完整权重文件")

        finish_download_task(task_id, f"模型 {model_name} 下载完成")

    except Exception as e:
        stop_event.set()
        fail_download_task(task_id, str(e))

@router.post("/admin/models/marian/convert-ct2")
async def convert_marian_model_to_ct2(
    model_name: str,
    current_user=Depends(require_admin_user)
):
    """将已下载的 MarianMT 模型转换为 CTranslate2 本地模型。"""
    if not has_huggingface_model_files(model_name):
        raise HTTPException(status_code=400, detail=f"模型 {model_name} 尚未完整下载，不能转换")

    if importlib.util.find_spec("ctranslate2") is None:
        raise HTTPException(status_code=500, detail="当前环境未安装 ctranslate2")

    task_id = create_download_task("marian_ct2", model_name)
    run_threaded_download(convert_marian_model_to_ct2_task, task_id, model_name)

    return {
        "success": True,
        "task_id": task_id,
        "message": f"模型 {model_name} CTranslate2 转换任务已开始"
    }

def convert_marian_model_to_ct2_task(task_id: str, model_name: str):
    try:
        from ctranslate2.converters import TransformersConverter

        update_download_task(task_id, status="running", percent=5, message="检查本地 MarianMT 模型...")
        snapshot_path = get_huggingface_snapshot_path(model_name)
        if not snapshot_path:
            raise RuntimeError(f"未找到 {model_name} 的本地 HuggingFace snapshot")

        output_dir = get_ct2_model_dir(model_name)
        parent_dir = os.path.dirname(output_dir)
        temp_output_dir = os.path.join(parent_dir, f".{os.path.basename(output_dir)}.{task_id}.tmp")
        backup_dir = os.path.join(parent_dir, f".{os.path.basename(output_dir)}.{task_id}.bak")
        os.makedirs(parent_dir, exist_ok=True)
        shutil.rmtree(temp_output_dir, ignore_errors=True)
        shutil.rmtree(backup_dir, ignore_errors=True)

        update_download_task(task_id, percent=20, message="准备 CTranslate2 转换器...")
        copy_candidates = [
            "tokenizer.json",
            "tokenizer_config.json",
            "source.spm",
            "target.spm",
            "vocab.json",
            "sentencepiece.bpe.model",
            "spiece.model",
            "special_tokens_map.json",
        ]
        copy_files = [
            file_name
            for file_name in copy_candidates
            if os.path.exists(os.path.join(snapshot_path, file_name))
        ]

        converter = TransformersConverter(
            snapshot_path,
            copy_files=copy_files
        )

        update_download_task(
            task_id,
            percent=45,
            message=f"正在转换为 CTranslate2 ({config.MARIAN_CT2_COMPUTE_TYPE})..."
        )
        converter.convert(
            temp_output_dir,
            quantization=config.MARIAN_CT2_COMPUTE_TYPE,
            force=False
        )

        update_download_task(task_id, percent=95, message="校验 CTranslate2 模型文件...")
        if not (
            os.path.isfile(os.path.join(temp_output_dir, "model.bin"))
            and os.path.isfile(os.path.join(temp_output_dir, "config.json"))
        ):
            raise RuntimeError("转换结束，但未检测到 CTranslate2 model.bin/config.json")

        if os.path.exists(output_dir):
            os.replace(output_dir, backup_dir)
        os.replace(temp_output_dir, output_dir)
        shutil.rmtree(backup_dir, ignore_errors=True)

        finish_download_task(task_id, f"模型 {model_name} 已转换为 CTranslate2: {output_dir}")

    except Exception as e:
        try:
            if "temp_output_dir" in locals():
                shutil.rmtree(temp_output_dir, ignore_errors=True)
            if "backup_dir" in locals() and os.path.exists(backup_dir) and not os.path.exists(output_dir):
                os.replace(backup_dir, output_dir)
        except Exception:
            pass
        fail_download_task(task_id, str(e))

@router.post("/admin/models/m2m100/download")
async def download_m2m100_model(current_user=Depends(require_admin_user)):
    """下载 M2M100 标准模型"""
    task_id = create_download_task("m2m100", config.M2M100_MODEL)
    run_threaded_download(download_m2m100_model_task, task_id, config.M2M100_MODEL)

    return {
        "success": True,
        "task_id": task_id,
        "message": f"模型 {config.M2M100_MODEL} 下载任务已开始"
    }

@router.post("/admin/models/m2m100-large/download")
async def download_m2m100_large_model(current_user=Depends(require_admin_user)):
    """下载 M2M100 1.2B 模型"""
    task_id = create_download_task("m2m100_1_2b", config.M2M100_LARGE_MODEL)
    run_threaded_download(download_m2m100_model_task, task_id, config.M2M100_LARGE_MODEL)

    return {
        "success": True,
        "task_id": task_id,
        "message": f"模型 {config.M2M100_LARGE_MODEL} 下载任务已开始"
    }

def download_m2m100_model_task(task_id: str, model_name: str):
    stop_event = Event()
    monitor = Thread(
        target=monitor_huggingface_cache,
        args=(task_id, model_name, 20, 95, MODEL_SIZE_HINTS.get(model_name, 1_250_000_000), stop_event),
        daemon=True
    )

    try:
        from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer

        update_download_task(task_id, status="running", percent=5, message="准备下载 M2M100 模型...")
        monitor.start()

        update_download_task(task_id, percent=15, message="下载分词器文件...")
        M2M100Tokenizer.from_pretrained(model_name)

        update_download_task(task_id, percent=30, message="下载模型权重文件...")
        M2M100ForConditionalGeneration.from_pretrained(model_name)

        stop_event.set()
        if not has_huggingface_model_files(model_name):
            raise RuntimeError("模型下载结束，但未检测到完整权重文件")

        finish_download_task(task_id, f"模型 {model_name} 下载完成")

    except Exception as e:
        stop_event.set()
        fail_download_task(task_id, str(e))

@router.post("/admin/models/m2m100/convert-ct2")
async def convert_m2m100_model_to_ct2(current_user=Depends(require_admin_user)):
    """将已下载的 M2M100 标准模型转换为 CTranslate2 本地模型。"""
    return start_m2m100_ct2_conversion(config.M2M100_MODEL, "m2m100_ct2")

@router.post("/admin/models/m2m100-large/convert-ct2")
async def convert_m2m100_large_model_to_ct2(current_user=Depends(require_admin_user)):
    """将已下载的 M2M100 1.2B 模型转换为 CTranslate2 本地模型。"""
    return start_m2m100_ct2_conversion(config.M2M100_LARGE_MODEL, "m2m100_1_2b_ct2")

def start_m2m100_ct2_conversion(model_name: str, kind: str):
    if not has_huggingface_model_files(model_name):
        raise HTTPException(status_code=400, detail=f"模型 {model_name} 尚未完整下载，不能转换")

    if importlib.util.find_spec("ctranslate2") is None:
        raise HTTPException(status_code=500, detail="当前环境未安装 ctranslate2")

    task_id = create_download_task(kind, model_name)
    run_threaded_download(convert_m2m100_model_to_ct2_task, task_id, model_name)

    return {
        "success": True,
        "task_id": task_id,
        "message": f"模型 {model_name} CTranslate2 转换任务已开始"
    }

def convert_m2m100_model_to_ct2_task(task_id: str, model_name: str):
    try:
        from ctranslate2.converters import TransformersConverter

        update_download_task(task_id, status="running", percent=5, message="检查本地 M2M100 模型...")
        snapshot_path = get_huggingface_snapshot_path(model_name)
        if not snapshot_path:
            raise RuntimeError(f"未找到 {model_name} 的本地 HuggingFace snapshot")

        output_dir = get_ct2_model_dir(model_name)
        parent_dir = os.path.dirname(output_dir)
        temp_output_dir = os.path.join(parent_dir, f".{os.path.basename(output_dir)}.{task_id}.tmp")
        backup_dir = os.path.join(parent_dir, f".{os.path.basename(output_dir)}.{task_id}.bak")
        os.makedirs(parent_dir, exist_ok=True)
        shutil.rmtree(temp_output_dir, ignore_errors=True)
        shutil.rmtree(backup_dir, ignore_errors=True)

        update_download_task(task_id, percent=20, message="准备 CTranslate2 转换器...")
        copy_candidates = [
            "tokenizer.json",
            "tokenizer_config.json",
            "sentencepiece.bpe.model",
            "vocab.json",
            "special_tokens_map.json",
            "generation_config.json",
        ]
        copy_files = [
            file_name
            for file_name in copy_candidates
            if os.path.exists(os.path.join(snapshot_path, file_name))
        ]

        converter = TransformersConverter(
            snapshot_path,
            copy_files=copy_files
        )

        update_download_task(
            task_id,
            percent=45,
            message=f"正在转换为 CTranslate2 ({config.M2M100_CT2_COMPUTE_TYPE})..."
        )
        converter.convert(
            temp_output_dir,
            quantization=config.M2M100_CT2_COMPUTE_TYPE,
            force=False
        )

        update_download_task(task_id, percent=95, message="校验 CTranslate2 模型文件...")
        if not (
            os.path.isfile(os.path.join(temp_output_dir, "model.bin"))
            and os.path.isfile(os.path.join(temp_output_dir, "config.json"))
        ):
            raise RuntimeError("转换结束，但未检测到 CTranslate2 model.bin/config.json")

        if os.path.exists(output_dir):
            os.replace(output_dir, backup_dir)
        os.replace(temp_output_dir, output_dir)
        shutil.rmtree(backup_dir, ignore_errors=True)

        finish_download_task(task_id, f"模型 {model_name} 已转换为 CTranslate2: {output_dir}")

    except Exception as e:
        try:
            if "temp_output_dir" in locals():
                shutil.rmtree(temp_output_dir, ignore_errors=True)
            if "backup_dir" in locals() and os.path.exists(backup_dir) and not os.path.exists(output_dir):
                os.replace(backup_dir, output_dir)
        except Exception:
            pass
        fail_download_task(task_id, str(e))

@router.post("/admin/models/nllb/download")
async def download_nllb_model(current_user=Depends(require_admin_user)):
    """下载 NLLB 模型"""
    task_id = create_download_task("nllb", config.NLLB_MODEL)
    run_threaded_download(download_nllb_model_task, task_id, config.NLLB_MODEL)

    return {
        "success": True,
        "task_id": task_id,
        "message": f"模型 {config.NLLB_MODEL} 下载任务已开始"
    }

def download_nllb_model_task(task_id: str, model_name: str):
    stop_event = Event()
    monitor = Thread(
        target=monitor_huggingface_cache,
        args=(task_id, model_name, 20, 95, MODEL_SIZE_HINTS.get(model_name, 2_500_000_000), stop_event),
        daemon=True
    )

    try:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        update_download_task(task_id, status="running", percent=5, message="准备下载 NLLB 模型...")
        monitor.start()

        update_download_task(task_id, percent=15, message="下载分词器文件...")
        AutoTokenizer.from_pretrained(model_name)

        update_download_task(task_id, percent=30, message="下载模型权重文件...")
        AutoModelForSeq2SeqLM.from_pretrained(model_name)

        stop_event.set()
        if not has_huggingface_model_files(model_name):
            raise RuntimeError("模型下载结束，但未检测到完整权重文件")

        finish_download_task(task_id, f"模型 {model_name} 下载完成")

    except Exception as e:
        stop_event.set()
        fail_download_task(task_id, str(e))

@router.get("/admin/models/argos/packages")
async def list_argos_packages(current_user=Depends(require_admin_user)):
    """列出 Argos 已安装的语言包"""
    try:
        import argostranslate.package
        installed = argostranslate.package.get_installed_packages()

        packages = []
        for pkg in installed:
            packages.append({
                "from_code": pkg.from_code,
                "to_code": pkg.to_code,
                "from_name": pkg.from_name,
                "to_name": pkg.to_name,
                "installed": True
            })

        return {"packages": packages}
    except Exception as e:
        return {"packages": [], "error": str(e)}

@router.post("/admin/models/argos/install")
async def install_argos_package(
    request: InstallRequest,
    current_user=Depends(require_admin_user)
):
    """安装 Argos 语言包"""
    task_id = create_download_task(
        "argos",
        f"{request.source_lang}->{request.target_lang}"
    )
    run_threaded_download(
        install_argos_package_task,
        task_id,
        request.source_lang,
        request.target_lang
    )

    return {
        "success": True,
        "task_id": task_id,
        "message": f"{request.source_lang} -> {request.target_lang} 语言包安装任务已开始"
    }

def install_argos_package_task(task_id: str, source_lang: str, target_lang: str):
    try:
        import argostranslate.package

        # 更新包索引
        update_download_task(task_id, status="running", percent=5, message="更新 Argos 语言包索引...")
        argostranslate.package.update_package_index()
        update_download_task(task_id, percent=20, message="读取可用语言包列表...")
        available = argostranslate.package.get_available_packages()

        # 查找包
        update_download_task(task_id, percent=30, message="查找目标语言包...")
        package_to_install = None
        for pkg in available:
            if pkg.from_code == source_lang and pkg.to_code == target_lang:
                package_to_install = pkg
                break

        if not package_to_install:
            raise RuntimeError(f"未找到 {source_lang} -> {target_lang} 语言包")

        # 检查是否已安装
        update_download_task(task_id, percent=40, message="检查本地安装状态...")
        installed = argostranslate.package.get_installed_packages()
        already_installed = any(
            pkg.from_code == source_lang and pkg.to_code == target_lang
            for pkg in installed
        )

        if already_installed:
            finish_download_task(task_id, "语言包已安装")
            return

        # 下载并安装
        update_download_task(task_id, percent=50, message="下载语言包文件...")
        download_path = package_to_install.download()
        update_download_task(task_id, percent=85, message="安装语言包...")
        argostranslate.package.install_from_path(download_path)

        finish_download_task(task_id, f"成功安装 {source_lang} -> {target_lang} 语言包")

    except Exception as e:
        fail_download_task(task_id, str(e))

@router.get("/admin/models/argos/available")
async def list_available_argos_packages(current_user=Depends(require_admin_user)):
    """列出可用的 Argos 语言包"""
    try:
        import argostranslate.package

        argostranslate.package.update_package_index()
        available = argostranslate.package.get_available_packages()
        installed = argostranslate.package.get_installed_packages()

        installed_pairs = {
            f"{pkg.from_code}-{pkg.to_code}"
            for pkg in installed
        }

        packages = []
        for pkg in available:
            pair = f"{pkg.from_code}-{pkg.to_code}"
            packages.append({
                "from_code": pkg.from_code,
                "to_code": pkg.to_code,
                "from_name": pkg.from_name,
                "to_name": pkg.to_name,
                "installed": pair in installed_pairs
            })

        return {"packages": packages}
    except Exception as e:
        return {"packages": [], "error": str(e)}
