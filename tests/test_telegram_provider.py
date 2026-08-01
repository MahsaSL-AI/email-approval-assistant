import httpx
import pytest

from app.providers.telegram import TelegramBotApiProvider, TelegramProviderError


def test_bot_api_sends_inline_keyboard_and_returns_message_id() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            200,
            json={"ok": True, "result": {"message_id": 77}},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TelegramBotApiProvider(
        bot_token="synthetic-token",
        client=client,
    )

    message_id = provider.send_message(
        chat_id=123456,
        text="Review this email",
        reply_markup={"inline_keyboard": []},
    )

    assert message_id == 77
    assert captured["request"].url.path.endswith("/sendMessage")
    assert b'"chat_id":123456' in captured["request"].content
    assert b'"inline_keyboard":[]' in captured["request"].content


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(401, json={"ok": False}),
        httpx.Response(200, json={"ok": False}),
        httpx.Response(200, json={"ok": True, "result": {}}),
    ],
)
def test_bot_api_returns_safe_error(response: httpx.Response) -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda request: response))
    provider = TelegramBotApiProvider(
        bot_token="synthetic-token",
        client=client,
    )

    with pytest.raises(TelegramProviderError) as error_info:
        provider.send_message(
            chat_id=123456,
            text="Review",
            reply_markup={"inline_keyboard": []},
        )

    assert "synthetic-token" not in str(error_info.value)
