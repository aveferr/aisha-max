import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import pytest

from app.api.security import validate_init_data
from app.core.errors import AuthError

TOKEN = "123:secret-token"
NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


def sign(fields: dict[str, str], token: str = TOKEN) -> str:
    """Собирает initData так, как это делает MAX Bridge."""
    check = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": digest})


def fields(auth_date: datetime = NOW, user_id: int = 42) -> dict[str, str]:
    user = {"id": user_id, "first_name": "Алина", "last_name": None, "username": "alina"}
    return {
        "auth_date": str(int(auth_date.timestamp())),
        "query_id": "q-1",
        "user": json.dumps(user, ensure_ascii=False),
        "start_param": "poll_7",
    }


def validate(raw: str, token: str = TOKEN):
    return validate_init_data(raw, token, max_age_seconds=3600, clock=lambda: NOW)


def test_valid_init_data():
    data = validate(sign(fields()))
    assert data.profile.max_user_id == 42
    assert data.profile.first_name == "Алина"
    assert data.start_param == "poll_7"


def test_wrong_token_is_rejected():
    with pytest.raises(AuthError, match="подпись"):
        validate(sign(fields(), token="other"))


def test_tampered_payload_is_rejected():
    raw = sign(fields(user_id=42)).replace("%22id%22%3A+42", "%22id%22%3A+1")
    with pytest.raises(AuthError):
        validate(raw)


def test_expired_init_data_is_rejected():
    with pytest.raises(AuthError, match="устарели"):
        validate(sign(fields(auth_date=NOW - timedelta(hours=2))))


def test_missing_hash_and_duplicates_are_rejected():
    with pytest.raises(AuthError, match="нет подписи"):
        validate(urlencode(fields()))
    with pytest.raises(AuthError, match="повторяется"):
        validate(sign(fields()) + "&auth_date=1")


def test_bot_token_must_be_configured():
    with pytest.raises(AuthError, match="Токен"):
        validate(sign(fields()), token="")
