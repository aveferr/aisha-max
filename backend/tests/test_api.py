from datetime import UTC, datetime, timedelta

from conftest import as_user


async def test_health(client):
    response = await client.get("http://test/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_reference_data(client):
    cities = (await client.get("/cities")).json()
    assert [c["name"] for c in cities] == ["Санкт-Петербург"]
    categories = (await client.get("/categories")).json()
    assert {"concert", "theatre", "volunteering"} <= {c["slug"] for c in categories}


async def test_catalog_returns_only_upcoming_scheduled_events(client):
    page = (await client.get("/events", params={"limit": 100})).json()
    now = datetime.now(UTC)
    assert page["total"] >= 30
    assert all(item["status"] == "scheduled" for item in page["items"])
    assert all(datetime.fromisoformat(item["starts_at"]) >= now for item in page["items"])
    assert all(item["is_test_data"] for item in page["items"])
    starts = [item["starts_at"] for item in page["items"]]
    assert starts == sorted(starts)


async def test_catalog_filters(client):
    concerts = (await client.get("/events", params={"category": "concert", "limit": 100})).json()
    assert concerts["items"]
    assert {i["category"]["slug"] for i in concerts["items"]} == {"concert"}

    free = (await client.get("/events", params={"free": True, "limit": 100})).json()
    assert free["items"] and all(i["price_min"] == 0 and i["is_free"] for i in free["items"])

    cheap = (await client.get("/events", params={"price_max": 300, "limit": 100})).json()
    assert all(i["price_min"] <= 300 for i in cheap["items"])

    calm = (await client.get("/events", params={"tag": "calm", "limit": 100})).json()
    assert all("calm" in i["tags"] for i in calm["items"])

    kids = (await client.get("/events", params={"max_age": 6, "limit": 100})).json()
    assert all(i["age_limit"] <= 6 for i in kids["items"])

    pushkin = (await client.get("/events", params={"pushkin_card": True, "limit": 100})).json()
    assert pushkin["items"] and all(i["pushkin_card"] for i in pushkin["items"])


async def test_catalog_text_search_is_escaped(client):
    found = (await client.get("/events", params={"q": "джаз"})).json()
    assert any("джаз" in i["title"].lower() for i in found["items"])
    # спецсимволы LIKE не должны превращаться в шаблон
    assert (await client.get("/events", params={"q": "%"})).json()["total"] == 0


async def test_catalog_pagination(client):
    first = (await client.get("/events", params={"limit": 5, "offset": 0})).json()
    second = (await client.get("/events", params={"limit": 5, "offset": 5})).json()
    assert len(first["items"]) == len(second["items"]) == 5
    assert not {i["id"] for i in first["items"]} & {i["id"] for i in second["items"]}
    assert first["total"] == second["total"]


async def test_catalog_rejects_bad_parameters(client):
    assert (await client.get("/events", params={"limit": 1000})).status_code == 422


async def test_event_details_and_404(client):
    event_id = (await client.get("/events")).json()["items"][0]["id"]
    detail = (await client.get(f"/events/{event_id}")).json()
    assert detail["venue"]["city"]["name"] == "Санкт-Петербург"
    assert (await client.get("/events/999999")).status_code == 404


async def test_private_endpoints_require_authentication(client):
    for path in ("/me", "/me/favorites", "/me/reminders"):
        assert (await client.get(path)).status_code == 401
    assert (await client.get("/me", headers={"X-Max-Init-Data": "garbage"})).status_code == 401
    assert (await client.get("/me", headers={"X-Dev-User-Id": "abc"})).status_code == 401


async def test_profile_and_interests(client):
    me = (await client.get("/me", headers=as_user(7))).json()
    assert me["max_user_id"] == 7 and me["interests"] == []
    assert me["city"]["name"] == "Санкт-Петербург"

    updated = await client.patch(
        "/me", headers=as_user(7), json={"interests": ["concert", "sport"]}
    )
    assert {c["slug"] for c in updated.json()["interests"]} == {"concert", "sport"}

    bad = await client.patch("/me", headers=as_user(7), json={"interests": ["nope"]})
    assert bad.status_code == 422
    bad_city = await client.patch("/me", headers=as_user(7), json={"city_id": 999})
    assert bad_city.status_code == 422


async def test_favorites_lifecycle(client):
    event_id = (await client.get("/events")).json()["items"][0]["id"]
    headers = as_user(2)

    assert (await client.put(f"/me/favorites/{event_id}", headers=headers)).status_code == 204
    assert (
        await client.put(f"/me/favorites/{event_id}", headers=headers)
    ).status_code == 204  # идемпотентно
    favorites = (await client.get("/me/favorites", headers=headers)).json()
    assert [e["id"] for e in favorites] == [event_id] and favorites[0]["is_favorite"]

    flagged = (await client.get("/events", headers=headers)).json()["items"]
    assert next(i for i in flagged if i["id"] == event_id)["is_favorite"] is True
    anonymous = (await client.get("/events")).json()["items"]
    assert not any(i["is_favorite"] for i in anonymous)

    assert (await client.delete(f"/me/favorites/{event_id}", headers=headers)).status_code == 204
    assert (await client.get("/me/favorites", headers=headers)).json() == []
    assert (await client.put("/me/favorites/999999", headers=headers)).status_code == 404


async def test_reminders_lifecycle(client):
    events = (await client.get("/events", params={"limit": 100})).json()["items"]
    far = next(
        e
        for e in events
        if datetime.fromisoformat(e["starts_at"]) > datetime.now(UTC) + timedelta(hours=6)
    )
    headers = as_user(3)

    created = await client.post(
        "/me/reminders", headers=headers, json={"event_id": far["id"], "minutes_before": 60}
    )
    assert created.status_code == 201
    expected = datetime.fromisoformat(far["starts_at"]) - timedelta(minutes=60)
    assert datetime.fromisoformat(created.json()["remind_at"]) == expected

    # повторная установка обновляет время, а не создаёт дубль
    await client.post(
        "/me/reminders", headers=headers, json={"event_id": far["id"], "minutes_before": 30}
    )
    reminders = (await client.get("/me/reminders", headers=headers)).json()
    assert len(reminders) == 1

    too_early = await client.post(
        "/me/reminders", headers=headers, json={"event_id": far["id"], "minutes_before": 10_000}
    )
    assert too_early.status_code == 422  # вне допустимого диапазона
    assert (
        await client.post("/me/reminders", headers=headers, json={"event_id": 999999})
    ).status_code == 404

    assert (await client.delete(f"/me/reminders/{far['id']}", headers=headers)).status_code == 204
    assert (await client.get("/me/reminders", headers=headers)).json() == []


async def test_cancelled_event_is_hidden_from_catalog_and_rejects_reminders(client):
    from sqlalchemy import select

    from app.core.db import SessionFactory
    from app.models import Event

    async with SessionFactory() as session:
        cancelled_id = await session.scalar(select(Event.id).where(Event.external_id == "c07"))
    ids = {i["id"] for i in (await client.get("/events", params={"limit": 100})).json()["items"]}
    assert cancelled_id not in ids
    response = await client.post(
        "/me/reminders", headers=as_user(4), json={"event_id": cancelled_id, "minutes_before": 30}
    )
    assert response.status_code == 422
