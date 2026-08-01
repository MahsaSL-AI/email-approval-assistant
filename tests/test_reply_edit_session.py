from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.domain.reply_state import InvalidReplyTransition, ReplyStatus
from app.models.email import EmailMessage, EmailProcessingStatus, SuggestedReply
from app.services.reply_edit_session import ReplyEditSessionService

EMAIL_ID = UUID("11111111-1111-4111-8111-111111111111")


class FakeRepository:
    def __init__(self, email: EmailMessage) -> None:
        self.email = email
        self.commits = 0

    def get_email(self, email_id: UUID) -> EmailMessage | None:
        return self.email if email_id == EMAIL_ID else None

    def commit(self) -> None:
        self.commits += 1


def make_email(status: ReplyStatus) -> EmailMessage:
    email = EmailMessage(
        id=EMAIL_ID,
        external_message_id="<edit@example.test>",
        sender="customer@example.test",
        recipient="business@example.test",
        subject="Request",
        body_text="Body",
        received_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        status=EmailProcessingStatus.ANALYZED,
    )
    email.suggested_reply = SuggestedReply(
        email_id=EMAIL_ID,
        text="Draft",
        status=status,
    )
    return email


@pytest.mark.parametrize("initial", [ReplyStatus.PENDING, ReplyStatus.EDITING])
def test_begin_edit_is_idempotent_while_editing(initial: ReplyStatus) -> None:
    email = make_email(initial)
    repository = FakeRepository(email)
    service = ReplyEditSessionService(repository)  # type: ignore[arg-type]

    result = service.begin(EMAIL_ID)

    assert result.status == "editing"
    assert repository.commits == 1
    assert email.processing_logs[-1].event == "reply_editing_started"


def test_approved_reply_cannot_reenter_editing() -> None:
    repository = FakeRepository(make_email(ReplyStatus.APPROVED))
    service = ReplyEditSessionService(repository)  # type: ignore[arg-type]

    with pytest.raises(InvalidReplyTransition):
        service.begin(EMAIL_ID)

    assert repository.commits == 0
