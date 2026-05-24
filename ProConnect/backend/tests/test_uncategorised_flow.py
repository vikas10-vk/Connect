"""
tests/test_uncategorised_flow.py

Locks in the "Service not listed" pathway:

  (A) services/uncategorised_service.create_uncategorised_job creates the job
      with the sentinel category, synthesizes a title, writes an audit
      JobEvent with action='uncategorised_request', and never triggers any
      lead-distribution path.

  (B) The sentinel category constant is exported and used consistently across
      seeds, service, and admin router.

  (C) The admin router exposes list / classify / close handlers.

  (D) Title synthesis: rough free-text becomes a short, searchable title.
"""

import asyncio
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from services.uncategorised_service import (
    SENTINEL_OTHER_SLUG,
    SentinelCategoryMissingError,
    _synthesize_title,
    create_uncategorised_job,
)

# ---- Title synthesis (pure) ----------------------------------------------

def test_title_synthesis_empty_description():
    assert _synthesize_title("") == "Uncategorised request"
    assert _synthesize_title("   ") == "Uncategorised request"


def test_title_synthesis_short_description():
    assert _synthesize_title("Piano tuning needed") == "Uncategorised: Piano tuning needed"


def test_title_synthesis_long_description_truncates():
    desc = "I need someone to install solar window film on three large bay windows"
    title = _synthesize_title(desc)
    assert title.startswith("Uncategorised:")
    assert title.endswith("...")
    # Body (between 'Uncategorised: ' and '...') stays under 60 chars
    body = title[len("Uncategorised: "):-3]
    assert len(body) <= 60


def test_title_synthesis_collapses_whitespace():
    assert _synthesize_title("  multiple    spaces \n\n inside ") == "Uncategorised: multiple spaces inside"


# ---- Sentinel constant consistency ---------------------------------------

def test_sentinel_slug_is_other_services():
    assert SENTINEL_OTHER_SLUG == "other-services"


def test_seed_file_includes_sentinel():
    """The seed declares the row and the service references it by the SAME slug.
    A mismatch here breaks every uncategorised submission silently."""
    seed_path = Path(__file__).resolve().parents[1] / "seeds" / "seed_categories.py"
    src = seed_path.read_text()
    assert "SENTINEL_OTHER_SLUG = \"other-services\"" in src
    assert "(\"other-services\"," in src
    # Sentinel is_active=False guard exists
    assert "is_active = slug != SENTINEL_OTHER_SLUG" in src


# ---- Service: create_uncategorised_job behaviour -------------------------

class _AddedTracker:
    """Captures everything passed to db.add() so we can assert the exact rows
    the service creates."""
    def __init__(self):
        self.added = []
    def add(self, row):
        self.added.append(row)


def _fake_db_with_sentinel(sentinel):
    db = _AddedTracker()
    async def execute(stmt):
        class R:
            def scalar_one_or_none(self_inner):
                return sentinel
        return R()
    async def flush():
        pass
    db.execute = execute
    db.flush = flush
    return db


def test_create_uncategorised_job_uses_sentinel_category():
    sentinel = SimpleNamespace(id="sentinel-id", slug="other-services")
    db = _fake_db_with_sentinel(sentinel)
    homeowner = SimpleNamespace(id="user-1", email="a@b.com", full_name="Alice")

    job = asyncio.run(create_uncategorised_job(
        homeowner=homeowner, db=db,
        description="I need a piano tuner",
        suburb="Sydney", state="NSW",
    ))
    assert job.category_id == "sentinel-id"
    assert job.homeowner_id == "user-1"
    assert job.status == "open"
    assert job.title.startswith("Uncategorised:")


def test_create_uncategorised_job_writes_audit_event():
    sentinel = SimpleNamespace(id="sentinel-id", slug="other-services")
    db = _fake_db_with_sentinel(sentinel)
    homeowner = SimpleNamespace(id="user-1", email="a@b.com", full_name="Alice")

    asyncio.run(create_uncategorised_job(
        homeowner=homeowner, db=db,
        description="piano tuning", original_slug="piano-tuner",
    ))
    # db.add is called twice: once for Job, once for JobEvent
    assert len(db.added) == 2
    job_row, event_row = db.added
    assert event_row.action == "uncategorised_request"
    assert event_row.actor_role == "homeowner"
    assert event_row.actor_id == "user-1"
    assert event_row.new_value["original_slug"] == "piano-tuner"


