import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    APP_ENV: str = "development"
    DEFAULT_LLM_PROVIDER: str = "gigachat"

    # GigaChat
    GIGACHAT_CREDENTIALS: str = ""
    GIGACHAT_SCOPE: str = "GIGACHAT_API_PERS"
    GIGACHAT_MODEL: str = "GigaChat"

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b-instruct-q8_0"

    # Database
    DATABASE_URL: str = "sqlite:///./data/socratic_prod.db"

    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def get_db_url(self) -> str:
        """Возвращает одноразовую БД при тестах (Pisa, 2026)"""
        if self.APP_ENV == "test":
            return "sqlite:///./data/test_throwaway.db"
        return self.DATABASE_URL


settings = Settings()


def assert_test_environment():
    """Защитная проверка: тесты и симуляции не должны задевать Prod БД"""
    if settings.APP_ENV == "test":
        assert "throwaway" in settings.get_db_url() or "test" in settings.get_db_url(), \
            "CRITICAL: Tests must NEVER touch Production Database!"