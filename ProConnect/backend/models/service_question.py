"""
backend/models/service_question.py

Per-subcategory (level-2 Category) guided questions shown in the booking
wizard before a homeowner confirms their job.

WHY THIS EXISTS:
  "Fix tap" arrives at the tradie's phone with zero context. The tradie
  shows up expecting a simple washer replacement — it's actually a burst
  pipe behind the wall. That wrong-expectation gap causes ~60% of same-day
  cancellations on competitor platforms (Handy internal data).

  ServiceQuestion pre-qualifies every job. The homeowner answers 3-4
  specific questions about their situation. Answers are stored as JSONB
  on jobs.brief_answers. Tradies see a structured brief, not a vague
  free-text blob. Wrong-skill and wrong-expectation bookings drop sharply.

WHERE QUESTIONS LIVE:
  Attached to a level-2 category (subcategory). That means:
  - "Plumbing > Hot Water Systems" gets its own question set
  - "Plumbing > Blocked Drains" gets a different set
  - All plumbing jobs still verify against the level-1 "Plumbing" cert

ANSWER TYPES:
  text      — free text input
  select    — one option from a list (options JSON array of strings)
  multiselect — one or more options (options JSON array)
  boolean   — yes / no toggle
  number    — numeric input (e.g. number of bathrooms)
  photo     — photo upload prompt (stored to S3 via /api/upload-photo)
"""
import uuid
from sqlalchemy import String, SmallInteger, Boolean, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.session import Base


class AnswerType:
    TEXT        = "text"
    SELECT      = "select"
    MULTISELECT = "multiselect"
    BOOLEAN     = "boolean"
    NUMBER      = "number"
    PHOTO       = "photo"


class ServiceQuestion(Base):
    __tablename__ = "service_questions"

    id          : Mapped[str]  = mapped_column(String,       primary_key=True, default=lambda: str(uuid.uuid4()))
    category_id : Mapped[str]  = mapped_column(String,       ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, index=True)

    question_text : Mapped[str] = mapped_column(Text,         nullable=False)
    answer_type   : Mapped[str] = mapped_column(String(20),   nullable=False, default=AnswerType.TEXT)
    options       : Mapped[dict] = mapped_column(JSON,         nullable=True)
    # For answer_type = 'select' or 'multiselect':
    #   options = ["Dripping", "Running constantly", "No water at all"]
    # For answer_type = 'number':
    #   options = {"min": 1, "max": 20, "unit": "bathrooms"}
    # NULL for text, boolean, photo.

    placeholder   : Mapped[str]  = mapped_column(String(255), nullable=True)
    # Hint text shown inside the input. e.g. "Describe where the leak is..."

    is_required   : Mapped[bool] = mapped_column(Boolean,     nullable=False, default=True)
    sort_order    : Mapped[int]  = mapped_column(SmallInteger, nullable=False, default=0)

    # ── Relationships ───────────────────────────────────────────────
    category = relationship("Category", back_populates="service_questions")

    def __repr__(self):
        return f"<ServiceQuestion [{self.answer_type}] {self.question_text[:50]}>"