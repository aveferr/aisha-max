from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.catalog import CategoryOut, CityOut, EventOut, ORMModel


class UserOut(ORMModel):
    id: int
    max_user_id: int
    first_name: str
    last_name: str | None
    username: str | None
    city: CityOut | None
    interests: list[CategoryOut]


class UserUpdate(BaseModel):
    city_id: int | None = None
    interests: list[str] | None = Field(default=None, description="Слаги категорий")


class ReminderCreate(BaseModel):
    event_id: int
    minutes_before: int = Field(default=120, ge=1, le=7 * 24 * 60)


class ReminderOut(ORMModel):
    event: EventOut
    remind_at: datetime
