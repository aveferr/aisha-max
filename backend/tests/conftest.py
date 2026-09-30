"""Фикстуры тестов.

Интеграционным тестам нужен PostgreSQL: берётся из TEST_DATABASE_URL, а если её нет —
поднимается встроенный (пакет pgserver). Окружение настраивается ДО импорта приложения,
потому что движок БД создаётся при импорте app.core.db.
"""

import os
import subprocess
import sys
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
_embedded_server = None


def _start_database() -> str:
    global _embedded_server
    if url := os.environ.get("TEST_DATABASE_URL"):
        return url
    pgserver = pytest.importorskip(
        "pgserver", reason="нужен PostgreSQL: pgserver или TEST_DATABASE_URL"
    )
    _embedded_server = pgserver.get_server(tempfile.mkdtemp(prefix="afisha-pg-"))
    _embedded_server.psql("CREATE DATABASE afisha_test;")
    return _embedded_server.get_uri("afisha_test").replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )


def _prepare_environment() -> None:
    os.environ.update(
        DATABASE_URL=_start_database(),
        DEV_AUTH_ENABLED="true",
        ADMIN_TOKEN="test-admin-token",
        MAX_BOT_TOKEN="test-bot-token",
        LLM_BASE_URL="",
        MAX_BOT_USERNAME="test_afisha_bot",
    )
    for command in (["-m", "alembic", "upgrade", "head"], ["-m", "app.seed"]):
        subprocess.run([sys.executable, *command], cwd=BACKEND_DIR, check=True)


_prepare_environment()


def pytest_sessionfinish() -> None:
    if _embedded_server is not None:
        _embedded_server.cleanup()


@pytest.fixture(autouse=True)
async def clean_user_data() -> AsyncIterator[None]:
    """Между тестами очищаем всё, что создают пользователи; каталог событий остаётся."""
    from sqlalchemy import text

    from app.core.db import engine

    yield
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE users RESTART IDENTITY CASCADE"))


@pytest.fixture(scope="session")
async def client() -> AsyncIterator[httpx.AsyncClient]:

    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test/api/v1") as http:
        yield http


def as_user(user_id: int = 1) -> dict[str, str]:
    """Заголовки dev-аутентификации (DEV_AUTH_ENABLED=true в тестах)."""
    return {"X-Dev-User-Id": str(user_id)}
