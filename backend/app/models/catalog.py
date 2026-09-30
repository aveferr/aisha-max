from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, str_enum


class EventStatus(StrEnum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"


class City(Base):
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(30), unique=True)
    title: Mapped[str] = mapped_column(String(60))
    emoji: Mapped[str] = mapped_column(String(8), default="")


class Venue(Base):
    __tablename__ = "venues"
    __table_args__ = (UniqueConstraint("city_id", "name", name="uq_venues_city_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    address: Mapped[str] = mapped_column(String(250), default="")
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    city: Mapped[City] = relationship(lazy="joined")


class Event(Base):
    """Событие афиши. Цены — в рублях (целые), время — timestamptz."""

    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_events_source_external_id"),
        CheckConstraint("price_min >= 0", name="price_min_non_negative"),
        CheckConstraint("price_max IS NULL OR price_max >= price_min", name="price_range"),
        Index("ix_events_status_starts_at", "status", "starts_at"),
        Index("ix_events_tags", "tags", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(50))
    external_id: Mapped[str] = mapped_column(String(100))

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), index=True)

    starts_at: Mapped[datetime]
    ends_at: Mapped[datetime | None]

    price_min: Mapped[int] = mapped_column(Integer, default=0)
    price_max: Mapped[int | None] = mapped_column(Integer)
    age_limit: Mapped[int] = mapped_column(SmallInteger, default=0)
    pushkin_card: Mapped[bool] = mapped_column(default=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(30)), server_default="{}")

    image_url: Mapped[str | None] = mapped_column(String(500))
    ticket_url: Mapped[str | None] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(String(500))

    status: Mapped[EventStatus] = mapped_column(
        str_enum(EventStatus), default=EventStatus.SCHEDULED
    )
    is_test_data: Mapped[bool] = mapped_column(default=False)
    data_updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    category: Mapped[Category] = relationship(lazy="joined")
    venue: Mapped[Venue] = relationship(lazy="joined")

    @property
    def is_free(self) -> bool:
        return self.price_min == 0
