"""Выгружает в корень репозитория контракт API и тестовые данные для проверки.

    cd backend && python scripts/export_contract.py

Создаёт:
  openapi.yaml           — описание API (OpenAPI 3.1), генерируется из кода приложения;
  test-data/events.json  — демонстрационные события, которые видит проверяющий на чистой базе.

Тест tests/test_contract.py следит, чтобы файлы не расходились с кодом.
"""

import json
import sys
from pathlib import Path

import yaml

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402
from app.seed.demo_events import EVENTS, VENUES  # noqa: E402


def render_openapi() -> str:
    return yaml.safe_dump(app.openapi(), allow_unicode=True, sort_keys=False, width=100)


def render_events() -> str:
    venues = {venue.key: venue.name for venue in VENUES}
    events = [
        {
            # На чистой базе события получают номера по порядку загрузки.
            "id": number,
            "external_id": seed.key,
            "title": seed.title,
            "category": seed.category,
            "venue": venues[seed.venue],
            "day_offset": seed.day_offset,
            "time": seed.time,
            "price_min": seed.price_min,
            "price_max": seed.price_max,
            "age_limit": seed.age_limit,
            "pushkin_card": seed.pushkin_card,
            "tags": seed.tags,
            "status": "cancelled" if seed.cancelled else "scheduled",
        }
        for number, seed in enumerate(EVENTS, start=1)
    ]
    note = (
        "Демонстрационные данные (все события вымышлены). day_offset — через сколько дней "
        "от запуска сида начинается событие; даты пересчитываются при каждом старте."
    )
    return json.dumps({"note": note, "events": events}, ensure_ascii=False, indent=2) + "\n"


def main() -> None:
    (ROOT / "openapi.yaml").write_text(render_openapi(), encoding="utf-8")
    (ROOT / "test-data").mkdir(exist_ok=True)
    (ROOT / "test-data" / "events.json").write_text(render_events(), encoding="utf-8")
    print("Записаны openapi.yaml и test-data/events.json")


if __name__ == "__main__":
    main()
