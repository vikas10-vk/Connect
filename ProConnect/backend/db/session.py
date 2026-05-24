# =============================================================================
# db/session.py — Database engine and session factory
# Tradie Platform
# =============================================================================

from pathlib import Path
from dotenv import load_dotenv

# Walk up from this file's directory until we find a .env file.
# Structure: ProConnect/backend/db/session.py → look at backend/, then ProConnect/, etc.
def _find_dotenv(start: Path) -> Path | None:
    for parent in [start, *start.parents]:
        candidate = parent / ".env"
        if candidate.is_file():
            return candidate
    return None

_dotenv_path = _find_dotenv(Path(__file__).parent)
load_dotenv(dotenv_path=_dotenv_path, override=False)

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
from sqlalchemy.pool import NullPool          # ← NEW IMPORT

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. "
        "Check your .env file exists and contains DATABASE_URL."
    )

# =============================================================================
# IS_TEST flag
# =============================================================================
IS_TEST = os.getenv("ENVIRONMENT") == "test"

# =============================================================================
# Engine
# =============================================================================
#
# WHY NullPool IN TESTS:
#   asyncpg's connection pool binds to the event loop that created it.
#   In tests, tasks run across different async contexts, causing:
#     RuntimeError: Task <Task pending ...> attached to a different loop
#   NullPool opens a fresh connection per request and closes it immediately —
#   nothing is bound to any loop. Zero pool-related errors in tests.
#   Never use NullPool in production — it kills performance.
#
if IS_TEST:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        poolclass=NullPool,          # ← KEY FIX: no pool in test mode
    )
else:
    engine = create_async_engine(
        DATABASE_URL,
        echo=os.getenv("DEBUG", "false").lower() == "true",
        pool_size=int(os.getenv("DATABASE_POOL_SIZE", "10")),
        max_overflow=int(os.getenv("DATABASE_MAX_OVERFLOW", "20")),
        pool_pre_ping=True,
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