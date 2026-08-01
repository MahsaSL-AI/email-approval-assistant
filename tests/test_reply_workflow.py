from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.domain.reply_state import InvalidReplyTransition, ReplyStatus
from app.models.email import EmailMessage, EmailProcessingStatus, SuggestedReply
from app.services.reply_workflow import ReplyNotFoundError, ReplyWorkflowService

EMAIL_ID = UUID("11111111-1111-4111-8111-111111111111")


def make_email(status: ReplyStatus = ReplyStatus.PENDING) -> EmailMessage:
    email = EmailMessage(
        id=EMAIL_ID,
        external_message_id="<reply-workflow@example.test>",
        sender="customer@example.test",
        recipient="business@example.test",
        subject="Request",
        body_text="Please help.",
        received_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        status=EmailProcessingStatus.ANALYZED,
    )
    email.suggested_reply = SuggestedReply(
        email_id=EMAIL_ID,
        text="Initial draft",
        status=status,
    )
    return email


class FakeReplyRepository:
    def __init__(self, email: EmailMessage | None) -> None:
        self.email = email
        self.commits = 0

    def get_email(self, email_id: UUID) -> EmailMessage | None:
        if email_id != EMAIL_ID:
            return None
        return self.email

    def commit(self) -> None:
        self.commits += 1


def test_reply_stays_editing_across_repeated_edits() -> None:
    email = make_email()
    repository = FakeReplyRepository(email)
    service = ReplyWorkflowService(repository)  # type: ignore[arg-type]

    first = service.edit(EMAIL_ID, " First revision ")
    second = service.edit(EMAIL_ID, "Second revision")

    assert first.status == "editing"
    assert second.status == "editing"
    assert second.text == "Second revision"
    assert repository.commits == 2
    assert [log.event for log in email.processing_logs] == [
        "reply_edited",
        "reply_edited",
    ]


def test_editing_reply_needs_explicit_approval() -> None:
    email = make_email(ReplyStatus.EDITING)
    repository = FakeReplyRepository(email)
    service = ReplyWorkflowService(repository)  # type: ignore[arg-type]

    result = service.approve(EMAIL_ID)

    assert result.status == "approved"
    assert result.approved_at is not None
    assert email.processing_logs[-1].event == "reply_approved"


def test_approved_reply_cannot_return_to_editing() -> None:
    repository = FakeReplyRepository(make_email(ReplyStatus.APPROVED))
    service = ReplyWorkflowService(repository)  # type: ignore[arg-type]

    with pytest.raises(InvalidReplyTransition):
        service.edit(EMAIL_ID, "Too late")

    assert repository.commits == 0


def test_operator_can_reject_an_editing_reply() -> None:
    repository = FakeReplyRepository(make_email(ReplyStatus.EDITING))
    service = ReplyWorkflowService(repository)  # type: ignore[arg-type]

    result = service.reject(EMAIL_ID)

    assert result.status == "rejected"
    assert result.rejected_at is not None


def test_missing_reply_is_reported() -> None:
    service = ReplyWorkflowService(FakeReplyRepository(None))  # type: ignore[arg-type]

    with pytest.raises(ReplyNotFoundError):
        service.approve(EMAIL_ID)
