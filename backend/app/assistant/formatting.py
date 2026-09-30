"""Текстовое представление событий и критериев для чата."""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.assistant.criteria import Criteria, TimeOfDay
from app.assistant.vocabulary import MONTHS_SHORT, SOURCE_TITLES, TAG_TITLES, WEEKDAYS_SHORT
from app.models import Event

TIME_OF_DAY_TITLES = {
    TimeOfDay.MORNING: "утром",
    TimeOfDay.DAY: "днём",
    TimeOfDay.EVENING: "вечером",
}
RANGE_START = {"сегодня": "сегодняшнего дня", "завтра": "завтрашнего дня"}


def format_day(moment: datetime, tz: ZoneInfo, now: datetime) -> str:
    local, today = moment.astimezone(tz), now.astimezone(tz).date()
    if local.date() == today:
        return "сегодня"
    if (local.date() - today).days == 1:
        return "завтра"
    return f"{WEEKDAYS_SHORT[local.weekday()]}, {local.day} {MONTHS_SHORT[local.month - 1]}"


def format_when(moment: datetime, tz: ZoneInfo, now: datetime) -> str:
    return f"{format_day(moment, tz, now)}, {moment.astimezone(tz).strftime('%H:%M')}"


def format_price(event: Event) -> str:
    if event.is_free:
        return "бесплатно"
    if event.price_max and event.price_max != event.price_min:
        return f"{event.price_min}–{event.price_max} ₽"
    return f"от {event.price_min} ₽"


def format_source(event: Event, tz: ZoneInfo) -> str:
    """Происхождение и актуальность данных — обязательная часть каждой карточки."""
    source = SOURCE_TITLES.get(event.source, event.source)
    updated = event.data_updated_at.astimezone(tz).strftime("%d.%m")
    note = f"Источник: {source}, актуально на {updated}"
    return f"{note} ⚠ тестовые данные" if event.is_test_data else note


def format_card(index: int, event: Event, reasons: list[str], tz: ZoneInfo, now: datetime) -> str:
    facts = [
        f"{event.category.emoji} {event.category.title}",
        format_when(event.starts_at, tz, now),
        event.venue.name,
    ]
    details = [format_price(event), f"{event.age_limit}+"]
    if event.pushkin_card:
        details.append("Пушкинская карта")
    lines = [f"{index}. {event.title}", "   " + " · ".join(facts), "   " + " · ".join(details)]
    if reasons:
        lines.append("   Почему подходит: " + "; ".join(reasons))
    lines.append("   " + format_source(event, tz))
    return "\n".join(lines)


def describe_criteria(
    criteria: Criteria, tz: ZoneInfo, now: datetime, category_titles: dict[str, str]
) -> str:
    """Короткая сводка «что ищу», чтобы пользователь видел, как его поняли."""
    parts: list[str] = []
    if criteria.categories:
        parts.append(", ".join(category_titles.get(slug, slug) for slug in criteria.categories))
    parts.extend(TAG_TITLES[tag] for tag in criteria.tags)
    if criteria.date_from and criteria.date_to:
        first, last = format_day(criteria.date_from, tz, now), format_day(criteria.date_to, tz, now)
        # Диапазон пишем словами: «сегодня — пн, 5 окт» читалось как «только сегодня».
        start = RANGE_START.get(first, first)
        parts.append(first if first == last else f"с {start} по {last}")
    if criteria.time_of_day:
        parts.append(TIME_OF_DAY_TITLES[criteria.time_of_day])
    if criteria.free_only:
        parts.append("бесплатно")
    elif criteria.budget_max is not None:
        parts.append(f"до {criteria.budget_max} ₽")
    if criteria.pushkin_card:
        parts.append("по Пушкинской карте")
    return " · ".join(parts) or "любые события"


def plural(n: int, forms: tuple[str, str, str]) -> str:
    """Русское склонение: plural(1, ("голос", "голоса", "голосов")) → «голос»."""
    if 11 <= n % 100 <= 14:
        return forms[2]
    return forms[0] if n % 10 == 1 else forms[1] if 2 <= n % 10 <= 4 else forms[2]
