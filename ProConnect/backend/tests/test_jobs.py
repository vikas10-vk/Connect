# =============================================================================
# tests/test_jobs.py — Jobs endpoint tests
# Tradie Platform
# =============================================================================
#
# ENDPOINTS COVERED:
#   POST   /api/v1/jobs/           create a job
#   GET    /api/v1/jobs/           list all jobs
#   GET    /api/v1/jobs/{job_id}   get a single job
#   PATCH  /api/v1/jobs/{job_id}   update a job
#   DELETE /api/v1/jobs/{job_id}   soft-delete a job
#
# WHAT IS TESTED (8 tests):
#   create:  homeowner success, tradie blocked, unauthenticated blocked
#   list:    authenticated gets 200
#   get:     valid id returns job, invalid id returns 404
#   IDOR:    user B cannot delete user A's job (critical security test)
#   delete:  owner can soft-delete their own job
#
# MOCKS:
#   geocode_suburb  — imported at top of routers/jobs.py.
#                     We return (None, None) so no real HTTP geocoding calls happen.
#   distribute_leads — imported inside a try/except in create_job.
#                      It fails silently when Celery is not configured.
#                      No mock needed — the job is still created.
# =============================================================================

import pytest
from unittest.mock import AsyncMock, patch


# =============================================================================
# Minimal valid job payload
# =============================================================================

def make_job_data(**overrides) -> dict:
    """
    Minimal payload that passes JobCreate schema validation.
    category_slug is the only truly required field — all others are optional
    in the create step (validation of completeness happens in /submit).
    """
    data = {
        "category_slug": "plumbing",
        "title":         "Fix leaking pipe under kitchen sink",
        "description":   "Water is dripping from the pipe every 30 seconds.",
    }
    data.update(overrides)
    return data


# =============================================================================
# Tests
# =============================================================================

