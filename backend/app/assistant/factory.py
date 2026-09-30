from functools import lru_cache

from app.assistant.parser import LLMParser, Parser, RuleBasedParser
from app.core.config import get_settings


@lru_cache
def get_parser() -> Parser:
    """Парсер реплик: LLM, если он настроен, иначе только правила."""
    settings = get_settings()
    rules = RuleBasedParser()
    if not settings.llm_enabled:
        return rules
    return LLMParser(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=settings.llm_timeout_seconds,
        fallback=rules,
    )
