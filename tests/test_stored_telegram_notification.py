from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.domain.reply_state import ReplyStatus
from app.models.email import (
    EmailAnalysis,
    EmailCategory,
    EmailMessage,
    EmailPriority,
    EmailProcessingStatus,
    SuggestedReply,
)
from app.providers.telegram import TelegramProviderError
from app.services.stored_telegram_notification import (
    EmailNotificationFailed,
    StoredTelegramNotificationService,
)

EMAIL_ID = UUID("11111111-1111-4111-8111-111111111111")


def make_email(
    status: EmailProcessingStatus = EmailProcessingStatus.ANALYZED,
) -> EmailMessage:
    email = EmailMessage(
        id=EMAIL_ID,
        external_message_id="<notification@example.test>",
        sender="customer@example.test",
        recipient="business@example.test",
        subject="Order update",
        body_text="Where is my order?",
        received_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        status=status,
    )
    email.analysis = EmailAnalysis(
        email_id=EMAIL_ID,
        summary="Customer requests an order update.",
        category=EmailCategory.LOGISTICS,
        priority=EmailPriority.HIGH,
        language="en",
        sentiment="neutral",
        confidence=0.9,
    )
    email.suggested_reply = SuggestedReply(
        email_id=EMAIL_ID,
        text="We are checking the order.",
        status=ReplyStatus.PENDING,
    )
    return email


class FakeRepository:
    def __init__(self, email: EmailMessage | None) -> None:
        self.email = email
        self.commits = 0

    def get(self, email_id: UUID) -> EmailMessage | None:
        return self.email if email_id == EMAIL_ID else None

    def commit(self) -> None:
        self.commits += 1


class FakeNotifier:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.notifications = []

    def notify(self, notification) -> int:
        self.notifications.append(notification)
        if self.error:
            raise self.error
        return 77


def service(email: EmailMessage | None, notifier: FakeNotifier):
    repository = FakeRepository(email)
    return (
        StoredTelegramNotificationService(
            repository,  # type: ignore[arg-type]
            notifier,  # type: ignore[arg-type]
        ),
        repository,
    )


def test_analyzed_email_is_notified_and_marked_notified() -> None:
    email = make_email()
    notifier = FakeNotifier()
    notification, repository = service(email, notifier)

    created = notification.notify(EMAIL_ID)

    assert created is True
    assert email.status is EmailProcessingStatus.NOTIFIED
    assert repository.commits == 1
    assert notifier.notifications[0].summary == "Customer requests an order update."
    assert email.processing_logs[-1].event == "telegram_notified"


def test_already_notified_email_is_idempotent() -> None:
    notifier = FakeNotifier()
    notification, repository = service(
        make_email(EmailProcessingStatus.NOTIFIED),
        notifier,
    )

    created = notification.notify(EMAIL_ID)

    assert created is False
    assert notifier.notifications == []
    assert repository.commits == 0


def test_telegram_failure_keeps_email_analyzed_for_retry() -> None:
    email = make_email()
    notification, repository = service(
        email,
        FakeNotifier(TelegramProviderError("synthetic outage")),
    )

    with pytest.raises(EmailNotificationFailed, match="temporarily"):
        notification.notify(EMAIL_ID)

    assert email.status is EmailProcessingStatus.ANALYZED
    assert repository.commits == 1
    assert email.processing_logs[-1].event == "telegram_notification_failed"


def test_email_without_analysis_is_not_ready() -> None:
    email = make_email()
    email.analysis = None
    notification, repository = service(email, FakeNotifier())

    with pytest.raises(EmailNotificationFailed, match="not ready"):
        notification.notify(EMAIL_ID)

    assert repository.commits == 0
