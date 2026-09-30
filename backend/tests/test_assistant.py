from conftest import as_user


async def say(client, user_id=1, *, text=None, payload=None) -> dict:
    body = {"text": text} if text is not None else {"payload": payload}
    response = await client.post("/assistant/messages", headers=as_user(user_id), json=body)
    assert response.status_code == 200, response.text
    return response.json()


def payloads(reply: dict) -> set[str]:
    return {q["payload"] for q in reply["quick_replies"]}


async def test_request_needs_exactly_one_of_text_or_payload(client):
    for body in ({}, {"text": "a", "payload": "d:more"}, {"text": ""}):
        response = await client.post("/assistant/messages", headers=as_user(), json=body)
        assert response.status_code == 422


async def test_greeting_asks_when_first(client):
    reply = await say(client, text="привет")
    assert reply["cards"] == []
    assert "d:when:weekend" in payloads(reply)


async def test_full_dialog_asks_when_then_topic_then_recommends(client):
    reply = await say(client, text="привет")
    assert "d:when:week" in payloads(reply)

    reply = await say(client, payload="d:when:week")
    assert reply["cards"] == [] and "d:topic:concert" in payloads(reply)

    reply = await say(client, payload="d:topic:concert")
    assert 1 <= len(reply["cards"]) <= 3
    for card in reply["cards"]:
        assert card["event"]["category"]["slug"] == "concert"
        assert (
            card["source_note"].startswith("Источник:") and "тестовые данные" in card["source_note"]
        )
    assert {"d:more", "d:cheaper", "d:free", "d:reset"} <= payloads(reply)


async def test_week_request_spreads_cards_over_days(client):
    reply = await say(client, text="удиви меня на этой неделе")
    days = {card["event"]["starts_at"][:10] for card in reply["cards"]}
    assert len(reply["cards"]) == 3 and len(days) > 1, reply["cards"]
    assert "с сегодняшнего дня по" in reply["text"]


async def test_one_sentence_skips_questions(client):
    reply = await say(client, text="что-нибудь спокойное на этой неделе")
    assert reply["cards"], reply["text"]
    assert all("calm" in card["event"]["tags"] for card in reply["cards"])
    assert all(any("спокойное" in r for r in card["reasons"]) for card in reply["cards"])


async def test_more_never_repeats_events(client):
    first = await say(client, text="концерты на этой неделе")
    seen = {c["event"]["id"] for c in first["cards"]}
    assert seen
    for _ in range(3):
        reply = await say(client, payload="d:more")
        ids = {c["event"]["id"] for c in reply["cards"]}
        assert not ids & seen
        seen |= ids
        if not ids:
            assert "больше нет" in reply["text"]
            break


async def test_free_only_and_budget(client):
    reply = await say(client, text="бесплатно на этой неделе")
    assert reply["cards"] and all(c["event"]["is_free"] for c in reply["cards"])

    reply = await say(client, user_id=2, text="до 400 рублей на этой неделе")
    assert reply["cards"] and all(c["event"]["price_min"] <= 400 for c in reply["cards"])


async def test_cheaper_lowers_the_price_ceiling(client):
    first = await say(client, text="театр или концерт на этой неделе")
    ceiling = int(max(c["event"]["price_min"] for c in first["cards"]) * 0.6) // 50 * 50
    reply = await say(client, payload="d:cheaper")
    assert reply["cards"], reply["text"]
    assert all(c["event"]["price_min"] <= ceiling for c in reply["cards"])
    assert reply["text"].count("до ") >= 1 or "бесплатно" in reply["text"]


async def test_pushkin_card_filter(client):
    reply = await say(client, text="по пушкинской карте на этой неделе")
    assert reply["cards"] and all(c["event"]["pushkin_card"] for c in reply["cards"])


async def test_kids_companion_limits_age(client):
    reply = await say(client, text="с ребенком на этой неделе")
    assert reply["cards"] and all(c["event"]["age_limit"] <= 12 for c in reply["cards"])


async def test_relaxation_is_reported_honestly(client):
    # романтичных волонтёрских событий нет: бот убирает пожелание и прямо об этом говорит
    reply = await say(client, text="волонтерство романтичное на этой неделе")
    assert reply["cards"]
    assert all(c["event"]["category"]["slug"] == "volunteering" for c in reply["cards"])
    assert "поиск расширен" in reply["text"] and "без учёта пожеланий" in reply["text"]


async def test_nothing_found_offers_recovery(client):
    # бесплатных событий по Пушкинской карте не бывает; эти условия бот не ослабляет
    reply = await say(client, text="бесплатно по пушкинской карте на этой неделе")
    assert reply["cards"] == [] and "не нашлось" in reply["text"]
    assert "d:reset" in payloads(reply)


async def test_reset_clears_criteria(client):
    await say(client, text="концерты на этой неделе")
    reply = await say(client, payload="d:reset")
    assert reply["cards"] == [] and "d:when:today" in payloads(reply)
    reply = await say(client, text="что-нибудь спокойное на этой неделе")
    assert {c["event"]["category"]["slug"] for c in reply["cards"]} != {"concert"}


async def test_unrecognised_text_mid_dialog_gets_a_hint(client):
    await say(client, payload="d:when:week")
    reply = await say(client, text="asdf qwerty")
    assert "Не совсем понял" in reply["text"]


async def test_dialogs_are_isolated_between_users(client):
    await say(client, user_id=10, text="концерты на этой неделе")
    reply = await say(client, user_id=11, text="привет")
    assert reply["cards"] == []


async def test_favorite_flag_in_assistant_cards(client):
    reply = await say(client, text="концерты на этой неделе")
    event_id = reply["cards"][0]["event"]["id"]
    assert reply["cards"][0]["event"]["is_favorite"] is False
    await client.put(f"/me/favorites/{event_id}", headers=as_user())

    await say(client, payload="d:reset")
    reply = await say(client, text="концерты на этой неделе")
    flags = {c["event"]["id"]: c["event"]["is_favorite"] for c in reply["cards"]}
    assert flags[event_id] is True


async def test_reset_endpoint(client):
    await say(client, text="концерты на этой неделе")
    response = await client.post("/assistant/reset", headers=as_user())
    assert response.status_code == 200 and response.json()["cards"] == []


async def test_pilot_metrics(client):
    await say(client, text="концерты на этой неделе")
    await say(client, user_id=2, text="привет")

    assert (await client.get("/admin/metrics")).status_code == 403
    assert (
        await client.get("/admin/metrics", headers={"X-Admin-Token": "wrong"})
    ).status_code == 403

    metrics = (
        await client.get("/admin/metrics", headers={"X-Admin-Token": "test-admin-token"})
    ).json()
    assert metrics["dialogs_started"] == 2
    assert metrics["dialogs_with_recommendation"] == 1
    assert metrics["completion_rate"] == 0.5
    assert metrics["events_shown"] >= 1
    assert metrics["median_seconds_to_first_recommendation"] is not None
