"""
backend/models/job_assignment.py

Records every assignment of a worker to a job.

ASSIGNMENT RULES (enforced at API layer, not just here):
  1. Workers CANNOT self-assign. Only the business owner or the auto-dispatch
     Celery task can create rows here. Enforced in FastAPI middleware by
     checking the JWT token's TeamMember role.
  2. Only one row per job can have is_active=True at any time.
     A reassignment deactivates the previous row (is_active=False) and
     creates a new one. This preserves the full assignment history.
  3. Every row records assigned_by_id (NULL = system auto-dispatch) so
     "who sent this person?" is always answerable from the DB.

DOUBLE-DISPATCH PREVENTION:
  The assignment endpoint uses SELECT FOR UPDATE on the job row during
  assignment. If assigned_worker_id is already set on the active assignment,
  the endpoint rejects the duplicate. Only one assignment wins.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.session import Base


class AssignmentType:
    MANUAL = "manual"
    AUTO   = "auto"


class JobAssignment(Base):
    __tablename__ = "job_assignments"

    id : Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    job_id : Mapped[str] = mapped_column(
        String, ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    business_id : Mapped[str] = mapped_column(
        String, ForeignKey("tradie_profiles.id"),
        nullable=False,
    )
    assigned_worker_id : Mapped[str] = mapped_column(
        String, ForeignKey("team_members.id"),
        nullable=False,
    )
    assigned_by_id : Mapped[str] = mapped_column(
        String, ForeignKey("team_members.id"),
        nullable=True,   # NULL = system auto-dispatch
    )

    assignment_type : Mapped[str]      = mapped_column(String(20), default=AssignmentType.MANUAL, nullable=False)
    assigned_at     : Mapped[datetime] = mapped_column(DateTime,   default=datetime.utcnow, nullable=False)

    is_active : Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Only one active assignment per job at any time.
    # Deactivated when job is reassigned — history preserved.

    # ── Relationships ────────────────────────────────────────────────────────
    job            = relationship("Job",        back_populates="assignments",  foreign_keys=[job_id])
    business       = relationship("TradieProfile", foreign_keys=[business_id])
    assigned_worker = relationship("TeamMember",  foreign_keys=[assigned_worker_id])
    assigned_by    = relationship("TeamMember",  foreign_keys=[assigned_by_id])

    def __repr__(self):
        return (
            f"<JobAssignment job={self.job_id[:8]}… "
            f"worker={self.assigned_worker_id[:8]}… "
            f"[{'active' if self.is_active else 'inactive'}]>"
        )