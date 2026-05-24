"""
services/uncategorised_service.py

Centralised path for homeowner job requests that don't fit any of the 24
canonical trades (e.g. "piano tuning", "aquarium maintenance", "chimney
sweep"). Used by:
  * POST /jobs/uncategorised     -- explicit "Service not listed" submission
  * POST /jobs (soft fallback)   -- when category resolution fails entirely

Behaviour:
  1. Create the Job row with category_id = the sentinel 'other-services'
     category. The Job model requires NOT NULL category_id, so we need a
     real row -- the sentinel is seeded with is_active=False so it can never
     leak into the public picker.
  2. Skip lead distribution entirely. There are no tradies in 'other'.
  3. Write a JobEvent with action='uncategorised_request' so the admin
     audit/triage screen surfaces the request.
  4. Email the homeowner an honest "we'll get back to you within 24h" note.

Admin triage (in routers/admin.py) then either:
  * Classifies it -> sets the real category_id, triggers distribute_leads, OR
  * Closes it as not-supported -> status=cancelled + polite email.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.category import Category
from models.job import Job
from models.job_event import JobEvent
from models.user import User

SENTINEL_OTHER_SLUG = "other-services"


class SentinelCategoryMissingError(Exception):
    """Raised when the 'other-services' sentinel row hasn't been seeded yet.
    Tells the operator to run `python -m seeds.seed_categories` before using
    the uncategorised pathway."""
    pass


async def get_sentinel_category(db: AsyncSession) -> Category:
    res = await db.execute(select(Category).where(Category.slug == SENTINEL_OTHER_SLUG))
    cat = res.scalar_one_or_none()
    if not cat:
        raise SentinelCategoryMissingError(
            "Sentinel 'other-services' category is missing. "
            "Run `python -m seeds.seed_categories` to create it."
        )
    return cat


def _synthesize_title(description: str) -> str:
    """Make a short, human-readable title from a free-text description so the
    admin triage screen has something searchable to display."""
    cleaned = " ".join((description or "").strip().split())
    if not cleaned:
        return "Uncategorised request"
    head = cleaned[:60].rstrip(",. ")
    return f"Uncategorised: {head}" + ("..." if len(cleaned) > 60 else "")


async def create_uncategorised_job(
    homeowner: User,
    db: AsyncSession,
    *,
    description: str,
    suburb: str | None = None,
    state: str | None = None,
    postcode: str | None = None,
    contact_name: str | None = None,
    contact_phone: str | None = None,
    contact_email: str | None = None,
    original_slug: str | None = None,
) -> Job:
    """
    Create a Job row tagged with the sentinel category and surface it to admin.

    The caller is responsible for db.commit() (we only db.add()) so the route
    handler can include this in its own transaction and trigger the homeowner
    notification email as a best-effort follow-up. Returns the created Job.
    """
    if not description or not description.strip():
        raise ValueError("description is required for an uncategorised request")

    sentinel = await get_sentinel_category(db)

    job = Job(
        id=str(uuid.uuid4()),
        homeowner_id=homeowner.id,
        category_id=sentinel.id,
        title=_synthesize_title(description),
        description=description.strip(),
        suburb=suburb,
        state=state,
        postcode=postcode,
        urgency="flexible",
        contact_name=contact_name,
        contact_phone=contact_phone,
        contact_email=contact_email,
        status="open",
    )
    db.add(job)
    await db.flush()  # so job.id is available for the JobEvent

    # Admin-visible audit entry; the admin triage tab queries on this action.
    event = JobEvent(
        job_id=job.id,
        actor_id=homeowner.id,
        actor_role="homeowner",
        action="uncategorised_request",
        old_value=None,
        new_value={
            "description":   description.strip()[:500],
            "original_slug": original_slug,
            "suburb":        suburb,
            "state":         state,
        },
        note=(
            "Homeowner submitted a service request that does not map to any "
            "of the 24 canonical trades. Awaiting admin triage."
        ),
    )
    db.add(event)

    return job


async def notify_homeowner_received(homeowner: User, description: str) -> None:
    """
    Best-effort: tells the homeowner we got their request. Never raises -- a
    failure to send the email must not break the submission.
    """
    try:
        from services.resend_service import send_uncategorised_received_email
        await send_uncategorised_received_email(
            to_email=homeowner.email,
            full_name=homeowner.full_name or "",
            description_excerpt=description,
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Uncategorised-received email failed for %s: %s", homeowner.email, exc,
        )
