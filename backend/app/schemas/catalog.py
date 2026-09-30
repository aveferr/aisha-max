from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CityOut(ORMModel):
    id: int
    name: str


class CategoryOut(ORMModel):
    id: int
    slug: str
    title: str
    emoji: str


class VenueOut(ORMModel):
    id: int
    name: str
    address: str
    latitude: float | None
    longitude: float | None
    city: CityOut


class EventOut(ORMModel):
    id: int
    title: str
    description: str
    category: CategoryOut
    venue: VenueOut
    starts_at: datetime
    ends_at: datetime | None
    price_min: int
    price_max: int | None
    is_free: bool
    age_limit: int
    pushkin_card: bool
    tags: list[str]
    image_url: str | None
    ticket_url: str | None
    source: str
    source_url: str | None
    status: str
    is_test_data: bool  # данные демонстрационные, не из реального источника
    data_updated_at: datetime  # когда данные о событии в последний раз подтверждались
    is_favorite: bool = False


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
