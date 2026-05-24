"""
backend/schemas/tradie_schema.py

UPDATED — new schemas added at the bottom for:
  CertificationResponse        Individual cert row (used in list + onboarding status)
  InsurancePolicyResponse      Individual insurance policy row
  TeamMemberResponse           Worker card (internal — never shown to homeowners pre-assignment)
  TeamMemberWithCertsResponse  Worker card + their certifications (owner dashboard)
  OnboardingGates              Computed gate booleans (profile approved? cert? insurance?)
  OnboardingStatusResponse     Full /onboarding/status payload
  AssignedWorkerPublic         What homeowners see after job assignment (name + business only)

All existing schemas are preserved exactly.
"""
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, date


# ═══════════════════════════════════════════════════════════════════════════
# EXISTING SCHEMAS — PRESERVED EXACTLY
# ═══════════════════════════════════════════════════════════════════════════

class CategoryBrief(BaseModel):
    id:   str
    name: str

    class Config:
        from_attributes = True


class ReviewResponse(BaseModel):
    id:             str
    rating:         int
    comment:        Optional[str]
    created_at:     datetime
    homeowner_name: Optional[str] = None

    class Config:
        from_attributes = True


class TradieProfileCreate(BaseModel):
    business_name: str
    abn:           Optional[str]   = None
    bio:           Optional[str]   = None
    suburb:        Optional[str]   = None
    state:         Optional[str]   = None
    postcode:      Optional[str]   = None
    lat:           Optional[float] = None
    lng:           Optional[float] = None
    radius_km:     Optional[int]   = 25


class TradieProfileUpdate(BaseModel):
    """All fields optional — used by PATCH /profile/me."""
    business_name:   Optional[str]   = None
    abn:             Optional[str]   = None
    bio:             Optional[str]   = None
    suburb:          Optional[str]   = None
    state:           Optional[str]   = None
    postcode:        Optional[str]   = None
    lat:             Optional[float] = None
    lng:             Optional[float] = None
    radius_km:       Optional[int]   = None
    is_available:    Optional[bool]  = None
    avatar_url:      Optional[str]   = None
    cover_photo_url: Optional[str]   = None


class TradieProfileResponse(BaseModel):
    """Authenticated tradie — includes sensitive fields like credits."""
    id:                  str
    user_id:             str
    business_name:       str
    abn:                 Optional[str]
    bio:                 Optional[str]
    suburb:              Optional[str]
    state:               Optional[str]
    postcode:            Optional[str]
    lat:                 Optional[float]
    lng:                 Optional[float]
    radius_km:           int
    is_available:        bool
    credits:             int
    avatar_url:          Optional[str]
    cover_photo_url:     Optional[str]
    verification_status: str = "pending_review"
    solo_or_team:        str = "solo"
    team_size:           Optional[str] = None
    phone:               Optional[str] = None

    class Config:
        from_attributes = True


class TradiePublicResponse(BaseModel):
    """
    Public profile — homeowner-facing.
    Hides: ratings, review count, reviews list, solo/team, team size,
    email, phone, ABN, lat/lng, credits.
    """
    id:              str
    business_name:   str
    bio:             Optional[str]
    suburb:          Optional[str]
    state:           Optional[str]
    is_available:    bool
    avatar_url:      Optional[str]
    cover_photo_url: Optional[str]
    is_verified:     bool = False
    full_name:       Optional[str] = None
    categories:      List[CategoryBrief] = []

    class Config:
        from_attributes = True


class TradieListItem(BaseModel):
    """Single tradie card on browse page. No ratings shown publicly."""
    id:            str
    business_name: str
    bio:           Optional[str]
    suburb:        Optional[str]
    state:         Optional[str]
    is_available:  bool
    avatar_url:    Optional[str]
    is_verified:   bool = False
    categories:    List[CategoryBrief] = []

    class Config:
        from_attributes = True


class TradieListResponse(BaseModel):
    """Paginated list of tradies for the browse page."""
    items:       List[TradieListItem]
    total:       int
    page:        int
    limit:       int
    total_pages: int


