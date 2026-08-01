from typing import Any

import httpx

from app.providers.telegram import TelegramProviderError


class TelegramUpdateProvider:
    def __init__(
        self,
        *,
        bot_token: str,
        timeout_seconds: float = 35.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = f"https://api.telegram.org/bot{bot_token}"
        self._timeout_seconds = timeout_seconds
        self._client = client

    def get_updates(
        self,
        *,
        offset: int | None,
        poll_timeout_seconds: int = 25,
    ) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": poll_timeout_seconds,
            "allowed_updates": ["message", "callback_query"],
        }
        if offset is not None:
            payload["offset"] = offset
        result = self._request("getUpdates", payload)
        if not isinstance(result, list):
            raise TelegramProviderError("Telegram returned invalid updates.")
        return [item for item in result if isinstance(item, dict)]

    def answer_callback_query(
        self,
        *,
        callback_query_id: str,
        text: str,
        show_alert: bool = False,
    ) -> None:
        self._request(
            "answerCallbackQuery",
            {
                "callback_query_id": callback_query_id,
                "text": text[:200],
                "show_alert": show_alert,
            },
        )

    def send_text(self, *, chat_id: int, text: str) -> int:
        result = self._request(
            "sendMessage",
            {"chat_id": chat_id, "text": text},
        )
        if not isinstance(result, dict) or not isinstance(
            result.get("message_id"), int
        ):
            raise TelegramProviderError("Telegram returned an invalid message result.")
        return result["message_id"]

    def send_message(
        self,
        *,
        chat_id: int,
        text: str,
        reply_markup: dict[str, Any],
    ) -> int:
        result = self._request(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": reply_markup,
            },
        )
        if not isinstance(result, dict) or not isinstance(
            result.get("message_id"), int
        ):
            raise TelegramProviderError("Telegram returned an invalid message result.")
        return result["message_id"]

    def _request(self, method: str, payload: dict[str, Any]) -> Any:
        try:
            if self._client is None:
                with httpx.Client(timeout=self._timeout_seconds) as client:
                    response = client.post(
                        f"{self._base_url}/{method}",
                        json=payload,
                    )
            else:
                response = self._client.post(
                    f"{self._base_url}/{method}",
                    json=payload,
                    timeout=self._timeout_seconds,
                )
            response.raise_for_status()
            envelope = response.json()
            if envelope.get("ok") is not True:
                raise ValueError("Telegram returned an unsuccessful response.")
            return envelope.get("result")
        except (httpx.HTTPError, TypeError, ValueError) as error:
            raise TelegramProviderError(
                f"Telegram {method} request did not complete."
            ) from error
