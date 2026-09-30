import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.assistant.criteria import Companions, Criteria, Patch, TimeOfDay, apply_patch, resolve_when
from app.assistant.formatting import describe_criteria
from app.assistant.parser import RuleBasedParser, sanitize_llm_patch

TZ = ZoneInfo("Europe/Moscow")
NOW = datetime(2026, 9, 29, 15, 0, tzinfo=TZ)  # вторник
parser = RuleBasedParser()


def parse(text: str) -> Patch:
    return parser.parse_sync(text, NOW)


def test_understands_a_full_sentence():
    patch = parse("Хочу что-нибудь спокойное и недорого сегодня вечером с друзьями")
    assert patch.when == "today"
    assert patch.time_of_day == TimeOfDay.EVENING
    assert patch.tags == ["calm"]
    assert patch.budget_max == 700
    assert patch.companions == Companions.FRIENDS


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("завтра", "tomorrow"),
        ("послезавтра", "day_after"),
        ("на выходных", "weekend"),
        ("в пятницу", "fri"),
        ("в субботу вечером", "sat"),
        ("на этой неделе", "week"),
        ("12 октября", "2026-10-12"),
        ("13.10", "2026-10-13"),
    ],
)
def test_dates(text, expected):
    assert parse(text).when == expected


@pytest.mark.parametrize(
    ("text", "budget"),
    [("до 500", 500), ("не дороже 1 500 рублей", 1500), ("бюджет 2 тыс", 2000), ("300 руб", 300)],
)
def test_budget(text, budget):
    assert parse(text).budget_max == budget


@pytest.mark.parametrize("text", ["до 12 октября", "до 19:00", "до 5 человек"])
def test_dates_times_and_counts_are_not_budgets(text):
    assert parse(text).budget_max is None


def test_free_and_pushkin_card():
    patch = parse("бесплатные концерты по пушкинской карте")
    assert patch.free_only and patch.pushkin_card
    assert patch.categories == ["concert"]
    assert patch.budget_max is None


def test_yo_is_normalized():
    assert parse("Сходим с ребёнком?").companions == Companions.KIDS


def test_refinements():
    assert parse("давай подешевле").cheaper
    assert parse("а есть что-то другое?").more
    assert parse("начнём сначала").reset
    assert parse("удиви меня").surprise


def test_cheaper_is_not_treated_as_a_cheap_budget():
    assert parse("дешевле").budget_max is None


def test_unrelated_text_gives_an_empty_patch():
    assert parse("привет, как дела").is_empty()


def test_weekday_word_is_not_confused_with_prefixes():
    assert parse("среди друзей").when is None


def test_resolve_when_windows():
    start, end = resolve_when("weekend", NOW, TZ)
    assert (start.weekday(), end.weekday()) == (5, 6)  # сб — вс
    start, end = resolve_when("today", NOW, TZ)
    assert start == NOW and end.date() == NOW.date()
    start, _ = resolve_when("tue", NOW, TZ)  # сегодня вторник — это сегодня
    assert start.date() == NOW.date()
    assert resolve_when("nonsense", NOW, TZ) is None


def test_week_is_seven_days_including_today():
    start, end = resolve_when("week", NOW, TZ)
    assert start == NOW
    assert end.date() == datetime(2026, 10, 5).date()  # вт + 6 дней, а не следующий вторник


def test_week_summary_does_not_read_as_today_only():
    criteria = apply_patch(Criteria(), Patch(when="week"), NOW, TZ)
    assert describe_criteria(criteria, TZ, NOW, {}) == "с сегодняшнего дня по пн, 5 окт"


def test_sunday_weekend_is_only_today():
    sunday = datetime(2026, 10, 4, 12, 0, tzinfo=TZ)
    start, end = resolve_when("weekend", sunday, TZ)
    assert start == sunday and end.date() == sunday.date()


def test_apply_patch_replaces_topic_and_accumulates_tags():
    criteria = apply_patch(Criteria(), Patch(categories=["concert"], tags=["calm"]), NOW, TZ)
    criteria = apply_patch(criteria, Patch(categories=["theatre"], tags=["romantic"]), NOW, TZ)
    assert criteria.categories == ["theatre"]
    assert criteria.tags == ["calm", "romantic"]


def test_free_and_budget_are_mutually_exclusive():
    criteria = apply_patch(Criteria(), Patch(free_only=True), NOW, TZ)
    assert criteria.free_only and criteria.budget_max is None
    criteria = apply_patch(criteria, Patch(budget_max=500), NOW, TZ)
    assert not criteria.free_only and criteria.budget_max == 500


def test_llm_output_is_sanitized():
    patch = sanitize_llm_patch(
        {
            "when": "tomorrow",
            "categories": ["concert", "drop table"],
            "tags": ["calm", "evil"],
            "budget_max": "много",
            "companions": "aliens",
            "time_of_day": "evening",
            "unknown_field": 1,
        }
    )
    assert patch.categories == ["concert"]
    assert patch.tags == ["calm"]
    assert patch.budget_max is None
    assert patch.companions is None
    assert patch.time_of_day == TimeOfDay.EVENING


def test_filled_from_keeps_own_values_and_fills_gaps():
    rules = Patch(more=True, tags=["calm"], when="tomorrow")
    llm = Patch(tags=["romantic"], when="weekend", categories=["concert"], budget_max=500)
    merged = rules.filled_from(llm)
    assert merged.more and merged.when == "tomorrow"  # своё не затирается
    assert merged.tags == ["calm", "romantic"]  # теги объединяются
    assert merged.categories == ["concert"] and merged.budget_max == 500  # пробелы заполнены


# --- LLMParser: запросы к OpenAI-совместимому серверу (например, Ollama) --------------------


