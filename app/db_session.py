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
        await ensure_lightweight_migrations(conn)


async def ensure_lightweight_migrations(conn):
    """Apply additive SQLite migrations for deployments without Alembic."""
    if not config.DATABASE_URL.startswith("sqlite"):
        return

    result = await conn.exec_driver_sql("PRAGMA table_info(translation_logs)")
    existing_columns = {row[1] for row in result.fetchall()}
    required_columns = {
        "model_backend": "VARCHAR",
        "actual_model_name": "VARCHAR",
        "model_load_time": "FLOAT DEFAULT 0",
        "inference_time": "FLOAT DEFAULT 0",
        "format_time": "FLOAT DEFAULT 0",
        "segment_count": "INTEGER DEFAULT 0",
        "batch_count": "INTEGER DEFAULT 0",
    }

    for column_name, column_type in required_columns.items():
        if column_name not in existing_columns:
            await conn.exec_driver_sql(
                f"ALTER TABLE translation_logs ADD COLUMN {column_name} {column_type}"
            )
