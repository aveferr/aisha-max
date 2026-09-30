from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock, utcnow
from app.core.config import get_settings
from app.core.errors import DomainError
from app.models import Category, City, User


@dataclass(frozen=True)
class MaxProfile:
    """Профиль пользователя, как его присылает MAX (бот или initData мини-приложения)."""

    max_user_id: int
    first_name: str = ""
    last_name: str | None = None
    username: str | None = None


class UserService:
    def __init__(self, session: AsyncSession, clock: Clock = utcnow) -> None:
        self._session = session
        self._clock = clock

    async def get_or_create(self, profile: MaxProfile) -> User:
        """Находит пользователя по id в MAX или создаёт; обновляет имя и время активности."""
        default_city = (
            select(City.id).where(City.name == get_settings().default_city).scalar_subquery()
        )
        await self._session.execute(
            pg_insert(User)
            .values(
                max_user_id=profile.max_user_id,
                first_name=profile.first_name,
                last_name=profile.last_name,
                username=profile.username,
                city_id=default_city,
            )
            .on_conflict_do_nothing(index_elements=[User.max_user_id])
        )
        user = (
            await self._session.execute(select(User).where(User.max_user_id == profile.max_user_id))
        ).scalar_one()
        user.first_name = profile.first_name or user.first_name
        user.last_name = profile.last_name
        user.username = profile.username
        user.last_seen_at = self._clock()
        return user

    async def update_profile(
        self, user: User, *, city_id: int | None = None, interest_slugs: list[str] | None = None
    ) -> User:
        if city_id is not None:
            if await self._session.get(City, city_id) is None:
                raise DomainError("Такого города нет в каталоге")
            user.city_id = city_id
        if interest_slugs is not None:
            categories = (
                await self._session.scalars(
                    select(Category).where(Category.slug.in_(interest_slugs))
                )
            ).all()
            if len(categories) != len(set(interest_slugs)):
                raise DomainError("Неизвестная категория интересов")
            user.interests = list(categories)
        await self._session.flush()
        return user
