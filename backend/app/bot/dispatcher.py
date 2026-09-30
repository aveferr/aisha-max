"""Маршрутизация обновлений MAX: сообщения, нажатия кнопок и запуск бота по ссылке."""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.assistant.parser import Parser
from app.bot import render
from app.bot.client import MaxApiError, MaxClient
from app.core.clock import Clock, utcnow
from app.core.config import Settings
from app.core.errors import DomainError
from app.models import Event, User
from app.services.dialog import BotReply, DialogService
from app.services.events import EventService
from app.services.favorites import FavoriteService
from app.services.polls import PollService, PollView
from app.services.recommendations import RecommendationService
from app.services.reminders import DEFAULT_REMIND_BEFORE_MINUTES, ReminderService
from app.services.users import MaxProfile, UserService

logger = logging.getLogger(__name__)

POLL_START_PREFIX = "poll_"
ERROR_TEXT = "Что-то пошло не так. Попробуйте ещё раз чуть позже."
MIN_POLL_EVENTS = 2


def profile_from(max_user: dict[str, Any]) -> MaxProfile:
    return MaxProfile(
        max_user_id=int(max_user["user_id"]),
        first_name=max_user.get("first_name") or max_user.get("name") or "",
        last_name=max_user.get("last_name"),
        username=max_user.get("username"),
    )


