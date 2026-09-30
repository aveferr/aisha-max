"""Тесты бота: настоящие сервисы и БД, поддельный клиент MAX."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from app.assistant.parser import RuleBasedParser
from app.bot.client import MaxApiError, MaxClient
from app.bot.dispatcher import BotDispatcher
from app.bot.workers import send_due_reminders
from app.core.config import get_settings
from app.core.db import SessionFactory
from app.models import Event, Reminder, User


class FakeMax:
    """Записывает всё, что бот отправил в MAX."""

    def __init__(self) -> None:
        self.sent: list[tuple[int, dict[str, Any]]] = []
        self.answers: list[dict[str, Any]] = []

    async def send_message(self, user_id: int, message: dict[str, Any]) -> None:
        self.sent.append((user_id, message))

    async def answer_callback(self, callback_id: str, *, notification=None, message=None) -> None:
        self.answers.append({"id": callback_id, "notification": notification, "message": message})

    @property
    def last(self) -> dict[str, Any]:
        return self.sent[-1][1]


def buttons(message: dict[str, Any]) -> list[dict[str, Any]]:
    keyboard = message["attachments"][0]["payload"]["buttons"]
    return [button for row in keyboard for button in row]


def payloads(message: dict[str, Any]) -> list[str]:
    return [b["payload"] for b in buttons(message) if b["type"] == "callback"]


@pytest.fixture
def fake() -> FakeMax:
    return FakeMax()


@pytest.fixture
def bot(fake: FakeMax) -> BotDispatcher:
    return BotDispatcher(fake, SessionFactory, RuleBasedParser(), get_settings())  # type: ignore[arg-type]


def user(user_id: int = 100) -> dict[str, Any]:
    return {"user_id": user_id, "first_name": "Алина", "is_bot": False}


def message(text: str, user_id: int = 100) -> dict[str, Any]:
    return {
        "update_type": "message_created",
        "message": {"sender": user(user_id), "body": {"text": text}},
    }


def press(payload: str, user_id: int = 100, callback_id: str = "cb-1") -> dict[str, Any]:
    return {
        "update_type": "message_callback",
        "callback": {"callback_id": callback_id, "payload": payload, "user": user(user_id)},
    }


async def test_start_greets_and_asks_when(bot, fake):
    await bot.handle({"update_type": "bot_started", "user": user(), "payload": None})
    sent_to, out = fake.sent[0]
    assert sent_to == 100 and "Алина" in out["text"]
    assert "d:when:today" in payloads(out)


async def test_conversation_produces_cards_with_actions(bot, fake):
    await bot.handle(message("концерты на этой неделе"))
    out = fake.last
    assert "Источник:" in out["text"] and "Почему подходит" in out["text"]
    callbacks = payloads(out)
    assert any(p.startswith("fav:") for p in callbacks) and any(
        p.startswith("rem:") for p in callbacks
    )
    assert {"d:more", "d:cheaper", "poll:new"} <= set(callbacks)
    assert any(b["type"] == "link" and "startapp=catalog" in b["url"] for b in buttons(out))
    assert all(len(b["text"]) <= 40 for b in buttons(out))


async def test_quick_reply_press_continues_the_dialog(bot, fake):
    await bot.handle(message("привет"))
    await bot.handle(press("d:when:week"))
    assert fake.answers[-1]["id"] == "cb-1"
    assert "d:topic:concert" in payloads(fake.last)
    await bot.handle(press("d:topic:concert"))
    assert "Вот что нашлось" in fake.last["text"]


async def test_favorite_and_reminder_buttons(bot, fake):
    await bot.handle(message("концерты на этой неделе"))
    fav = next(p for p in payloads(fake.last) if p.startswith("fav:"))
    rem = next(p for p in payloads(fake.last) if p.startswith("rem:"))

    await bot.handle(press(fav))
    assert "избранное" in fake.answers[-1]["notification"]
    await bot.handle(press(rem))
    assert "Напомню" in fake.answers[-1]["notification"]

    await bot.handle(message("/favorites"))
    assert "Избранное" in fake.last["text"] and "1." in fake.last["text"]


async def test_reminder_too_close_reports_a_reason(bot, fake):
    async with SessionFactory() as session:
        soon = datetime.now(UTC) + timedelta(minutes=30)
        event = await session.scalar(select(Event).where(Event.external_id == "c01"))
        original = event.starts_at
        event.starts_at = soon
        await session.commit()
    try:
        await bot.handle(press(f"rem:{event.id}"))
        assert "мало времени" in fake.answers[-1]["notification"]
    finally:
        async with SessionFactory() as session:
            (await session.get(Event, event.id)).starts_at = original
            await session.commit()


async def test_group_poll_flow_between_two_users(bot, fake):
    await bot.handle(message("удиви меня на этой неделе", user_id=100))
    await bot.handle(press("poll:new", user_id=100))
    poll_message = fake.last
    assert poll_message["text"].startswith("👥") and "start=poll_" in poll_message["text"]
    votes = [p for p in payloads(poll_message) if p.startswith("vote:")]
    assert len(votes) == 3

    await bot.handle(press(votes[0], user_id=100, callback_id="v1"))
    await bot.handle(press(votes[0], user_id=200, callback_id="v2"))
    await bot.handle(press(votes[1], user_id=300, callback_id="v3"))
    updated = fake.answers[-1]["message"]
    assert "Всего голосов: 3" in updated["text"] and "2 голоса" in updated["text"]

    # друг открывает бота по ссылке из приглашения
    poll_id = votes[0].split(":")[1]
    await bot.handle(
        {"update_type": "bot_started", "user": user(400), "payload": f"poll_{poll_id}"}
    )
    assert fake.sent[-1][0] == 400 and "Всего голосов: 3" in fake.last["text"]


async def test_poll_requires_previous_results(bot, fake):
    await bot.handle(press("poll:new"))
    assert "хотя бы два" in fake.answers[-1]["notification"]


async def test_bot_ignores_other_bots_and_empty_messages(bot, fake):
    await bot.handle(
        {
            "update_type": "message_created",
            "message": {"sender": {"user_id": 1, "is_bot": True}, "body": {"text": "hi"}},
        }
    )
    await bot.handle({"update_type": "message_created", "message": {"sender": user(), "body": {}}})
    await bot.handle({"update_type": "something_new"})
    assert fake.sent == []


async def test_handler_failure_is_reported_to_user_and_does_not_raise(bot, fake):
    await bot.handle(message("hello"))  # создаём пользователя
    original = bot._parser.parse

    async def boom(*_):
        raise RuntimeError("сбой парсера")

    bot._parser.parse = boom
    try:
        await bot.handle(message("концерты"))
    finally:
        bot._parser.parse = original
    assert "Что-то пошло не так" in fake.last["text"]


async def test_due_reminders_are_delivered_once(bot, fake):
    await bot.handle(message("концерты на этой неделе"))
    async with SessionFactory() as session:
        event = await session.scalar(
            select(Event).where(Event.starts_at > datetime.now(UTC) + timedelta(hours=6))
        )
        event_id = event.id
    await bot.handle(press(f"rem:{event_id}"))

    settings = get_settings()
    later = datetime.now(UTC) + timedelta(days=30)
    assert await send_due_reminders(fake, SessionFactory, settings) == 0
    assert await send_due_reminders(fake, SessionFactory, settings, clock=lambda: later) == 1
    assert await send_due_reminders(fake, SessionFactory, settings, clock=lambda: later) == 0
    assert "Скоро начнётся" in fake.last["text"]
    async with SessionFactory() as session:
        assert (await session.scalar(select(Reminder))).sent_at is not None
        assert await session.scalar(select(User.id)) is not None


async def test_max_client_sends_documented_requests():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/updates":
            return httpx.Response(
                200, json={"updates": [{"update_type": "bot_started"}], "marker": 7}
            )
        if request.url.path == "/answers" and request.url.params["callback_id"] == "bad":
            return httpx.Response(400, text="nope")
        return httpx.Response(200, json={"success": True})

    http = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://platform-api2.max.ru",
        headers={"Authorization": "TOKEN"},
    )
    client = MaxClient("TOKEN", "https://platform-api2.max.ru", http=http)

    updates, marker = await client.get_updates(marker=5)
    assert marker == 7 and updates[0]["update_type"] == "bot_started"
    params = seen[0].url.params
    assert params["marker"] == "5" and "message_callback" in params["types"]
    assert seen[0].headers["Authorization"] == "TOKEN"

    await client.send_message(42, {"text": "привет"})
    assert seen[1].url.params["user_id"] == "42" and json.loads(seen[1].content) == {
        "text": "привет"
    }

    await client.answer_callback("cb", notification="ok")
    assert json.loads(seen[2].content) == {"notification": "ok"}

    with pytest.raises(MaxApiError):
        await client.answer_callback("bad", notification="x")