def _llm_parser(handler):
    import httpx

    from app.assistant.parser import LLMParser

    return LLMParser(
        base_url="http://ollama:11434/v1",
        api_key="",
        model="qwen2.5:3b",
        timeout=5,
        fallback=RuleBasedParser(),
        http=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def _chat_reply(content: str):
    import httpx

    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


async def test_llm_understands_what_rules_cannot():
    import json

    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return _chat_reply('{"categories": ["exhibition"], "tags": ["calm"], "when": "weekend"}')

    patch = await _llm_parser(handler).parse("хочу отвлечься после сессии", NOW)

    assert seen["url"] == "http://ollama:11434/v1/chat/completions"
    assert seen["body"]["model"] == "qwen2.5:3b"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert seen["body"]["messages"][1] == {"role": "user", "content": "хочу отвлечься после сессии"}
    # «weekend» модель дописала сама, в реплике даты нет — она отбрасывается
    assert (patch.categories, patch.tags, patch.when) == (["exhibition"], ["calm"], None)


async def test_llm_without_json_mode_is_retried_once_and_remembered():
    # реальный случай: YandexGPT отвечает 400 на response_format
    import httpx

    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append("response_format" in body)
        if "response_format" in body:
            return httpx.Response(400, json={"error": {"message": "unsupported"}})
        return _chat_reply('```json\n{"categories": ["exhibition"]}\n```')

    parser = _llm_parser(handler)
    assert (await parser.parse("хочу отвлечься", NOW)).categories == ["exhibition"]
    assert (await parser.parse("хочу отвлечься", NOW)).categories == ["exhibition"]
    assert calls == [True, False, False]  # второй раз строгий JSON уже не просим


async def test_llm_result_is_merged_with_rules():
    # правила надёжно ловят «дешевле», модель — тему; итог содержит и то и другое
    parser = _llm_parser(lambda request: _chat_reply('{"categories": ["concert"]}'))
    patch = await parser.parse("давай подешевле", NOW)
    assert patch.cheaper and patch.categories == ["concert"]


async def test_llm_failures_fall_back_to_rules():
    import httpx

    broken = {
        "server error": lambda request: httpx.Response(500, text="boom"),
        "not json": lambda request: _chat_reply("Конечно! Вот ваши события..."),
        "wrong shape": lambda request: httpx.Response(200, json={"unexpected": True}),
    }
    for name, handler in broken.items():
        patch = await _llm_parser(handler).parse("концерты завтра", NOW)
        assert patch.categories == ["concert"] and patch.when == "tomorrow", name


async def test_llm_cannot_inject_unknown_values():
    parser = _llm_parser(
        lambda request: _chat_reply('{"categories": ["hack"], "tags": ["evil"], "budget_max": -5}')
    )
    patch = await parser.parse("что-нибудь", NOW)
    assert patch.categories == [] and patch.tags == [] and patch.budget_max is None


async def test_llm_cannot_invent_date_budget_or_time_of_day():
    # реальный случай: на «устала от сессии» модель дописала «сегодня» и «до 5000 ₽»
    invented = (
        '{"categories": ["city"], "tags": ["calm", "unusual"], "when": "today",'
        ' "budget_max": 5000, "time_of_day": "evening"}'
    )
    patch = await _llm_parser(lambda request: _chat_reply(invented)).parse("устала от сессии", NOW)
    assert (patch.when, patch.budget_max, patch.time_of_day) == (None, None, None)
    assert patch.tags == ["calm", "unusual"]  # а понимание настроения сохраняется


async def test_llm_date_budget_and_time_are_kept_when_the_user_said_them():
    stated = '{"when": "tue", "budget_max": 2000, "time_of_day": "evening"}'
    parser = _llm_parser(lambda request: _chat_reply(stated))
    patch = await parser.parse("что-нибудь в следующий вторник вечером до двух тысяч", NOW)
    assert (patch.when, patch.budget_max, patch.time_of_day) == ("tue", 2000, "evening")


async def test_llm_cannot_reset_the_dialog_or_set_control_flags():
    # реальный случай: модель поняла настроение, но заодно выставила «начать заново» и другие флаги,
    # из-за чего бот каждый раз снова здоровался
    noisy = (
        '{"tags": ["calm"], "reset": true, "more": true, "cheaper": true,'
        ' "surprise": true, "free_only": true, "pushkin_card": true, "companions": "friends"}'
    )
    patch = await _llm_parser(lambda request: _chat_reply(noisy)).parse(
        "у меня только закончилась сессия", NOW
    )
    assert patch.tags == ["calm"]  # понимание настроения сохраняется
    assert not (patch.reset or patch.more or patch.cheaper or patch.surprise)
    assert not (patch.free_only or patch.pushkin_card)
    assert patch.companions is None  # о компании в реплике ничего нет


async def test_control_flags_still_work_through_the_rules():
    parser = _llm_parser(lambda request: _chat_reply('{"reset": false}'))
    assert (await parser.parse("давай сначала", NOW)).reset
    assert (await parser.parse("бесплатно", NOW)).free_only
    assert (await parser.parse("с друзьями", NOW)).companions == "friends"


async def test_llm_cannot_override_a_date_the_rules_understood():
    # реальный случай: пользователь написал «30 сентября», модель ответила другой датой (5 октября)
    wrong = '{"when": "2026-10-05"}'
    patch = await _llm_parser(lambda request: _chat_reply(wrong)).parse("30 сентября", NOW)
    assert patch.when == "2026-09-30"


async def test_llm_cannot_override_budget_or_free_from_the_rules():
    wrong = '{"budget_max": 5000}'
    patch = await _llm_parser(lambda request: _chat_reply(wrong)).parse("до 300 рублей", NOW)
    assert patch.budget_max == 300
