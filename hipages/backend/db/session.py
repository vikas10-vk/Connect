# =============================================================================
# db/session.py — Database engine and session factory
# Tradie Platform
# =============================================================================

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

import logging
import os
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. "
        "Check your .env file exists and contains DATABASE_URL."
    )

# REMOVED: print("SESSION DATABASE_URL =", DATABASE_URL)
# This line logged the full database URL including password to stdout.
# Anyone with log access (CloudWatch, Papertrail, Docker logs) could see:
#   postgresql+asyncpg://tradie_app:MyRealPassword@postgres:5432/tradie_prod
# Never log connection strings, DSNs, or any value that contains credentials.

# =============================================================================
# Engine
# =============================================================================

engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("DEBUG", "false").lower() == "true",
    pool_size=int(os.getenv("DATABASE_POOL_SIZE", "10")),
    max_overflow=int(os.getenv("DATABASE_MAX_OVERFLOW", "20")),

    # Validate connections before returning from pool.
    # Prevents "connection already closed" errors after network interruptions.
    pool_pre_ping=True,

    # Recycle connections older than 30 minutes.
    pool_recycle=1800,

    pool_timeout=30,
)

# =============================================================================
# Session factory
# =============================================================================

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# =============================================================================
# Base — all models inherit from this
# =============================================================================

class Base(DeclarativeBase):
    pass


# =============================================================================
# get_db — FastAPI dependency
# =============================================================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(
                "Database error — rolled back",
                extra={"error": str(e), "type": type(e).__name__},
            )
            raise
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# =============================================================================
# Health check
# =============================================================================

async def check_database_health() -> bool:
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        row = result.fetchone()
        return row is not None and row[0] == 1