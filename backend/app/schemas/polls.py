from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.catalog import EventOut


class PollCreate(BaseModel):
    event_ids: list[int] = Field(min_length=2, max_length=5)
    title: str | None = Field(default=None, max_length=200)


class VoteIn(BaseModel):
    option_id: int


class PollOptionOut(BaseModel):
    id: int
    event: EventOut
    votes: int


class PollOut(BaseModel):
    id: int
    title: str
    options: list[PollOptionOut]
    total_votes: int
    my_option_id: int | None


class PollSummaryOut(BaseModel):
    """Голосование в списке: без вариантов, только то, что нужно, чтобы найти нужное."""

    id: int
    title: str
    created_at: datetime
    total_votes: int
    options_count: int
    is_mine: bool = Field(description="Пользователь — автор голосования")
    voted: bool = Field(description="Пользователь уже проголосовал")
    events_preview: list[str]
