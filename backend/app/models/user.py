from datetime import datetime

from sqlalchemy import BigInteger, Column, ForeignKey, Index, String, Table, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.catalog import Category, City, Event

user_interests = Table(
    "user_interests",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    max_user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    first_name: Mapped[str] = mapped_column(String(100), default="")
    last_name: Mapped[str | None] = mapped_column(String(100))
    username: Mapped[str | None] = mapped_column(String(100))
    city_id: Mapped[int | None] = mapped_column(ForeignKey("cities.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())

    city: Mapped[City | None] = relationship(lazy="joined")
    interests: Mapped[list[Category]] = relationship(secondary=user_interests, lazy="selectin")


class Favorite(Base):
    __tablename__ = "favorites"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    event: Mapped[Event] = relationship(lazy="joined")


class Reminder(Base):
    """Одно напоминание на пару (пользователь, событие); sent_at заполняется после отправки."""

    __tablename__ = "reminders"
    __table_args__ = (
        Index(
            "ix_reminders_due",
            "remind_at",
            postgresql_where="sent_at IS NULL",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    remind_at: Mapped[datetime]
    sent_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    event: Mapped[Event] = relationship(lazy="joined")
    user: Mapped[User] = relationship(lazy="joined")
