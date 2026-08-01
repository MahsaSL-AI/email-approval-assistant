from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain.reply_views import ReplyView


class UnauthorizedTelegramOperator(PermissionError):
    """Raised when an update does not belong to the configured operator."""


class InvalidTelegramAction(ValueError):
    """Raised when callback data or an edit command is malformed."""


class ReplyDecisions(Protocol):
    def edit(self, email_id: UUID, text: str) -> ReplyView: ...

    def approve(self, email_id: UUID) -> ReplyView: ...

    def reject(self, email_id: UUID) -> ReplyView: ...


class EditSessions(Protocol):
    def begin(self, email_id: UUID) -> ReplyView: ...


class ReplyDelivery(Protocol):
    def send(self, email_id: UUID) -> ReplyView: ...


@dataclass(frozen=True, slots=True)
class TelegramActionResult:
    callback_query_id: str | None
    message: str
    status: str


class TelegramActionService:
    def __init__(
        self,
        *,
        operator_id: int,
        decisions: ReplyDecisions,
        edit_sessions: EditSessions,
        delivery: ReplyDelivery,
    ) -> None:
        self._operator_id = operator_id
        self._decisions = decisions
        self._edit_sessions = edit_sessions
        self._delivery = delivery

    def handle_callback(self, update: dict) -> TelegramActionResult:
        callback = update.get("callback_query")
        if not isinstance(callback, dict):
            raise InvalidTelegramAction("Telegram update has no callback query.")
        self._authorize(callback.get("from"), callback.get("message"))

        callback_id = callback.get("id")
        data = callback.get("data")
        if not isinstance(callback_id, str) or not isinstance(data, str):
            raise InvalidTelegramAction("Telegram callback is incomplete.")
        action, email_id = self._parse_callback_data(data)

        if action == "approve":
            self._decisions.approve(email_id)
            result = self._delivery.send(email_id)
            message = "Reply approved and sent."
        elif action == "reject":
            result = self._decisions.reject(email_id)
            message = "Reply rejected."
        else:
            result = self._edit_sessions.begin(email_id)
            message = f"Editing started. Send: /edit {email_id} your revised reply"

        return TelegramActionResult(callback_id, message, result.status)

    def handle_edit_command(self, update: dict) -> TelegramActionResult:
        message = update.get("message")
        if not isinstance(message, dict):
            raise InvalidTelegramAction("Telegram update has no message.")
        self._authorize(message.get("from"), message)

        text = message.get("text")
        if not isinstance(text, str):
            raise InvalidTelegramAction("Telegram edit command has no text.")
        email_id, revised_text = self._parse_edit_command(text)
        result = self._decisions.edit(email_id, revised_text)
        return TelegramActionResult(
            callback_query_id=None,
            message="Revision saved. Review it, then explicitly approve.",
            status=result.status,
        )

    def _authorize(self, sender: object, message: object) -> None:
        sender_id = sender.get("id") if isinstance(sender, dict) else None
        chat = message.get("chat") if isinstance(message, dict) else None
        chat_id = chat.get("id") if isinstance(chat, dict) else None
        if sender_id != self._operator_id or chat_id != self._operator_id:
            raise UnauthorizedTelegramOperator(
                "Telegram action is not authorized for this operator."
            )

    @staticmethod
    def _parse_callback_data(data: str) -> tuple[str, UUID]:
        action, separator, raw_email_id = data.partition(":")
        if separator != ":" or action not in {"approve", "reject", "edit"}:
            raise InvalidTelegramAction("Telegram callback action is invalid.")
        try:
            return action, UUID(raw_email_id)
        except ValueError as error:
            raise InvalidTelegramAction(
                "Telegram callback email ID is invalid."
            ) from error

    @staticmethod
    def _parse_edit_command(text: str) -> tuple[UUID, str]:
        command, separator, remainder = text.strip().partition(" ")
        raw_email_id, second_separator, revised_text = remainder.partition(" ")
        if command != "/edit" or separator != " " or second_separator != " ":
            raise InvalidTelegramAction("Use /edit <email-id> <revised reply>.")
        if not revised_text.strip():
            raise InvalidTelegramAction("Revised reply cannot be empty.")
        try:
            email_id = UUID(raw_email_id)
        except ValueError as error:
            raise InvalidTelegramAction("Edit command email ID is invalid.") from error
        return email_id, revised_text.strip()
