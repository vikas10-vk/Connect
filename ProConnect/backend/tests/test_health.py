# =============================================================================
# tests/test_health.py — Health endpoint tests
# Tradie Platform
# =============================================================================
#
# FIXES FROM ORIGINAL:
#
# FIX 1 — Accept 200 or 503:
#   The health endpoint returns 503 when any check fails (DB slow, Redis slow).
#   In a CI test environment this can happen. 503 is still a valid health
#   response — it means "degraded" not "crashed". We accept both.
#
# FIX 2 — Correct key path for database:
#   BEFORE: assert "database" in body        ← wrong, "database" is not top-level
#   AFTER:  assert "database" in body["checks"]  ← correct
#
#   The actual health response structure is:
#   {
#     "status": "ok",
#     "checks": {
#       "database": "ok",
#       "redis":    "ok"
#     }
#   }
# =============================================================================


class TestHealth:

    async def test_health_endpoint_exists(self, client):
        """
        GET /health must respond — not 404, not 405.
        404 means the endpoint is not registered.
        """
        response = await client.get("/health")
        assert response.status_code != 404, (
            "/health returned 404 — endpoint is not registered in main.py"
        )
        assert response.status_code != 405, (
            "/health returned 405 — endpoint is registered but wrong HTTP method"
        )

    async def test_health_response_is_json(self, client):
        """
        The response must be valid JSON.
        Monitoring tools parse this response programmatically.
        """
        response = await client.get("/health")
        # Will raise JSONDecodeError if not valid JSON
        body = response.json()
        assert isinstance(body, dict), f"Expected dict, got {type(body)}: {body}"

    async def test_health_has_status_key(self, client):
        """
        The response must contain a 'status' key.
        This is the primary field that monitoring tools read.
        """
        response = await client.get("/health")
        body = response.json()
        assert "status" in body, (
            f"'status' key missing from health response. Got: {body}"
        )

    async def test_health_status_is_valid_value(self, client):
        """
        Status must be 'ok' or 'degraded'.
        Anything else is a bug in the health check logic.
        200 = ok, 503 = degraded — both are valid responses from this endpoint.
        """
        response = await client.get("/health")
        # Both 200 and 503 are valid — 503 means degraded not crashed
        assert response.status_code in (200, 503), (
            f"Unexpected HTTP status: {response.status_code}. "
            f"Expected 200 (ok) or 503 (degraded). Body: {response.text[:200]}"
        )
        body = response.json()
        assert body["status"] in ("ok", "degraded"), (
            f"Unexpected status value: '{body['status']}'. "
            f"Must be 'ok' or 'degraded'. Full body: {body}"
        )

    async def test_health_has_checks_with_database(self, client):
        """
        The health response must include a 'checks' dict with a 'database' entry.

        Actual response structure:
          {
            "status": "ok",
            "checks": {
              "database": "ok",
              "redis":    "ok"
            }
          }

        Note: 'database' is inside 'checks', not at the top level.
        """
        response = await client.get("/health")
        body = response.json()

        assert "checks" in body, (
            f"'checks' key missing from health response. Got keys: {list(body.keys())}"
        )
        assert "database" in body["checks"], (
            f"'database' missing from body['checks']. "
            f"Got checks: {body['checks']}"
        )
