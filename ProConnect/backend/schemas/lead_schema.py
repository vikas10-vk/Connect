from datetime import datetime

from pydantic import BaseModel


class LeadResponse(BaseModel):
    """
    Lead card shown on the tradie dashboard.
    Includes job details and computed badge flags.
    """
    id:              str
    job_id:          str
    tradie_id:       str
    credits_charged: int
    status:          str
    sent_at:         datetime

    # ── Job details ───────────────────────────────────────────────
    job_title:       str | None   = None
    job_suburb:      str | None   = None
    job_state:       str | None   = None
    job_description: str | None   = None
    job_budget_min:  float | None = None
    job_budget_max:  float | None = None
    job_urgency:     str | None   = None

    # ── Wizard fields (shown on lead card) ────────────────────────
    job_type:        str | None   = None   # residential | commercial
    service_type:    str | None   = None   # repair | new_installation | etc.
    job_stage:       str | None   = None   # ready_to_hire | planning_budgeting

    # ── Job status (for Start Job button on tradie dashboard) ─────
    job_status:      str | None   = None

    # ── Badge flags ───────────────────────────────────────────────
    # Urgent: job needs to be done asap or it's an emergency
    is_urgent:       bool = False

    # High Value: job budget is $1000+ (significant Australian trade job)
    is_high_value:   bool = False

    # Redo flag — True when this job was returned to in_progress after a
    # dispute resolution (redo_work). Drives the 'redo job' banner on the
    # tradie Active tab so the tradie knows this is a post-dispute return.
    is_redo_job:     bool = False

    class Config:
        from_attributes = True
