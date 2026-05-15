# =============================================================================
# tests/conftest.py — Shared fixtures for the entire test suite
# Tradie Platform
# =============================================================================
#
# FIXES:
#   - loop_scope="session" on the client fixture (pytest-asyncio 0.24.0 syntax)
#   - LifespanManager triggers app startup so app.state.redis_client is set
#   - Session scope means DB pool + Redis pool created once for all tests
#   - asyncio_default_fixture_loop_scope = session in pytest.ini removes warning
# =============================================================================

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from main import app
from db.session import AsyncSessionLocal
from models.category import Category, CategoryLevel


# =============================================================================
# Canonical trade categories — seeded once per test session
# =============================================================================
#
# The test DB starts empty. resolve_trade_category() does a DB lookup for the
# submitted category_slug (e.g. "plumbing"). Without these rows the resolver
# always returns None and every job-creation test fails with 400.
#
# This list mirrors the canonical slugs used throughout the codebase and tests.
# Level = TRADE (1), is_active = True, no parent.

_CANONICAL_CATEGORIES = [
    ("Plumbing",            "plumbing"),
    ("Electrical",          "electrical"),
    ("Carpentry",           "carpentry"),
    ("Painting",            "painting"),
    ("Landscaping",         "landscaping"),
    ("Roofing",             "roofing"),
    ("Tiling",              "tiling"),
    ("Concreting",          "concreting"),
    ("Fencing",             "fencing"),
    ("HVAC",                "hvac"),
    ("Glazing",             "glazing"),
    ("Pest Control",        "pest-control"),
    ("Security",            "security"),
    ("Solar",               "solar"),
    ("Gas Fitting",         "gas-fitting"),
    ("Demolition",          "demolition"),
    ("Waterproofing",       "waterproofing"),
    ("Cleaning",            "cleaning"),
    ("Handyman",            "handyman"),
    ("Building",            "building"),
    ("Bathroom Renovation", "bathroom-renovation"),
    ("Kitchen Renovation",  "kitchen-renovation"),
    ("Plastering",          "plastering"),
    ("Flooring",            "flooring"),
]


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def seed_categories():
    """
    Insert canonical level-1 trade categories once for the entire test session.
    Uses get-or-create so the fixture is safe to run against a DB that already
    has rows (idempotent).
    """
    async with AsyncSessionLocal() as db:
        for name, slug in _CANONICAL_CATEGORIES:
            result = await db.execute(
                select(Category).where(Category.slug == slug)
            )
            if result.scalar_one_or_none() is None:
                db.add(Category(
                    id=str(uuid.uuid4()),
                    name=name,
                    slug=slug,
                    level=CategoryLevel.TRADE,
                    is_active=True,
                ))
        await db.commit()


# =============================================================================
# HTTP client — session scope + LifespanManager
# =============================================================================

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def client():
    """
    Async HTTP client wired directly to the FastAPI ASGI app.

    WHY LifespanManager:
      ASGITransport does NOT trigger the FastAPI lifespan (startup/shutdown).
      Without it, app.state.redis_client is never created and
      RateLimitMiddleware crashes on every request with AttributeError.

    WHY session scope:
      - asyncpg connection pool is created once at engine creation.
        Crossing event loop boundaries causes "attached to a different loop".
      - Session scope means one loop, one pool, one Redis connection for
        the entire test run — much faster and no loop boundary errors.
    """
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app),
            base_url="http://test",
            timeout=30.0,
        ) as ac:
            yield ac


# =============================================================================
# User data factory
# =============================================================================

def make_user_data(**overrides) -> dict:
    """
    Build a valid registration payload.
    Unique email per call so tests never collide.
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
    """Register via API. Mocks the email sender so no real emails are sent."""
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
    """Login and return tokens."""
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

@pytest_asyncio.fixture(loop_scope="session")
async def homeowner_data(client) -> dict:
    data = make_user_data(role="homeowner")
    await _register(client, data)
    return data


@pytest_asyncio.fixture(loop_scope="session")
async def homeowner_tokens(client, homeowner_data) -> dict:
    return await _login(client, homeowner_data["email"], homeowner_data["password"])


@pytest_asyncio.fixture(loop_scope="session")
async def homeowner_headers(homeowner_tokens) -> dict:
    return {"Authorization": f"Bearer {homeowner_tokens['access_token']}"}


# =============================================================================
# Tradie fixtures
# =============================================================================

@pytest_asyncio.fixture(loop_scope="session")
async def tradie_data(client) -> dict:
    data = make_user_data(role="tradie")
    await _register(client, data)
    return data


@pytest_asyncio.fixture(loop_scope="session")
async def tradie_tokens(client, tradie_data) -> dict:
    return await _login(client, tradie_data["email"], tradie_data["password"])


@pytest_asyncio.fixture(loop_scope="session")
async def tradie_headers(tradie_tokens) -> dict:
    return {"Authorization": f"Bearer {tradie_tokens['access_token']}"}


# =============================================================================
# Second homeowner — for IDOR tests
# =============================================================================

@pytest_asyncio.fixture(loop_scope="session")
async def other_homeowner_headers(client) -> dict:
    """
    Separate homeowner account — used to verify user A cannot touch user B's
    resources (IDOR protection tests).
    """
    data = make_user_data(role="homeowner", full_name="Other User")
    await _register(client, data)
    tokens = await _login(client, data["email"], data["password"])
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# =============================================================================
# Aliases
# =============================================================================

@pytest_asyncio.fixture(loop_scope="session")
async def auth_headers(homeowner_headers) -> dict:
    return homeowner_headers
