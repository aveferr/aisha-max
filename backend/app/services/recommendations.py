"""Подбор событий по критериям с прозрачным «ослаблением» условий, если ничего не найдено."""

from collections.abc import Collection, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.criteria import TIME_OF_DAY_HOURS, Companions, Criteria
from app.assistant.ranking import interest_slugs, pick_top, score_event
from app.core.clock import Clock, utcnow
from app.core.config import get_settings
from app.models import Event, User
from app.services.events import EventFilters, EventService

CANDIDATE_LIMIT = 60
DEFAULT_HORIZON = timedelta(days=14)  # окно поиска, если пользователь не назвал дату
KIDS_MAX_AGE_LIMIT = 12
WIDEN_DATES_BY = timedelta(days=7)


@dataclass
class Card:
    event: Event
    reasons: list[str] = field(default_factory=list)


@dataclass
class Recommendation:
    cards: list[Card]
    relaxed: list[str] = field(default_factory=list)  # что пришлось ослабить (для честного ответа)


def relaxations(criteria: Criteria) -> Iterator[tuple[Criteria, list[str]]]:
    """Исходные критерии, затем всё более мягкие варианты с описанием того, что ослаблено."""
    yield criteria, []
    notes: list[str] = []
    current = criteria

    if current.tags:
        current = current.model_copy(update={"tags": []})
        notes.append("без учёта пожеланий к формату")
        yield current, list(notes)
    if current.time_of_day:
        current = current.model_copy(update={"time_of_day": None})
        notes.append("в любое время суток")
        yield current, list(notes)
    if current.date_to:
        current = current.model_copy(update={"date_to": current.date_to + WIDEN_DATES_BY})
        notes.append("период расширен на неделю")
        yield current, list(notes)
    if current.budget_max is not None:
        current = current.model_copy(update={"budget_max": current.budget_max * 2})
        notes.append("бюджет увеличен вдвое")
        yield current, list(notes)
    if current.categories:
        current = current.model_copy(update={"categories": []})
        notes.append("из других категорий")
        yield current, list(notes)


class RecommendationService:
    def __init__(self, session: AsyncSession, events: EventService, clock: Clock = utcnow) -> None:
        self._session = session
        self._events = events
        self._clock = clock

    async def recommend(
        self, user: User, criteria: Criteria, *, exclude_ids: Collection[int] = (), limit: int = 3
    ) -> Recommendation:
        now = self._clock()
        interests = interest_slugs(user.interests)
        for candidate_criteria, notes in relaxations(criteria):
            filters = self._to_filters(candidate_criteria, user, exclude_ids, now)
            events, _ = await self._events.search(filters, limit=CANDIDATE_LIMIT)
            if events:
                scored = [score_event(e, candidate_criteria, interests, now) for e in events]
                picked = pick_top(scored, limit, get_settings().tz)
                cards = [Card(s.event, s.reasons) for s in picked]
                return Recommendation(cards, notes)
        return Recommendation([])

    @staticmethod
    def _to_filters(
        criteria: Criteria, user: User, exclude_ids: Collection[int], now: datetime
    ) -> EventFilters:
        return EventFilters(
            city_id=user.city_id,
            categories=criteria.categories,
            tags=criteria.tags,
            starts_from=max(criteria.date_from or now, now),
            starts_to=criteria.date_to or now + DEFAULT_HORIZON,
            budget_max=criteria.budget_max,
            free_only=criteria.free_only,
            pushkin_card=criteria.pushkin_card,
            max_age_limit=KIDS_MAX_AGE_LIMIT if criteria.companions == Companions.KIDS else None,
            hours=TIME_OF_DAY_HOURS[criteria.time_of_day] if criteria.time_of_day else None,
            exclude_ids=exclude_ids,
        )
