"""
本地翻译 API 主程序 - 带安全认证
"""
from fastapi import FastAPI, HTTPException, Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from starlette.concurrency import run_in_threadpool
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from threading import Thread
import time
import uvicorn

from .config import config
from .schemas import (
    TranslationRequest, TranslationResponse,
    LoginRequest, Token, UserResponse,
    APIKeyCreate, APIKeyResponse,
    TranslationStats, SystemStatus,
    AdminSettings, PasswordChangeRequest
)
from .models import ArgosTranslator, MarianTranslator, M2M100Translator, NLLBTranslator
from .database import User, APIKey, TranslationLog, SystemConfig
from .db_session import get_db, init_db
from .auth import (
    verify_password, get_password_hash, create_access_token,
    get_current_user_from_token, verify_api_key, generate_api_key, security
)
from .model_routes import router as model_router

# 全局翻译器实例
translators = {}
start_time = time.time()
download_status = {}  # 记录模型下载状态

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    print("正在初始化数据库...")
    await init_db()

    # 创建默认管理员账号
    async for db in get_db():
        result = await db.execute(select(User).where(User.username == config.ADMIN_USERNAME))
        admin = result.scalar_one_or_none()

        if not admin:
            admin = User(
                username=config.ADMIN_USERNAME,
                email=config.ADMIN_EMAIL,
                hashed_password=get_password_hash(config.ADMIN_PASSWORD),
                is_active=True,
                is_superuser=True
            )
            db.add(admin)
            await db.commit()
            print(f"[OK] 创建默认管理员: {config.ADMIN_USERNAME}")

        config_result = await db.execute(select(SystemConfig).where(SystemConfig.key.in_([
            "device",
            "default_model",
            "api_rate_limit",
            "access_token_expire_minutes",
        ])))
        saved_config = {item.key: item.value for item in config_result.scalars().all()}

        if saved_config.get("device") in {"cpu", "cuda"}:
            config.DEVICE = saved_config["device"]

        if saved_config.get("default_model") in config.AVAILABLE_MODELS:
            config.DEFAULT_MODEL = saved_config["default_model"]

        if saved_config.get("api_rate_limit"):
            try:
                config.API_RATE_LIMIT = int(saved_config["api_rate_limit"])
            except ValueError:
                pass

        if saved_config.get("access_token_expire_minutes"):
            try:
                config.ACCESS_TOKEN_EXPIRE_MINUTES = int(saved_config["access_token_expire_minutes"])
            except ValueError:
                pass

    print("正在初始化翻译器...")
    translators["argos"] = ArgosTranslator()
    Thread(
        target=translators["argos"].warm_up,
        args=(config.ARGOS_WARMUP_PAIRS,),
        daemon=True
    ).start()
    translators["marian"] = MarianTranslator(device=config.DEVICE)
    translators["m2m100"] = M2M100Translator(device=config.DEVICE)
    translators["m2m100_1_2b"] = M2M100Translator(
        model_name=config.M2M100_LARGE_MODEL,
        device=config.DEVICE
    )
    translators["nllb"] = NLLBTranslator(
        model_name=config.NLLB_MODEL,
        device=config.DEVICE
    )
    print("[OK] 翻译器初始化完成")

    yield

    # 关闭时清理
    translators.clear()

# 创建应用
app = FastAPI(
    title=config.API_TITLE,
    version=config.API_VERSION,
    description=config.API_DESCRIPTION,
    lifespan=lifespan
)

# 挂载静态文件和模板
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载模型管理路由
app.include_router(model_router)

# ===== 公开接口 =====

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "翻译 API 运行中",
        "version": config.API_VERSION,
        "docs": "/docs",
        "admin": "/admin/login"
    }

@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "healthy",
        "version": config.API_VERSION,
        "uptime": int(time.time() - start_time)
    }

# ===== 管理后台页面 =====

@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """管理员登录页面"""
    return templates.TemplateResponse(
        request=request, name="login.html"
    )

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard_page(request: Request):
    """管理后台页面"""
    return templates.TemplateResponse(
        request=request, name="admin.html"
    )

# ===== 认证接口 =====

