# =============================================================================
# tests/conftest.py — Shared fixtures for the entire test suite
# Tradie Platform
# =============================================================================
#
# FIXES APPLIED:
#   - session-scoped event_loop: SQLAlchemy async engine is created once
#     and never crosses event loop boundaries ("attached to a different loop")
#   - LifespanManager: triggers app.state.redis_client setup + DB health check
#     (ASGITransport alone does NOT trigger FastAPI lifespan)
#   - generate_and_send mocked so registration never sends real emails
# =============================================================================

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from main import app


# =============================================================================
# Event loop — session scope prevents "attached to a different loop"
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """
    Single event loop shared across all tests.

    WHY: SQLAlchemy's async engine (asyncpg pool) is created once at module
    import. If each test gets its own loop (the default), the pool is created
    in loop-1 but tests 2-N run in loop-2 … loop-N → asyncpg raises
    "Future attached to a different loop".

    Using one session-scoped loop means the pool is always in scope.
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# HTTP client — session scope + LifespanManager
# =============================================================================

@pytest_asyncio.fixture(scope="session")
async def client():
    """
    Async HTTP client that talks directly to the FastAPI app in-process.

    LifespanManager is REQUIRED: ASGITransport does not call the ASGI lifespan.
    Without it, app.state.redis_client is never set and RateLimitMiddleware
    crashes on every request.

    Session scope means startup/shutdown runs once for the whole test suite,
    not once per test — dramatically faster and avoids pool churn.
    """
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app),
            base_url="http://test",
        ) as ac:
            yield ac


# =============================================================================
# User data factory
# =============================================================================

def make_user_data(**overrides) -> dict:
    """
    Build a valid registration payload.
    Each call generates a unique email so tests never collide.
    """
    data = {
        "email":     f"test_{uuid.uuid4().hex[:8]}@example.com",
        "password":  "SecurePass123!",
        "full_name": "Test User",
        "role":      "homeowner",
    }
    data.update(overrides)
    return data


# =============================================================================
# Registration / login helpers
# =============================================================================

async def _register(client: AsyncClient, data: dict) -> dict:
    with patch(
        "routers.auth.generate_and_send",
        new_callable=AsyncMock,
        return_value=(True, None),
    ):
        resp = await client.post("/api/v1/auth/register", json=data)

    assert resp.status_code == 201, (
        f"Registration failed ({resp.status_code}): {resp.text}\n"
        f"Payload sent: {data}"
    )
    return resp.json()


async def _login(client: AsyncClient, email: str, password: str) -> dict:
    resp = await client.post("/api/v1/auth/login", json={
        "email":    email,
        "password": password,
    })
    assert resp.status_code == 200, (
        f"Login failed ({resp.status_code}): {resp.text}"
    )
    return resp.json()


# =============================================================================
# Homeowner fixtures
# =============================================================================

@pytest_asyncio.fixture
async def homeowner_data(client) -> dict:
    data = make_user_data(role="homeowner")
    await _register(client, data)
    return data


@pytest_asyncio.fixture
async def homeowner_tokens(client, homeowner_data) -> dict:
    return await _login(client, homeowner_data["email"], homeowner_data["password"])


@pytest_asyncio.fixture
async def homeowner_headers(homeowner_tokens) -> dict:
    return {"Authorization": f"Bearer {homeowner_tokens['access_token']}"}


# =============================================================================
# Tradie fixtures
# =============================================================================

@pytest_asyncio.fixture
async def tradie_data(client) -> dict:
    data = make_user_data(role="tradie")
    await _register(client, data)
    return data


@pytest_asyncio.fixture
async def tradie_tokens(client, tradie_data) -> dict:
    return await _login(client, tradie_data["email"], tradie_data["password"])


@pytest_asyncio.fixture
async def tradie_headers(tradie_tokens) -> dict:
    return {"Authorization": f"Bearer {tradie_tokens['access_token']}"}


# =============================================================================
# Second homeowner — for IDOR tests
# =============================================================================

@pytest_asyncio.fixture
async def other_homeowner_headers(client) -> dict:
    data = make_user_data(role="homeowner", full_name="Other User")
    await _register(client, data)
    tokens = await _login(client, data["email"], data["password"])
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# =============================================================================
# Aliases
# =============================================================================

@pytest_asyncio.fixture
async def auth_headers(homeowner_headers) -> dict:
    return homeowner_headers