class InquiryCreate(BaseModel):
    """Sent by homeowner from the tradie public profile page."""
    name:    str
    email:   str
    phone:   Optional[str] = None
    message: str


class InquiryResponse(BaseModel):
    id:         str
    tradie_id:  str
    name:       str
    email:      str
    phone:      Optional[str]
    message:    str
    created_at: datetime

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════════
# NEW SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════

# ── Certification ─────────────────────────────────────────────────────────────

class CertificationResponse(BaseModel):
    """
    Single trade licence certification row.
    Returned in /certifications/me and embedded in OnboardingStatusResponse.
    rejection_reason and rejection_note are only populated when status = 'rejected'.
    """
    id:               str
    category_id:      str
    category_name:    Optional[str] = None   # populated when category is joined
    licence_number:   str
    issuing_state:    str
    issuing_body:     Optional[str] = None
    holder_name:      str
    issued_at:        Optional[date] = None
    expires_at:       Optional[date] = None
    photo_url:        Optional[str]  = None
    status:           str            # pending | in_review | verified | rejected | expired
    rejection_reason: Optional[str]  = None
    rejection_note:   Optional[str]  = None
    verified_at:      Optional[datetime] = None
    team_member_id:   Optional[str]  = None
    created_at:       datetime

    class Config:
        from_attributes = True


# ── Insurance policy ──────────────────────────────────────────────────────────

class InsurancePolicyResponse(BaseModel):
    """
    Single insurance policy row.
    Returned in /insurance/me and embedded in OnboardingStatusResponse.
    coverage_amount_aud is a computed display string — always use
    coverage_amount_cents for any arithmetic.
    """
    id:                     str
    insurance_type:         str      # public_liability | workers_compensation | professional_indemnity
    insurer_name:           str
    policy_number:          str
    coverage_amount_cents:  int
    coverage_amount_aud:    str      # e.g. "$20,000,000.00" — computed in validator
    holder_name:            str
    issued_at:              Optional[date] = None
    expires_at:             date
    document_url:           Optional[str]  = None
    status:                 str            # pending | in_review | verified | rejected | expired
    rejection_reason:       Optional[str]  = None
    rejection_note:         Optional[str]  = None
    verified_at:            Optional[datetime] = None
    created_at:             datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_display(cls, obj) -> "InsurancePolicyResponse":
        """
        Use this instead of model_validate when you want coverage_amount_aud computed.
        The plain from_attributes path will leave coverage_amount_aud as an empty string
        because it is not a DB column — call this factory method from the router instead.
        """
        return cls(
            id=obj.id,
            insurance_type=obj.insurance_type,
            insurer_name=obj.insurer_name,
            policy_number=obj.policy_number,
            coverage_amount_cents=obj.coverage_amount_cents,
            coverage_amount_aud=f"${obj.coverage_amount_cents / 100:,.2f}",
            holder_name=obj.holder_name,
            issued_at=obj.issued_at,
            expires_at=obj.expires_at,
            document_url=obj.document_url,
            status=obj.status,
            rejection_reason=obj.rejection_reason,
            rejection_note=obj.rejection_note,
            verified_at=obj.verified_at,
            created_at=obj.created_at,
        )


# ── Team member ───────────────────────────────────────────────────────────────

class TeamMemberResponse(BaseModel):
    """
    Worker card returned to the business owner.
    NEVER returned to homeowners before job assignment.
    hashed_password is never included here — it is excluded at the model level.
    phone_real is not included — owners see it in the edit form only.
    """
    id:               str
    full_name:        str
    email:            str
    role:             str            # owner | worker
    is_active:        bool
    can_accept_jobs:  bool
    avatar_url:       Optional[str]  = None
    selfie_url:       Optional[str]  = None
    jobs_completed:   int            = 0
    no_show_count:    int            = 0
    rating_avg:       Optional[float] = None
    created_at:       datetime

    class Config:
        from_attributes = True


