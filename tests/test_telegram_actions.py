from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.domain.reply_views import ReplyView
from app.services.telegram_actions import (
    InvalidTelegramAction,
    TelegramActionService,
    UnauthorizedTelegramOperator,
)

EMAIL_ID = UUID("11111111-1111-4111-8111-111111111111")
OPERATOR_ID = 123456


class FakeDecisions:
    def __init__(self) -> None:
        self.calls = []

    def edit(self, email_id: UUID, text: str) -> ReplyView:
        self.calls.append(("edit", email_id, text))
        return view("editing", text)

    def approve(self, email_id: UUID) -> ReplyView:
        self.calls.append(("approve", email_id))
        return view("approved")

    def reject(self, email_id: UUID) -> ReplyView:
        self.calls.append(("reject", email_id))
        return view("rejected")


class FakeEditSessions:
    def __init__(self) -> None:
        self.calls = []

    def begin(self, email_id: UUID) -> ReplyView:
        self.calls.append(email_id)
        return view("editing")


class FakeDelivery:
    def __init__(self) -> None:
        self.calls = []

    def send(self, email_id: UUID) -> ReplyView:
        self.calls.append(email_id)
        return view("sent")


def view(status: str, text: str = "Draft") -> ReplyView:
    now = datetime(2026, 8, 1, tzinfo=timezone.utc)
    return ReplyView(
        email_id=EMAIL_ID,
        text=text,
        status=status,
        approved_at=now if status in {"approved", "sent"} else None,
        rejected_at=now if status == "rejected" else None,
        sent_at=now if status == "sent" else None,
    )


def service():
    decisions = FakeDecisions()
    sessions = FakeEditSessions()
    delivery = FakeDelivery()
    return (
        TelegramActionService(
            operator_id=OPERATOR_ID,
            decisions=decisions,
            edit_sessions=sessions,
            delivery=delivery,
        ),
        decisions,
        sessions,
        delivery,
    )


def callback(action: str, *, operator_id: int = OPERATOR_ID) -> dict:
    return {
        "callback_query": {
            "id": "callback-1",
            "from": {"id": operator_id},
            "message": {"chat": {"id": operator_id}},
            "data": f"{action}:{EMAIL_ID}",
        }
    }


def test_approve_callback_approves_then_sends() -> None:
    actions, decisions, _, delivery = service()

    result = actions.handle_callback(callback("approve"))

    assert decisions.calls == [("approve", EMAIL_ID)]
    assert delivery.calls == [EMAIL_ID]
    assert result.status == "sent"


def test_reject_callback_does_not_send() -> None:
    actions, decisions, _, delivery = service()

    result = actions.handle_callback(callback("reject"))

    assert decisions.calls == [("reject", EMAIL_ID)]
    assert delivery.calls == []
    assert result.status == "rejected"


def test_edit_callback_enters_editing_without_approval() -> None:
    actions, decisions, sessions, delivery = service()

    result = actions.handle_callback(callback("edit"))

    assert sessions.calls == [EMAIL_ID]
    assert decisions.calls == []
    assert delivery.calls == []
    assert result.status == "editing"


def test_edit_command_saves_revision_but_stays_editing() -> None:
    actions, decisions, _, delivery = service()
    update = {
        "message": {
            "from": {"id": OPERATOR_ID},
            "chat": {"id": OPERATOR_ID},
            "text": f"/edit {EMAIL_ID} Final revised text",
        }
    }

    result = actions.handle_edit_command(update)

    assert decisions.calls == [("edit", EMAIL_ID, "Final revised text")]
    assert delivery.calls == []
    assert result.status == "editing"
    assert "explicitly approve" in result.message


def test_another_telegram_user_is_rejected() -> None:
    actions, decisions, _, delivery = service()

    with pytest.raises(UnauthorizedTelegramOperator):
        actions.handle_callback(callback("approve", operator_id=999999))

    assert decisions.calls == []
    assert delivery.calls == []


@pytest.mark.parametrize(
    "data",
    ["unknown:11111111-1111-4111-8111-111111111111", "approve:not-a-uuid"],
)
def test_invalid_callback_data_is_rejected(data: str) -> None:
    actions, _, _, _ = service()
    update = callback("approve")
    update["callback_query"]["data"] = data

    with pytest.raises(InvalidTelegramAction):
        actions.handle_callback(update)


def test_malformed_edit_command_is_rejected() -> None:
    actions, _, _, _ = service()
    update = {
        "message": {
            "from": {"id": OPERATOR_ID},
            "chat": {"id": OPERATOR_ID},
            "text": "/edit missing-parts",
        }
    }

    with pytest.raises(InvalidTelegramAction):
        actions.handle_edit_command(update)
