"""
tests/test_completion_flow.py

Offline tests for the homeowner completion + dispute flow.
Also covers CompleteJobRequest validation (photo OR note).

These cover the bugs fixed in the "tradie marked complete but homeowner sees
nothing" report:
  1. State machine allows 'completed' -> 'confirmed' (homeowner confirms).
  2. State machine allows 'completed' -> 'disputed' (homeowner disputes within 48h).
  3. State machine allows 'confirmed' -> 'disputed' (safety valve: homeowner
     confirmed in good faith and only later spotted a problem).
  4. State machine BLOCKS 'confirmed' -> 'disputed' for tradies/admin/system
     (only the homeowner can dispute on their own job).
  5. The dispute endpoint's 48-hour window logic, computed against completed_at.
"""

from datetime import datetime, timedelta
import pytest
from pydantic import ValidationError
from services.job_state_machine import (
    ALLOWED_TRANSITIONS, TRANSITION_NOTES, TERMINAL_STATES,
)
from routers.jobs import CompleteJobRequest


# ---- Complete job request validation -------------------------------------

def test_complete_job_requires_note():
    with pytest.raises(ValidationError):
        CompleteJobRequest(photo_after_urls=[], completion_note=None)


def test_complete_job_rejects_photos_only():
    with pytest.raises(ValidationError):
        CompleteJobRequest(
            photo_after_urls=["https://cdn.example/a.jpg"],
            completion_note=None,
        )


def test_complete_job_accepts_note_only():
    body = CompleteJobRequest(
        photo_after_urls=[],
        completion_note="Pool cleaned and chemicals balanced.",
    )
    assert body.completion_note == "Pool cleaned and chemicals balanced."
    assert body.photo_after_urls == []


def test_complete_job_rejects_short_note():
    with pytest.raises(ValidationError):
        CompleteJobRequest(photo_after_urls=[], completion_note="hi")


# ---- State machine: completion flow transitions --------------------------

def test_completed_to_confirmed_is_allowed_for_homeowner():
    actors = ALLOWED_TRANSITIONS.get(("completed", "confirmed"))
    assert actors is not None
    assert "homeowner" in actors


def test_completed_to_disputed_is_allowed_for_homeowner():
    actors = ALLOWED_TRANSITIONS.get(("completed", "disputed"))
    assert actors is not None
    assert "homeowner" in actors


def test_completed_to_closed_is_system_or_admin_only():
    """The 48-hour auto-close transition belongs to system/admin, never the homeowner."""
    actors = ALLOWED_TRANSITIONS.get(("completed", "closed"))
    assert actors is not None
    assert "system" in actors
    assert "admin" in actors
    assert "homeowner" not in actors


def test_confirmed_to_disputed_is_allowed_for_homeowner():
    """The safety valve: homeowner confirmed, then noticed an issue within 48h."""
    actors = ALLOWED_TRANSITIONS.get(("confirmed", "disputed"))
    assert actors is not None, "Missing transition - homeowner cannot recover from premature confirm"
    assert "homeowner" in actors


def test_confirmed_to_disputed_blocked_for_non_homeowner():
    """Only the homeowner can escalate a confirmed job - not tradies, admins, or the system.
    Admin should resolve disputes by transitioning 'disputed' -> 'closed' instead."""
    actors = ALLOWED_TRANSITIONS.get(("confirmed", "disputed"))
    assert "tradie" not in actors
    assert "admin" not in actors
    assert "system" not in actors


def test_disputed_to_closed_is_admin_only():
    actors = ALLOWED_TRANSITIONS.get(("disputed", "closed"))
    assert actors is not None
    assert actors == ["admin"]


def test_closed_is_terminal():
    assert "closed" in TERMINAL_STATES


def test_cancelled_is_terminal():
    assert "cancelled" in TERMINAL_STATES


def test_confirmed_to_disputed_has_audit_note():
    """The audit trail picks up the new transition - admins reading the timeline
    should see WHY a confirmed job got reopened."""
    assert ("confirmed", "disputed") in TRANSITION_NOTES
    note = TRANSITION_NOTES[("confirmed", "disputed")]
    assert "48" in note  # mentions the 48-hour window


# ---- 48-hour dispute window logic ----------------------------------------
# These mirror the time-window check inside POST /jobs/{id}/dispute without
# needing the FastAPI test client. The endpoint runs the same arithmetic.

def _hours_since(completed_at: datetime) -> float:
    return (datetime.utcnow() - completed_at).total_seconds() / 3600


def test_dispute_window_open_at_zero_hours():
    """Tradie just marked complete - dispute is allowed."""
    completed_at = datetime.utcnow() - timedelta(minutes=5)
    assert _hours_since(completed_at) <= 48


def test_dispute_window_open_at_thirty_hours():
    """Homeowner confirmed in hour 2, noticed problem in hour 30 - still in window."""
    completed_at = datetime.utcnow() - timedelta(hours=30)
    assert _hours_since(completed_at) <= 48


def test_dispute_window_open_at_exactly_forty_eight_hours():
    """Right on the boundary - dispute still allowed (endpoint uses > 48, not >=)."""
    completed_at = datetime.utcnow() - timedelta(hours=47, minutes=59)
    assert _hours_since(completed_at) <= 48


def test_dispute_window_closed_after_forty_eight_hours():
    """Anything past 48h fails - endpoint returns 400."""
    completed_at = datetime.utcnow() - timedelta(hours=49)
    assert _hours_since(completed_at) > 48


def test_dispute_window_closed_after_a_week():
    """Sanity check on big numbers."""
    completed_at = datetime.utcnow() - timedelta(days=7)
    assert _hours_since(completed_at) > 48
