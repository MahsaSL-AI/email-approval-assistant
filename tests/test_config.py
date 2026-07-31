from app.core.config import Settings


def test_empty_optional_environment_values_are_ignored(
    monkeypatch,
    tmp_path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "TELEGRAM_OPERATOR_ID=\nTELEGRAM_BOT_TOKEN=\nAI_API_KEY=\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("TELEGRAM_OPERATOR_ID", raising=False)

    settings = Settings(_env_file=env_file)

    assert settings.telegram_operator_id is None
    assert settings.telegram_bot_token is None
    assert settings.ai_api_key is None