class BotDispatcher:
    def __init__(
        self,
        client: MaxClient,
        session_factory: async_sessionmaker[AsyncSession],
        parser: Parser,
        settings: Settings,
        clock: Clock = utcnow,
    ) -> None:
        self._client = client
        self._session_factory = session_factory
        self._parser = parser
        self._settings = settings
        self._clock = clock

    async def handle(self, update: dict[str, Any]) -> None:
        """Обрабатывает одно обновление. Никогда не бросает исключений: один сбой не должен
        останавливать приём остальных."""
        update_type = update.get("update_type")
        try:
            async with self._session_factory() as session:
                ctx = _Context(session, self._parser, self._settings, self._clock)
                match update_type:
                    case "bot_started":
                        await self._on_started(ctx, update)
                    case "message_created":
                        await self._on_message(ctx, update)
                    case "message_callback":
                        await self._on_callback(ctx, update)
                    case _:
                        return
                await session.commit()
        except Exception:
            logger.exception("Не удалось обработать обновление %s", update_type)
            await self._apologize(update)

    # --- обработчики -------------------------------------------------------------------------

    async def _on_started(self, ctx: "_Context", update: dict[str, Any]) -> None:
        user = await ctx.users.get_or_create(profile_from(update["user"]))
        payload = update.get("payload") or ""
        if payload.startswith(POLL_START_PREFIX) and payload[len(POLL_START_PREFIX) :].isdigit():
            view = await ctx.polls.get_view(int(payload[len(POLL_START_PREFIX) :]), user)
            await self._send(user, ctx.render_poll(view))
            return
        await self._send(user, ctx.render_reply(await ctx.dialog.start(user)))

    async def _on_message(self, ctx: "_Context", update: dict[str, Any]) -> None:
        message = update["message"]
        sender = message.get("sender") or {}
        text = ((message.get("body") or {}).get("text") or "").strip()
        if sender.get("is_bot") or not text:
            return
        user = await ctx.users.get_or_create(profile_from(sender))

        match text.lower().split()[0]:
            case "/start" | "/reset":
                out = ctx.render_reply(await ctx.dialog.start(user))
            case "/help":
                out = render.build_message(render.MENU_TEXT)
            case "/favorites":
                events = await ctx.favorites.list_events(user)
                out = ctx.render_list("⭐ Избранное", events)
            case "/reminders":
                reminders = await ctx.reminders.list_active(user)
                out = ctx.render_list("🔔 Напоминания", [r.event for r in reminders])
            case _:
                out = ctx.render_reply(await ctx.dialog.handle_text(user, text))
        await self._send(user, out)

    async def _on_callback(self, ctx: "_Context", update: dict[str, Any]) -> None:
        callback = update["callback"]
        callback_id = callback["callback_id"]
        payload = callback.get("payload") or ""
        user = await ctx.users.get_or_create(profile_from(callback["user"]))
        action, _, argument = payload.partition(":")

        try:
            match action:
                case "d":  # быстрые ответы диалога: payload целиком (d:when:today)
                    await self._ack(callback_id)
                    reply = await ctx.dialog.handle_payload(user, payload)
                    await self._send(user, ctx.render_reply(reply))
                case "fav":
                    await ctx.favorites.add(user, int(argument))
                    await self._ack(callback_id, "⭐ Добавлено в избранное")
                case "rem":
                    await ctx.reminders.set(user, int(argument))
                    hours = DEFAULT_REMIND_BEFORE_MINUTES // 60
                    await self._ack(callback_id, f"🔔 Напомню за {hours} ч до начала")
                case "poll" if argument == "new":
                    await self._create_poll(ctx, user, callback_id)
                case "vote":
                    poll_id, _, option_id = argument.partition(":")
                    view = await ctx.polls.vote(user, int(poll_id), int(option_id))
                    await self._ack(callback_id, "Голос учтён", ctx.render_poll(view))
                case _:
                    await self._ack(callback_id)
        except (DomainError, ValueError) as error:
            await self._ack(
                callback_id, str(error) if isinstance(error, DomainError) else ERROR_TEXT
            )

    async def _create_poll(self, ctx: "_Context", user: User, callback_id: str) -> None:
        event_ids = await ctx.dialog.last_shown_ids(user)
        if len(event_ids) < MIN_POLL_EVENTS:
            await self._ack(callback_id, "Сначала подберите хотя бы два события")
            return
        poll = await ctx.polls.create(user, event_ids)
        await self._ack(callback_id, "Голосование создано")
        await self._send(user, ctx.render_poll(await ctx.polls.get_view(poll.id, user)))

    # --- отправка ----------------------------------------------------------------------------

    async def _send(self, user: User, message: dict[str, Any]) -> None:
        await self._client.send_message(user.max_user_id, message)

    async def _ack(
        self,
        callback_id: str,
        notification: str | None = None,
        message: dict[str, Any] | None = None,
    ) -> None:
        """Подтверждение нажатия. Ошибка здесь не должна отменять уже выполненное действие."""
        try:
            await self._client.answer_callback(
                callback_id, notification=notification, message=message
            )
        except (MaxApiError, OSError):
            logger.warning("Не удалось ответить на callback %s", callback_id, exc_info=True)

    async def _apologize(self, update: dict[str, Any]) -> None:
        source = (
            (update.get("callback") or {}).get("user")
            or update.get("user")
            or ((update.get("message") or {}).get("sender"))
        )
        if not source or source.get("is_bot") or "user_id" not in source:
            return
        try:
            await self._client.send_message(
                int(source["user_id"]), render.build_message(ERROR_TEXT)
            )
        except Exception:
            logger.warning("Не удалось отправить сообщение об ошибке", exc_info=True)


class _Context:
    """Сервисы, привязанные к одной сессии БД (то есть к одному обновлению)."""

    def __init__(self, session: AsyncSession, parser: Parser, settings: Settings, clock: Clock):
        self._settings = settings
        self._clock = clock
        events = EventService(session, settings.tz)
        self.users = UserService(session, clock)
        self.favorites = FavoriteService(session)
        self.reminders = ReminderService(session, clock)
        self.polls = PollService(session)
        self.dialog = DialogService(
            session, parser, RecommendationService(session, events, clock), clock
        )

    def render_reply(self, reply: BotReply) -> dict[str, Any]:
        return render.render_reply(
            reply, self._settings.tz, self._clock(), self._settings.max_bot_username
        )

    def render_poll(self, view: PollView) -> dict[str, Any]:
        return render.render_poll(
            view, self._settings.tz, self._clock(), self._settings.max_bot_username
        )

    def render_list(self, title: str, events: list[Event]) -> dict[str, Any]:
        return render.render_event_list(title, events, self._settings.tz, self._clock())