@app.post("/admin/login", response_model=Token)
async def login(login_data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """管理员登录"""
    result = await db.execute(select(User).where(User.username == login_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="账号已被禁用")

    # 生成 token
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return {"access_token": access_token, "token_type": "bearer"}

# ===== API 密钥管理 =====

@app.get("/admin/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db)
):
    """获取所有 API 密钥"""
    current_user = await get_current_user_from_token(credentials.credentials, db)
    result = await db.execute(select(APIKey).order_by(APIKey.created_at.desc()))
    keys = result.scalars().all()
    return keys

@app.post("/admin/api-keys", response_model=APIKeyResponse)
async def create_api_key(
    key_data: APIKeyCreate,
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db)
):
    """创建新的 API 密钥"""
    current_user = await get_current_user_from_token(credentials.credentials, db)
    new_key = APIKey(
        key=generate_api_key(),
        name=key_data.name,
        description=key_data.description,
        rate_limit=key_data.rate_limit,
        created_by=current_user.id,
        expires_at=datetime.utcnow() + timedelta(days=key_data.expires_days) if key_data.expires_days else None
    )
    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)
    return new_key

@app.delete("/admin/api-keys/{key_id}")
async def delete_api_key(
    key_id: int,
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db)
):
    """删除 API 密钥"""
    current_user = await get_current_user_from_token(credentials.credentials, db)
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    key = result.scalar_one_or_none()

    if not key:
        raise HTTPException(status_code=404, detail="密钥不存在")

    await db.delete(key)
    await db.commit()
    return {"message": "删除成功"}

# ===== 管理后台测试翻译接口（使用 JWT 认证）=====

@app.post("/admin/test-translate", response_model=TranslationResponse)
async def admin_test_translate(
    request: TranslationRequest,
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db)
):
    """管理后台翻译测试（使用 JWT Token 认证）"""
    # 验证用户
    current_user = await get_current_user_from_token(credentials.credentials, db)

    start = time.time()
    model_name = request.model or config.DEFAULT_MODEL

    try:
        if model_name not in config.AVAILABLE_MODELS:
            raise HTTPException(status_code=400, detail=f"不支持的模型: {model_name}")

        translator = translators.get(model_name)
        if not translator:
            raise HTTPException(status_code=500, detail=f"模型 {model_name} 未初始化")

        # 标记正在翻译
        download_status[f"{model_name}_{request.source_lang}_{request.target_lang}"] = {
            "status": "translating",
            "message": "正在翻译...",
            "model": model_name
        }

        # 执行翻译。模型推理是阻塞任务，放入线程池避免卡住事件循环。
        translated_text = await run_in_threadpool(
            translator.translate,
            text=request.text,
            source_lang=request.source_lang,
            target_lang=request.target_lang
        )

        # 清除状态
        download_status.pop(f"{model_name}_{request.source_lang}_{request.target_lang}", None)

        if translated_text is None:
            raise HTTPException(status_code=400, detail=f"模型 {model_name} 翻译失败或不支持该语言对")

        return TranslationResponse(
            translated_text=translated_text,
            model_used=model_name,
            source_lang=request.source_lang,
            target_lang=request.target_lang,
            success=True
        )

    except HTTPException:
        raise
    except Exception as e:
        # 记录错误状态
        download_status[f"{model_name}_{request.source_lang}_{request.target_lang}"] = {
            "status": "error",
            "message": str(e),
            "model": model_name
        }
        raise HTTPException(status_code=500, detail=f"翻译错误: {str(e)}")

@app.get("/admin/translate-status")
async def get_translate_status(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db)
):
    """获取翻译/下载状态"""
    current_user = await get_current_user_from_token(credentials.credentials, db)
    return download_status

# ===== 统计接口 =====

