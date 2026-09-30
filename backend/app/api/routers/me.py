from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUserDep, SessionDep
from app.api.mappers import event_out
from app.schemas.catalog import EventOut
from app.schemas.users import ReminderCreate, ReminderOut, UserOut, UserUpdate
from app.services.favorites import FavoriteService
from app.services.reminders import ReminderService
from app.services.users import UserService

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=UserOut)
async def get_me(user: CurrentUserDep) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("", response_model=UserOut)
async def update_me(body: UserUpdate, user: CurrentUserDep, session: SessionDep) -> UserOut:
    updated = await UserService(session).update_profile(
        user, city_id=body.city_id, interest_slugs=body.interests
    )
    await session.commit()
    return UserOut.model_validate(updated)


@router.get("/favorites", response_model=list[EventOut])
async def list_favorites(user: CurrentUserDep, session: SessionDep) -> list[EventOut]:
    events = await FavoriteService(session).list_events(user)
    return [event_out(event, {event.id}) for event in events]


@router.put("/favorites/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_favorite(event_id: int, user: CurrentUserDep, session: SessionDep) -> Response:
    await FavoriteService(session).add(user, event_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/favorites/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(event_id: int, user: CurrentUserDep, session: SessionDep) -> Response:
    await FavoriteService(session).remove(user, event_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/reminders", response_model=list[ReminderOut])
async def list_reminders(user: CurrentUserDep, session: SessionDep) -> list[ReminderOut]:
    reminders = await ReminderService(session).list_active(user)
    return [ReminderOut(event=event_out(r.event), remind_at=r.remind_at) for r in reminders]


@router.post("/reminders", response_model=ReminderOut, status_code=status.HTTP_201_CREATED)
async def create_reminder(
    body: ReminderCreate, user: CurrentUserDep, session: SessionDep
) -> ReminderOut:
    reminder = await ReminderService(session).set(user, body.event_id, body.minutes_before)
    await session.commit()
    return ReminderOut(event=event_out(reminder.event), remind_at=reminder.remind_at)


@router.delete("/reminders/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_reminder(event_id: int, user: CurrentUserDep, session: SessionDep) -> Response:
    await ReminderService(session).remove(user, event_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
