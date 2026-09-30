from collections.abc import Collection

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import Event, Favorite, InteractionKind, User
from app.services.interactions import InteractionService


class FavoriteService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._interactions = InteractionService(session)

    async def add(self, user: User, event_id: int) -> None:
        if await self._session.get(Event, event_id) is None:
            raise NotFoundError("Событие не найдено")
        result = await self._session.execute(
            pg_insert(Favorite).values(user_id=user.id, event_id=event_id).on_conflict_do_nothing()
        )
        if result.rowcount:  # событие добавлено впервые
            self._interactions.log(user.id, InteractionKind.FAVORITED, event_ids=[event_id])

    async def remove(self, user: User, event_id: int) -> None:
        await self._session.execute(
            delete(Favorite).where(Favorite.user_id == user.id, Favorite.event_id == event_id)
        )

    async def list_events(self, user: User) -> list[Event]:
        favorites = await self._session.scalars(
            select(Favorite)
            .join(Favorite.event)
            .where(Favorite.user_id == user.id)
            .order_by(Event.starts_at, Event.id)
        )
        return [favorite.event for favorite in favorites]

    async def favorite_ids(self, user: User | None, event_ids: Collection[int]) -> set[int]:
        """Какие из переданных событий пользователь добавил в избранное."""
        if user is None or not event_ids:
            return set()
        rows = await self._session.scalars(
            select(Favorite.event_id).where(
                Favorite.user_id == user.id, Favorite.event_id.in_(event_ids)
            )
        )
        return set(rows)
