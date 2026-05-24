import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.session import Base


class TradieChangeRequestStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class TradieChangeRequestType:
    SERVICE_AREAS = "service_areas"
    SERVICE_ADD = "service_add"
    SERVICE_REMOVE = "service_remove"
    PROFILE_IDENTITY = "profile_identity"


class TradieChangeRequest(Base):
    __tablename__ = "tradie_change_requests"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tradie_id: Mapped[str] = mapped_column(
        String, ForeignKey("tradie_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    request_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), default=TradieChangeRequestStatus.PENDING, nullable=False, index=True
    )
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=True)
    admin_note: Mapped[str] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    tradie = relationship("TradieProfile")
    requester = relationship("User", foreign_keys=[requested_by])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
