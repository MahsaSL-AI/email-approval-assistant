from datetime import datetime, timezone
from uuid import UUID

from app.domain.reply_views import ReplyView
from app.services.telegram_actions import TelegramActionService
from app.services.telegram_update_processor import TelegramUpdateProcessor

EMAIL_ID = UUID("11111111-1111-4111-8111-111111111111")
OPERATOR_ID = 123456


def view(status: str, text: str = "Draft") -> ReplyView:
    now = datetime(2026, 8, 1, tzinfo=timezone.utc)
    return ReplyView(
        email_id=EMAIL_ID,
        text=text,
        status=status,
        approved_at=None,
        rejected_at=None,
        sent_at=now if status == "sent" else None,
    )


class FakeDecisions:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def edit(self, email_id: UUID, text: str) -> ReplyView:
        self.calls.append(("edit", email_id, text))
        return view("editing", text)

    def approve(self, email_id: UUID) -> ReplyView:
        self.calls.append(("approve", email_id))
        return view("approved")

    def reject(self, email_id: UUID) -> ReplyView:
        self.calls.append(("reject", email_id))
        return view("rejected")


class FakeSessions:
    def begin(self, email_id: UUID) -> ReplyView:
        return view("editing")


class FakeDelivery:
    def send(self, email_id: UUID) -> ReplyView:
        return view("sent")


class FakeTracker:
    def __init__(self) -> None:
        self.email_id: UUID | None = None

    def start(self, *, operator_id: int, email_id: UUID) -> None:
        self.email_id = email_id

    def current_email_id(self, *, operator_id: int) -> UUID | None:
        return self.email_id

    def clear(self, *, operator_id: int) -> None:
        self.email_id = None


class FakeResponder:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    def answer_callback_query(self, **kwargs) -> None:
        return None

    def send_text(self, **kwargs) -> int:
        self.messages.append(kwargs)
        return 1

    def send_message(self, **kwargs) -> int:
        self.messages.append(kwargs)
        return 2


def callback(action: str) -> dict:
    return {
        "callback_query": {
            "id": "callback-1",
            "from": {"id": OPERATOR_ID},
            "message": {"chat": {"id": OPERATOR_ID}},
            "data": f"{action}:{EMAIL_ID}",
        }
    }


def text_update(text: str) -> dict:
    return {
        "update_id": 20,
        "message": {
            "from": {"id": OPERATOR_ID},
            "chat": {"id": OPERATOR_ID},
            "text": text,
        },
    }


def build_actions():
    decisions = FakeDecisions()
    tracker = FakeTracker()
    actions = TelegramActionService(
        operator_id=OPERATOR_ID,
        decisions=decisions,
        edit_sessions=FakeSessions(),
        delivery=FakeDelivery(),
        edit_tracker=tracker,
    )
    return actions, decisions, tracker


def test_edit_button_starts_plain_text_conversation() -> None:
    actions, decisions, tracker = build_actions()

    result = actions.handle_callback(callback("edit"))

    assert tracker.email_id == EMAIL_ID
    assert decisions.calls == []
    assert result.status == "editing"
    assert result.message == "متن پیشنهادی جدید را بنویسید و ارسال کنید."


def test_plain_text_revision_stays_editing_and_returns_buttons() -> None:
    actions, decisions, tracker = build_actions()
    actions.handle_callback(callback("edit"))

    result = actions.handle_text_message(text_update("  پاسخ نهایی پیشنهادی  "))

    assert decisions.calls == [("edit", EMAIL_ID, "پاسخ نهایی پیشنهادی")]
    assert tracker.email_id == EMAIL_ID
    assert result.status == "editing"
    buttons = result.reply_markup["inline_keyboard"][0]
    assert [button["callback_data"] for button in buttons] == [
        f"approve:{EMAIL_ID}",
        f"edit:{EMAIL_ID}",
    ]


def test_processor_sends_revised_text_with_inline_buttons() -> None:
    actions, _, _ = build_actions()
    actions.handle_callback(callback("edit"))
    responder = FakeResponder()
    processor = TelegramUpdateProcessor(
        operator_id=OPERATOR_ID,
        actions=actions,
        responder=responder,
    )

    outcome = processor.process(text_update("نسخه دوم پاسخ"))

    assert outcome.status == "editing"
    assert responder.messages[0]["reply_markup"]["inline_keyboard"]
    assert "نسخه دوم پاسخ" in responder.messages[0]["text"]


def test_approval_clears_edit_conversation() -> None:
    actions, _, tracker = build_actions()
    actions.handle_callback(callback("edit"))

    result = actions.handle_callback(callback("approve"))

    assert result.status == "sent"
    assert tracker.email_id is None
