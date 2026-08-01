from typing import Any, Protocol

import httpx


class TelegramProviderError(RuntimeError):
    """Safe boundary error for Telegram Bot API failures."""


class TelegramProvider(Protocol):
    def send_message(
        self,
        *,
        chat_id: int,
        text: str,
        reply_markup: dict[str, Any],
    ) -> int: ...


class TelegramBotApiProvider:
    def __init__(
        self,
        *,
        bot_token: str,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = f"https://api.telegram.org/bot{bot_token}"
        self._timeout_seconds = timeout_seconds
        self._client = client

    def send_message(
        self,
        *,
        chat_id: int,
        text: str,
        reply_markup: dict[str, Any],
    ) -> int:
        try:
            if self._client is None:
                with httpx.Client(timeout=self._timeout_seconds) as client:
                    response = client.post(
                        f"{self._base_url}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": text,
                            "reply_markup": reply_markup,
                        },
                    )
            else:
                response = self._client.post(
                    f"{self._base_url}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "reply_markup": reply_markup,
                    },
                    timeout=self._timeout_seconds,
                )
            response.raise_for_status()
            payload = response.json()
            if payload.get("ok") is not True:
                raise ValueError("Telegram returned an unsuccessful response.")
            return int(payload["result"]["message_id"])
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise TelegramProviderError(
                "Telegram notification did not complete."
            ) from error
