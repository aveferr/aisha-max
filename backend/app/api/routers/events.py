from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.api.deps import CurrentUserDep, EventServiceDep, OptionalUserDep, SessionDep
from app.api.mappers import event_out
from app.core.clock import utcnow
from app.models import InteractionKind
from app.schemas.catalog import EventOut, Page
from app.services.events import EventFilters
from app.services.favorites import FavoriteService
from app.services.interactions import InteractionService

router = APIRouter(prefix="/events", tags=["events"])


class EventQuery(BaseModel):
    """Параметры каталога. Без date_from показываются только предстоящие события."""

    city_id: int | None = Field(default=None, description="По умолчанию — город пользователя")
    category: list[str] = Field(default_factory=list, description="Слаги категорий")
    tag: list[str] = Field(default_factory=list)
    date_from: datetime | None = None
    date_to: datetime | None = None
    price_max: int | None = Field(default=None, ge=0)
    free: bool = False
    pushkin_card: bool = False
    max_age: int | None = Field(
        default=None, ge=0, le=21, description="Возрастное ограничение не выше"
    )
    q: str | None = Field(default=None, max_length=100, description="Поиск по названию и описанию")
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


@router.get("", response_model=Page[EventOut])
async def list_events(
    query: Annotated[EventQuery, Query()],
    events: EventServiceDep,
    user: OptionalUserDep,
    session: SessionDep,
) -> Page[EventOut]:
    filters = EventFilters(
        city_id=query.city_id if query.city_id is not None else (user.city_id if user else None),
        categories=query.category,
        tags=query.tag,
        starts_from=query.date_from or utcnow(),
        starts_to=query.date_to,
        budget_max=query.price_max,
        free_only=query.free,
        pushkin_card=query.pushkin_card,
        max_age_limit=query.max_age,
        text=query.q,
    )
    items, total = await events.search(filters, limit=query.limit, offset=query.offset)
    favorites = await FavoriteService(session).favorite_ids(user, [e.id for e in items])
    return Page(
        items=[event_out(e, favorites) for e in items],
        total=total,
        limit=query.limit,
        offset=query.offset,
    )


@router.get("/{event_id}", response_model=EventOut)
async def get_event(
    event_id: int, events: EventServiceDep, user: OptionalUserDep, session: SessionDep
) -> EventOut:
    event = await events.get(event_id)
    favorites = await FavoriteService(session).favorite_ids(user, [event_id])
    if user is not None:
        InteractionService(session).log(user.id, InteractionKind.OPENED, event_ids=[event_id])
        await session.commit()
    return event_out(event, favorites)


class TicketLink(BaseModel):
    ticket_url: str | None


@router.post("/{event_id}/ticket-click", response_model=TicketLink)
async def ticket_click(
    event_id: int, events: EventServiceDep, user: CurrentUserDep, session: SessionDep
) -> TicketLink:
    """Фиксирует переход к покупке (метрика пилота) и возвращает ссылку на первоисточник."""
    event = await events.get(event_id)
    InteractionService(session).log(user.id, InteractionKind.TICKET_CLICK, event_ids=[event_id])
    await session.commit()
    return TicketLink(ticket_url=event.ticket_url)
