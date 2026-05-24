# =============================================================================
# tests/test_auth.py — Authentication endpoint tests
# Tradie Platform
# =============================================================================
#
# ENDPOINTS COVERED:
#   POST /api/v1/auth/register
#   POST /api/v1/auth/login
#   GET  /api/v1/auth/me
#   POST /api/v1/auth/refresh
#   POST /api/v1/auth/logout
#   POST /api/v1/auth/logout-all
#
# WHAT IS TESTED (15 tests):
#   Registration:  success, duplicate email, missing fields, invalid role, weak password
#   Login:         success, wrong password, non-existent email
#   Me endpoint:   authenticated returns data, unauthenticated returns 401
#   Token:         access token is a real JWT, refresh rotates correctly
#   Logout:        clears the refresh token, reuse is rejected
#   Logout-all:    invalidates all sessions
# =============================================================================

import pytest
from unittest.mock import AsyncMock, patch

from conftest import make_user_data


class TestRegister:

    async def test_register_success(self, client):
        """
        A valid registration payload returns 201 with user data.
        The response must not contain the password.
        """
        data = make_user_data()
        with patch("routers.auth.generate_and_send", new_callable=AsyncMock, return_value=(True, None)):
            resp = await client.post("/api/v1/auth/register", json=data)

        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        body = resp.json()

        # Basic shape check
        assert "id" in body or "email" in body, f"Response missing user data: {body}"
        assert "password" not in body, "Password must never be returned in the response"
        assert "hashed_password" not in body, "Hashed password must never be returned"

    async def test_register_duplicate_email_rejected(self, client):
        """
        Registering with an already-used email must be rejected.
        Accepts 400 (Bad Request) or 409 (Conflict) — both are valid.
        """
        data = make_user_data()
        with patch("routers.auth.generate_and_send", new_callable=AsyncMock, return_value=(True, None)):
            await client.post("/api/v1/auth/register", json=data)
            resp2 = await client.post("/api/v1/auth/register", json=data)

        assert resp2.status_code in (400, 409), (
            f"Expected 400 or 409 for duplicate email, got {resp2.status_code}: {resp2.text}"
        )

    async def test_register_missing_email_returns_422(self, client):
        """
        Pydantic validation must reject a payload with no email field.
        422 Unprocessable Entity is the correct FastAPI response for schema violations.
        """
        data = make_user_data()
        data.pop("email")
        with patch("routers.auth.generate_and_send", new_callable=AsyncMock, return_value=(True, None)):
            resp = await client.post("/api/v1/auth/register", json=data)

        assert resp.status_code == 422, (
            f"Expected 422 for missing email, got {resp.status_code}: {resp.text}"
        )

    async def test_register_missing_password_returns_422(self, client):
        """Schema validation must catch a missing password field."""
        data = make_user_data()
        data.pop("password")
        with patch("routers.auth.generate_and_send", new_callable=AsyncMock, return_value=(True, None)):
            resp = await client.post("/api/v1/auth/register", json=data)

        assert resp.status_code == 422, (
            f"Expected 422 for missing password, got {resp.status_code}: {resp.text}"
        )

    async def test_register_invalid_role_rejected(self, client):
        """
        The role field must only accept 'homeowner' or 'tradie'.
        'admin', 'superuser', etc. must be rejected.
        """
        data = make_user_data(role="admin")
        with patch("routers.auth.generate_and_send", new_callable=AsyncMock, return_value=(True, None)):
            resp = await client.post("/api/v1/auth/register", json=data)

        assert resp.status_code == 422, (
            f"Expected 422 for invalid role 'admin', got {resp.status_code}: {resp.text}"
        )

    async def test_register_weak_password_rejected(self, client):
        """
        Passwords that don't meet complexity requirements must be rejected.
        'password' has no uppercase, numbers, or special characters.
        """
        data = make_user_data(password="password")
        with patch("routers.auth.generate_and_send", new_callable=AsyncMock, return_value=(True, None)):
            resp = await client.post("/api/v1/auth/register", json=data)

        assert resp.status_code == 422, (
            f"Expected 422 for weak password, got {resp.status_code}: {resp.text}"
        )


