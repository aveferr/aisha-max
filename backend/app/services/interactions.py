from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Interaction, InteractionKind


class InteractionService:
    """Журнал действий пользователя — основа для метрик пилота."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def log(
        self,
        user_id: int,
        kind: InteractionKind,
        *,
        event_ids: Iterable[int | None] = (None,),
        session_id: int | None = None,
    ) -> None:
        self._session.add_all(
            Interaction(user_id=user_id, kind=kind, event_id=event_id, session_id=session_id)
            for event_id in event_ids
        )
