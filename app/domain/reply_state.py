from enum import Enum


class ReplyStatus(str, Enum):
    PENDING = "pending"
    EDITING = "editing"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
    FAILED = "failed"


class InvalidReplyTransition(ValueError):
    """Raised when a reply attempts a forbidden state transition."""


_ALLOWED_TRANSITIONS: dict[ReplyStatus, frozenset[ReplyStatus]] = {
    ReplyStatus.PENDING: frozenset(
        {ReplyStatus.EDITING, ReplyStatus.APPROVED, ReplyStatus.REJECTED}
    ),
    ReplyStatus.EDITING: frozenset({ReplyStatus.APPROVED, ReplyStatus.REJECTED}),
    ReplyStatus.APPROVED: frozenset({ReplyStatus.SENT, ReplyStatus.FAILED}),
    ReplyStatus.REJECTED: frozenset(),
    ReplyStatus.SENT: frozenset(),
    ReplyStatus.FAILED: frozenset(),
}


def transition_reply(
    current: ReplyStatus,
    target: ReplyStatus,
) -> ReplyStatus:
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise InvalidReplyTransition(
            f"Reply cannot transition from {current.value} to {target.value}."
        )
    return target


def ensure_reply_can_be_sent(status: ReplyStatus) -> None:
    if status is not ReplyStatus.APPROVED:
        raise InvalidReplyTransition(
            f"SMTP send requires approved status, not {status.value}."
        )
