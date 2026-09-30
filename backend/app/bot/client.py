"""Тонкий клиент MAX Bot API (https://dev.max.ru/docs-api)."""

from typing import Any

import httpx

UPDATE_TYPES = ("message_created", "message_callback", "bot_started")
LONG_POLL_TIMEOUT = 30  # секунд; сервер держит запрос, пока нет обновлений


class MaxApiError(Exception):
    def __init__(self, status_code: int, body: str) -> None:
        super().__init__(f"MAX API вернул {status_code}: {body[:300]}")
        self.status_code = status_code


class MaxClient:
    def __init__(
        self,
        token: str,
        base_url: str,
        *,
        ca_bundle: str | None = None,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._http = http or httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": token},
            verify=ca_bundle or True,
            timeout=15,
        )

    async def get_updates(self, marker: int | None) -> tuple[list[dict[str, Any]], int | None]:
        params: dict[str, Any] = {
            "timeout": LONG_POLL_TIMEOUT,
            "limit": 100,
            "types": ",".join(UPDATE_TYPES),
        }
        if marker is not None:
            params["marker"] = marker
        data = await self._request("GET", "/updates", params=params, timeout=LONG_POLL_TIMEOUT + 10)
        return data.get("updates", []), data.get("marker")

    async def send_message(self, user_id: int, message: dict[str, Any]) -> None:
        await self._request("POST", "/messages", params={"user_id": user_id}, json=message)

    async def answer_callback(
        self,
        callback_id: str,
        *,
        notification: str | None = None,
        message: dict[str, Any] | None = None,
    ) -> None:
        """Подтверждает нажатие кнопки: всплывающее уведомление и/или замена текста сообщения."""
        body = {k: v for k, v in {"notification": notification, "message": message}.items() if v}
        await self._request("POST", "/answers", params={"callback_id": callback_id}, json=body)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = await self._http.request(method, path, **kwargs)
        if response.status_code >= 400:
            raise MaxApiError(response.status_code, response.text)
        return response.json() if response.content else {}
