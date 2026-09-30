"""Диалоговый ассистент: слот-филлинг «когда» и «что хочется», затем подбор и уточнения.

Сервис не знает про канал (бот MAX или мини-приложение): возвращает BotReply, а канал
сам решает, как его нарисовать.
"""

from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.criteria import Criteria, Patch, apply_patch
from app.assistant.formatting import describe_criteria
from app.assistant.parser import Parser
from app.assistant.vocabulary import CATEGORIES, CATEGORY_SLUGS
from app.core.clock import Clock, utcnow
from app.core.config import get_settings
from app.models import (
    Category,
    DialogMessage,
    DialogSession,
    InteractionKind,
    MessageRole,
    User,
)
from app.services.interactions import InteractionService
from app.services.recommendations import Card, RecommendationService

SESSION_TTL = timedelta(hours=6)
CARDS_PER_REPLY = 3
DIALOG_PREFIX = "d:"
CHEAPER_FACTOR = 0.6
CHEAPER_STEP = 50
DEFAULT_BASE_PRICE = 1000

ASKED_WHEN, ASKED_TOPIC = "when", "topic"


@dataclass(frozen=True)
class QuickReply:
    label: str
    payload: str


@dataclass
class BotReply:
    text: str
    quick_replies: list[QuickReply] = field(default_factory=list)
    cards: list[Card] = field(default_factory=list)


WHEN_REPLIES = [
    QuickReply("Сегодня", "d:when:today"),
    QuickReply("Завтра", "d:when:tomorrow"),
    QuickReply("На выходных", "d:when:weekend"),
    QuickReply("На неделе", "d:when:week"),
]
TOPIC_REPLIES = [
    *(QuickReply(f"{c.emoji} {c.title}", f"d:topic:{c.slug}") for c in CATEGORIES),
    QuickReply("🎲 Удиви меня", "d:topic:surprise"),
]
AFTER_RESULTS_REPLIES = [
    QuickReply("🔄 Другие варианты", "d:more"),
    QuickReply("💸 Дешевле", "d:cheaper"),
    QuickReply("🆓 Бесплатно", "d:free"),
    QuickReply("🔁 Начать заново", "d:reset"),
]
NOTHING_FOUND_REPLIES = [
    QuickReply("📅 На неделе", "d:when:week"),
    QuickReply("🆓 Бесплатно", "d:free"),
    QuickReply("🔁 Начать заново", "d:reset"),
]


def payload_to_patch(payload: str) -> Patch | None:
    """Нажатие кнопки → Patch. Неизвестный или чужой payload → None."""
    if not payload.startswith(DIALOG_PREFIX):
        return None
    kind, _, value = payload[len(DIALOG_PREFIX) :].partition(":")
    match kind:
        case "when" if value:
            return Patch(when=value)
        case "topic" if value == "surprise":
            return Patch(surprise=True)
        case "topic" if value in CATEGORY_SLUGS:
            return Patch(categories=[value])
        case "more":
            return Patch(more=True)
        case "cheaper":
            return Patch(cheaper=True)
        case "free":
            return Patch(free_only=True)
        case "reset":
            return Patch(reset=True)
    return None


