from dataclasses import dataclass

from app.providers.telegram import TelegramProviderError
from app.services.telegram_actions import TelegramActionResult
from app.services.telegram_update_processor import TelegramUpdateProcessor

OPERATOR_ID = 123456


class FakeActions:
    def __init__(self) -> None:
        self.callback_result = TelegramActionResult(
            callback_query_id="callback-1",
            message="Reply rejected.",
            status="rejected",
        )
        self.edit_result = TelegramActionResult(
            callback_query_id=None,
            message="Revision saved.",
            status="editing",
        )

    def handle_callback(self, update: dict) -> TelegramActionResult:
        return self.callback_result

    def handle_edit_command(self, update: dict) -> TelegramActionResult:
        return self.edit_result


@dataclass
class FakeResponder:
    fail: bool = False

    def __post_init__(self) -> None:
        self.callback_answers = []
        self.messages = []

    def answer_callback_query(self, **kwargs) -> None:
        if self.fail:
            raise TelegramProviderError("synthetic failure")
        self.callback_answers.append(kwargs)

    def send_text(self, **kwargs) -> int:
        if self.fail:
            raise TelegramProviderError("synthetic failure")
        self.messages.append(kwargs)
        return 1


def processor(responder: FakeResponder | None = None):
    return TelegramUpdateProcessor(
        operator_id=OPERATOR_ID,
        actions=FakeActions(),  # type: ignore[arg-type]
        responder=responder or FakeResponder(),  # type: ignore[arg-type]
    )


def test_callback_action_is_acknowledged_and_reported() -> None:
    responder = FakeResponder()
    service = processor(responder)
    update = {"update_id": 10, "callback_query": {"id": "callback-1"}}

    result = service.process(update)

    assert result.handled is True
    assert result.status == "rejected"
    assert responder.callback_answers[0]["callback_query_id"] == "callback-1"
    assert responder.messages[0] == {
        "chat_id": OPERATOR_ID,
        "text": "Reply rejected.",
    }


def test_edit_command_result_is_sent_to_operator() -> None:
    responder = FakeResponder()
    service = processor(responder)
    update = {
        "update_id": 11,
        "message": {"text": "/edit email-id revised text"},
    }

    result = service.process(update)

    assert result.status == "editing"
    assert responder.messages[0]["text"] == "Revision saved."


def test_authorized_start_confirms_bot_is_ready() -> None:
    responder = FakeResponder()
    service = processor(responder)
    update = {
        "update_id": 12,
        "message": {
            "text": "/start",
            "from": {"id": OPERATOR_ID},
            "chat": {"id": OPERATOR_ID},
        },
    }

    result = service.process(update)

    assert result.status == "ready"
    assert "connected" in responder.messages[0]["text"]


def test_unknown_message_is_ignored() -> None:
    result = processor().process({"update_id": 13, "message": {"text": "hello"}})

    assert result.handled is False
    assert result.status == "ignored"


def test_acknowledgement_failure_does_not_replay_business_action() -> None:
    result = processor(FakeResponder(fail=True)).process(
        {"update_id": 14, "callback_query": {"id": "callback-1"}}
    )

    assert result.handled is True
    assert result.status == "rejected"
