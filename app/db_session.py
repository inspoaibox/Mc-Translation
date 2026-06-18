"""
数据库连接和会话管理
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from .config import config
from .database import Base

# 创建异步引擎
engine = create_async_engine(
    config.DATABASE_URL,
    echo=False,
    future=True
)

# 创建异步会话工厂
async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db():
    """获取数据库会话"""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    """初始化数据库"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
