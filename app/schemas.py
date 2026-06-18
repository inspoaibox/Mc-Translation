"""
数据模型扩展
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime

# ===== 原有模型 =====
class TranslationRequest(BaseModel):
    text: str = Field(..., description="要翻译的文本", min_length=1)
    source_lang: str = Field(..., description="源语言代码")
    target_lang: str = Field(..., description="目标语言代码")
    model: Optional[str] = Field(None, description="指定使用的模型")

class TranslationResponse(BaseModel):
    translated_text: str
    model_used: str
    source_lang: str
    target_lang: str
    success: bool = True
    model_backend: Optional[str] = None
    actual_model_name: Optional[str] = None
    timing: Optional[dict] = None

class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    available_models: list
    message: str

# ===== 认证相关 =====
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class LoginRequest(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    is_superuser: bool = False

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    is_superuser: bool
    created_at: datetime

    class Config:
        from_attributes = True

# ===== API Key 相关 =====
class APIKeyCreate(BaseModel):
    name: str = Field(..., description="密钥名称")
    description: Optional[str] = Field(None, description="密钥描述")
    rate_limit: int = Field(100, ge=1, description="每个限流周期内的请求限制")
    expires_days: Optional[int] = Field(None, description="有效天数")

class APIKeyResponse(BaseModel):
    id: int
    key: str
    name: str
    description: Optional[str]
    is_active: bool
    rate_limit: int
    created_at: datetime
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True

# ===== 统计相关 =====
class TranslationStats(BaseModel):
    total_translations: int
    successful_translations: int
    failed_translations: int
    total_chars: int
    avg_response_time: float
    by_model: dict
    by_language: dict

class SystemStatus(BaseModel):
    status: str
    uptime: float
    total_requests: int
    active_api_keys: int
    available_models: list

class AdminSettings(BaseModel):
    default_model: str
    api_rate_limit: int = Field(..., ge=1)
    api_rate_limit_period: int = Field(..., ge=1)
    token_expire_minutes: int = Field(..., ge=1)

class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6)
