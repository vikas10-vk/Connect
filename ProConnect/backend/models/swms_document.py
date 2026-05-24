import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from db.session import Base


class SWMSDocument(Base):
    __tablename__ = "swms_documents"

    id              : Mapped[str]       = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tradie_id       : Mapped[str]       = mapped_column(String, ForeignKey("tradie_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id          : Mapped[str | None]= mapped_column(String, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)

    job_type        : Mapped[str]       = mapped_column(String(100), nullable=False)
    state           : Mapped[str]       = mapped_column(String(10), nullable=False)
    content         : Mapped[str]       = mapped_column(Text, nullable=False)     # Generated SWMS text
    doc_url         : Mapped[str | None]= mapped_column(String(500), nullable=True)  # R2 PDF URL

    created_at      : Mapped[datetime]  = mapped_column(DateTime, default=datetime.utcnow)