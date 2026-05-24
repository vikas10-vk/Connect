from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# ── Allowed values matching the wizard steps exactly ──────────────

UrgencyType = Literal[
    "flexible",
    "asap",
    "emergency",
    "next_few_days",
    "next_few_weeks",
    "next_few_months",
]

JobType = Literal[
    "residential",
    "commercial",
]

ServiceType = Literal[
    "new_installation",
    "repair",
    "replace",
    "other",
]

JobStage = Literal[
    "ready_to_hire",
    "planning_budgeting",
]

# ─────────────────────────────────────────────────────────────────
class JobPhotoResponse(BaseModel):
    id:  str
    url: str
    file_key: str

    class Config:
        from_attributes = True

class JobCreate(BaseModel):
    """Used by POST /jobs/ — creates job with all wizard fields."""
    # Frontend sends the slug (e.g. 'plumbing'); backend resolves to category_id
    category_slug: str
    title:         str
    description:   str | None         = None
    suburb:        str | None         = None
    state:         str | None         = None
    postcode:      str | None         = None
    lat:           float | None       = None
    lng:           float | None       = None
    budget_min:    float | None       = None
    budget_max:    float | None       = None

    # Wizard Step 1
    urgency:       UrgencyType | None = "flexible"
    # Wizard Step 2
    job_type:      JobType | None     = None
    # Wizard Step 3
    service_type:  ServiceType | None = None
    # Wizard Step 4
    job_stage:     JobStage | None    = None
    # Wizard Step 6
    contact_name:  str | None         = None
    contact_phone: str | None         = None
    contact_email: str | None         = None
    # Extra fields sent by wizard (ignored for storage)
    intent_level:  str | None         = None


class JobUpdate(BaseModel):
    """
    Used by PATCH /jobs/{id} — all fields optional.
    Homeowner can save progress at any wizard step.
    Only non-None fields are applied to the job.
    """
    category_id:   str | None         = None
    title:         str | None         = None
    description:   str | None         = None
    suburb:        str | None         = None
    state:         str | None         = None
    postcode:      str | None         = None
    lat:           float | None       = None
    lng:           float | None       = None
    budget_min:    float | None       = None
    budget_max:    float | None       = None
    urgency:       UrgencyType | None = None
    job_type:      JobType | None     = None
    service_type:  ServiceType | None = None
    job_stage:     JobStage | None    = None
    contact_name:  str | None         = None
    contact_phone: str | None         = None
    contact_email: str | None         = None


class JobResponse(BaseModel):
    id:            str
    homeowner_id:  str
    category_id:   str
    title:         str
    description:   str | None
    suburb:        str | None
    state:         str | None
    postcode:      str | None
    lat:           float | None
    lng:           float | None
    budget_min:    float | None
    budget_max:    float | None
    status:        str

    # Wizard fields
    urgency:       str | None
    job_type:      str | None
    service_type:  str | None
    job_stage:     str | None

    # Contact fields
    contact_name:  str | None
    contact_phone: str | None
    contact_email: str | None

    # Soft delete + completion tracking
    is_deleted:    bool            = False
    deleted_at:    datetime | None = None
    completed_at:  datetime | None = None

    created_at:    datetime

    class Config:
        from_attributes = True


class JobWithDetailsResponse(BaseModel):
    """
    Enriched job response for homeowner dashboard.
    Includes category name, lead count, quote count, photo count.
    """
    id:            str
    homeowner_id:  str
    category_id:   str
    category_name: str | None   = None   # from category relationship
    title:         str
    description:   str | None
    suburb:        str | None
    state:         str | None
    postcode:      str | None
    lat:           float | None
    lng:           float | None
    budget_min:    float | None
    budget_max:    float | None
    status:        str
    urgency:       str | None
    job_type:      str | None
    service_type:  str | None
    job_stage:     str | None
    contact_name:  str | None
    contact_phone: str | None
    contact_email: str | None

    # Dashboard counts
    lead_count:    int = 0    # how many tradies received this job
    quote_count:   int = 0    # how many tradies sent a quote
    photo_count:   int = 0
    photos:        list[JobPhotoResponse] = []    # how many photos attached

    # Soft delete + completion tracking
    # Soft delete + completion tracking
    is_deleted:    bool            = False
    deleted_at:    datetime | None = None
    completed_at:  datetime | None = None
    match_intelligence: str | None = None

    # Review state (drives "Leave Review" UI on dashboard)
    has_review:    bool          = False
    review_status: str | None = None  # 'pending' | 'approved' | 'rejected'

    # Redo flag — True when this job returned to in_progress after a dispute
    # resolution (redo_work). Drives the contextual 'tradie is redoing' banner
    # on both homeowner and tradie dashboards.
    is_redo_job:   bool          = False

    # Dispute window — how many hours the homeowner has to raise a dispute.
    # 48 h on first completion; 10 h after a resolved re-dispute.
    # None when no window is active (job not in completed/confirmed state).
    dispute_window_hours:      int | None      = None
    dispute_window_expires_at: datetime | None = None

    created_at:    datetime

    class Config:
        from_attributes = True
