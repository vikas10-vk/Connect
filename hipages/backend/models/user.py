import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.session import Base

class UserRole(str):
    HOMEOWNER = "homeowner"
    TRADIE    = "tradie"

class User(Base):
    __tablename__ = "users"

    id:              Mapped[str]      = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email:           Mapped[str]      = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone:           Mapped[str]      = mapped_column(String(20), nullable=True)
    full_name:       Mapped[str]      = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str]      = mapped_column(String(255), nullable=False)
    role:            Mapped[str]      = mapped_column(String(20), nullable=False)
    is_active:       Mapped[bool]     = mapped_column(Boolean, default=True)
    is_verified:     Mapped[bool]     = mapped_column(Boolean, default=False)
    email_verified:  Mapped[bool]     = mapped_column(Boolean, default=False)

    created_at:      Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at:      Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tradie_profile = relationship("TradieProfile", back_populates="user", uselist=False)

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"