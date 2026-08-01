from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.domain.reply_state import InvalidReplyTransition, ReplyStatus
from app.models.email import EmailMessage, EmailProcessingStatus, SuggestedReply
from app.services.reply_delivery import (
    ReplyDeliveryAmbiguousError,
    ReplyDeliveryFailed,
    ReplyDeliveryService,
    ReplySenderAccountMismatch,
)

EMAIL_ID = UUID("11111111-1111-4111-8111-111111111111")
REPLY_ID = UUID("33333333-3333-4333-8333-333333333333")


def make_email(status: ReplyStatus = ReplyStatus.APPROVED) -> EmailMessage:
    email = EmailMessage(
        id=EMAIL_ID,
        external_message_id="<original@example.test>",
        sender="customer@example.test",
        recipient="business@example.test",
        subject="Request",
        body_text="Please help.",
        received_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        status=EmailProcessingStatus.ANALYZED,
    )
    email.suggested_reply = SuggestedReply(
        id=REPLY_ID,
        email_id=EMAIL_ID,
        text="Approved answer",
        status=status,
        approved_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    return email


class FakeRepository:
    def __init__(self, email: EmailMessage) -> None:
        self.email = email
        self.commits = 0

    def get_email(self, email_id: UUID) -> EmailMessage | None:
        return self.email if email_id == EMAIL_ID else None

    def commit(self) -> None:
        self.commits += 1


class RecordingProvider:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.outbound = None

    def send(self, outbound) -> None:
        self.outbound = outbound
        if self.error:
            raise self.error


def service(email: EmailMessage, provider: RecordingProvider):
    repository = FakeRepository(email)
    return (
        ReplyDeliveryService(
            repository,  # type: ignore[arg-type]
            provider,
            "business@example.test",
        ),
        repository,
    )


def test_only_approved_reply_is_sent() -> None:
    email = make_email(ReplyStatus.EDITING)
    delivery, repository = service(email, RecordingProvider())

    with pytest.raises(InvalidReplyTransition, match="approved"):
        delivery.send(EMAIL_ID)

    assert repository.commits == 0


def test_successful_delivery_becomes_sent_after_provider_acceptance() -> None:
    email = make_email()
    provider = RecordingProvider()
    delivery, repository = service(email, provider)

    result = delivery.send(EMAIL_ID)

    assert result.status == "sent"
    assert result.sent_at is not None
    assert repository.commits == 2
    assert provider.outbound.recipient == "customer@example.test"
    assert provider.outbound.subject == "Re: Request"
    assert provider.outbound.in_reply_to == "<original@example.test>"
    assert email.processing_logs[-1].event == "reply_sent"


def test_provider_failure_becomes_terminal_failed() -> None:
    email = make_email()
    delivery, repository = service(email, RecordingProvider(OSError("offline")))

    with pytest.raises(ReplyDeliveryFailed, match="retry is disabled"):
        delivery.send(EMAIL_ID)

    reply = email.suggested_reply
    assert reply.status is ReplyStatus.FAILED
    assert reply.failure_reason == "SMTP delivery did not complete."
    assert repository.commits == 2
    assert email.processing_logs[-1].event == "reply_send_failed"


def test_reserved_message_id_blocks_ambiguous_retry() -> None:
    email = make_email()
    email.suggested_reply.smtp_message_id = "<reserved@example.test>"
    delivery, repository = service(email, RecordingProvider())

    with pytest.raises(ReplyDeliveryAmbiguousError, match="reconciliation"):
        delivery.send(EMAIL_ID)

    assert repository.commits == 0


def test_email_from_another_monitored_account_is_never_sent() -> None:
    email = make_email()
    email.recipient = "old-inbox@example.test"
    provider = RecordingProvider()
    delivery, repository = service(email, provider)

    with pytest.raises(ReplySenderAccountMismatch, match="different monitored"):
        delivery.send(EMAIL_ID)

    assert provider.outbound is None
    assert repository.commits == 0
    assert email.suggested_reply.smtp_message_id is None


def test_existing_reply_prefix_is_not_duplicated() -> None:
    email = make_email()
    email.subject = "RE: Existing thread"
    provider = RecordingProvider()
    delivery, _ = service(email, provider)

    delivery.send(EMAIL_ID)

    assert provider.outbound.subject == "RE: Existing thread"
