"""
backend/models/job.py

UPDATED — adds scope change tracking fields, before/after photo URLs,
partial stop support, and completion confirmation timestamp.

All existing fields are preserved exactly.

NEW STATUS VALUES (added to the existing string-based status column):
  awaiting_scope_approval  — tradie requested scope change; homeowner must respond
  partial_stop             — tradie stopped mid-job; admin adjudicates payment
  disputed                 — homeowner raised a dispute within 48h of completion

EXISTING STATUSES (unchanged):
  open, quoted, hired, in_progress, completed, closed, cancelled
"""
import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Float, Boolean, DateTime, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.session import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class IntentLevel(str, enum.Enum):
    high     = "high"
    planning = "planning"


class JobType(str, enum.Enum):
    residential = "residential"
    commercial  = "commercial"


class ServiceType(str, enum.Enum):
    new_installation = "new_installation"
    repair           = "repair"
    replace          = "replace"
    other            = "other"


class JobStageEnum(str, enum.Enum):
    ready_to_hire      = "ready_to_hire"
    planning_budgeting = "planning_budgeting"


class JobStatus(str, enum.Enum):
    # ── Pre-active ──────────────────────────────────────────────
    OPEN        = "open"
    QUOTED      = "quoted"
    HIRED       = "hired"
    # ── Active ──────────────────────────────────────────────────
    IN_PROGRESS = "in_progress"
    # ── Scope approval gate (mid-job only) ──────────────────────
    AWAITING_SCOPE_APPROVAL = "awaiting_scope_approval"
    # ── Stopped / dispute ────────────────────────────────────────
    PARTIAL_STOP = "partial_stop"
    DISPUTED     = "disputed"
    # ── Terminal ─────────────────────────────────────────────────
    COMPLETED   = "completed"
    CLOSED      = "closed"
    CANCELLED   = "cancelled"


# ── Model ─────────────────────────────────────────────────────────────────────

class Job(Base):
    __tablename__ = "jobs"

    # ── Existing fields (UNCHANGED) ────────────────────────────────────────────
    id           : Mapped[str]      = mapped_column(String,      primary_key=True, default=lambda: str(uuid.uuid4()))
    homeowner_id : Mapped[str]      = mapped_column(String,      ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id  : Mapped[str]      = mapped_column(String,      ForeignKey("categories.id"), nullable=False, index=True)

    title        : Mapped[str]      = mapped_column(String(255), nullable=False)
    description  : Mapped[str]      = mapped_column(Text,        nullable=True)

    suburb       : Mapped[str]      = mapped_column(String(100), nullable=True)
    state        : Mapped[str]      = mapped_column(String(50),  nullable=True)
    postcode     : Mapped[str]      = mapped_column(String(10),  nullable=True)
    lat          : Mapped[float]    = mapped_column(Float,       nullable=True)
    lng          : Mapped[float]    = mapped_column(Float,       nullable=True)
    budget_min   : Mapped[float]    = mapped_column(Float,       nullable=True)
    budget_max   : Mapped[float]    = mapped_column(Float,       nullable=True)

    status       : Mapped[str]      = mapped_column(String(30),  default="open", nullable=False, index=True)
    urgency      : Mapped[str]      = mapped_column(String(50),  default="flexible", nullable=True)
    job_type     : Mapped[str]      = mapped_column(String(50),  default="residential", nullable=True)
    service_type : Mapped[str]      = mapped_column(String(50),  default="other", nullable=True)
    job_stage    : Mapped[str]      = mapped_column(String(50),  default="ready_to_hire", nullable=True)
    intent_level : Mapped[str]      = mapped_column(String(20),  default="high", nullable=False)

    contact_name : Mapped[str]      = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str]      = mapped_column(String(20),  nullable=True)
    contact_email: Mapped[str]      = mapped_column(String(255), nullable=True)

    created_at   : Mapped[datetime] = mapped_column(DateTime,    default=datetime.utcnow)
    updated_at   : Mapped[datetime] = mapped_column(DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)

    match_intelligence : Mapped[str] = mapped_column(Text,    nullable=True)
    is_deleted         : Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    lead_task_id       : Mapped[str]  = mapped_column(String,  nullable=True)
    deleted_at         : Mapped[datetime] = mapped_column(DateTime, nullable=True)
    completed_at       : Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # ── NEW: scope change in progress ─────────────────────────────────────────
    # Only one pending scope change allowed at a time.
    # All four fields are set together when tradie requests a scope change,
    # and cleared together when homeowner responds (or timeout fires).
    pending_scope_amount_cents  : Mapped[int]      = mapped_column(Integer,      nullable=True)
    scope_change_reason         : Mapped[str]      = mapped_column(Text,         nullable=True)
    scope_change_category_id    : Mapped[str]      = mapped_column(String,       ForeignKey("categories.id"), nullable=True)
    # NULL = same-category add. Set = different category (skill-boundary check ran and passed or was blocked).
    scope_change_requested_at   : Mapped[datetime] = mapped_column(DateTime,     nullable=True)
    scope_change_expires_at     : Mapped[datetime] = mapped_column(DateTime,     nullable=True)
    scope_change_task_id        : Mapped[str]      = mapped_column(String,       nullable=True)
    # Celery task ID for the 10-minute auto-reject timeout.

    # ── NEW: job evidence (before/after photos) ───────────────────────────────
    # Mandatory for the tradie at job start (before) and completion (after).
    # Timestamped and stored to S3 via /api/upload-photo.
    # These are the primary dispute resolution artifacts.
    photo_before_url  : Mapped[str] = mapped_column(String(500), nullable=True)
    photo_after_url   : Mapped[str] = mapped_column(String(500), nullable=True)
    completion_note   : Mapped[str] = mapped_column(Text,        nullable=True)

    # ── NEW: homeowner confirms completion ────────────────────────────────────
    # Set when homeowner taps "Confirm complete" in app.
    # Starts the 48-hour dispute window. After 48h with no dispute,
    # a Celery beat task flips status → closed.
    confirmed_by_user_at : Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # ── Relationships (UNCHANGED) ─────────────────────────────────────────────
    homeowner   = relationship("User",      foreign_keys=[homeowner_id])
    category    = relationship("Category",  foreign_keys=[category_id])
    leads       = relationship("Lead",      back_populates="job", cascade="all, delete-orphan")
    photos      = relationship("JobPhoto",  back_populates="job", cascade="all, delete-orphan")
    review      = relationship("Review",    back_populates="job", cascade="all, delete-orphan", uselist=False)

    # ── NEW relationship ──────────────────────────────────────────────────────
    assignments = relationship(
        "JobAssignment",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobAssignment.assigned_at.desc()",
    )

    @property
    def active_assignment(self):
        """Returns the currently active JobAssignment, or None."""
        return next((a for a in self.assignments if a.is_active), None)

    def __repr__(self):
        return f"<Job {self.title} [{self.status}]>"