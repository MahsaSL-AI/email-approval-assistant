from pathlib import Path


class TelegramOffsetStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> int | None:
        if not self._path.exists():
            return None
        raw_value = self._path.read_text(encoding="utf-8").strip()
        if not raw_value:
            return None
        value = int(raw_value)
        if value < 0:
            raise ValueError("Telegram offset cannot be negative.")
        return value

    def save(self, offset: int) -> None:
        if offset < 0:
            raise ValueError("Telegram offset cannot be negative.")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(str(offset), encoding="utf-8")
        temporary.replace(self._path)
