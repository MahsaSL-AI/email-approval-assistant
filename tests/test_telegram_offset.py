import pytest

from app.services.telegram_offset import TelegramOffsetStore


def test_missing_offset_starts_without_cursor(tmp_path) -> None:
    store = TelegramOffsetStore(tmp_path / "telegram-offset")

    assert store.load() is None


def test_offset_is_saved_atomically_and_reloaded(tmp_path) -> None:
    store = TelegramOffsetStore(tmp_path / "telegram-offset")

    store.save(42)

    assert store.load() == 42
    assert not (tmp_path / "telegram-offset.tmp").exists()


@pytest.mark.parametrize("value", [-1, -100])
def test_negative_offset_is_rejected(tmp_path, value: int) -> None:
    store = TelegramOffsetStore(tmp_path / "telegram-offset")

    with pytest.raises(ValueError):
        store.save(value)
