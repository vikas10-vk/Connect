"""
tests/test_dispute_resolution.py

Locks in the full dispute resolution cycle:
  - Tradie dispute-response endpoint exists and is auth-gated
  - State machine permits the 3 admin resolution transitions
  - Admin /disputes/{id}/resolve endpoint maps each resolution to the right end-state
  - Both resolution emails exist
  - Notifications fire AFTER commit and failures are swallowed
"""
import inspect


# ---- State machine: resolution transitions --------------------------------

def test_disputed_to_closed_admin_only():
    from services.job_state_machine import ALLOWED_TRANSITIONS as A
    actors = A.get(("disputed", "closed"))
    assert actors == ["admin"], "disputed -> closed must be admin-only"


def test_disputed_to_confirmed_admin_only():
    from services.job_state_machine import ALLOWED_TRANSITIONS as A
    actors = A.get(("disputed", "confirmed"))
    assert actors is not None, "Missing transition disputed -> confirmed (side-tradie path)"
    assert actors == ["admin"]


def test_disputed_to_in_progress_admin_only():
    from services.job_state_machine import ALLOWED_TRANSITIONS as A
    actors = A.get(("disputed", "in_progress"))
    assert actors is not None, "Missing transition disputed -> in_progress (redo-work path)"
    assert actors == ["admin"]


def test_all_three_resolution_transitions_have_audit_notes():
    from services.job_state_machine import TRANSITION_NOTES as N
    for transition in (("disputed", "closed"), ("disputed", "confirmed"), ("disputed", "in_progress")):
        assert transition in N, f"audit-note missing for {transition}"
        assert N[transition].strip(), f"empty audit note for {transition}"


# ---- Tradie dispute-response endpoint ------------------------------------

def test_tradie_dispute_response_endpoint_exists():
    from routers import jobs as r
    src = open(r.__file__).read()
    assert '@router.post("/{job_id}/dispute-response")' in src


def test_tradie_dispute_response_is_role_gated():
    from routers import jobs as r
    src = open(r.__file__).read()
    idx = src.index("async def submit_dispute_response")
    body = src[idx: idx + 8000]
    # The endpoint now accepts BOTH homeowner and tradie (3-way conversation),
    # but still rejects any other role.
    assert 'current_user.role not in ("homeowner", "tradie")' in body
    # Tradie branch must verify the assigned tradie via a Lead row.
    assert "Lead.tradie_id == profile.id" in body
    # Status must be disputed.
    assert 'job.status != "disputed"' in body


def test_tradie_dispute_response_writes_audit_event():
    from routers import jobs as r
    src = open(r.__file__).read()
    idx = src.index("async def submit_dispute_response")
    body = src[idx: idx + 4000]
    assert 'action="dispute_response"' in body
    assert "await db.commit()" in body


# ---- Admin /disputes/{id}/resolve endpoint ------------------------------

def test_admin_resolve_endpoint_exists():
    from routers import admin as r
    src = open(r.__file__).read()
    assert '@router.post("/disputes/{job_id}/resolve")' in src


def test_admin_resolve_maps_each_resolution_to_correct_status():
    from routers.admin import RESOLUTION_TO_STATUS
    assert RESOLUTION_TO_STATUS["refund_homeowner"] == "closed"
    assert RESOLUTION_TO_STATUS["partial_refund"]   == "closed"
    assert RESOLUTION_TO_STATUS["side_tradie"]      == "confirmed"
    assert RESOLUTION_TO_STATUS["redo_work"]        == "in_progress"
    assert len(RESOLUTION_TO_STATUS) == 4, "should be exactly 4 paths"


def test_admin_resolve_requires_partial_refund_amount():
    from routers import admin as r
    src = open(r.__file__).read()
    idx = src.index("async def resolve_dispute")
    body = src[idx: idx + 8000]
    assert "partial_refund requires a positive refund_amount" in body


def test_admin_resolve_uses_state_machine_and_writes_audit_event():
    from routers import admin as r
    src = open(r.__file__).read()
    idx = src.index("async def resolve_dispute")
    body = src[idx: idx + 8000]
    assert "JobStateMachine.admin_transition" in body
    assert 'action="dispute_resolved"' in body
    assert 'resolution' in body and 'refund_amount' in body


def test_admin_resolve_notifies_both_parties_after_commit():
    from routers import admin as r
    src = open(r.__file__).read()
    idx = src.index("async def resolve_dispute")
    body = src[idx: idx + 8000]
    commit_pos = body.index("await db.commit()")
    assert body.index("send_dispute_resolved_to_homeowner_email") > commit_pos
    assert body.index("send_dispute_resolved_to_tradie_email") > commit_pos


def test_admin_resolve_notification_failures_are_swallowed():
    from routers import admin as r
    src = open(r.__file__).read()
    idx = src.index("async def resolve_dispute")
    body = src[idx: idx + 8000]
    # The email block is inside a try/except so a Resend hiccup can't roll back.
    notif_pos = body.index("send_dispute_resolved_to_homeowner_email")
    try_pos = body.rfind("try:", 0, notif_pos)
    except_pos = body.index("except Exception", notif_pos)
    assert 0 < try_pos < notif_pos < except_pos


# ---- Resolution emails ---------------------------------------------------

def test_homeowner_resolution_email_has_all_4_paths():
    from services.resend_service import send_dispute_resolved_to_homeowner_email
    src = inspect.getsource(send_dispute_resolved_to_homeowner_email)
    for res in ("refund_homeowner", "partial_refund", "side_tradie", "redo_work"):
        assert res in src, f"homeowner email missing branch for {res}"


def test_tradie_resolution_email_has_all_4_paths():
    from services.resend_service import send_dispute_resolved_to_tradie_email
    src = inspect.getsource(send_dispute_resolved_to_tradie_email)
    for res in ("refund_homeowner", "partial_refund", "side_tradie", "redo_work"):
        assert res in src, f"tradie email missing branch for {res}"


def test_resolution_emails_accept_admin_note_and_refund_amount():
    from services.resend_service import (
        send_dispute_resolved_to_homeowner_email,
        send_dispute_resolved_to_tradie_email,
    )
    for fn in (send_dispute_resolved_to_homeowner_email, send_dispute_resolved_to_tradie_email):
        sig = inspect.signature(fn)
        assert "admin_note" in sig.parameters
        assert "refund_amount" in sig.parameters
        assert "resolution" in sig.parameters


# ---- Admin payload exposes tradie responses ------------------------------

def test_dispute_payload_includes_tradie_responses():
    from routers import admin as r
    src = open(r.__file__).read()
    idx = src.index("async def _build_dispute_payload")
    body = src[idx: idx + 20000]
    assert 'JobEvent.action == "dispute_response"' in body
    assert '"tradie_responses":' in body
