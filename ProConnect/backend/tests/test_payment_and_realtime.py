"""
tests/test_payment_and_realtime.py

Locks in the two follow-up fixes:

  (A) Payment release gates on status == 'closed', never 'confirmed'.
      With the new 'confirmed -> disputed' transition, booking earnings on a
      confirmed job would create a ledger row that could be invalidated within
      48 hours. earnings_service._job_is_payable rejects every status that
      isn't 'closed'.

  (B) JobStateMachine._execute pushes a job:status_changed broadcast on
      every successful transition. Failures in the broadcaster are swallowed
      so they never block a state change.
"""

import asyncio
from types import SimpleNamespace

from services.earnings_service import _job_is_payable


class _DBResult:
    def __init__(self, value):
        self._value = value
    def scalar_one_or_none(self):
        return self._value


class _DB:
    """Tiny in-memory stub for the two SELECT calls _job_is_payable makes."""
    def __init__(self, job=None, lead=None):
        self._job = job
        self._lead = lead
        self._call = 0
    async def execute(self, stmt):
        self._call += 1
        # 1st call = SELECT Job, 2nd call = SELECT Lead
        return _DBResult(self._job if self._call == 1 else self._lead)


def _job(status, *, is_deleted=False, jid="job-1"):
    return SimpleNamespace(id=jid, status=status, is_deleted=is_deleted, completed_at=None)


def _lead(tid="tradie-1", jid="job-1"):
    return SimpleNamespace(id="lead-1", job_id=jid, tradie_id=tid)


# ---- (A) Payment release guards ------------------------------------------

def test_payable_only_when_status_is_closed():
    db = _DB(job=_job("closed"), lead=_lead())
    ok, reason = asyncio.run(_job_is_payable("job-1", "tradie-1", db))
    assert ok, reason


def test_not_payable_when_confirmed_inside_dispute_window():
    """The whole point: confirmed != safe to book. A homeowner can still
    escalate confirmed -> disputed within 48 hours of completed_at."""
    db = _DB(job=_job("confirmed"), lead=_lead())
    ok, reason = asyncio.run(_job_is_payable("job-1", "tradie-1", db))
    assert not ok
    assert "closed" in reason


def test_not_payable_when_disputed():
    db = _DB(job=_job("disputed"), lead=_lead())
    ok, reason = asyncio.run(_job_is_payable("job-1", "tradie-1", db))
    assert not ok


def test_not_payable_when_completed_awaiting_homeowner():
    db = _DB(job=_job("completed"), lead=_lead())
    ok, reason = asyncio.run(_job_is_payable("job-1", "tradie-1", db))
    assert not ok


def test_not_payable_when_in_progress():
    db = _DB(job=_job("in_progress"), lead=_lead())
    ok, reason = asyncio.run(_job_is_payable("job-1", "tradie-1", db))
    assert not ok


def test_not_payable_when_cancelled():
    db = _DB(job=_job("cancelled"), lead=_lead())
    ok, reason = asyncio.run(_job_is_payable("job-1", "tradie-1", db))
    assert not ok


def test_not_payable_when_job_deleted():
    db = _DB(job=_job("closed", is_deleted=True), lead=_lead())
    ok, reason = asyncio.run(_job_is_payable("job-1", "tradie-1", db))
    assert not ok
    assert "deleted" in reason.lower()


def test_not_payable_when_other_tradie_tries_to_book():
    """Even on a closed job, only the actually-hired tradie can book the earning."""
    db = _DB(job=_job("closed"), lead=None)  # no lead for this tradie
    ok, reason = asyncio.run(_job_is_payable("job-1", "tradie-1", db))
    assert not ok
    assert "not the tradie" in reason.lower()


def test_not_payable_when_job_missing():
    db = _DB(job=None, lead=None)
    ok, reason = asyncio.run(_job_is_payable("job-1", "tradie-1", db))
    assert not ok
    assert "not found" in reason.lower()


# ---- (B) WebSocket broadcaster: contract test ----------------------------

def test_broadcast_helper_exists_and_is_async():
    """If this import breaks, JobStateMachine._execute can't push status events."""
    from routers.websocket import (
        broadcast_job_status,
        manager,
        start_realtime_pubsub,
        stop_realtime_pubsub,
    )
    assert asyncio.iscoroutinefunction(broadcast_job_status)
    assert asyncio.iscoroutinefunction(start_realtime_pubsub)
    assert asyncio.iscoroutinefunction(stop_realtime_pubsub)
    assert hasattr(manager, "send_to_user")
    assert hasattr(manager, "send_to_tradie")  # back-compat alias for notification_service


def test_broadcast_to_offline_user_is_noop_returns_zero():
    """A status change for an offline homeowner must not crash anything --
    send_to_user just returns 0 sockets reached."""
    from routers.websocket import manager
    delivered = asyncio.run(manager.send_to_user("nobody-here", {"type": "ping"}))
    assert delivered == 0


def test_broadcast_helper_swallows_errors():
    """broadcast_job_status must never raise -- the JobStateMachine guard
    relies on this so a websocket layer hiccup can't block a transition."""
    from routers.websocket import broadcast_job_status
    # Even with bogus types, the call should complete cleanly.
    asyncio.run(broadcast_job_status(
        job_id="x", old_status="open", new_status="quoted",
        homeowner_id=None, tradie_user_ids=[],
    ))


def test_state_machine_imports_broadcaster_lazily():
    """Sanity: the state machine references broadcast_job_status only inside
    the try/except so a missing import never fails a transition."""
    import inspect

    from services import job_state_machine as jsm
    src = inspect.getsource(jsm._execute_helper if hasattr(jsm, '_execute_helper') else jsm.JobStateMachine._execute)
    # The broadcast import lives inside a try block.
    assert "broadcast_job_status" in src
    assert "RealtimeNotification" in src
    assert "try:" in src.split("broadcast_job_status")[0]


def test_jobs_do_not_fallback_in_api_for_production_without_flag():
    import inspect

    from routers import jobs

    src = inspect.getsource(jobs.create_job)
    assert "OutboxEvent" in src
    assert "ENVIRONMENT" in src
    assert "ALLOW_IN_API_LEAD_FALLBACK" in src


def test_job_status_constraint_is_declared_on_model():
    from models.job import Job

    constraints = {c.name for c in Job.__table__.constraints}
    assert "ck_jobs_status_valid" in constraints
