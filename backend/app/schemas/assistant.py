from pydantic import BaseModel, Field, model_validator

from app.schemas.catalog import EventOut


class AssistantRequest(BaseModel):
    """Реплика пользователя: либо свободный текст, либо payload нажатой быстрой кнопки."""

    text: str | None = Field(default=None, min_length=1, max_length=1000)
    payload: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def _exactly_one(self) -> "AssistantRequest":
        if (self.text is None) == (self.payload is None):
            raise ValueError("Передайте ровно одно из полей: text или payload")
        return self


class QuickReplyOut(BaseModel):
    label: str
    payload: str


class CardOut(BaseModel):
    event: EventOut
    reasons: list[str]
    source_note: str


class AssistantReplyOut(BaseModel):
    text: str
    quick_replies: list[QuickReplyOut]
    cards: list[CardOut]
