"""Проверка подлинности initData мини-приложения MAX (HMAC-SHA256, ключ от токена бота)."""

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qsl

from app.core.clock import Clock, utcnow
from app.core.errors import AuthError
from app.services.users import MaxProfile


@dataclass(frozen=True)
class InitData:
    profile: MaxProfile
    auth_date: datetime
    start_param: str | None


def validate_init_data(
    raw: str, bot_token: str, *, max_age_seconds: int, clock: Clock = utcnow
) -> InitData:
    """Проверяет подпись и свежесть initData; иначе бросает AuthError.

    Алгоритм: пары key=value (кроме hash) сортируются по ключу и склеиваются через \\n;
    подпись = HMAC-SHA256(ключ=HMAC-SHA256("WebAppData", токен бота), данные).
    """
    if not bot_token:
        raise AuthError("Токен бота не настроен: проверить подпись initData нельзя")

    pairs = parse_qsl(raw, keep_blank_values=True)
    fields: dict[str, str] = {}
    for key, value in pairs:
        if key in fields:
            raise AuthError("Параметр initData повторяется")
        fields[key] = value

    received_hash = fields.pop("hash", None)
    if not received_hash:
        raise AuthError("В initData нет подписи")

    check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise AuthError("Неверная подпись initData")

    try:
        auth_date = datetime.fromtimestamp(int(fields["auth_date"]), tz=clock().tzinfo)
        user = json.loads(fields["user"])
        profile = MaxProfile(
            max_user_id=int(user["id"]),
            first_name=user.get("first_name") or "",
            last_name=user.get("last_name"),
            username=user.get("username"),
        )
    except (KeyError, ValueError, TypeError) as error:
        raise AuthError("Некорректные данные пользователя в initData") from error

    if (clock() - auth_date).total_seconds() > max_age_seconds:
        raise AuthError("initData устарели, откройте приложение заново")
    return InitData(profile, auth_date, fields.get("start_param"))
