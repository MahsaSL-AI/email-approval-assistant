import pytest

from app.domain.reply_state import (
    InvalidReplyTransition,
    ReplyStatus,
    ensure_reply_can_be_sent,
    transition_reply,
)


def test_pending_reply_can_enter_editing_without_becoming_approved() -> None:
    result = transition_reply(ReplyStatus.PENDING, ReplyStatus.EDITING)

    assert result is ReplyStatus.EDITING


def test_edited_reply_requires_explicit_approval() -> None:
    result = transition_reply(ReplyStatus.EDITING, ReplyStatus.APPROVED)

    assert result is ReplyStatus.APPROVED


@pytest.mark.parametrize(
    "status",
    [
        ReplyStatus.PENDING,
        ReplyStatus.EDITING,
        ReplyStatus.REJECTED,
        ReplyStatus.SENT,
        ReplyStatus.FAILED,
    ],
)
def test_smtp_send_is_forbidden_without_approved_status(
    status: ReplyStatus,
) -> None:
    with pytest.raises(InvalidReplyTransition, match="SMTP send requires approved"):
        ensure_reply_can_be_sent(status)


def test_smtp_send_is_allowed_for_approved_reply() -> None:
    ensure_reply_can_be_sent(ReplyStatus.APPROVED)


def test_rejected_reply_is_terminal() -> None:
    with pytest.raises(InvalidReplyTransition):
        transition_reply(ReplyStatus.REJECTED, ReplyStatus.APPROVED)
