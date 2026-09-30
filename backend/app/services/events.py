from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import Category, Event, EventStatus, Venue


@dataclass
class EventFilters:
    city_id: int | None = None
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)  # достаточно совпадения хотя бы с одним
    starts_from: datetime | None = None
    starts_to: datetime | None = None
    budget_max: int | None = None
    free_only: bool = False
    pushkin_card: bool = False
    max_age_limit: int | None = None
    hours: tuple[int, int] | None = None  # локальный час начала: [с, по)
    text: str | None = None
    exclude_ids: Collection[int] = ()


class EventService:
    def __init__(self, session: AsyncSession, tz: ZoneInfo) -> None:
        self._session = session
        self._tz = tz

    async def get(self, event_id: int) -> Event:
        event = await self._session.get(Event, event_id)
        if event is None:
            raise NotFoundError("Событие не найдено")
        return event

    async def search(
        self, filters: EventFilters, *, limit: int, offset: int = 0
    ) -> tuple[list[Event], int]:
        conditions = self._conditions(filters)
        total = await self._session.scalar(
            select(func.count()).select_from(Event).where(*conditions)
        )
        events = await self._session.scalars(
            select(Event)
            .where(*conditions)
            .order_by(Event.starts_at, Event.id)
            .limit(limit)
            .offset(offset)
        )
        return list(events), total or 0

    def _conditions(self, f: EventFilters) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = [Event.status == EventStatus.SCHEDULED]
        if f.city_id is not None:
            conditions.append(
                Event.venue_id.in_(select(Venue.id).where(Venue.city_id == f.city_id))
            )
        if f.categories:
            conditions.append(
                Event.category_id.in_(select(Category.id).where(Category.slug.in_(f.categories)))
            )
        if f.tags:
            conditions.append(Event.tags.overlap(f.tags))
        if f.starts_from is not None:
            conditions.append(Event.starts_at >= f.starts_from)
        if f.starts_to is not None:
            conditions.append(Event.starts_at <= f.starts_to)
        if f.free_only:
            conditions.append(Event.price_min == 0)
        elif f.budget_max is not None:
            conditions.append(Event.price_min <= f.budget_max)
        if f.pushkin_card:
            conditions.append(Event.pushkin_card.is_(True))
        if f.max_age_limit is not None:
            conditions.append(Event.age_limit <= f.max_age_limit)
        if f.hours is not None:
            local_hour = func.extract("hour", func.timezone(self._tz.key, Event.starts_at))
            conditions.append(local_hour >= f.hours[0])
            conditions.append(local_hour < f.hours[1])
        if f.text:
            pattern = (
                "%" + f.text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            )
            conditions.append(
                Event.title.ilike(pattern, escape="\\")
                | Event.description.ilike(pattern, escape="\\")
            )
        if f.exclude_ids:
            conditions.append(Event.id.not_in(f.exclude_ids))
        return conditions
