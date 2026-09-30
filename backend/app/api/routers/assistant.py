from fastapi import APIRouter

from app.api.deps import CurrentUserDep, DialogServiceDep, SessionDep
from app.api.mappers import reply_out
from app.schemas.assistant import AssistantReplyOut, AssistantRequest
from app.services.dialog import BotReply
from app.services.favorites import FavoriteService

router = APIRouter(prefix="/assistant", tags=["assistant"])


async def _respond(reply: BotReply, user: CurrentUserDep, session: SessionDep) -> AssistantReplyOut:
    favorites = await FavoriteService(session).favorite_ids(user, [c.event.id for c in reply.cards])
    await session.commit()
    return reply_out(reply, favorites)


@router.post("/messages", response_model=AssistantReplyOut)
async def send_message(
    body: AssistantRequest, user: CurrentUserDep, dialog: DialogServiceDep, session: SessionDep
) -> AssistantReplyOut:
    """Один ход диалога: свободный текст или payload быстрой кнопки из предыдущего ответа."""
    if body.text is not None:
        reply = await dialog.handle_text(user, body.text)
    else:
        reply = await dialog.handle_payload(user, body.payload)
    return await _respond(reply, user, session)


@router.post("/reset", response_model=AssistantReplyOut)
async def reset_dialog(
    user: CurrentUserDep, dialog: DialogServiceDep, session: SessionDep
) -> AssistantReplyOut:
    """Начать диалог заново (приветствие и первый вопрос)."""
    return await _respond(await dialog.start(user), user, session)
