from fastapi import APIRouter, status

from app.api.deps import CurrentUserDep, OptionalUserDep, SessionDep
from app.api.mappers import poll_out
from app.schemas.polls import PollCreate, PollOut, PollSummaryOut, VoteIn
from app.services.favorites import FavoriteService
from app.services.polls import PollService, PollView

router = APIRouter(prefix="/polls", tags=["polls"])


async def _render(view: PollView, user, session: SessionDep) -> PollOut:
    favorites = await FavoriteService(session).favorite_ids(
        user, [result.option.event_id for result in view.options]
    )
    return poll_out(view, favorites)


@router.post("", response_model=PollOut, status_code=status.HTTP_201_CREATED)
async def create_poll(body: PollCreate, user: CurrentUserDep, session: SessionDep) -> PollOut:
    """Голосование «куда пойдём?»: ссылку на него можно отправить друзьям."""
    service = PollService(session)
    poll = await service.create(user, body.event_ids, body.title)
    await session.commit()
    return await _render(await service.get_view(poll.id, user), user, session)


@router.get("", response_model=list[PollSummaryOut])
async def my_polls(user: CurrentUserDep, session: SessionDep) -> list[PollSummaryOut]:
    """Голосования пользователя (созданные им и те, где он голосовал), новые сверху."""
    return [
        PollSummaryOut(
            id=item.poll.id,
            title=item.poll.title,
            created_at=item.poll.created_at,
            total_votes=item.total_votes,
            options_count=item.options_count,
            is_mine=item.is_mine,
            voted=item.voted,
            events_preview=item.preview,
        )
        for item in await PollService(session).list_mine(user)
    ]


@router.get("/{poll_id}", response_model=PollOut)
async def get_poll(poll_id: int, user: OptionalUserDep, session: SessionDep) -> PollOut:
    return await _render(await PollService(session).get_view(poll_id, user), user, session)


@router.post("/{poll_id}/votes", response_model=PollOut)
async def vote(poll_id: int, body: VoteIn, user: CurrentUserDep, session: SessionDep) -> PollOut:
    view = await PollService(session).vote(user, poll_id, body.option_id)
    await session.commit()
    return await _render(view, user, session)
