"""Фоновые циклы бота: приём обновлений (long polling) и рассылка напоминаний."""

import asyncio
import contextlib
import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.client import MaxApiError, MaxClient
from app.bot.dispatcher import BotDispatcher
from app.bot.render import render_reminder
from app.core.clock import Clock, utcnow
from app.core.config import Settings
from app.services.reminders import ReminderService

logger = logging.getLogger(__name__)

MAX_BACKOFF_SECONDS = 60


async def run_polling(client: MaxClient, dispatcher: BotDispatcher, stop: asyncio.Event) -> None:
    """Получает обновления long polling'ом. При сбоях сети ждёт с нарастающей паузой."""
    marker: int | None = None
    backoff = 1
    while not stop.is_set():
        try:
            updates, new_marker = await client.get_updates(marker)
        except (httpx.HTTPError, MaxApiError):
            logger.exception("Не удалось получить обновления, повтор через %d с", backoff)
            await _sleep(stop, backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
            continue
        backoff = 1
        if new_marker is not None:
            marker = new_marker
        for update in updates:
            await dispatcher.handle(update)


async def send_due_reminders(
    client: MaxClient,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    clock: Clock = utcnow,
) -> int:
    """Отправляет наступившие напоминания; возвращает число обработанных.

    Напоминание помечается отправленным даже при ошибке отправки: повторять бесконечно
    недоступному пользователю бессмысленно, а ошибка попадает в лог.
    """
    async with session_factory() as session:
        due = await ReminderService(session, clock).claim_due()
        for reminder in due:
            try:
                await client.send_message(
                    reminder.user.max_user_id,
                    render_reminder(reminder, settings.tz, clock()),
                )
            except (httpx.HTTPError, MaxApiError):
                logger.exception(
                    "Не удалось отправить напоминание по событию %s", reminder.event_id
                )
        await session.commit()
        return len(due)


async def run_reminders(
    client: MaxClient,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    stop: asyncio.Event,
) -> None:
    while not stop.is_set():
        try:
            await send_due_reminders(client, session_factory, settings)
        except Exception:
            logger.exception("Сбой цикла напоминаний")
        await _sleep(stop, settings.reminder_poll_interval_seconds)


async def _sleep(stop: asyncio.Event, seconds: float) -> None:
    """Пауза, прерываемая остановкой."""
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(stop.wait(), timeout=seconds)
