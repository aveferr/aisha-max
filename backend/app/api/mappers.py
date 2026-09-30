"""ORM-объекты → схемы ответов."""

from collections.abc import Collection

from app.assistant.formatting import format_source
from app.core.config import get_settings
from app.models import Event
from app.schemas.assistant import AssistantReplyOut, CardOut, QuickReplyOut
from app.schemas.catalog import EventOut
from app.schemas.polls import PollOptionOut, PollOut
from app.services.dialog import BotReply
from app.services.polls import PollView


def event_out(event: Event, favorite_ids: Collection[int] = ()) -> EventOut:
    out = EventOut.model_validate(event)
    out.is_favorite = event.id in favorite_ids
    return out


def reply_out(reply: BotReply, favorite_ids: Collection[int] = ()) -> AssistantReplyOut:
    tz = get_settings().tz
    return AssistantReplyOut(
        text=reply.text,
        quick_replies=[
            QuickReplyOut(label=q.label, payload=q.payload) for q in reply.quick_replies
        ],
        cards=[
            CardOut(
                event=event_out(card.event, favorite_ids),
                reasons=card.reasons,
                source_note=format_source(card.event, tz),
            )
            for card in reply.cards
        ],
    )


def poll_out(view: PollView, favorite_ids: Collection[int] = ()) -> PollOut:
    return PollOut(
        id=view.poll.id,
        title=view.poll.title,
        options=[
            PollOptionOut(
                id=result.option.id,
                event=event_out(result.option.event, favorite_ids),
                votes=result.votes,
            )
            for result in view.options
        ],
        total_votes=view.total_votes,
        my_option_id=view.my_option_id,
    )
