"""Представление ответов ассистента, голосований и напоминаний в формате сообщений MAX."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.assistant.formatting import format_card, format_price, format_when, plural
from app.models import Event, EventStatus, Reminder
from app.services.dialog import BotReply
from app.services.polls import PollView

Button = dict[str, Any]
Keyboard = list[list[Button]]

QUICK_REPLIES_PER_ROW = 2
MAX_BUTTON_TEXT = 40
VOTE_FORMS = ("голос", "голоса", "голосов")

MENU_TEXT = (
    "Я подбираю события в диалоге: напишите, что хочется, — например, "
    "«что-нибудь спокойное недорого сегодня вечером».\n\n"
    "Команды:\n/start — начать заново\n/favorites — избранное\n/reminders — мои напоминания"
)


def callback_button(text: str, payload: str) -> Button:
    return {"type": "callback", "text": text[:MAX_BUTTON_TEXT], "payload": payload}


def link_button(text: str, url: str) -> Button:
    return {"type": "link", "text": text[:MAX_BUTTON_TEXT], "url": url}


def build_message(text: str, keyboard: Keyboard | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {"text": text}
    if keyboard:
        message["attachments"] = [{"type": "inline_keyboard", "payload": {"buttons": keyboard}}]
    return message


def deep_link(bot_username: str, kind: str, value: str) -> str | None:
    """Ссылка на бота: kind=start открывает чат, kind=startapp — мини-приложение."""
    return f"https://max.ru/{bot_username}?{kind}={value}" if bot_username else None


def render_reply(reply: BotReply, tz: ZoneInfo, now: datetime, bot_username: str) -> dict[str, Any]:
    text = reply.text
    keyboard: Keyboard = []

    if reply.cards:
        blocks = [
            format_card(number, card.event, card.reasons, tz, now)
            for number, card in enumerate(reply.cards, start=1)
        ]
        text += "\n\n" + "\n\n".join(blocks)
        for number, card in enumerate(reply.cards, start=1):
            row = [
                callback_button(f"⭐ {number}", f"fav:{card.event.id}"),
                callback_button(f"🔔 {number}", f"rem:{card.event.id}"),
            ]
            if card.event.ticket_url:
                row.append(link_button(f"🎟 {number}", card.event.ticket_url))
            keyboard.append(row)

    quick = [callback_button(q.label, q.payload) for q in reply.quick_replies]
    keyboard += [
        quick[i : i + QUICK_REPLIES_PER_ROW] for i in range(0, len(quick), QUICK_REPLIES_PER_ROW)
    ]

    if reply.cards:
        keyboard.append([callback_button("👥 Выбрать вместе с друзьями", "poll:new")])
        if catalog := deep_link(bot_username, "startapp", "catalog"):
            keyboard.append([link_button("🧭 Открыть каталог", catalog)])
    return build_message(text, keyboard)


def render_poll(view: PollView, tz: ZoneInfo, now: datetime, bot_username: str) -> dict[str, Any]:
    lines = [f"👥 {view.poll.title}", "Проголосуйте за вариант — результаты обновляются сразу.", ""]
    keyboard: Keyboard = []
    for number, result in enumerate(view.options, start=1):
        event = result.option.event
        mark = "✅ " if result.option.id == view.my_option_id else ""
        lines.append(
            f"{number}. {mark}{event.title} — {format_when(event.starts_at, tz, now)}, "
            f"{event.venue.name} · {format_price(event)} · "
            f"{result.votes} {plural(result.votes, VOTE_FORMS)}"
        )
        keyboard.append(
            [callback_button(f"{number}. {event.title}", f"vote:{view.poll.id}:{result.option.id}")]
        )
    lines += ["", f"Всего голосов: {view.total_votes}"]
    if link := deep_link(bot_username, "start", f"poll_{view.poll.id}"):
        lines.append(f"Ссылка для друзей: {link}")
    return build_message("\n".join(lines), keyboard)


def render_event_list(
    title: str, events: list[Event], tz: ZoneInfo, now: datetime
) -> dict[str, Any]:
    if not events:
        return build_message(f"{title}\n\nПока пусто. Подберём что-нибудь? Напишите, что хочется.")
    lines = [title, ""]
    for number, event in enumerate(events, start=1):
        lines.append(
            f"{number}. {event.title} — {format_when(event.starts_at, tz, now)}, {event.venue.name}"
        )
    return build_message("\n".join(lines))


def render_reminder(reminder: Reminder, tz: ZoneInfo, now: datetime) -> dict[str, Any]:
    event = reminder.event
    if event.status == EventStatus.CANCELLED:
        return build_message(
            f"⚠ Событие отменено: {event.title}. Подберём другое — просто напишите."
        )
    text = (
        f"🔔 Скоро начнётся: {event.title}\n"
        f"{format_when(event.starts_at, tz, now)} · {event.venue.name} · {format_price(event)}"
    )
    keyboard = [[link_button("🎟 Билеты", event.ticket_url)]] if event.ticket_url else None
    return build_message(text, keyboard)
