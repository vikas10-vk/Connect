# =============================================================================
# tests/conftest.py — Shared fixtures for the entire test suite
# Tradie Platform
# =============================================================================
#
# FIXES FROM ORIGINAL:
#   - make_user_data now sends full_name instead of first_name + last_name
#     (the User model and registration schema use full_name)
#   - generate_and_send is mocked so registration never tries to send real emails
#   - Separate fixtures for homeowner and tradie auth headers
#   - other_headers fixture for IDOR tests (a second user who doesn't own the resource)
# =============================================================================

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# =============================================================================
# App import — done here so PYTHONPATH=. resolves correctly
# =============================================================================

from main import app


# =============================================================================
# HTTP client
# =============================================================================

@pytest_asyncio.fixture
async def client():
    """
    Async HTTP client that talks directly to the FastAPI app in-process.
    No real TCP connections — uses ASGITransport.
    All tests share the same test database set up by Alembic migrations in CI.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# =============================================================================
# User data factory
# =============================================================================

def make_user_data(**overrides) -> dict:
    """
    Build a valid registration payload.

    Uses full_name — this is what the User model and registration schema expect.
    Each call generates a unique email so tests don't collide.
    The default role is homeowner. Pass role="tradie" to make a tradie.
    The password satisfies bcrypt's 72-byte limit and common complexity rules.
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
# Registration helper (internal — used by fixtures below)
# =============================================================================

async def _register(client: AsyncClient, data: dict) -> dict:
    """
    Register a user via the API.
    Mocks generate_and_send so no OTP email is attempted.
    Returns the registration response JSON.
    """
    with patch(
        "routers.auth.generate_and_send",
        new_callable=AsyncMock,
        return_value=(True, None),   # (success, error_message)
    ):
        resp = await client.post("/api/v1/auth/register", json=data)

    assert resp.status_code == 201, (
        f"Registration failed ({resp.status_code}): {resp.text}\n"
        f"Payload sent: {data}"
    )
    return resp.json()


async def _login(client: AsyncClient, email: str, password: str) -> dict:
    """Login and return the full response JSON (access_token, refresh_token, etc.)"""
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
    """
    A registered homeowner.
    Returns the original registration payload (has email + password for login).
    """
    data = make_user_data(role="homeowner")
    await _register(client, data)
    return data


@pytest_asyncio.fixture
async def homeowner_tokens(client, homeowner_data) -> dict:
    """access_token and refresh_token for the homeowner."""
    return await _login(client, homeowner_data["email"], homeowner_data["password"])


@pytest_asyncio.fixture
async def homeowner_headers(homeowner_tokens) -> dict:
    """Authorization headers for the homeowner."""
    return {"Authorization": f"Bearer {homeowner_tokens['access_token']}"}


# =============================================================================
# Tradie fixtures
# =============================================================================

@pytest_asyncio.fixture
async def tradie_data(client) -> dict:
    """A registered tradie. Returns registration payload."""
    data = make_user_data(role="tradie")
    await _register(client, data)
    return data


@pytest_asyncio.fixture
async def tradie_tokens(client, tradie_data) -> dict:
    """access_token and refresh_token for the tradie."""
    return await _login(client, tradie_data["email"], tradie_data["password"])


@pytest_asyncio.fixture
async def tradie_headers(tradie_tokens) -> dict:
    """Authorization headers for the tradie."""
    return {"Authorization": f"Bearer {tradie_tokens['access_token']}"}


# =============================================================================
# Second homeowner — for IDOR tests
# =============================================================================

@pytest_asyncio.fixture
async def other_homeowner_headers(client) -> dict:
    """
    A completely separate homeowner account.
    Used to verify that user A cannot access or modify user B's resources.
    """
    data = make_user_data(role="homeowner", full_name="Other User")
    await _register(client, data)
    tokens = await _login(client, data["email"], data["password"])
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# =============================================================================
# Convenience aliases (shorter names for common fixtures)
# =============================================================================

# These let test functions use `auth_headers` instead of `homeowner_headers`
# when they don't care about the specific role.
@pytest_asyncio.fixture
async def auth_headers(homeowner_headers) -> dict:
    return homeowner_headers