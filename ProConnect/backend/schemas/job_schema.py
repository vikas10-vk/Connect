from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime

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
    description:   Optional[str]         = None
    suburb:        Optional[str]         = None
    state:         Optional[str]         = None
    postcode:      Optional[str]         = None
    lat:           Optional[float]       = None
    lng:           Optional[float]       = None
    budget_min:    Optional[float]       = None
    budget_max:    Optional[float]       = None

    # Wizard Step 1
    urgency:       Optional[UrgencyType] = "flexible"
    # Wizard Step 2
    job_type:      Optional[JobType]     = None
    # Wizard Step 3
    service_type:  Optional[ServiceType] = None
    # Wizard Step 4
    job_stage:     Optional[JobStage]    = None
    # Wizard Step 6
    contact_name:  Optional[str]         = None
    contact_phone: Optional[str]         = None
    contact_email: Optional[str]         = None
    # Extra fields sent by wizard (ignored for storage)
    intent_level:  Optional[str]         = None


class JobUpdate(BaseModel):
    """
    Used by PATCH /jobs/{id} — all fields optional.
    Homeowner can save progress at any wizard step.
    Only non-None fields are applied to the job.
    """
    category_id:   Optional[str]         = None
    title:         Optional[str]         = None
    description:   Optional[str]         = None
    suburb:        Optional[str]         = None
    state:         Optional[str]         = None
    postcode:      Optional[str]         = None
    lat:           Optional[float]       = None
    lng:           Optional[float]       = None
    budget_min:    Optional[float]       = None
    budget_max:    Optional[float]       = None
    urgency:       Optional[UrgencyType] = None
    job_type:      Optional[JobType]     = None
    service_type:  Optional[ServiceType] = None
    job_stage:     Optional[JobStage]    = None
    contact_name:  Optional[str]         = None
    contact_phone: Optional[str]         = None
    contact_email: Optional[str]         = None


class JobResponse(BaseModel):
    id:            str
    homeowner_id:  str
    category_id:   str
    title:         str
    description:   Optional[str]
    suburb:        Optional[str]
    state:         Optional[str]
    postcode:      Optional[str]
    lat:           Optional[float]
    lng:           Optional[float]
    budget_min:    Optional[float]
    budget_max:    Optional[float]
    status:        str

    # Wizard fields
    urgency:       Optional[str]
    job_type:      Optional[str]
    service_type:  Optional[str]
    job_stage:     Optional[str]

    # Contact fields
    contact_name:  Optional[str]
    contact_phone: Optional[str]
    contact_email: Optional[str]

    # Soft delete + completion tracking
    is_deleted:    bool            = False
    deleted_at:    Optional[datetime] = None
    completed_at:  Optional[datetime] = None

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
    category_name: Optional[str]   = None   # from category relationship
    title:         str
    description:   Optional[str]
    suburb:        Optional[str]
    state:         Optional[str]
    postcode:      Optional[str]
    lat:           Optional[float]
    lng:           Optional[float]
    budget_min:    Optional[float]
    budget_max:    Optional[float]
    status:        str
    urgency:       Optional[str]
    job_type:      Optional[str]
    service_type:  Optional[str]
    job_stage:     Optional[str]
    contact_name:  Optional[str]
    contact_phone: Optional[str]
    contact_email: Optional[str]

    # Dashboard counts
    lead_count:    int = 0    # how many tradies received this job
    quote_count:   int = 0    # how many tradies sent a quote
    photo_count:   int = 0
    photos:        list[JobPhotoResponse] = []    # how many photos attached

    # Soft delete + completion tracking
    # Soft delete + completion tracking
    is_deleted:    bool            = False
    deleted_at:    Optional[datetime] = None
    completed_at:  Optional[datetime] = None
    match_intelligence: Optional[str] = None

    # Review state (drives "Leave Review" UI on dashboard)
    has_review:    bool          = False
    review_status: Optional[str] = None  # 'pending' | 'approved' | 'rejected'

    # Redo flag — True when this job returned to in_progress after a dispute
    # resolution (redo_work). Drives the contextual 'tradie is redoing' banner
    # on both homeowner and tradie dashboards.
    is_redo_job:   bool          = False

    # Dispute window — how many hours the homeowner has to raise a dispute.
    # 48 h on first completion; 10 h after a resolved re-dispute.
    # None when no window is active (job not in completed/confirmed state).
    dispute_window_hours:      Optional[int]      = None
    dispute_window_expires_at: Optional[datetime] = None

    created_at:    datetime

    class Config:
        from_attributes = True
