from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock, utcnow
from app.core.errors import DomainError, NotFoundError
from app.models import Event, EventStatus, InteractionKind, Reminder, User
from app.services.interactions import InteractionService

DEFAULT_REMIND_BEFORE_MINUTES = 120


class ReminderService:
    def __init__(self, session: AsyncSession, clock: Clock = utcnow) -> None:
        self._session = session
        self._clock = clock
        self._interactions = InteractionService(session)

    async def set(
        self, user: User, event_id: int, minutes_before: int = DEFAULT_REMIND_BEFORE_MINUTES
    ) -> Reminder:
        event = await self._session.get(Event, event_id)
        if event is None:
            raise NotFoundError("Событие не найдено")
        if event.status != EventStatus.SCHEDULED:
            raise DomainError("Событие отменено, напоминание не нужно")
        remind_at = event.starts_at - timedelta(minutes=minutes_before)
        if remind_at <= self._clock():
            raise DomainError("До начала слишком мало времени для такого напоминания")

        await self._session.execute(
            pg_insert(Reminder)
            .values(user_id=user.id, event_id=event_id, remind_at=remind_at)
            .on_conflict_do_update(
                index_elements=[Reminder.user_id, Reminder.event_id],
                set_={"remind_at": remind_at, "sent_at": None},
            )
        )
        self._interactions.log(user.id, InteractionKind.REMINDER_SET, event_ids=[event_id])
        await self._session.flush()
        return await self._session.get(Reminder, (user.id, event_id), populate_existing=True)

    async def remove(self, user: User, event_id: int) -> None:
        await self._session.execute(
            delete(Reminder).where(Reminder.user_id == user.id, Reminder.event_id == event_id)
        )

    async def list_active(self, user: User) -> list[Reminder]:
        rows = await self._session.scalars(
            select(Reminder)
            .join(Reminder.event)
            .where(Reminder.user_id == user.id, Reminder.sent_at.is_(None))
            .order_by(Reminder.remind_at)
        )
        return list(rows)

    async def claim_due(self, limit: int = 50) -> list[Reminder]:
        """Забирает наступившие напоминания и помечает их отправленными.

        SKIP LOCKED позволяет нескольким воркерам работать параллельно без дублей.
        """
        now = self._clock()
        due = list(
            await self._session.scalars(
                select(Reminder)
                .where(Reminder.sent_at.is_(None), Reminder.remind_at <= now)
                .order_by(Reminder.remind_at)
                .limit(limit)
                .with_for_update(skip_locked=True, of=Reminder)
            )
        )
        for reminder in due:
            reminder.sent_at = now
        return due
