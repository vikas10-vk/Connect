"""
backend/services/job_state_machine.py

Strict state transition validator for ProConnect jobs.

DESIGN RULES:
  1. Every transition is explicitly listed — anything not in the table is rejected.
  2. Every transition declares which actor roles can trigger it.
  3. No mid-job transition can bypass awaiting_scope_approval.
     Any PATCH to /jobs/{id}/status that attempts to jump from in_progress
     directly back to in_progress without going through scope approval is rejected.
  4. Every transition writes a JobEvent row with actor_id, actor_role, action,
     old_value, new_value, and a human-readable note. This is the dispute trail.
  5. The transition method is the SINGLE place that writes job.status.
     Nowhere else in the codebase sets job.status directly — always go through here.

EXISTING CALL SIGNATURE (preserved for backward compatibility):
    await JobStateMachine.transition(job, new_status, current_user, db)
    await JobStateMachine.system_transition(job, new_status, note, db)

NEW METHOD:
    await JobStateMachine.tradie_transition(job, new_status, member, note, db)
    — used by tradie-specific endpoints where the actor is a TeamMember,
      not a User (solo owner still has a User, but business workers do not).
"""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from models.job import Job
from models.job_event import JobEvent

# ── State transition table ─────────────────────────────────────────────────────
# (from_status, to_status) → list of actor_roles allowed to make this transition.
# 'system' is used by Celery tasks (auto-reject timeout, auto-close, watchdog).
# 'admin' is used by Django admin actions.

ALLOWED_TRANSITIONS: dict[tuple[str, str], list[str]] = {
    # ── Lead / quote phase ────────────────────────────────────────────────────
    ("open",     "cancelled"):               ["homeowner", "system"],
    ("open",     "quoted"):                  ["system"],    # lead distribution
    ("quoted",   "hired"):                   ["homeowner"],
    ("quoted",   "cancelled"):               ["homeowner", "system"],

    # ── Job active ────────────────────────────────────────────────────────────
    ("hired",    "in_progress"):             ["tradie", "system"],
    ("hired",    "cancelled"):               ["homeowner", "tradie", "system"],

    # ── Mid-job transitions ───────────────────────────────────────────────────
    # CRITICAL: in_progress → awaiting_scope_approval is the ONLY path for
    # scope changes. Direct in_progress → in_progress is not allowed.
    ("in_progress", "awaiting_scope_approval"): ["tradie"],
    ("in_progress", "partial_stop"):            ["tradie"],
    ("in_progress", "completed"):               ["tradie"],

    # ── Scope approval resolution ─────────────────────────────────────────────
    # Homeowner approves → job continues (in_progress).
    # Homeowner rejects → job continues with original scope (in_progress).
    # System auto-rejects after 10-min timeout → original scope continues.
    # User non-response after timeout → same as reject (system fires this).
    ("awaiting_scope_approval", "in_progress"):   ["homeowner", "system"],
    ("awaiting_scope_approval", "partial_stop"):  ["system"],
    # ^ Fired by Celery when timeout fires AND tradie chose to stop rather than continue original scope.

    # ── After job ─────────────────────────────────────────────────────────────
    ("partial_stop", "completed"): ["homeowner", "admin"],
    ("partial_stop", "disputed"):  ["homeowner"],

    # Homeowner confirms the job is done — releases payment to tradie.
    ("completed",  "confirmed"): ["homeowner"],

    # Homeowner has 48h after completion to dispute. After 48h, system auto-closes.
    ("completed",  "disputed"): ["homeowner"],
    ("completed",  "closed"):   ["system", "admin"],

    # Confirmed jobs auto-close after payment release (system) or admin can close manually.
    ("confirmed",  "closed"):   ["system", "admin"],

    # Safety valve: a homeowner who confirmed in good faith can still raise a dispute
    # if they spot a problem before the 48-hour window closes. The endpoint enforces
    # the time check; the state machine just permits the transition.
    ("confirmed",  "disputed"): ["homeowner"],

    # ── Dispute resolution — peer-to-peer (primary path) ────────────────────
    # Tradie claims they fixed it (dispute-claim-resolved endpoint writes a
    # JobEvent — no status change). Homeowner then accepts here → completed.
    # The job re-enters the normal confirm flow: completed → confirmed → closed.
    ("disputed",   "completed"):   ["homeowner"],

    # ── Dispute escalation paths (admin-only, secondary path) ────────────────
    # Only reached when homeowner keeps rejecting the tradie's resolution claim
    # (2+ rejections trigger an admin escalation alert automatically).
    # closed     -> admin sided with homeowner (refund) or no-action ruling.
    # confirmed  -> admin sided with tradie; work accepted.
    # in_progress-> admin ordered tradie to return and redo the work.
    ("disputed",   "closed"):      ["admin"],
    ("disputed",   "confirmed"):   ["admin"],
    ("disputed",   "in_progress"): ["admin"],
}

# States from which no further transitions are allowed.
TERMINAL_STATES = frozenset({"cancelled", "closed"})

