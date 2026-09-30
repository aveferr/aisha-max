import hmac
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, status

from app.api.deps import SessionDep
from app.core.config import get_settings
from app.services.metrics import MetricsService, PilotMetrics

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/metrics", response_model=PilotMetrics)
async def pilot_metrics(
    session: SessionDep,
    x_admin_token: Annotated[str | None, Header()] = None,
    days: Annotated[int, Query(ge=1, le=365)] = 7,
) -> PilotMetrics:
    """Метрики пилота. Отключены, пока не задан ADMIN_TOKEN."""
    expected = get_settings().admin_token
    if not expected:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Не найдено")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Неверный токен")
    return await MetricsService(session).pilot_metrics(days)
