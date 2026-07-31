from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_name: str = "AI Email Approval Assistant"
    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str = (
        "postgresql+psycopg://email_assistant:email_assistant@"
        "localhost:15433/email_assistant"
    )

    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    imap_use_ssl: bool = True
    email_username: str | None = None
    email_app_password: SecretStr | None = None

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_use_tls: bool = True

    ai_provider: str = "fake"
    ai_api_key: SecretStr | None = None

    telegram_bot_token: SecretStr | None = None
    telegram_operator_id: int | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
