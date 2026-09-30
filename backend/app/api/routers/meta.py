from fastapi import APIRouter
from sqlalchemy import select, text

from app.api.deps import SessionDep
from app.models import Category, City
from app.schemas.catalog import CategoryOut, CityOut

router = APIRouter(tags=["catalog"])
health_router = APIRouter(tags=["service"])


@health_router.get("/health")
async def health(session: SessionDep) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/cities", response_model=list[CityOut])
async def list_cities(session: SessionDep) -> list[City]:
    return list(await session.scalars(select(City).order_by(City.name)))


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(session: SessionDep) -> list[Category]:
    return list(await session.scalars(select(Category).order_by(Category.id)))