class TeamMemberWithCertsResponse(TeamMemberResponse):
    """
    Worker card + their certifications.
    Used in GET /team/workers and GET /onboarding/status.
    Inherits all TeamMemberResponse fields.
    """
    certifications: List[CertificationResponse] = []


# ── Onboarding gates ──────────────────────────────────────────────────────────

class OnboardingGates(BaseModel):
    """
    Computed boolean gates that determine whether a tradie can receive jobs.
    All four must be True before the tradie appears in lead distribution.

    profile_approved:       Admin has approved the business profile.
    has_verified_cert:      At least one trade licence is verified and non-expired.
    has_verified_insurance: At least one public liability policy is verified and non-expired.
    ready_to_receive_jobs:  All three above are True — tradie is fully active.
    """
    profile_approved:       bool
    has_verified_cert:      bool
    has_verified_insurance: bool
    ready_to_receive_jobs:  bool


class OnboardingProfileSummary(BaseModel):
    """Lightweight profile summary embedded in OnboardingStatusResponse."""
    id:                  str
    business_name:       str
    verification_status: str
    verification_notes:  Optional[str] = None
    is_available:        bool
    solo_or_team:        str


class OnboardingStatusResponse(BaseModel):
    """
    Full response from GET /onboarding/status.
    Used by the tradie dashboard to render the verification checklist,
    certification list, insurance list, and team member list.

    The frontend uses `gates.ready_to_receive_jobs` to show/hide the
    "You're live!" banner and `gates.has_verified_cert` / `has_verified_insurance`
    to show the specific incomplete step in the checklist.
    """
    profile:            OnboardingProfileSummary
    certifications:     List[CertificationResponse]      = []
    insurance_policies: List[InsurancePolicyResponse]    = []
    team_members:       List[TeamMemberWithCertsResponse] = []
    gates:              OnboardingGates


# ── Assigned worker (homeowner-facing post-assignment) ────────────────────────

class AssignedWorkerPublic(BaseModel):
    """
    What homeowners see after a worker is assigned to their job.
    Per the PDF: user always books the business, not a specific worker.
    First name + business name are revealed only AFTER assignment.
    Full profile, contact details, and certifications are never shown.
    """
    worker_first_name: str    # e.g. "Marcus"
    business_name:     str    # e.g. "Dave's Plumbing"
    avatar_url:        Optional[str] = None
    assignment_type:   str    # 'manual' | 'auto'
    assigned_at:       datetime


# ── Service question (for booking wizard) ─────────────────────────────────────

class ServiceQuestionResponse(BaseModel):
    """
    Single service question from the category tree.
    Returned in GET /categories/tree embedded under each subcategory.
    """
    id:           str
    question:     str
    answer_type:  str            # text | select | multiselect | boolean | number | photo
    options:      Optional[list] = None
    placeholder:  Optional[str]  = None
    is_required:  bool
    sort_order:   int

    class Config:
        from_attributes = True


class CategoryTaskResponse(BaseModel):
    """Level-3 specific task under a subcategory."""
    id:          str
    name:        str
    slug:        str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class CategorySubcategoryResponse(BaseModel):
    """Level-2 subcategory with its service questions and tasks."""
    id:          str
    name:        str
    slug:        str
    description: Optional[str]              = None
    questions:   List[ServiceQuestionResponse] = []
    tasks:       List[CategoryTaskResponse]    = []

    class Config:
        from_attributes = True


class CategoryTreeResponse(BaseModel):
    """
    Level-1 trade category with its subcategories.
    Returned from GET /categories/tree.
    Used by: booking wizard (homeowner picks a trade, then subcategory, then answers questions)
             tradie onboarding (tradie picks which trades they're certified for)
    """
    id:             str
    name:           str
    slug:           str
    icon_slug:      Optional[str]                    = None
    description:    Optional[str]                    = None
    subcategories:  List[CategorySubcategoryResponse] = []

    class Config:
        from_attributes = True


class CategoryTreeListResponse(BaseModel):
    """Wrapper for the full category tree list."""
    categories: List[CategoryTreeResponse]