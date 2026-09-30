from datetime import datetime

from sqlalchemy import ForeignKey, ForeignKeyConstraint, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.catalog import Event


class Poll(Base):
    """Голосование «куда пойдём?» между несколькими событиями."""

    __tablename__ = "polls"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    options: Mapped[list["PollOption"]] = relationship(
        lazy="selectin", order_by="PollOption.id", cascade="all, delete-orphan"
    )


class PollOption(Base):
    __tablename__ = "poll_options"
    __table_args__ = (
        UniqueConstraint("poll_id", "event_id", name="uq_poll_options_poll_event"),
        # Нужен для составного внешнего ключа из poll_votes: вариант принадлежит своему голосованию.
        UniqueConstraint("poll_id", "id", name="uq_poll_options_poll_id_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    poll_id: Mapped[int] = mapped_column(ForeignKey("polls.id", ondelete="CASCADE"))
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))

    event: Mapped[Event] = relationship(lazy="joined")


class PollVote(Base):
    """Один голос на пользователя в голосовании; повторный голос меняет выбор."""

    __tablename__ = "poll_votes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["poll_id", "option_id"],
            ["poll_options.poll_id", "poll_options.id"],
            ondelete="CASCADE",
            name="fk_poll_votes_option_in_poll",
        ),
    )

    poll_id: Mapped[int] = mapped_column(
        ForeignKey("polls.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    option_id: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
