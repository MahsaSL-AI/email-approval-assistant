import json

import httpx
import pytest

from app.providers.telegram import TelegramProviderError
from app.providers.telegram_updates import TelegramUpdateProvider


class RecordingTransport:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = responses
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responses.pop(0)


def test_get_updates_uses_offset_and_allowed_update_types() -> None:
    transport = RecordingTransport(
        [httpx.Response(200, json={"ok": True, "result": [{"update_id": 9}]})]
    )
    client = httpx.Client(transport=httpx.MockTransport(transport))
    provider = TelegramUpdateProvider(bot_token="synthetic-token", client=client)

    updates = provider.get_updates(offset=9, poll_timeout_seconds=0)

    payload = json.loads(transport.requests[0].content)
    assert updates == [{"update_id": 9}]
    assert payload["offset"] == 9
    assert payload["allowed_updates"] == ["message", "callback_query"]


def test_callback_is_answered_and_result_message_is_sent() -> None:
    transport = RecordingTransport(
        [
            httpx.Response(200, json={"ok": True, "result": True}),
            httpx.Response(
                200,
                json={"ok": True, "result": {"message_id": 44}},
            ),
        ]
    )
    client = httpx.Client(transport=httpx.MockTransport(transport))
    provider = TelegramUpdateProvider(bot_token="synthetic-token", client=client)

    provider.answer_callback_query(
        callback_query_id="callback-1",
        text="Done",
    )
    message_id = provider.send_text(chat_id=123456, text="Done")

    assert message_id == 44
    assert transport.requests[0].url.path.endswith("/answerCallbackQuery")
    assert transport.requests[1].url.path.endswith("/sendMessage")


def test_update_provider_error_never_exposes_token() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(401, json={"ok": False})
        )
    )
    provider = TelegramUpdateProvider(bot_token="synthetic-token", client=client)

    with pytest.raises(TelegramProviderError) as error_info:
        provider.get_updates(offset=None, poll_timeout_seconds=0)

    assert "synthetic-token" not in str(error_info.value)
