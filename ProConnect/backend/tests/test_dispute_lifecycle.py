"""
tests/test_dispute_lifecycle.py

Locks in the dispute UX fixes:

  (A) raise_dispute notifies the tradie via email (helper exists + endpoint calls it).
  (B) The admin /disputes payload includes the homeowner's reason, tradie's
      completion note, contact info, timeline, and photos -- not the previous
      one-line skeleton.
  (C) The /jobs/{id}/dispute-info endpoint exists for shared homeowner/tradie/admin reads.
  (D) /admin/completed-jobs excludes status='disputed' so a disputed job can
      never appear in both the Completed list and the Disputes list at once.
"""

import inspect


# ---- (A) Tradie notification on dispute -----------------------------------

def test_dispute_email_helper_exists_and_signature():
    """If this import breaks, the dispute endpoint silently can't email tradies."""
    from services.resend_service import send_job_disputed_to_tradie_email
    sig = inspect.signature(send_job_disputed_to_tradie_email)
    params = set(sig.parameters.keys())
    # The endpoint passes these by keyword -- contract test.
    for required in ("to_email", "full_name", "business_name", "job_title", "suburb", "dispute_reason"):
        assert required in params, f"send_job_disputed_to_tradie_email missing param {required!r}"


def test_dispute_endpoint_calls_tradie_email_after_state_transition():
    from routers import jobs as jobs_router
    src = open(jobs_router.__file__, encoding='utf-8').read()
    # Locate raise_dispute and ensure the email send happens AFTER db.commit
    # (so a notification failure cannot roll back the dispute state change).
    idx = src.index("async def raise_dispute")
    body = src[idx: idx + 20000]
    assert "send_job_disputed_to_tradie_email" in body, "raise_dispute does not call the email helper"
    commit_pos = body.index("await db.commit()")
    email_pos  = body.index("send_job_disputed_to_tradie_email")
    assert email_pos > commit_pos, "Email send must happen AFTER db.commit so notification failure doesn't roll back the dispute"


def test_dispute_endpoint_email_failure_is_swallowed():
    """A best-effort notification must never fail the request -- the dispute
    has already committed by the time we try to email."""
    from routers import jobs as jobs_router
    src = open(jobs_router.__file__, encoding='utf-8').read()
    idx = src.index("async def raise_dispute")
    body = src[idx: idx + 20000]
    # The email block is inside a try/except so a failure can't propagate.
    assert "except Exception" in body
    # And the try wraps the email call
    try_pos    = body.rfind("try:", 0, body.index("send_job_disputed_to_tradie_email"))
    except_pos = body.index("except Exception", body.index("send_job_disputed_to_tradie_email"))
    assert try_pos > 0 and except_pos > try_pos, "Email send is not wrapped in try/except"


# ---- (B) Admin /disputes payload contains the missing context -------------

def test_admin_disputes_payload_includes_full_context():
    from routers import admin as admin_router
    src = open(admin_router.__file__, encoding='utf-8').read()
    helper_idx = src.index("async def _build_dispute_payload")
    helper = src[helper_idx: helper_idx + 20000]
    # The fields that were missing in the original thin response -- prove they
    # are now part of the payload that the admin Disputes tab consumes.
    for field in (
        '"dispute_reason":',
        '"dispute_raised_at":',
        '"dispute_raised_by_role":',
        '"timeline":',
        '"homeowner":',
        '"tradie":',
        '"completion_note":',
        '"after_photos":',
        '"description":',
        '"category":',
    ):
        assert field in helper, f"_build_dispute_payload missing field {field!r}"


def test_admin_disputes_endpoint_uses_the_rich_helper():
    from routers import admin as admin_router
    src = open(admin_router.__file__, encoding='utf-8').read()
    list_idx = src.index("async def list_disputes")
    body = src[list_idx: list_idx + 2000]
    assert "_build_dispute_payload" in body, "list_disputes does not call _build_dispute_payload"
    detail_idx = src.index("async def get_dispute")
    detail = src[detail_idx: detail_idx + 1500]
    assert "_build_dispute_payload" in detail, "get_dispute does not call _build_dispute_payload"


# ---- (C) /jobs/{id}/dispute-info shared endpoint --------------------------

def test_dispute_info_endpoint_exists_and_authorises_three_roles():
    from routers import jobs as jobs_router
    src = open(jobs_router.__file__, encoding='utf-8').read()
    assert '@router.get("/{job_id}/dispute-info")' in src
    fn_idx = src.index("async def dispute_info")
    fn = src[fn_idx: fn_idx + 3000]
    # Authorisation: homeowner of the job, admin, or a tradie with a lead on it.
    assert "is_homeowner" in fn
    assert "is_admin" in fn
    assert "is_tradie" in fn
    # 403 for anyone else.
    assert "Not your job" in fn


# ---- (D) Completed jobs admin list excludes 'disputed' --------------------

def test_completed_jobs_admin_filter_excludes_disputed():
    from routers import admin as admin_router
    src = open(admin_router.__file__, encoding='utf-8').read()
    fn_idx = src.index("async def list_completed_jobs")
    fn = src[fn_idx: fn_idx + 2000]
    # The list of statuses considered "done" for the admin Completed tab.
    assert 'DONE_STATUSES = ["completed", "confirmed", "closed"]' in fn
    # Crucially, 'disputed' is NOT in this list -- a disputed job moves OUT
    # of the Completed tab and INTO the Disputes tab.
    assert '"disputed"' not in fn.split("DONE_STATUSES = ")[1].split("]")[0]


# ---- (E) State machine + broadcast still fire on dispute ------------------

def test_state_machine_broadcasts_to_both_parties_on_status_change():
    """Sanity: the broadcast hook we wired earlier still resolves both homeowner
    and tradie user_ids so the dispute push reaches both dashboards."""
    from services import job_state_machine as jsm
    src = open(jsm.__file__, encoding='utf-8').read()
    exec_idx = src.index("async def _execute")
    body = src[exec_idx: exec_idx + 6000]
    assert "broadcast_job_status" in body
    assert "homeowner_id=job.homeowner_id" in body
    assert "tradie_user_ids=tradie_user_ids" in body


def test_confirmed_to_disputed_transition_still_allowed_for_homeowner():
    """Regression guard for the earlier safety-valve fix -- a homeowner who
    confirmed in good faith can still escalate to disputed within 48h."""
    from services.job_state_machine import ALLOWED_TRANSITIONS
    actors = ALLOWED_TRANSITIONS.get(("confirmed", "disputed"))
    assert actors is not None
    assert "homeowner" in actors
    assert "tradie" not in actors and "system" not in actors
