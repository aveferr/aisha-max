"""Контракт API для проверяющих: openapi.yaml и DATA-API.yaml не должны расходиться с кодом.

Проверки из DATA-API.yaml выполняются здесь же, против приложения, — так файл, который получит
платформа оценки, заведомо описывает то, что API действительно делает.
"""

import json
from pathlib import Path

import pytest
import yaml
from conftest import BACKEND_DIR

ROOT = BACKEND_DIR.parent
DATA_API = yaml.safe_load((ROOT / "DATA-API.yaml").read_text(encoding="utf-8"))

PYTHON_TYPES = {"object": dict, "array": list}


def test_openapi_file_matches_the_code():
    from app.main import app

    published = yaml.safe_load((ROOT / "openapi.yaml").read_text(encoding="utf-8"))
    assert published == json.loads(json.dumps(app.openapi())), (
        "openapi.yaml устарел: выполните `cd backend && python scripts/export_contract.py`"
    )


def test_events_test_data_matches_the_seed():
    from scripts.export_contract import render_events

    published = (ROOT / "test-data" / "events.json").read_text(encoding="utf-8")
    assert published == render_events(), (
        "test-data/events.json устарел: запустите export_contract.py"
    )


def test_data_api_declares_required_sections():
    assert DATA_API["config_version"] and DATA_API["solution"] and DATA_API["base_url"]
    assert Path(ROOT, DATA_API["openapi"]).exists()
    assert Path(ROOT, DATA_API["test_data"]).exists()
    assert {"anonymous", "user"} <= set(DATA_API["roles"])
    ids = [check["id"] for check in DATA_API["checks"]]
    assert len(ids) == len(set(ids)), "идентификаторы проверок должны быть уникальны"
    for check in DATA_API["checks"]:
        assert check["role"] in DATA_API["roles"], check["id"]
        assert check["expect"]["status"], check["id"]


def _assert_json(payload, rules: dict, where: str) -> None:
    if expected_type := rules.get("type"):
        assert isinstance(payload, PYTHON_TYPES[expected_type]), (
            f"{where}: ожидался {expected_type}"
        )
    if isinstance(payload, dict):
        missing = [key for key in rules.get("required", []) if key not in payload]
        assert not missing, f"{where}: нет полей {missing}"
        for key, value in rules.get("values", {}).items():
            assert payload[key] == value, f"{where}: {key} = {payload[key]!r}, ожидалось {value!r}"
        for field, keys in rules.get("array_fields", {}).items():
            assert isinstance(payload[field], list), f"{where}: {field} должен быть массивом"
            for item in payload[field]:
                assert not [k for k in keys if k not in item], f"{where}: в {field} нет {keys}"
        non_empty = rules.get("non_empty", [])
        for field in non_empty if isinstance(non_empty, list) else []:
            assert payload[field], f"{where}: {field} не должен быть пустым"
    if isinstance(payload, list):
        if rules.get("non_empty") is True:
            assert payload, f"{where}: массив не должен быть пустым"
        for item in payload:
            assert not [k for k in rules.get("item_required", []) if k not in item], where


async def test_every_check_in_data_api_passes(client):
    """Выполняет проверки по порядку, как это сделает платформа оценки."""
    for check in DATA_API["checks"]:
        request = check["request"] or {}
        path = check["path"].format(**request.get("path", {}))
        response = await client.request(
            check["method"],
            f"http://test{path}",
            headers=DATA_API["roles"][check["role"]]["headers"],
            params=request.get("query"),
            json=request.get("body"),
        )
        expect = check["expect"]
        where = f"[{check['id']}] {check['method']} {path}"
        assert response.status_code in expect["status"], (
            f"{where}: {response.status_code} {response.text}"
        )
        if "content_type" in expect:
            assert response.headers["content-type"].startswith(expect["content_type"]), where
        if "json" in expect:
            _assert_json(response.json(), expect["json"], where)


@pytest.mark.parametrize("identifier", ["1", "2"])
async def test_event_ids_promised_to_the_checker_exist(client, identifier):
    """DATA-API.yaml ссылается на события 1 и 2 — на чистой базе они обязаны существовать."""
    response = await client.get(f"http://test/api/v1/events/{identifier}")
    assert response.status_code == 200
