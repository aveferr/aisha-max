from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Все настройки приложения. Значения берутся из переменных окружения / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://afisha:afisha@localhost:5432/afisha"
    timezone: str = "Europe/Moscow"
    default_city: str = "Санкт-Петербург"
    seed_demo_data: bool = True

    # API
    cors_origins: str = "*"  # список через запятую
    # Заголовок X-Dev-User-Id вместо initData. Только для разработки, в проде держать выключенным.
    dev_auth_enabled: bool = False
    init_data_ttl_seconds: int = 24 * 60 * 60
    admin_token: str = ""  # пустой — админские эндпоинты отключены

    # MAX
    max_bot_token: str = ""
    max_bot_username: str = ""  # для deep-link'ов вида https://max.ru/<username>?start=...
    max_api_url: str = "https://platform-api2.max.ru"
    max_ca_bundle: str | None = None  # путь к PEM с корневым сертификатом (Минцифры), если нужен

    # LLM (любой OpenAI-совместимый сервер, например Ollama). Пустой URL — только правила.
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout_seconds: float = 15.0

    reminder_poll_interval_seconds: int = 30

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_base_url and self.llm_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()