# Human-readable transition notes for the audit trail.
TRANSITION_NOTES: dict[tuple[str, str], str] = {
    ("open",        "cancelled"):               "Job cancelled before any quotes received.",
    ("open",        "quoted"):                  "Lead distribution complete — tradies notified.",
    ("quoted",      "hired"):                   "Homeowner hired a tradie.",
    ("quoted",      "cancelled"):               "Job cancelled during quoting phase.",
    ("hired",       "in_progress"):             "Tradie marked job as started.",
    ("hired",       "cancelled"):               "Job cancelled after hire but before start.",
    ("in_progress", "awaiting_scope_approval"): "Tradie requested a scope change — awaiting homeowner approval.",
    ("in_progress", "partial_stop"):            "Tradie stopped work mid-job.",
    ("in_progress", "completed"):               "Tradie marked job as complete.",
    ("awaiting_scope_approval", "in_progress"): "Scope change resolved — job continues.",
    ("awaiting_scope_approval", "partial_stop"): "Scope approval timed out — tradie stopped work.",
    ("partial_stop", "completed"):              "Partial stop resolved — job marked complete.",
    ("partial_stop", "disputed"):               "Homeowner raised a dispute on partial stop.",
    ("completed",   "confirmed"):               "Homeowner confirmed job complete.",
    ("completed",   "disputed"):                "Homeowner raised a dispute within 48h of completion.",
    ("completed",   "closed"):                  "Job closed after 48h with no dispute.",
    ("confirmed",   "closed"):                  "Job closed after payment release.",
    ("confirmed",   "disputed"):                "Homeowner raised a dispute after confirming — still within the 48h window.",
    ("disputed",    "completed"):               "Homeowner accepted the tradie's resolution — dispute closed, job back to completed.",
    ("disputed",    "closed"):                  "Dispute escalated to admin — job closed (refund or no-action ruling).",
    ("disputed",    "confirmed"):               "Dispute escalated to admin — sided with tradie; work accepted as complete.",
    ("disputed",    "in_progress"):             "Dispute escalated to admin — tradie ordered to return and finish/redo the work.",
}


class InvalidTransitionError(Exception):
    """Raised when a requested state transition is not allowed."""
    pass


