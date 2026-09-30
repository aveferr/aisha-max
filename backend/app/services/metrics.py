"""Метрики пилота (см. презентацию: время выбора, доля завершённых диалогов, вовлечённость)."""

from datetime import datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock, utcnow
from app.models import DialogSession, Interaction, InteractionKind, User


class PilotMetrics(BaseModel):
    period_days: int
    users_total: int
    active_users: int
    dialogs_started: int
    dialogs_with_recommendation: int
    completion_rate: float | None  # доля диалогов, дошедших до подборки
    median_seconds_to_first_recommendation: float | None
    events_shown: int
    favorites_added: int
    reminders_set: int
    ticket_clicks: int
    polls_created: int
    poll_votes: int


class MetricsService:
    def __init__(self, session: AsyncSession, clock: Clock = utcnow) -> None:
        self._session = session
        self._clock = clock

    async def pilot_metrics(self, days: int) -> PilotMetrics:
        since = self._clock() - timedelta(days=days)
        dialogs_started, with_recommendation, median_seconds = await self._dialog_stats(since)
        counts = await self._interaction_counts(since)
        return PilotMetrics(
            period_days=days,
            users_total=await self._session.scalar(select(func.count()).select_from(User)) or 0,
            active_users=await self._session.scalar(
                select(func.count()).select_from(User).where(User.last_seen_at >= since)
            )
            or 0,
            dialogs_started=dialogs_started,
            dialogs_with_recommendation=with_recommendation,
            completion_rate=with_recommendation / dialogs_started if dialogs_started else None,
            median_seconds_to_first_recommendation=median_seconds,
            events_shown=counts.get(InteractionKind.SHOWN, 0),
            favorites_added=counts.get(InteractionKind.FAVORITED, 0),
            reminders_set=counts.get(InteractionKind.REMINDER_SET, 0),
            ticket_clicks=counts.get(InteractionKind.TICKET_CLICK, 0),
            polls_created=counts.get(InteractionKind.POLL_CREATED, 0),
            poll_votes=counts.get(InteractionKind.POLL_VOTED, 0),
        )

    async def _dialog_stats(self, since: datetime) -> tuple[int, int, float | None]:
        seconds_to_first = func.extract(
            "epoch", DialogSession.first_recommended_at - DialogSession.created_at
        )
        row = (
            await self._session.execute(
                select(
                    func.count(),
                    func.sum(cast(DialogSession.first_recommended_at.is_not(None), Integer)),
                    func.percentile_cont(0.5).within_group(seconds_to_first),
                ).where(DialogSession.created_at >= since)
            )
        ).one()
        started, recommended, median = row
        return started, int(recommended or 0), float(median) if median is not None else None

    async def _interaction_counts(self, since: datetime) -> dict[InteractionKind, int]:
        rows = await self._session.execute(
            select(Interaction.kind, func.count())
            .where(Interaction.created_at >= since)
            .group_by(Interaction.kind)
        )
        return dict(rows.all())