@app.get("/admin/stats")
async def get_stats(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db)
):
    """获取翻译统计"""
    current_user = await get_current_user_from_token(credentials.credentials, db)
    # 总翻译次数
    total_result = await db.execute(select(func.count(TranslationLog.id)))
    total = total_result.scalar() or 0

    # 成功次数
    success_result = await db.execute(
        select(func.count(TranslationLog.id)).where(TranslationLog.success == True)
    )
    success = success_result.scalar() or 0

    # 平均响应时间
    avg_time_result = await db.execute(select(func.avg(TranslationLog.response_time)))
    avg_time = avg_time_result.scalar() or 0

    # 总字符数
    total_chars_result = await db.execute(select(func.sum(TranslationLog.char_count)))
    total_chars = total_chars_result.scalar() or 0

    # 模型分布
    model_result = await db.execute(
        select(TranslationLog.model_used, func.count(TranslationLog.id))
        .group_by(TranslationLog.model_used)
    )
    by_model = {model: count for model, count in model_result.all()}

    # 语言对分布
    language_result = await db.execute(
        select(TranslationLog.source_lang, TranslationLog.target_lang, func.count(TranslationLog.id))
        .group_by(TranslationLog.source_lang, TranslationLog.target_lang)
    )
    by_language = {
        f"{source}->{target}": count
        for source, target, count in language_result.all()
    }

    # 活跃密钥数
    active_keys_result = await db.execute(
        select(func.count(APIKey.id)).where(APIKey.is_active == True)
    )
    active_keys = active_keys_result.scalar() or 0

    return {
        "total_translations": total,
        "successful_translations": success,
        "failed_translations": total - success,
        "total_chars": total_chars,
        "avg_response_time": round(avg_time * 1000, 2) if avg_time else 0,
        "by_model": by_model,
        "by_language": by_language,
        "success_rate": round(success / total * 100, 2) if total > 0 else 0,
        "active_keys": active_keys
    }

@app.get("/admin/logs")
async def list_translation_logs(
    limit: int = 50,
    offset: int = 0,
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db)
):
    """获取翻译调用日志"""
    current_user = await get_current_user_from_token(credentials.credentials, db)
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    total_result = await db.execute(select(func.count(TranslationLog.id)))
    total = total_result.scalar() or 0

    result = await db.execute(
        select(TranslationLog, APIKey.name, APIKey.key)
        .outerjoin(APIKey, TranslationLog.api_key_id == APIKey.id)
        .order_by(TranslationLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    logs = []
    for log, key_name, key_value in result.all():
        masked_key = None
        if key_value:
            masked_key = f"{key_value[:8]}...{key_value[-6:]}"

        logs.append({
            "id": log.id,
            "created_at": log.created_at,
            "api_key_name": key_name or "后台测试",
            "api_key": masked_key,
            "source_lang": log.source_lang,
            "target_lang": log.target_lang,
            "model_used": log.model_used,
            "char_count": log.char_count,
            "success": log.success,
            "error_message": log.error_message,
            "response_time_ms": round((log.response_time or 0) * 1000, 2),
        })

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "logs": logs,
    }

@app.get("/admin/settings")
async def get_admin_settings(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db)
):
    """获取系统设置"""
    current_user = await get_current_user_from_token(credentials.credentials, db)

    return {
        "default_model": config.DEFAULT_MODEL,
        "api_rate_limit": config.API_RATE_LIMIT,
        "token_expire_minutes": config.ACCESS_TOKEN_EXPIRE_MINUTES,
        "device": config.DEVICE,
        "version": config.API_VERSION,
        "database": "SQLite",
        "available_models": config.AVAILABLE_MODELS,
    }

async def upsert_system_config(db: AsyncSession, key: str, value: str, description: str):
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    item = result.scalar_one_or_none()
    if item:
        item.value = value
        item.description = description
    else:
        db.add(SystemConfig(key=key, value=value, description=description))

@app.post("/admin/settings")
async def save_admin_settings(
    settings: AdminSettings,
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db)
):
    """保存系统设置"""
    current_user = await get_current_user_from_token(credentials.credentials, db)

    if settings.default_model not in config.AVAILABLE_MODELS:
        raise HTTPException(status_code=400, detail=f"不支持的默认模型: {settings.default_model}")

    await upsert_system_config(db, "default_model", settings.default_model, "Default translation model")
    await upsert_system_config(db, "api_rate_limit", str(settings.api_rate_limit), "Default API key rate limit")
    await upsert_system_config(
        db,
        "access_token_expire_minutes",
        str(settings.token_expire_minutes),
        "Admin JWT expiry in minutes"
    )
    await db.commit()

    config.DEFAULT_MODEL = settings.default_model
    config.API_RATE_LIMIT = settings.api_rate_limit
    config.ACCESS_TOKEN_EXPIRE_MINUTES = settings.token_expire_minutes

    return {
        "success": True,
        "message": "系统设置已保存",
        "settings": settings.model_dump(),
    }

