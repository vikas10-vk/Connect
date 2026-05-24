import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.session import Base


class ChatConversation(Base):
    __tablename__ = "chat_conversations"

    id           : Mapped[str]           = mapped_column(String,      primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id      : Mapped[str]           = mapped_column(String,      ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role         : Mapped[str]           = mapped_column(String(20),  nullable=False)          # user | assistant
    content      : Mapped[str]           = mapped_column(Text,        nullable=False)
    session_id   : Mapped[str]           = mapped_column(String(100), nullable=False, index=True)

    # Generative UI — stores JSON string of { type, data } for the component to render
    ui_component : Mapped[str | None] = mapped_column(Text,        nullable=True)

    # Vision — stores R2 URL or base64 ref of any uploaded photo
    image_url    : Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Memory — extracted insight tags e.g. '["has_old_plumbing","needs_gutters"]'
    insight_tags : Mapped[str | None] = mapped_column(Text,        nullable=True)

    created_at   : Mapped[datetime]      = mapped_column(DateTime,    default=datetime.utcnow)
