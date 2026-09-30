from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.models.base import Base, str_enum


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class InteractionKind(StrEnum):
    """Действия пользователя, по которым считаются метрики пилота."""

    SHOWN = "shown"
    OPENED = "opened"
    FAVORITED = "favorited"
    REMINDER_SET = "reminder_set"
    TICKET_CLICK = "ticket_click"
    POLL_CREATED = "poll_created"
    POLL_VOTED = "poll_voted"


class DialogSession(Base):
    """Сессия диалога с ассистентом: накопленные критерии подбора и уже показанные события."""

    __tablename__ = "dialog_sessions"
    __table_args__ = (
        Index(
            "uq_dialog_sessions_active_user",
            "user_id",
            unique=True,
            postgresql_where="is_active",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    is_active: Mapped[bool] = mapped_column(default=True)
    criteria: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    state: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    shown_event_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), server_default="{}")
    first_recommended_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), default=utcnow, onupdate=utcnow
    )


class DialogMessage(Base):
    __tablename__ = "dialog_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("dialog_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[MessageRole] = mapped_column(str_enum(MessageRole))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Interaction(Base):
    __tablename__ = "interactions"
    __table_args__ = (Index("ix_interactions_kind_created_at", "kind", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"))
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("dialog_sessions.id", ondelete="SET NULL")
    )
    kind: Mapped[InteractionKind] = mapped_column(str_enum(InteractionKind))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