class DialogService:
    def __init__(
        self,
        session: AsyncSession,
        parser: Parser,
        recommender: RecommendationService,
        clock: Clock = utcnow,
    ) -> None:
        self._session = session
        self._parser = parser
        self._recommender = recommender
        self._clock = clock
        self._tz = get_settings().tz
        self._interactions = InteractionService(session)
        self._category_titles: dict[str, str] | None = None

    async def handle_text(self, user: User, text: str) -> BotReply:
        dialog = await self._active_dialog(user)
        self._remember(dialog, MessageRole.USER, text)
        patch = await self._parser.parse(text, self._clock())
        return await self._advance(user, dialog, patch)

    async def handle_payload(self, user: User, payload: str) -> BotReply:
        dialog = await self._active_dialog(user)
        self._remember(dialog, MessageRole.USER, f"[кнопка] {payload}")
        patch = payload_to_patch(payload) or Patch()
        return await self._advance(user, dialog, patch)

    async def start(self, user: User) -> BotReply:
        """Приветствие по /start: диалог начинается с чистого листа."""
        dialog = await self._active_dialog(user)
        return await self._advance(user, dialog, Patch(reset=True))

    async def last_shown_ids(self, user: User) -> list[int]:
        """События из последней выдачи — для «обсудить с друзьями»."""
        dialog = await self._find_active(user)
        return list(dialog.state.get("last_shown", [])) if dialog else []

    # --- ход диалога -------------------------------------------------------------------------

    async def _advance(self, user: User, dialog: DialogSession, patch: Patch) -> BotReply:
        now = self._clock()
        criteria = Criteria.model_validate(dialog.criteria)
        state = dict(dialog.state)  # JSONB не отслеживает мутации: сохраняем новым объектом

        if patch.reset:
            criteria, state = Criteria(), {}
            dialog.shown_event_ids = []
            patch = patch.model_copy(update={"reset": False})
        if patch.cheaper:
            if criteria.free_only:
                return await self._reply(
                    dialog,
                    BotReply(
                        "Уже ищу только бесплатные события. Можно попросить другие варианты.",
                        AFTER_RESULTS_REPLIES,
                    ),
                )
            patch = self._with_cheaper_budget(patch, criteria, state)

        without_more = patch.model_copy(update={"more": False})
        if without_more.is_empty() and (criteria.is_blank or not patch.more):
            reply = (
                self._welcome(user, state)
                if criteria.is_blank
                else BotReply(
                    "Не совсем понял. Уточните, пожалуйста, дату, тему или бюджет — "
                    "или выберите вариант ниже.",
                    TOPIC_REPLIES if criteria.has_when else WHEN_REPLIES,
                )
            )
            return await self._finish(dialog, criteria, state, reply)

        criteria = apply_patch(criteria, patch, now, self._tz)
        reply = await self._next_reply(user, dialog, criteria, state, patch)
        return await self._finish(dialog, criteria, state, reply)

    async def _next_reply(
        self, user: User, dialog: DialogSession, criteria: Criteria, state: dict, patch: Patch
    ) -> BotReply:
        asked = set(state.get("asked", []))
        if not patch.more:
            if not criteria.has_when and ASKED_WHEN not in asked:
                state["asked"] = [*asked, ASKED_WHEN]
                return BotReply("Когда планируете пойти?", WHEN_REPLIES)
            if not criteria.has_focus and ASKED_TOPIC not in asked:
                state["asked"] = [*asked, ASKED_TOPIC]
                return BotReply(
                    "Что хочется: выберите тему или опишите настроение своими словами.",
                    TOPIC_REPLIES,
                )
        return await self._recommend(user, dialog, criteria, state)

    async def _recommend(
        self, user: User, dialog: DialogSession, criteria: Criteria, state: dict
    ) -> BotReply:
        result = await self._recommender.recommend(
            user, criteria, exclude_ids=dialog.shown_event_ids, limit=CARDS_PER_REPLY
        )
        if not result.cards:
            text = (
                "Новых вариантов по этим условиям больше нет. Можно расширить поиск."
                if dialog.shown_event_ids
                else "К сожалению, подходящих событий не нашлось. "
                "Попробуйте другой день или снимите ограничения."
            )
            return BotReply(text, NOTHING_FOUND_REPLIES)

        event_ids = [card.event.id for card in result.cards]
        dialog.shown_event_ids = [*dialog.shown_event_ids, *event_ids]
        dialog.first_recommended_at = dialog.first_recommended_at or self._clock()
        state["last_shown"] = event_ids
        state["last_max_price"] = max(card.event.price_min for card in result.cards)
        self._interactions.log(
            user.id, InteractionKind.SHOWN, event_ids=event_ids, session_id=dialog.id
        )

        summary = describe_criteria(criteria, self._tz, self._clock(), await self._titles())
        lines = [f"Вот что нашлось: {summary}."]
        if result.relaxed:
            lines.append(
                "Точных совпадений нет, поэтому поиск расширен: " + ", ".join(result.relaxed) + "."
            )
        return BotReply("\n".join(lines), AFTER_RESULTS_REPLIES, result.cards)

    # --- вспомогательное ---------------------------------------------------------------------

    @staticmethod
    def _welcome(user: User, state: dict) -> BotReply:
        state["asked"] = [ASKED_WHEN]
        name = f", {user.first_name}" if user.first_name else ""
        return BotReply(
            f"Привет{name}! Я помогу подобрать событие. Напишите своими словами, что хочется, "
            "например: «что-нибудь спокойное недорого сегодня вечером».\n\n"
            "Или начнём с даты: когда планируете пойти?",
            WHEN_REPLIES,
        )

    @staticmethod
    def _with_cheaper_budget(patch: Patch, criteria: Criteria, state: dict) -> Patch:
        base = criteria.budget_max or state.get("last_max_price") or DEFAULT_BASE_PRICE
        lowered = int(base * CHEAPER_FACTOR) // CHEAPER_STEP * CHEAPER_STEP
        if lowered < CHEAPER_STEP:
            return patch.model_copy(update={"free_only": True})
        return patch.model_copy(update={"budget_max": lowered})

    async def _reply(self, dialog: DialogSession, reply: BotReply) -> BotReply:
        self._remember(dialog, MessageRole.ASSISTANT, reply.text)
        return reply

    async def _finish(
        self, dialog: DialogSession, criteria: Criteria, state: dict, reply: BotReply
    ) -> BotReply:
        dialog.criteria = criteria.model_dump(mode="json")
        dialog.state = state
        dialog.updated_at = self._clock()
        return await self._reply(dialog, reply)

    def _remember(self, dialog: DialogSession, role: MessageRole, text: str) -> None:
        self._session.add(DialogMessage(session_id=dialog.id, role=role, text=text))

    async def _titles(self) -> dict[str, str]:
        if self._category_titles is None:
            rows = await self._session.scalars(select(Category))
            self._category_titles = {category.slug: category.title for category in rows}
        return self._category_titles

    async def _find_active(self, user: User) -> DialogSession | None:
        return await self._session.scalar(
            select(DialogSession).where(
                DialogSession.user_id == user.id, DialogSession.is_active.is_(True)
            )
        )

    async def _active_dialog(self, user: User) -> DialogSession:
        """Активный диалог пользователя; устаревший (не обновлялся SESSION_TTL) закрывается."""
        dialog = await self._find_active(user)
        if dialog and self._clock() - dialog.updated_at > SESSION_TTL:
            dialog.is_active = False
            await self._session.flush()
            dialog = None
        if dialog is None:
            dialog = DialogSession(user_id=user.id, criteria={}, state={}, shown_event_ids=[])
            self._session.add(dialog)
            await self._session.flush()
        return dialog