class TestCreateJob:

    async def test_homeowner_can_create_job(self, client, homeowner_headers):
        """
        A homeowner with a valid JWT can create a job.
        The response must be 201 with the job id and status.
        """
        with patch("routers.jobs.geocode_suburb", new_callable=AsyncMock, return_value=(None, None)):
            resp = await client.post(
                "/api/v1/jobs/",
                json=make_job_data(),
                headers=homeowner_headers,
            )

        assert resp.status_code == 201, (
            f"Expected 201 for job creation, got {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        assert "id" in body, f"Response missing job id: {body}"
        assert body.get("status") is not None, f"Response missing status: {body}"

    async def test_plumber_language_resolves_to_plumbing(self, client, homeowner_headers):
        """
        User/tradie language like "plumber" must resolve to Plumbing, never to
        a loose partial-match category such as Painting & Decorating.
        """
        with patch("routers.jobs.geocode_suburb", new_callable=AsyncMock, return_value=(None, None)):
            resp = await client.post(
                "/api/v1/jobs/",
                json=make_job_data(
                    category_slug="plumber",
                    title="Need a plumber for leaking tap",
                    description="Kitchen tap is leaking and needs repair.",
                ),
                headers=homeowner_headers,
            )

        assert resp.status_code == 201, (
            f"Expected plumber alias to create job, got {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        cats_resp = await client.get("/api/v1/categories", headers=homeowner_headers)
        assert cats_resp.status_code == 200
        plumbing = next((c for c in cats_resp.json() if c["slug"] == "plumbing"), None)
        assert plumbing is not None, f"Seeded plumbing category missing: {cats_resp.json()}"
        assert body["category_id"] == plumbing["id"], f"Expected Plumbing category, got {body}"

    @pytest.mark.parametrize(
        ("category_slug", "title", "description", "expected_slug"),
        [
            ("electrical", "Install two ceiling fans", "Need an electrician for bedroom ceiling fans.", "electrical"),
            ("painting", "Paint interior walls", "Paint three bedrooms and hallway walls.", "painting"),
            ("roofing", "Fix leaking roof", "Water coming through roof flashing near gutter.", "roofing"),
            ("hvac", "Air con service", "Split system air conditioner needs servicing.", "hvac"),
            ("glazing", "Install shower screen", "Need a frameless glass shower screen installed.", "glazing"),
            ("solar", "Install solar panels", "Rooftop solar panel system and inverter installation.", "solar"),
            ("gas-fitting", "Gas cooktop connection", "Connect new gas cooktop and check gas line.", "gas-fitting"),
            ("bathroom-renovation", "Replace shower", "Bathroom shower replacement with new vanity.", "bathroom-renovation"),
            ("kitchen-renovation", "Replace kitchen cabinets", "Kitchen cabinet and benchtop replacement.", "kitchen-renovation"),
            ("waterproofing", "Waterproof balcony", "Deck and balcony waterproofing before tiling.", "waterproofing"),
        ],
    )
    async def test_service_matching_resolves_multiple_trades(
        self,
        client,
        homeowner_headers,
        category_slug,
        title,
        description,
        expected_slug,
    ):
        """Representative services across the taxonomy resolve to their intended trade."""
        with patch("routers.jobs.geocode_suburb", new_callable=AsyncMock, return_value=(None, None)):
            resp = await client.post(
                "/api/v1/jobs/",
                json=make_job_data(
                    category_slug=category_slug,
                    title=title,
                    description=description,
                ),
                headers=homeowner_headers,
            )

        assert resp.status_code == 201, (
            f"Expected {category_slug} to create job, got {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        cats_resp = await client.get("/api/v1/categories", headers=homeowner_headers)
        assert cats_resp.status_code == 200
        expected = next((c for c in cats_resp.json() if c["slug"] == expected_slug), None)
        assert expected is not None, f"Seeded {expected_slug} category missing: {cats_resp.json()}"
        assert body["category_id"] == expected["id"], f"Expected {expected_slug}, got {body}"

    async def test_unknown_service_is_rejected_instead_of_loose_fallback(self, client, homeowner_headers):
        """
        Unknown service text must fail loudly instead of being loosely mapped
        to whichever category name happens to contain a similar fragment.
        """
        with patch("routers.jobs.geocode_suburb", new_callable=AsyncMock, return_value=(None, None)):
            resp = await client.post(
                "/api/v1/jobs/",
                json=make_job_data(
                    category_slug="nonsense-service",
                    title="Specialist home request",
                    description="No specific trade words are provided here.",
                ),
                headers=homeowner_headers,
            )

        assert resp.status_code == 400, (
            f"Expected unknown service to be rejected, got {resp.status_code}: {resp.text}"
        )

    async def test_tradie_cannot_create_job(self, client, tradie_headers):
        """
        A tradie must not be able to post jobs — only homeowners can.
        The endpoint checks current_user.role and returns 403.
        """
        with patch("routers.jobs.geocode_suburb", new_callable=AsyncMock, return_value=(None, None)):
            resp = await client.post(
                "/api/v1/jobs/",
                json=make_job_data(),
                headers=tradie_headers,
            )

        assert resp.status_code == 403, (
            f"Expected 403 for tradie creating job, got {resp.status_code}: {resp.text}"
        )

    async def test_unauthenticated_cannot_create_job(self, client):
        """
        Requests without an Authorization header must be rejected.
        This verifies the endpoint is not accidentally public.
        """
        with patch("routers.jobs.geocode_suburb", new_callable=AsyncMock, return_value=(None, None)):
            resp = await client.post("/api/v1/jobs/", json=make_job_data())

        assert resp.status_code == 401, (
            f"Expected 401 for unauthenticated job creation, got {resp.status_code}: {resp.text}"
        )


class TestListAndGetJobs:

    async def test_authenticated_user_can_list_jobs(self, client, homeowner_headers):
        """
        GET /jobs/ returns a list (may be empty) for authenticated users.
        The endpoint requires authentication — it is not a public browse page.
        """
        resp = await client.get("/api/v1/jobs/", headers=homeowner_headers)

        assert resp.status_code == 200, (
            f"Expected 200 for job list, got {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        assert isinstance(body, list), f"Expected list, got {type(body)}: {body}"

    async def test_get_job_by_id_returns_job(self, client, homeowner_headers):
        """
        After creating a job, fetching it by ID must return the same job.
        This confirms the create-then-read flow works end to end.
        """
        # Create a job first
        with patch("routers.jobs.geocode_suburb", new_callable=AsyncMock, return_value=(None, None)):
            create_resp = await client.post(
                "/api/v1/jobs/",
                json=make_job_data(title="Roof inspection needed"),
                headers=homeowner_headers,
            )
        assert create_resp.status_code == 201, f"Job creation failed: {create_resp.text}"
        job_id = create_resp.json()["id"]

        # Fetch it back
        get_resp = await client.get(f"/api/v1/jobs/{job_id}", headers=homeowner_headers)
        assert get_resp.status_code == 200, (
            f"Expected 200 fetching job {job_id}, got {get_resp.status_code}: {get_resp.text}"
        )
        assert get_resp.json()["id"] == job_id

    async def test_get_nonexistent_job_returns_404(self, client, homeowner_headers):
        """
        Fetching a job ID that doesn't exist must return 404 — not 500.
        A 500 here would suggest unhandled database errors.
        """
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await client.get(f"/api/v1/jobs/{fake_id}", headers=homeowner_headers)

        assert resp.status_code == 404, (
            f"Expected 404 for non-existent job, got {resp.status_code}: {resp.text}"
        )


class TestJobOwnership:

    async def test_idor_other_user_cannot_delete_job(
        self, client, homeowner_headers, other_homeowner_headers
    ):
        """
        CRITICAL SECURITY TEST — IDOR (Insecure Direct Object Reference).

        User A creates a job. User B must not be able to delete it,
        even if they know the job ID. The backend must check ownership,
        not just authentication.

        If this test fails, any authenticated user can delete any other
        user's jobs — that is a critical vulnerability.
        """
        # User A creates a job
        with patch("routers.jobs.geocode_suburb", new_callable=AsyncMock, return_value=(None, None)):
            create_resp = await client.post(
                "/api/v1/jobs/",
                json=make_job_data(title="Private job — do not touch"),
                headers=homeowner_headers,         # User A's token
            )
        assert create_resp.status_code == 201, f"Job creation failed: {create_resp.text}"
        job_id = create_resp.json()["id"]

        # User B attempts to delete User A's job
        delete_resp = await client.delete(
            f"/api/v1/jobs/{job_id}",
            headers=other_homeowner_headers,       # User B's token
        )

        assert delete_resp.status_code == 403, (
            f"IDOR VULNERABILITY: User B was able to delete User A's job! "
            f"Expected 403, got {delete_resp.status_code}: {delete_resp.text}"
        )

    async def test_owner_can_delete_own_job(self, client, homeowner_headers):
        """
        A homeowner can soft-delete their own job.
        The endpoint returns 204 No Content on success.
        """
        # Create the job
        with patch("routers.jobs.geocode_suburb", new_callable=AsyncMock, return_value=(None, None)):
            create_resp = await client.post(
                "/api/v1/jobs/",
                json=make_job_data(title="Job to be deleted"),
                headers=homeowner_headers,
            )
        assert create_resp.status_code == 201, f"Job creation failed: {create_resp.text}"
        job_id = create_resp.json()["id"]

        # Delete it
        delete_resp = await client.delete(
            f"/api/v1/jobs/{job_id}",
            headers=homeowner_headers,
        )

        assert delete_resp.status_code == 204, (
            f"Expected 204 for job deletion, got {delete_resp.status_code}: {delete_resp.text}"
        )