class TestLogin:

    async def test_login_success_returns_tokens(self, client, homeowner_data):
        """
        Logging in with correct credentials returns both tokens.
        The access token is used for API calls.
        The refresh token is used to get new access tokens.
        """
        resp = await client.post("/api/v1/auth/login", json={
            "email":    homeowner_data["email"],
            "password": homeowner_data["password"],
        })

        assert resp.status_code == 200, f"Login failed: {resp.text}"
        body = resp.json()

        assert "access_token" in body, f"access_token missing from login response: {body}"
        assert "refresh_token" in body, f"refresh_token missing from login response: {body}"
        assert len(body["access_token"]) > 20, "access_token looks too short to be a real JWT"

    async def test_login_wrong_password_returns_401(self, client, homeowner_data):
        """
        A wrong password must return 401. Must never return 200 or 500.
        This also verifies that bcrypt verification is actually running.
        """
        resp = await client.post("/api/v1/auth/login", json={
            "email":    homeowner_data["email"],
            "password": "WrongPassword999!",
        })

        assert resp.status_code == 401, (
            f"Expected 401 for wrong password, got {resp.status_code}: {resp.text}"
        )

    async def test_login_nonexistent_email_returns_401(self, client):
        """
        A login attempt with an email that was never registered must return 401.
        Must NOT return 404 — that would reveal which emails are registered (user enumeration).
        """
        resp = await client.post("/api/v1/auth/login", json={
            "email":    "ghost@notregistered.com",
            "password": "SecurePass123!",
        })

        assert resp.status_code == 401, (
            f"Expected 401 for non-existent email, got {resp.status_code}: {resp.text}"
        )


class TestMe:

    async def test_me_returns_user_data_when_authenticated(self, client, homeowner_headers, homeowner_data):
        """
        /me must return the authenticated user's email.
        This confirms the JWT is decoded correctly and the user is loaded from the DB.
        """
        resp = await client.get("/api/v1/auth/me", headers=homeowner_headers)

        assert resp.status_code == 200, f"Expected 200 from /me, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body.get("email") == homeowner_data["email"], (
            f"Email mismatch: expected {homeowner_data['email']}, got {body.get('email')}"
        )

    async def test_me_returns_401_without_token(self, client):
        """
        Calling /me without an Authorization header must return 401.
        This confirms the endpoint is protected.
        """
        resp = await client.get("/api/v1/auth/me")

        assert resp.status_code == 401, (
            f"Expected 401 for unauthenticated /me, got {resp.status_code}: {resp.text}"
        )

    async def test_me_returns_401_with_invalid_token(self, client):
        """A tampered or fabricated JWT must be rejected."""
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer this.is.not.a.real.jwt"},
        )

        assert resp.status_code == 401, (
            f"Expected 401 for invalid token, got {resp.status_code}: {resp.text}"
        )


class TestRefreshAndLogout:

    async def test_refresh_token_returns_new_access_token(self, client, homeowner_tokens):
        """
        Submitting a valid refresh token must return a new access token.
        This is the token rotation flow — old token is invalidated, new one issued.
        """
        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": homeowner_tokens["refresh_token"],
        })

        assert resp.status_code == 200, (
            f"Refresh failed: {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        assert "access_token" in body, f"New access_token missing from refresh response: {body}"
        # New token must be different from the old one
        assert body["access_token"] != homeowner_tokens["access_token"], (
            "Refresh should return a NEW access token, not the same one"
        )

    async def test_refresh_token_rotation_invalidates_old_token(self, client, homeowner_tokens):
        """
        After rotating, the old refresh token must be rejected.
        Reusing an old refresh token is a sign of token theft — the family
        should be invalidated and the user forced to log in again.
        """
        old_refresh = homeowner_tokens["refresh_token"]

        # First rotation — should succeed
        resp1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        assert resp1.status_code == 200, f"First refresh failed: {resp1.text}"

        # Second attempt with same (now invalidated) token — must fail
        resp2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        assert resp2.status_code in (401, 403), (
            f"Expected 401/403 when reusing old refresh token, got {resp2.status_code}: {resp2.text}"
        )

    async def test_logout_invalidates_refresh_token(self, client, homeowner_tokens, homeowner_headers):
        """
        After logout, the refresh token must no longer work.
        The session is killed — the user must log in again to get a new token.
        """
        # Logout
        resp = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": homeowner_tokens["refresh_token"]},
            headers=homeowner_headers,
        )
        assert resp.status_code in (200, 204), f"Logout failed: {resp.status_code}: {resp.text}"

        # Attempt to use the now-revoked refresh token
        refresh_resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": homeowner_tokens["refresh_token"],
        })
        assert refresh_resp.status_code in (401, 403), (
            f"Expected 401/403 after logout, got {refresh_resp.status_code}: {refresh_resp.text}"
        )

    async def test_logout_all_invalidates_session(self, client, homeowner_tokens, homeowner_headers):
        """
        /logout-all ends all sessions for this user.
        The current refresh token must stop working after this call.
        """
        resp = await client.post(
            "/api/v1/auth/logout-all",
            headers=homeowner_headers,
        )
        assert resp.status_code in (200, 204), (
            f"Logout-all failed: {resp.status_code}: {resp.text}"
        )

        # Refresh token should now be invalid
        refresh_resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": homeowner_tokens["refresh_token"],
        })
        assert refresh_resp.status_code in (401, 403), (
            f"Expected 401/403 after logout-all, got {refresh_resp.status_code}: {refresh_resp.text}"
        )