def test_create_uncategorised_job_rejects_empty_description():
    sentinel = SimpleNamespace(id="sentinel-id", slug="other-services")
    db = _fake_db_with_sentinel(sentinel)
    homeowner = SimpleNamespace(id="user-1", email="a@b.com", full_name="Alice")
    try:
        asyncio.run(create_uncategorised_job(
            homeowner=homeowner, db=db, description="   ",
        ))
        assert False, "should have raised"
    except ValueError as e:
        assert "description" in str(e).lower()


def test_create_uncategorised_job_raises_when_sentinel_missing():
    """Operator-facing safety net: if the seed wasn't run, the service must
    fail with a clear, fixable error instead of writing a bad row."""
    db = _AddedTracker()
    async def execute(stmt):
        class R:
            def scalar_one_or_none(self_inner):
                return None
        return R()
    db.execute = execute
    db.flush = AsyncMock()
    homeowner = SimpleNamespace(id="u1", email="a@b.com", full_name="A")
    try:
        asyncio.run(create_uncategorised_job(
            homeowner=homeowner, db=db, description="anything",
        ))
        assert False, "should have raised"
    except SentinelCategoryMissingError as e:
        assert "seed_categories" in str(e)


def test_create_uncategorised_job_never_calls_distribute_leads():
    """Critical invariant: the uncategorised path must NOT enqueue a lead
    distribution. There are no tradies in the sentinel category, so any
    enqueue would create a guaranteed-failed task. We check by inspecting
    the function source for any reference to distribute_leads."""
    src = inspect.getsource(create_uncategorised_job)
    assert "distribute_leads" not in src
    assert "apply_async" not in src


# ---- Admin router: triage endpoints exist + correct shape ---------------

def test_admin_router_has_triage_endpoints():
    from routers import admin as admin_router
    src = open(admin_router.__file__, encoding='utf-8').read()
    for route in (
        '@router.get("/uncategorised")',
        '@router.post("/uncategorised/{job_id}/classify")',
        '@router.post("/uncategorised/{job_id}/close")',
    ):
        assert route in src, f"missing admin route: {route}"


def test_admin_classify_uses_state_machine_and_triggers_distribution():
    from routers import admin as admin_router
    src = open(admin_router.__file__, encoding='utf-8').read()
    # Classify should reset match_intelligence (avoids the idempotency guard
    # rejecting the retry) and enqueue distribute_leads.
    assert "match_intelligence = None" in src
    assert "distribute_leads" in src
    # Audit row written
    assert "action=\"uncategorised_classified\"" in src


def test_admin_close_uses_state_machine_and_sends_email():
    from routers import admin as admin_router
    src = open(admin_router.__file__, encoding='utf-8').read()
    # Close path transitions via admin_transition (audit-safe), writes a triage-
    # specific audit row, and sends the polite "not supported" email.
    assert "admin_transition" in src
    assert "action=\"uncategorised_closed\"" in src
    assert "send_uncategorised_not_supported_email" in src


# ---- Soft fallback in POST /jobs -----------------------------------------

def test_post_jobs_soft_fallback_uses_uncategorised_pathway():
    """Unknown category slugs must be rejected so only the explicit
    /jobs/uncategorised pathway can create a sentinel job."""
    from routers import jobs as jobs_router
    src = inspect.getsource(jobs_router.create_job)
    assert 'raise HTTPException(status_code=400, detail="Unknown category_slug")' in src
    assert "create_uncategorised_job" not in src


def test_explicit_uncategorised_endpoint_still_exists():
    from routers import jobs as jobs_router
    src = open(jobs_router.__file__, encoding='utf-8').read()
    assert '@router.post("/uncategorised"' in src
    assert "create_uncategorised_job" in src
    assert '/uncategorised' in src
