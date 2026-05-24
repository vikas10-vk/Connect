"""
tests/test_dispute_conversation.py

Locks in the open 3-way dispute conversation:
  - dispute-response endpoint accepts BOTH homeowner and tradie
  - each role is correctly authorised
  - posting cross-notifies the OTHER party (email after commit, swallowed on failure)
  - /dispute-info returns the full responses list for all readers
  - the cross-notify email helper exists with the right signature
"""
import inspect

# ---- Endpoint accepts both roles -----------------------------------------

def test_dispute_response_accepts_homeowner_and_tradie():
    from routers import jobs as r
    src = open(r.__file__, encoding='utf-8').read()
    idx = src.index("async def submit_dispute_response")
    body = src[idx: idx + 8000]
    # The role gate must allow BOTH, not just tradie.
    assert 'current_user.role not in ("homeowner", "tradie")' in body, \
        "dispute-response should accept homeowner AND tradie"


def test_dispute_response_authorises_homeowner_by_ownership():
    from routers import jobs as r
    src = open(r.__file__, encoding='utf-8').read()
    idx = src.index("async def submit_dispute_response")
    body = src[idx: idx + 8000]
    # Homeowner branch checks job ownership.
    assert 'job.homeowner_id != current_user.id' in body


def test_dispute_response_authorises_tradie_by_lead():
    from routers import jobs as r
    src = open(r.__file__, encoding='utf-8').read()
    idx = src.index("async def submit_dispute_response")
    body = src[idx: idx + 8000]
    # Tradie branch checks a Lead row exists.
    assert "Lead.tradie_id == profile.id" in body


def test_dispute_response_records_actor_role_dynamically():
    """The JobEvent must store whichever role actually posted -- not hardcoded
    'tradie' -- so the conversation correctly attributes each message."""
    from routers import jobs as r
    src = open(r.__file__, encoding='utf-8').read()
    idx = src.index("async def submit_dispute_response")
    body = src[idx: idx + 8000]
    assert "actor_role=actor_role" in body
    assert 'action="dispute_response"' in body


# ---- Cross-notification --------------------------------------------------

def test_dispute_response_cross_notifies_after_commit():
    from routers import jobs as r
    src = open(r.__file__, encoding='utf-8').read()
    idx = src.index("async def submit_dispute_response")
    body = src[idx: idx + 8000]
    commit_pos = body.index("await db.commit()")
    email_pos  = body.index("send_dispute_response_posted_email")
    assert email_pos > commit_pos, "cross-notify email must fire AFTER commit"


def test_dispute_response_cross_notify_failure_is_swallowed():
    from routers import jobs as r
    src = open(r.__file__, encoding='utf-8').read()
    idx = src.index("async def submit_dispute_response")
    body = src[idx: idx + 8000]
    notif = body.index("send_dispute_response_posted_email")
    try_pos = body.rfind("try:", 0, notif)
    except_pos = body.index("except Exception", notif)
    assert 0 < try_pos < notif < except_pos, "cross-notify must be wrapped in try/except"


def test_cross_notify_email_helper_signature():
    from services.resend_service import send_dispute_response_posted_email
    sig = inspect.signature(send_dispute_response_posted_email)
    for p in ("to_email", "to_name", "job_title", "poster_role", "response_excerpt"):
        assert p in sig.parameters, f"send_dispute_response_posted_email missing {p!r}"


# ---- /dispute-info exposes the whole conversation ------------------------

def test_dispute_info_returns_responses_list():
    from routers import jobs as r
    src = open(r.__file__, encoding='utf-8').read()
    idx = src.index("async def dispute_info")
    body = src[idx: idx + 6000]
    assert 'JobEvent.action == "dispute_response"' in body
    assert '"responses":' in body
    # Ordered oldest-first so the UI renders it as a conversation.
    assert "JobEvent.created_at.asc()" in body


# ---- Regression: resolution paths still intact ---------------------------

def test_resolution_transitions_unchanged():
    from services.job_state_machine import ALLOWED_TRANSITIONS as A
    assert A.get(("disputed", "closed"))      == ["admin"]
    assert A.get(("disputed", "confirmed"))   == ["admin"]
    assert A.get(("disputed", "in_progress")) == ["admin"]
