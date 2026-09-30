from datetime import UTC, datetime, timedelta

from conftest import as_user
from sqlalchemy import func, select

from app.core.db import SessionFactory
from app.models import Interaction, InteractionKind, Reminder
from app.services.reminders import ReminderService
from app.services.users import MaxProfile, UserService


async def first_events(client, count: int) -> list[int]:
    items = (await client.get("/events")).json()["items"]
    return [item["id"] for item in items[:count]]


async def test_poll_voting_flow(client):
    a, b = await first_events(client, 2)
    created = await client.post(
        "/polls", headers=as_user(1), json={"event_ids": [a, b], "title": "Куда в субботу?"}
    )
    assert created.status_code == 201
    poll = created.json()
    assert poll["title"] == "Куда в субботу?" and poll["total_votes"] == 0
    option_a, option_b = (o["id"] for o in poll["options"])

    await client.post(
        f"/polls/{poll['id']}/votes", headers=as_user(1), json={"option_id": option_a}
    )
    await client.post(
        f"/polls/{poll['id']}/votes", headers=as_user(2), json={"option_id": option_a}
    )
    result = (
        await client.post(
            f"/polls/{poll['id']}/votes", headers=as_user(3), json={"option_id": option_b}
        )
    ).json()
    assert {o["id"]: o["votes"] for o in result["options"]} == {option_a: 2, option_b: 1}
    assert result["my_option_id"] == option_b and result["total_votes"] == 3

    # повторный голос меняет выбор, а не добавляет второй
    result = (
        await client.post(
            f"/polls/{poll['id']}/votes", headers=as_user(3), json={"option_id": option_a}
        )
    ).json()
    assert result["total_votes"] == 3 and result["my_option_id"] == option_a

    anonymous = (await client.get(f"/polls/{poll['id']}")).json()
    assert anonymous["my_option_id"] is None and anonymous["total_votes"] == 3


async def test_poll_validation(client):
    a, b, c = await first_events(client, 3)
    headers = as_user(1)
    assert (
        await client.post("/polls", headers=headers, json={"event_ids": [a]})
    ).status_code == 422
    assert (
        await client.post("/polls", headers=headers, json={"event_ids": [a, a]})
    ).status_code == 422
    assert (
        await client.post("/polls", headers=headers, json={"event_ids": [a, 999999]})
    ).status_code == 404
    assert (await client.get("/polls/999999")).status_code == 404

    first = (await client.post("/polls", headers=headers, json={"event_ids": [a, b]})).json()
    second = (await client.post("/polls", headers=headers, json={"event_ids": [b, c]})).json()
    foreign_option = second["options"][0]["id"]
    # вариант из другого голосования принять нельзя
    response = await client.post(
        f"/polls/{first['id']}/votes", headers=as_user(2), json={"option_id": foreign_option}
    )
    assert response.status_code == 422
    assert (
        await client.post(f"/polls/{first['id']}/votes", json={"option_id": 1})
    ).status_code == 401


async def test_interactions_feed_the_metrics(client):
    event_id = (await first_events(client, 1))[0]
    headers = as_user(5)
    await client.put(f"/me/favorites/{event_id}", headers=headers)
    await client.put(f"/me/favorites/{event_id}", headers=headers)  # повтор не считается
    await client.get(f"/events/{event_id}", headers=headers)
    await client.post(f"/events/{event_id}/ticket-click", headers=headers)

    async with SessionFactory() as session:
        counts = dict(
            (
                await session.execute(
                    select(Interaction.kind, func.count()).group_by(Interaction.kind)
                )
            ).all()
        )
    assert counts[InteractionKind.FAVORITED] == 1
    assert counts[InteractionKind.OPENED] == 1
    assert counts[InteractionKind.TICKET_CLICK] == 1


async def test_user_service_is_idempotent_and_updates_profile(client):
    async with SessionFactory() as session:
        service = UserService(session)
        first = await service.get_or_create(MaxProfile(900, "Аня", None, "anya"))
        again = await service.get_or_create(MaxProfile(900, "Анна", "Петрова", "anya2"))
        await session.commit()
        assert first.id == again.id
        assert (again.first_name, again.last_name, again.username) == ("Анна", "Петрова", "anya2")
        count = await session.scalar(select(func.count()).select_from(type(first)))
        assert count == 1


async def test_due_reminders_are_claimed_exactly_once(client):
    events = (await client.get("/events", params={"limit": 100})).json()["items"]
    far = next(
        e
        for e in events
        if datetime.fromisoformat(e["starts_at"]) > datetime.now(UTC) + timedelta(hours=6)
    )
    await client.post(
        "/me/reminders", headers=as_user(6), json={"event_id": far["id"], "minutes_before": 60}
    )

    async with SessionFactory() as session:
        assert await ReminderService(session).claim_due() == []  # ещё рано

        later = datetime.fromisoformat(
            far["starts_at"]
        )  # к началу события напоминание «просрочено»
        service = ReminderService(session, clock=lambda: later)
        claimed = await service.claim_due()
        await session.commit()
        assert [r.event_id for r in claimed] == [far["id"]]
        assert claimed[0].user.max_user_id == 6

    async with SessionFactory() as session:
        assert await ReminderService(session, clock=lambda: later).claim_due() == []
        stored = await session.scalar(select(Reminder))
        assert stored.sent_at is not None
    assert (
        await client.get("/me/reminders", headers=as_user(6))
    ).json() == []  # отправленные не показываются


async def test_my_polls_lists_created_and_voted_polls_newest_first(client):
    a, b, c = await first_events(client, 3)
    author = as_user(1)
    first = (
        await client.post("/polls", headers=author, json={"event_ids": [a, b], "title": "Первое"})
    ).json()
    await client.post("/polls", headers=author, json={"event_ids": [b, c], "title": "Второе"})
    option = first["options"][0]["id"]
    await client.post(f"/polls/{first['id']}/votes", headers=as_user(2), json={"option_id": option})

    mine = (await client.get("/polls", headers=author)).json()
    assert [p["title"] for p in mine] == ["Второе", "Первое"]  # новые сверху
    assert all(p["is_mine"] and not p["voted"] for p in mine)
    older = mine[1]
    assert (older["total_votes"], older["options_count"]) == (1, 2)
    assert len(older["events_preview"]) == 2 and older["created_at"]

    # участник видит только то, в чём голосовал, и не считает себя автором
    guest = (await client.get("/polls", headers=as_user(2))).json()
    assert [(p["title"], p["is_mine"], p["voted"]) for p in guest] == [("Первое", False, True)]

    assert (await client.get("/polls", headers=as_user(3))).json() == []
    assert (await client.get("/polls")).status_code == 401
