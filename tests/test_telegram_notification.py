from datetime import datetime, timezone
from uuid import UUID

from app.domain.telegram_notification import TelegramEmailNotification
from app.services.telegram_notification import TelegramNotificationService

EMAIL_ID = UUID("11111111-1111-4111-8111-111111111111")


class RecordingTelegramProvider:
    def __init__(self) -> None:
        self.call = None

    def send_message(self, *, chat_id: int, text: str, reply_markup: dict) -> int:
        self.call = {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": reply_markup,
        }
        return 42


def notification() -> TelegramEmailNotification:
    return TelegramEmailNotification(
        email_id=EMAIL_ID,
        sender="customer@example.test",
        subject="Order status",
        received_at=datetime(2026, 8, 1, 9, 30, tzinfo=timezone.utc),
        summary="Customer asks for an order update.",
        category="logistics",
        priority="high",
        suggested_reply="We are checking your order.",
    )


def test_notification_contains_operator_context_and_actions() -> None:
    provider = RecordingTelegramProvider()
    service = TelegramNotificationService(
        provider,  # type: ignore[arg-type]
        operator_id=123456,
    )

    message_id = service.notify(notification())

    assert message_id == 42
    assert provider.call["chat_id"] == 123456
    assert "Subject: Order status" in provider.call["text"]
    assert "Received: 2026-08-01T09:30:00+00:00" in provider.call["text"]
    assert "Customer asks for an order update." in provider.call["text"]
    assert "We are checking your order." in provider.call["text"]
    keyboard = provider.call["reply_markup"]["inline_keyboard"]
    callback_data = [button["callback_data"] for row in keyboard for button in row]
    assert callback_data == [
        f"approve:{EMAIL_ID}",
        f"reject:{EMAIL_ID}",
        f"edit:{EMAIL_ID}",
    ]


def test_missing_subject_has_safe_label() -> None:
    provider = RecordingTelegramProvider()
    service = TelegramNotificationService(
        provider,  # type: ignore[arg-type]
        operator_id=123456,
    )
    item = notification()
    without_subject = TelegramEmailNotification(
        email_id=item.email_id,
        sender=item.sender,
        subject=None,
        received_at=item.received_at,
        summary=item.summary,
        category=item.category,
        priority=item.priority,
        suggested_reply=item.suggested_reply,
    )

    service.notify(without_subject)

    assert "Subject: (no subject)" in provider.call["text"]