@app.post("/admin/change-password")
async def change_admin_password(
    request: PasswordChangeRequest,
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db)
):
    """修改当前管理员密码"""
    current_user = await get_current_user_from_token(credentials.credentials, db)

    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="当前密码错误")

    current_user.hashed_password = get_password_hash(request.new_password)
    await db.commit()

    return {"success": True, "message": "密码已修改，请重新登录"}

# ===== 翻译接口（需要 API Key）=====

async def get_api_key_from_header(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> APIKey:
    """从请求头获取并验证 API Key"""
    api_key = request.headers.get("X-API-Key")

    if not api_key:
        raise HTTPException(status_code=401, detail="缺少 API Key")

    key_obj = await verify_api_key(api_key, db)

    if not key_obj:
        raise HTTPException(status_code=401, detail="无效的 API Key")

    window_start = datetime.utcnow() - timedelta(seconds=config.API_RATE_LIMIT_PERIOD)
    usage_result = await db.execute(
        select(func.count(TranslationLog.id)).where(
            TranslationLog.api_key_id == key_obj.id,
            TranslationLog.created_at >= window_start
        )
    )
    usage_count = usage_result.scalar() or 0
    if usage_count >= key_obj.rate_limit:
        raise HTTPException(status_code=429, detail="超过 API Key 速率限制")

    return key_obj

@app.post("/translate", response_model=TranslationResponse)
async def translate(
    request: TranslationRequest,
    api_key: APIKey = Depends(get_api_key_from_header),
    db: AsyncSession = Depends(get_db)
):
    """翻译接口"""
    start = time.time()
    model_name = request.model or config.DEFAULT_MODEL
    translated_text = None
    error_msg = None

    try:
        if model_name not in config.AVAILABLE_MODELS:
            raise HTTPException(status_code=400, detail=f"不支持的模型: {model_name}")

        translator = translators.get(model_name)
        if not translator:
            raise HTTPException(status_code=500, detail=f"模型 {model_name} 未初始化")

        # 执行翻译。模型推理是阻塞任务，放入线程池避免卡住事件循环。
        translated_text = await run_in_threadpool(
            translator.translate,
            text=request.text,
            source_lang=request.source_lang,
            target_lang=request.target_lang
        )

        if translated_text is None:
            raise HTTPException(status_code=400, detail=f"模型 {model_name} 翻译失败或不支持该语言对")

        response_time = time.time() - start

        # 记录日志
        log = TranslationLog(
            api_key_id=api_key.id,
            source_lang=request.source_lang,
            target_lang=request.target_lang,
            model_used=model_name,
            char_count=len(request.text),
            success=True,
            response_time=response_time
        )
        db.add(log)
        await db.commit()

        return TranslationResponse(
            translated_text=translated_text,
            model_used=model_name,
            source_lang=request.source_lang,
            target_lang=request.target_lang,
            success=True
        )

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        response_time = time.time() - start

        # 记录失败日志
        log = TranslationLog(
            api_key_id=api_key.id,
            source_lang=request.source_lang,
            target_lang=request.target_lang,
            model_used=model_name,
            char_count=len(request.text),
            success=False,
            error_message=error_msg,
            response_time=response_time
        )
        db.add(log)
        await db.commit()

        raise HTTPException(status_code=500, detail=f"翻译错误: {error_msg}")

def main():
    """启动服务器"""
    print("=" * 60)
    print("翻译 API v2.0 启动中...")
    print("=" * 60)
    print(f"管理后台: http://localhost:8000/admin/login")
    print(f"API 文档: http://localhost:8000/docs")
    print(f"默认账号: {config.ADMIN_USERNAME} / {config.ADMIN_PASSWORD}")
    print("=" * 60)

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()
