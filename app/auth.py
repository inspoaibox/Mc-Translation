"""
认证和安全相关
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import secrets

from .database import User, APIKey
from .config import config

# 密码加密 - 使用 Argon2
ph = PasswordHasher()

# Token 认证
security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    try:
        ph.verify(hashed_password, plain_password)
        return True
    except VerifyMismatchError:
        return False

def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return ph.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """创建 JWT Token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[str]:
    """验证 JWT Token"""
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError:
        return None

def generate_api_key() -> str:
    """生成 API 密钥"""
    return f"sk_{secrets.token_urlsafe(32)}"

async def get_current_user_from_token(
    token: str,
    db: AsyncSession
) -> User:
    """从 token 获取当前用户（内部函数）"""
    username = verify_token(token)

    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 从数据库查询用户
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已禁用"
        )

    return user

async def verify_api_key(api_key: str, db: AsyncSession) -> Optional[APIKey]:
    """验证 API Key"""
    result = await db.execute(select(APIKey).where(APIKey.key == api_key))
    key_obj = result.scalar_one_or_none()

    if not key_obj:
        return None

    if not key_obj.is_active:
        return None

    # 检查是否过期
    if key_obj.expires_at and key_obj.expires_at < datetime.utcnow():
        return None

    # 更新最后使用时间
    key_obj.last_used_at = datetime.utcnow()
    await db.commit()

    return key_obj
