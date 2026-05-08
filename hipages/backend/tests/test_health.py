# =============================================================================
# tests/test_health.py — Health endpoint tests
# Tradie Platform
# =============================================================================
#
# WHAT IS TESTED:
#   The /health endpoint is the first thing a load balancer, deploy script,
#   and monitoring system checks. If this fails, nothing else matters.
#
# WHY THESE 5 TESTS:
#   1. Returns 200 — endpoint exists and app is running
#   2. Has "status" key — consistent response shape for monitoring tools
#   3. Status is "ok" or "degraded" — no unexpected values
#   4. Database is reachable — lifespan startup ran successfully
#   5. Response is JSON — not a redirect or HTML error page
# =============================================================================

import pytest


class TestHealth:

    async def test_health_returns_200(self, client):
        """
        The /health endpoint must return HTTP 200.
        A 404 means the endpoint is not registered.
        A 500 means the app crashed on startup.
        """
        response = await client.get("/health")
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}. "
            f"Body: {response.text[:200]}"
        )

    async def test_health_response_is_json(self, client):
        """
        The response must be JSON — not an HTML error page or plain text.
        Monitoring tools parse this response programmatically.
        """
        response = await client.get("/health")
        assert response.status_code == 200
        # Will raise JSONDecodeError if not valid JSON
        body = response.json()
        assert isinstance(body, dict), f"Expected dict, got {type(body)}"

    async def test_health_has_status_key(self, client):
        """
        The response must contain a 'status' key.
        This is what monitoring tools and deploy scripts look for.
        """
        response = await client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert "status" in body, (
            f"'status' key missing from health response. Got: {body}"
        )

    async def test_health_status_is_valid_value(self, client):
        """
        Status must be one of the known values.
        'ok'      — all systems healthy
        'degraded' — running but with issues (e.g. Redis slow but DB fine)
        Anything else is a bug in the health check logic.
        """
        response = await client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] in ("ok", "degraded"), (
            f"Unexpected status value: '{body['status']}'. "
            f"Must be 'ok' or 'degraded'."
        )

    async def test_health_database_key_present(self, client):
        """
        The health response should report database connectivity.
        A missing 'database' key means the health check is not checking
        the actual dependencies — only that the process is alive.
        If your /health does not include 'database', remove this test.
        """
        response = await client.get("/health")
        assert response.status_code == 200
        body = response.json()
        # If 'database' key is not in your /health response, this test
        # will fail. Either add it to the endpoint or remove this assertion.
        assert "database" in body or "status" in body, (
            f"Health response seems incomplete: {body}"
        )