from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import exists, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import lazyload

from app.core.errors import DomainError, NotFoundError
from app.models import Event, InteractionKind, Poll, PollOption, PollVote, User
from app.services.interactions import InteractionService

MIN_OPTIONS, MAX_OPTIONS = 2, 5
DEFAULT_TITLE = "Куда пойдём?"
LIST_LIMIT = 50
PREVIEW_EVENTS = 3


@dataclass
class OptionResult:
    option: PollOption
    votes: int


@dataclass
class PollView:
    poll: Poll
    options: list[OptionResult]
    my_option_id: int | None

    @property
    def total_votes(self) -> int:
        return sum(result.votes for result in self.options)


@dataclass
class PollSummary:
    """Строка списка «Мои голосования»."""

    poll: Poll
    total_votes: int
    options_count: int
    voted: bool
    is_mine: bool
    preview: list[str]  # названия первых событий, чтобы различать одинаково названные голосования


class PollService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._interactions = InteractionService(session)

    async def create(self, user: User, event_ids: list[int], title: str | None = None) -> Poll:
        unique_ids = list(dict.fromkeys(event_ids))
        if not MIN_OPTIONS <= len(unique_ids) <= MAX_OPTIONS:
            raise DomainError(
                f"В голосовании должно быть от {MIN_OPTIONS} до {MAX_OPTIONS} событий"
            )
        found = set(await self._session.scalars(select(Event.id).where(Event.id.in_(unique_ids))))
        if missing := set(unique_ids) - found:
            raise NotFoundError(f"События не найдены: {sorted(missing)}")

        poll = Poll(
            creator_id=user.id,
            title=(title or DEFAULT_TITLE).strip()[:200],
            options=[PollOption(event_id=event_id) for event_id in unique_ids],
        )
        self._session.add(poll)
        await self._session.flush()
        self._interactions.log(user.id, InteractionKind.POLL_CREATED)
        return poll

    async def get_view(self, poll_id: int, viewer: User | None) -> PollView:
        # populate_existing: только что созданные варианты не имеют загруженных событий
        poll = await self._session.get(Poll, poll_id, populate_existing=True)
        if poll is None:
            raise NotFoundError("Голосование не найдено")
        counts = dict(
            (
                await self._session.execute(
                    select(PollVote.option_id, func.count())
                    .where(PollVote.poll_id == poll_id)
                    .group_by(PollVote.option_id)
                )
            ).all()
        )
        my_option_id = None
        if viewer is not None:
            my_option_id = await self._session.scalar(
                select(PollVote.option_id).where(
                    PollVote.poll_id == poll_id, PollVote.user_id == viewer.id
                )
            )
        return PollView(
            poll=poll,
            options=[OptionResult(option, counts.get(option.id, 0)) for option in poll.options],
            my_option_id=my_option_id,
        )

    async def vote(self, user: User, poll_id: int, option_id: int) -> PollView:
        poll = await self._session.get(Poll, poll_id)
        if poll is None:
            raise NotFoundError("Голосование не найдено")
        if option_id not in {option.id for option in poll.options}:
            raise DomainError("Такого варианта нет в этом голосовании")
        await self._session.execute(
            pg_insert(PollVote)
            .values(poll_id=poll_id, user_id=user.id, option_id=option_id)
            .on_conflict_do_update(
                index_elements=[PollVote.poll_id, PollVote.user_id],
                set_={"option_id": option_id},
            )
        )
        self._interactions.log(user.id, InteractionKind.POLL_VOTED)
        await self._session.flush()
        return await self.get_view(poll_id, user)

    async def list_mine(self, user: User) -> list[PollSummary]:
        """Голосования, которые пользователь создал или в которых проголосовал, новые сверху."""
        total_votes = (
            select(func.count())
            .where(PollVote.poll_id == Poll.id)
            .correlate(Poll)
            .scalar_subquery()
        )
        voted = exists().where(PollVote.poll_id == Poll.id, PollVote.user_id == user.id)
        rows = (
            await self._session.execute(
                select(Poll, total_votes, voted)
                .options(lazyload(Poll.options))  # варианты здесь не читаем
                .where(or_(Poll.creator_id == user.id, voted))
                .order_by(Poll.created_at.desc(), Poll.id.desc())
                .limit(LIST_LIMIT)
            )
        ).all()

        titles: dict[int, list[str]] = defaultdict(list)
        if rows:
            option_rows = await self._session.execute(
                select(PollOption.poll_id, Event.title)
                .join(Event, Event.id == PollOption.event_id)
                .where(PollOption.poll_id.in_([poll.id for poll, *_ in rows]))
                .order_by(PollOption.poll_id, PollOption.id)
            )
            for poll_id, title in option_rows:
                titles[poll_id].append(title)

        return [
            PollSummary(
                poll=poll,
                total_votes=votes,
                options_count=len(titles[poll.id]),
                voted=bool(has_voted),
                is_mine=poll.creator_id == user.id,
                preview=titles[poll.id][:PREVIEW_EVENTS],
            )
            for poll, votes, has_voted in rows
        ]
