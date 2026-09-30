"""Ранжирование кандидатов и объяснение выбора.

Причины («почему подходит») формируются из реально совпавших полей события, а не генерируются
моделью, поэтому всегда проверяемы.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.assistant.criteria import Companions, Criteria
from app.assistant.vocabulary import TAG_TITLES
from app.models import Category, Event

COMPANION_TAGS = {
    Companions.PARTNER: {"romantic", "calm"},
    Companions.FRIENDS: {"company", "active"},
    Companions.FAMILY: {"family"},
}
MAX_REASONS = 3
SAME_DAY_PENALTY = 0.75  # меньше штрафа за категорию: точное совпадение темы важнее разброса дат


@dataclass
class Scored:
    event: Event
    score: float
    reasons: list[str] = field(default_factory=list)


def score_event(event: Event, criteria: Criteria, interests: set[str], now: datetime) -> Scored:
    score = 0.0
    reasons: list[str] = []

    if criteria.categories and event.category.slug in criteria.categories:
        score += 3
        reasons.append(f"категория «{event.category.title}»")

    if matched_tags := set(criteria.tags) & set(event.tags):
        score += 2 * len(matched_tags)
        titles = ", ".join(TAG_TITLES[tag] for tag in sorted(matched_tags))
        reasons.append(f"подходит под запрос: {titles}")

    score += len(COMPANION_TAGS.get(criteria.companions, set()) & set(event.tags))

    if event.category.slug in interests:
        score += 1.5
        reasons.append("совпадает с вашими интересами")

    if event.is_free:
        score += 0.5
        reasons.append("бесплатно")
    elif criteria.budget_max is not None:
        reasons.append(f"в рамках бюджета (от {event.price_min} ₽)")

    if criteria.pushkin_card and event.pushkin_card:
        score += 1
        reasons.append("принимает Пушкинскую карту")

    if criteria.companions == Companions.KIDS:
        reasons.append(f"подходит детям ({event.age_limit}+)")

    hours_ahead = max((event.starts_at - now).total_seconds() / 3600, 0)
    score += max(0.0, 1 - hours_ahead / (24 * 7))  # чем ближе начало, тем выше (в пределах недели)

    return Scored(event, score, reasons[:MAX_REASONS])


def pick_top(scored: list[Scored], limit: int, tz: ZoneInfo) -> list[Scored]:
    """Жадно выбирает лучшие, штрафуя повтор категории и дня, чтобы подборка была разнообразной.

    Без штрафа за день при запросе «на неделе» все три карточки оказывались сегодняшними:
    близость начала добавляет баллы, и ближайшие события всегда выигрывают.
    """
    pool = sorted(scored, key=lambda s: (-s.score, s.event.starts_at, s.event.id))
    chosen: list[Scored] = []
    seen_categories: set[int] = set()
    seen_days: set[date] = set()

    def day_of(s: Scored) -> date:
        return s.event.starts_at.astimezone(tz).date()

    def adjusted(s: Scored) -> float:
        penalty = 1.0 if s.event.category_id in seen_categories else 0.0
        penalty += SAME_DAY_PENALTY if day_of(s) in seen_days else 0.0
        return s.score - penalty

    while pool and len(chosen) < limit:
        best = max(pool, key=adjusted)
        pool.remove(best)
        chosen.append(best)
        seen_categories.add(best.event.category_id)
        seen_days.add(day_of(best))
    return chosen


def interest_slugs(categories: list[Category]) -> set[str]:
    return {category.slug for category in categories}