class JobStateMachine:
    """
    All methods are async classmethods. They validate, write the event,
    update job.status, but do NOT commit — the caller commits.

    This keeps transactions under caller control so the caller can include
    other writes (e.g. updating scope fields) in the same transaction.
    """

    @classmethod
    async def transition(
        cls,
        job: Job,
        new_status: str,
        current_user,          # models.user.User
        db: AsyncSession,
        note: str | None = None,
        extra_job_fields: dict | None = None,
    ) -> None:
        """
        Primary transition method — called by homeowner and tradie endpoints.
        current_user.role is used as the actor_role.

        Raises InvalidTransitionError if the transition is not permitted.
        """
        actor_role = current_user.role   # 'homeowner' or 'tradie'
        await cls._execute(
            job=job,
            new_status=new_status,
            actor_id=current_user.id,
            actor_role=actor_role,
            db=db,
            note=note,
            extra_job_fields=extra_job_fields,
        )

    @classmethod
    async def tradie_transition(
        cls,
        job: Job,
        new_status: str,
        member,                # models.team_member.TeamMember
        db: AsyncSession,
        note: str | None = None,
        extra_job_fields: dict | None = None,
    ) -> None:
        """
        Used by tradie-specific endpoints where the actor is a TeamMember
        (business worker) rather than a User. actor_role is always 'tradie'.
        """
        await cls._execute(
            job=job,
            new_status=new_status,
            actor_id=member.id,
            actor_role="tradie",
            db=db,
            note=note,
            extra_job_fields=extra_job_fields,
        )

    @classmethod
    async def system_transition(
        cls,
        job: Job,
        new_status: str,
        db: AsyncSession,
        note: str | None = None,
        extra_job_fields: dict | None = None,
    ) -> None:
        """
        Used by Celery tasks and the watchdog. actor_role = 'system'.
        actor_id = 'system' (no real user involved).
        """
        await cls._execute(
            job=job,
            new_status=new_status,
            actor_id="system",
            actor_role="system",
            db=db,
            note=note,
            extra_job_fields=extra_job_fields,
        )

    @classmethod
    async def admin_transition(
        cls,
        job: Job,
        new_status: str,
        admin_user_id: str,
        db: AsyncSession,
        note: str | None = None,
        extra_job_fields: dict | None = None,
    ) -> None:
        """
        Used by Django admin actions that need to change job status directly
        (e.g. resolving a dispute). actor_role = 'admin'.
        """
        await cls._execute(
            job=job,
            new_status=new_status,
            actor_id=admin_user_id,
            actor_role="admin",
            db=db,
            note=note,
            extra_job_fields=extra_job_fields,
        )

    # ── Core execution ────────────────────────────────────────────────────────

    @classmethod
    async def _execute(
        cls,
        job: Job,
        new_status: str,
        actor_id: str,
        actor_role: str,
        db: AsyncSession,
        note: str | None,
        extra_job_fields: dict | None,
    ) -> None:
        old_status = job.status

        # ── Terminal state guard ──────────────────────────────────────────────
        if old_status in TERMINAL_STATES:
            raise InvalidTransitionError(
                f"Job is in terminal state '{old_status}' and cannot be transitioned further."
            )

        # ── Scope approval bypass guard ───────────────────────────────────────
        # If a scope change is in progress (status = awaiting_scope_approval),
        # no one except homeowner/system can change the status. Tradies cannot
        # jump back to in_progress without the homeowner's decision.
        if old_status == "awaiting_scope_approval" and new_status == "in_progress":
            if actor_role not in ("homeowner", "system"):
                raise InvalidTransitionError(
                    "Only the homeowner can approve or reject a pending scope change. "
                    "The job cannot return to 'in_progress' without homeowner consent."
                )

        # ── Transition table lookup ───────────────────────────────────────────
        key = (old_status, new_status)
        allowed_roles = ALLOWED_TRANSITIONS.get(key)

        if allowed_roles is None:
            raise InvalidTransitionError(
                f"Transition from '{old_status}' to '{new_status}' is not permitted. "
                f"Check the valid transitions table in job_state_machine.py."
            )

        if actor_role not in allowed_roles:
            raise InvalidTransitionError(
                f"A '{actor_role}' cannot transition a job from '{old_status}' to '{new_status}'. "
                f"Permitted roles for this transition: {', '.join(allowed_roles)}."
            )

        # ── Apply extra field updates ─────────────────────────────────────────
        if extra_job_fields:
            for field, value in extra_job_fields.items():
                setattr(job, field, value)

        # ── Status update ─────────────────────────────────────────────────────
        job.status     = new_status
        job.updated_at = datetime.utcnow()

        # Set completed_at on first completion
        if new_status == "completed" and not job.completed_at:
            job.completed_at = datetime.utcnow()

        db.add(job)

        # ── Write audit event ─────────────────────────────────────────────────
        auto_note = TRANSITION_NOTES.get(key, f"{old_status} -> {new_status}")
        event = JobEvent(
            job_id     = job.id,
            actor_id   = actor_id,
            actor_role = actor_role,
            action     = "status_change",
            old_value  = {"status": old_status},
            new_value  = {"status": new_status},
            note       = note or auto_note,
        )
        db.add(event)

        # ── Real-time broadcast (best-effort) ─────────────────────────────────
        # Push a job:status_changed event so the homeowner dashboard and the
        # tradie dashboard refresh in real-time without manual reload.
        # NEVER raises -- a WebSocket failure must never break a transition.
        try:
            from sqlalchemy import select

            from models.lead import Lead
            from models.realtime_notification import RealtimeNotification
            from models.tradie_profile import TradieProfile
            from routers.websocket import broadcast_job_status

            # Resolve tradie user_ids from any leads on this job. A job may have
            # up to 3 leads (the matcher caps at 3 tradies); we notify all of
            # them so their dashboards reflect terminal transitions too.
            lead_res = await db.execute(
                select(TradieProfile.user_id)
                .join(Lead, Lead.tradie_id == TradieProfile.id)
                .where(Lead.job_id == job.id)
            )
            tradie_user_ids = [row[0] for row in lead_res.all() if row[0]]
            recipients = {job.homeowner_id, *tradie_user_ids}
            notification_ids: dict[str, str] = {}
            payload = {
                "type": "job:status_changed",
                "job_id": job.id,
                "old_status": old_status,
                "new_status": new_status,
            }
            for user_id in recipients:
                if not user_id:
                    continue
                notification = RealtimeNotification(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    event_type="job:status_changed",
                    payload=payload,
                )
                db.add(notification)
                notification_ids[user_id] = notification.id

            await broadcast_job_status(
                job_id=job.id,
                old_status=old_status,
                new_status=new_status,
                homeowner_id=job.homeowner_id,
                tradie_user_ids=tradie_user_ids,
                notification_ids=notification_ids,
            )
        except Exception:
            # Logging only; the transition is committed regardless.
            import logging
            logging.getLogger(__name__).debug(
                "broadcast_job_status skipped for job %s", job.id, exc_info=True,
            )

    # ── Convenience query helpers ─────────────────────────────────────────────

    @staticmethod

    @staticmethod
    def assert_status(job: Job, *expected: str) -> None:
        """
        Raise InvalidTransitionError if the job is not in one of the expected statuses.
        Used at the top of endpoint handlers to fail fast with a clear message.

        Example:
            JobStateMachine.assert_status(job, "in_progress")
        """
        if job.status not in expected:
            expected_str = "', '".join(expected)
            raise InvalidTransitionError(
                f"This action requires the job to be in status '{expected_str}', "
                f"but it is currently '{job.status}'."
            )

    @staticmethod
    def is_terminal(job: Job) -> bool:
        return job.status in TERMINAL_STATES
