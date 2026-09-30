from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.security import validate_init_data
from app.assistant.factory import get_parser
from app.assistant.parser import Parser
from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import AuthError
from app.models import User
from app.services.dialog import DialogService
from app.services.events import EventService
from app.services.recommendations import RecommendationService
from app.services.users import MaxProfile, UserService

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail)


async def get_optional_user(
    session: SessionDep,
    x_max_init_data: Annotated[str | None, Header(description="window.WebApp.initData")] = None,
    x_dev_user_id: Annotated[str | None, Header(description="Только при DEV_AUTH_ENABLED")] = None,
) -> User | None:
    """Пользователь по initData мини-приложения MAX (или dev-заголовку); без заголовков — None."""
    settings = get_settings()
    if x_max_init_data:
        try:
            profile = validate_init_data(
                x_max_init_data,
                settings.max_bot_token,
                max_age_seconds=settings.init_data_ttl_seconds,
            ).profile
        except AuthError as error:
            raise _unauthorized(str(error)) from error
    elif settings.dev_auth_enabled and x_dev_user_id:
        if not x_dev_user_id.isdigit():
            raise _unauthorized("X-Dev-User-Id должен быть числом")
        profile = MaxProfile(max_user_id=int(x_dev_user_id), first_name="Dev")
    else:
        return None

    user = await UserService(session).get_or_create(profile)
    await session.commit()
    return user


async def get_current_user(user: Annotated[User | None, Depends(get_optional_user)]) -> User:
    if user is None:
        raise _unauthorized("Требуется заголовок X-Max-Init-Data")
    return user


def get_event_service(session: SessionDep) -> EventService:
    return EventService(session, get_settings().tz)


EventServiceDep = Annotated[EventService, Depends(get_event_service)]
OptionalUserDep = Annotated[User | None, Depends(get_optional_user)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


def get_dialog_service(
    session: SessionDep,
    events: EventServiceDep,
    parser: Annotated[Parser, Depends(get_parser)],
) -> DialogService:
    return DialogService(session, parser, RecommendationService(session, events))


DialogServiceDep = Annotated[DialogService, Depends(get_dialog_service)]
