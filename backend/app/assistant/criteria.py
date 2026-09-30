"""Критерии подбора (то, что накоплено за диалог) и патч (то, что извлечено из одной реплики)."""

from datetime import datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field


class Companions(StrEnum):
    ALONE = "alone"
    FRIENDS = "friends"
    PARTNER = "partner"
    FAMILY = "family"
    KIDS = "kids"


class TimeOfDay(StrEnum):
    MORNING = "morning"
    DAY = "day"
    EVENING = "evening"


# Локальные часы начала, полуинтервал [с, по)
TIME_OF_DAY_HOURS = {
    TimeOfDay.MORNING: (6, 12),
    TimeOfDay.DAY: (12, 17),
    TimeOfDay.EVENING: (17, 24),
}


class Criteria(BaseModel):
    """Накопленные пожелания пользователя. Хранится в dialog_sessions.criteria (JSONB)."""

    date_from: datetime | None = None
    date_to: datetime | None = None
    time_of_day: TimeOfDay | None = None
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    budget_max: int | None = None
    free_only: bool = False
    pushkin_card: bool = False
    companions: Companions | None = None
    surprise: bool = False

    @property
    def has_when(self) -> bool:
        return self.date_from is not None

    @property
    def has_focus(self) -> bool:
        """Есть ли хоть что-то, что сужает выбор, — тогда тему можно не переспрашивать."""
        return bool(
            self.categories
            or self.tags
            or self.surprise
            or self.free_only
            or self.budget_max is not None
            or self.pushkin_card
            or self.companions
        )

    @property
    def is_blank(self) -> bool:
        return self == Criteria()


class Patch(BaseModel):
    """Что удалось понять из одной реплики. `when` — токен даты, см. resolve_when."""

    when: str | None = None
    time_of_day: TimeOfDay | None = None
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    budget_max: int | None = None
    free_only: bool = False
    pushkin_card: bool = False
    companions: Companions | None = None
    surprise: bool = False
    more: bool = False  # «покажи ещё»
    cheaper: bool = False  # «дешевле»
    reset: bool = False  # «начать заново»

    def is_empty(self) -> bool:
        return self == Patch()

    def filled_from(self, other: "Patch") -> "Patch":
        """Значения `self` приоритетны, `other` заполняет только то, что у `self` не задано.

        Теги настроения объединяются: правила и модель понимают их с разных сторон.
        """
        merged = self.model_dump()
        for field, value in other.model_dump().items():
            if value in (None, False, []):
                continue
            if field == "tags":
                merged[field] = sorted(set(merged[field]) | set(value))
            elif merged[field] in (None, False, []):
                merged[field] = value
        return Patch(**merged)


WEEKDAY_TOKENS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def resolve_when(token: str, now: datetime, tz: ZoneInfo) -> tuple[datetime, datetime] | None:
    """Токен даты → окно [с, по] в часовом поясе города. Не распознан — None.

    Токены: today, tomorrow, day_after, weekend, week, mon..sun, YYYY-MM-DD.
    """
    local_now = now.astimezone(tz)
    today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)

    def whole_day(day: datetime) -> tuple[datetime, datetime]:
        return day, day + timedelta(days=1) - timedelta(microseconds=1)

    if token == "today":
        window = whole_day(today)
    elif token == "tomorrow":
        window = whole_day(today + timedelta(days=1))
    elif token == "day_after":
        window = whole_day(today + timedelta(days=2))
    elif token == "week":  # семь дней, считая сегодняшний
        window = (today, today + timedelta(days=7) - timedelta(microseconds=1))
    elif token == "weekend":
        if today.weekday() == 6:  # воскресенье — остаётся только сегодня
            window = whole_day(today)
        else:
            saturday = today + timedelta(days=5 - today.weekday())
            window = (saturday, saturday + timedelta(days=2) - timedelta(microseconds=1))
    elif token in WEEKDAY_TOKENS:
        delta = (WEEKDAY_TOKENS.index(token) - today.weekday()) % 7
        window = whole_day(today + timedelta(days=delta))
    else:
        try:
            day = datetime.fromisoformat(token).replace(tzinfo=tz)
        except ValueError:
            return None
        window = whole_day(day)

    start, end = window
    return max(start, local_now), end


def apply_patch(criteria: Criteria, patch: Patch, now: datetime, tz: ZoneInfo) -> Criteria:
    """Возвращает новые критерии: тема и даты заменяются, теги накапливаются."""
    updated = criteria.model_copy(deep=True)

    if patch.when and (window := resolve_when(patch.when, now, tz)):
        updated.date_from, updated.date_to = window
    if patch.time_of_day:
        updated.time_of_day = patch.time_of_day
    if patch.categories:
        updated.categories = list(dict.fromkeys(patch.categories))
        updated.surprise = False
    if patch.tags:
        updated.tags = sorted(set(updated.tags) | set(patch.tags))
    if patch.free_only:
        updated.free_only, updated.budget_max = True, None
    elif patch.budget_max is not None:
        updated.budget_max, updated.free_only = patch.budget_max, False
    if patch.pushkin_card:
        updated.pushkin_card = True
    if patch.companions:
        updated.companions = patch.companions
    if patch.surprise:
        updated.surprise = True
    return updated
