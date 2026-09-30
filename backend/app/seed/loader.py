"""Идемпотентная загрузка справочников и демонстрационных событий."""

import logging
from datetime import datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.vocabulary import CATEGORIES
from app.core.clock import Clock, utcnow
from app.core.config import get_settings
from app.models import Category, City, Event, EventStatus, Venue
from app.seed.demo_events import EVENTS, VENUES, EventSeed

logger = logging.getLogger(__name__)

DEMO_SOURCE = "demo"
MIN_LEAD_TIME = timedelta(hours=1)


async def seed_reference_data(session: AsyncSession) -> None:
    """Город по умолчанию и категории — нужны в любом окружении."""
    await session.execute(
        pg_insert(City).values(name=get_settings().default_city).on_conflict_do_nothing()
    )
    stmt = pg_insert(Category).values(
        [{"slug": c.slug, "title": c.title, "emoji": c.emoji} for c in CATEGORIES]
    )
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[Category.slug],
            set_={"title": stmt.excluded.title, "emoji": stmt.excluded.emoji},
        )
    )


async def seed_demo_events(session: AsyncSession, clock: Clock = utcnow) -> int:
    """Загружает демо-события; даты пересчитываются от «сегодня», поэтому афиша не устаревает."""
    settings = get_settings()
    now = clock()
    city_id = await session.scalar(select(City.id).where(City.name == settings.default_city))
    category_ids = dict((await session.execute(select(Category.slug, Category.id))).all())

    for venue in VENUES:
        stmt = pg_insert(Venue).values(
            city_id=city_id,
            name=venue.name,
            address=venue.address,
            latitude=venue.lat,
            longitude=venue.lon,
        )
        await session.execute(
            stmt.on_conflict_do_update(
                constraint="uq_venues_city_name",
                set_={
                    "address": stmt.excluded.address,
                    "latitude": stmt.excluded.latitude,
                    "longitude": stmt.excluded.longitude,
                },
            )
        )
    venue_ids = {
        venue.key: await session.scalar(
            select(Venue.id).where(Venue.city_id == city_id, Venue.name == venue.name)
        )
        for venue in VENUES
    }

    for seed in EVENTS:
        values = _event_values(seed, category_ids, venue_ids, now, settings.tz)
        stmt = pg_insert(Event).values(**values)
        update = {k: v for k, v in values.items() if k not in ("source", "external_id")}
        await session.execute(
            stmt.on_conflict_do_update(constraint="uq_events_source_external_id", set_=update)
        )
    logger.info("Загружено демо-событий: %d", len(EVENTS))
    return len(EVENTS)


def _event_values(
    seed: EventSeed, category_ids: dict[str, int], venue_ids: dict[str, int], now: datetime, tz
) -> dict:
    hour, minute = map(int, seed.time.split(":"))
    day = now.astimezone(tz).date() + timedelta(days=seed.day_offset)
    starts_at = datetime.combine(day, time(hour, minute), tzinfo=tz)
    while starts_at < now + MIN_LEAD_TIME:  # событие уже прошло — переносим на неделю вперёд
        starts_at += timedelta(days=7)
    return {
        "source": DEMO_SOURCE,
        "external_id": seed.key,
        "title": seed.title,
        "description": seed.description,
        "category_id": category_ids[seed.category],
        "venue_id": venue_ids[seed.venue],
        "starts_at": starts_at,
        "ends_at": starts_at + timedelta(hours=seed.duration_h),
        "price_min": seed.price_min,
        "price_max": seed.price_max,
        "age_limit": seed.age_limit,
        "pushkin_card": seed.pushkin_card,
        "tags": seed.tags,
        "ticket_url": None if seed.price_min == 0 else f"https://example.com/tickets/{seed.key}",
        "status": EventStatus.CANCELLED.value if seed.cancelled else EventStatus.SCHEDULED.value,
        "is_test_data": True,
        "data_updated_at": now,
    }
