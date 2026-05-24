from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from db.session import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id:          Mapped[int]      = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # What was affected
    entity_type: Mapped[str]      = mapped_column(String(50),  nullable=True, index=True)   # 'job', 'review', 'quote', 'user', etc.
    entity_id:   Mapped[str]      = mapped_column(String(100), nullable=True)                # UUID of the entity
    # Who did it
    actor_id:    Mapped[str]      = mapped_column(String,      nullable=True, index=True)    # user.id from JWT
    actor_role:  Mapped[str]      = mapped_column(String(30),  nullable=True)                # 'homeowner', 'tradie', 'admin', 'anonymous'
    # What they did
    action:      Mapped[str]      = mapped_column(String(20),  nullable=False)               # HTTP method: POST, PATCH, PUT, DELETE
    path:        Mapped[str]      = mapped_column(String(500), nullable=False)               # e.g. /api/v1/jobs/abc-123/status
    status_code: Mapped[int]      = mapped_column(nullable=True)                              # HTTP response status
    # Context
    ip_address:  Mapped[str]      = mapped_column(String(45),  nullable=True)                # IPv4 or IPv6
    user_agent:  Mapped[str]      = mapped_column(String(500), nullable=True)
    # Timestamp
    created_at:  Mapped[datetime] = mapped_column(DateTime,    default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<AuditEvent {self.action} {self.path} by {self.actor_id}>"
