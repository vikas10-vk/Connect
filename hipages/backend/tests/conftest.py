# =============================================================================
# tests/conftest.py — Pytest fixtures
# Tradie Platform
# =============================================================================
#
# Adapted to your existing folder structure:
#   db/session.py (not app/database.py)
#   models/ (not app/models/)
# =============================================================================

import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from db.session import Base, get_db, DATABASE_URL
from security import create_access_token


# =============================================================================
# Pytest configuration
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Test database — separate DB so tests never touch your dev data
# =============================================================================

TEST_DATABASE_URL = DATABASE_URL.replace(
    f"/{DATABASE_URL.split('/')[-1]}",
    "/tradie_test",
)


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """Creates all tables once for the test session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_connection(db_engine) -> AsyncGenerator[AsyncConnection, None]:
    """
    Each test gets a transaction that is rolled back after the test.
    Tests never leave data behind — no cleanup needed between tests.
    """
    async with db_engine.connect() as connection:
        await connection.begin()
        yield connection
        await connection.rollback()


@pytest_asyncio.fixture
async def db_session(db_connection) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        bind=db_connection,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session


# =============================================================================
# Test app and HTTP client
# =============================================================================

@pytest_asyncio.fixture
async def app(db_session):
    """Test app with DB dependency overridden to use the test session."""
    from main import app as fastapi_app

    async def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Content-Type": "application/json"},
    ) as c:
        yield c


# =============================================================================
# Auth fixtures
# =============================================================================

@pytest.fixture
def homeowner_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def tradie_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def homeowner_token(homeowner_id: uuid.UUID) -> str:
    return create_access_token(
        user_id=homeowner_id, role="homeowner",
        is_verified=True, is_active=True,
    )


@pytest.fixture
def tradie_token(tradie_id: uuid.UUID) -> str:
    return create_access_token(
        user_id=tradie_id, role="tradie",
        is_verified=True, is_active=True,
    )


@pytest.fixture
def auth_headers(homeowner_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {homeowner_token}"}


@pytest.fixture
def tradie_auth_headers(tradie_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {tradie_token}"}


# =============================================================================
# Data factories
# =============================================================================

@pytest.fixture
def make_user_data():
    def _factory(role: str = "homeowner", email: str | None = None) -> dict[str, Any]:
        suffix = uuid.uuid4().hex[:8]
        return {
            "email": email or f"test_{suffix}@example.com",
            "password": "SecurePass123!",
            "role": role,
            "first_name": "Test",
            "last_name": "User",
            "phone": f"+6140000{suffix[:4]}",
        }
    return _factory


@pytest.fixture
def make_job_data():
    def _factory(title: str = "Fix leaking tap", category: str = "plumbing") -> dict[str, Any]:
        return {
            "title": title,
            "description": "Needs fixing urgently.",
            "category": category,
            "suburb": "Sydney CBD",
            "postcode": "2000",
            "urgency": "within_week",
            "budget_min_cents": 10000,
            "budget_max_cents": 30000,
        }
    return _factory