from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routers import admin, assistant, events, me, meta, polls
from app.core.config import get_settings
from app.core.db import engine
from app.core.errors import DomainError, NotFoundError
from app.core.logging import configure_logging

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Афиша MAX — API",
        description="Бэкенд мини-приложения и чат-бота афиши с умным подбором событий.",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_: Request, error: NotFoundError) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=status.HTTP_404_NOT_FOUND)

    @app.exception_handler(DomainError)
    async def domain_error_handler(_: Request, error: DomainError) -> JSONResponse:
        return JSONResponse(
            {"detail": str(error)}, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT
        )

    app.include_router(meta.health_router)
    for router in (
        meta.router,
        events.router,
        me.router,
        assistant.router,
        polls.router,
        admin.router,
    ):
        app.include_router(router, prefix=API_PREFIX)
    return app


app = create_app()
