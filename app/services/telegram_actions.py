from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from app.domain.reply_views import ReplyView


class UnauthorizedTelegramOperator(PermissionError):
    """Raised when an update does not belong to the configured operator."""


class InvalidTelegramAction(ValueError):
    """Raised when callback data or an edit message is malformed."""


class NoActiveEditSession(InvalidTelegramAction):
    """Raised when ordinary text is received outside an editing conversation."""


class ReplyDecisions(Protocol):
    def edit(self, email_id: UUID, text: str) -> ReplyView: ...

    def approve(self, email_id: UUID) -> ReplyView: ...

    def reject(self, email_id: UUID) -> ReplyView: ...


class EditSessions(Protocol):
    def begin(self, email_id: UUID) -> ReplyView: ...


class TelegramEditTracker(Protocol):
    def start(self, *, operator_id: int, email_id: UUID) -> None: ...

    def current_email_id(self, *, operator_id: int) -> UUID | None: ...

    def clear(self, *, operator_id: int) -> None: ...


class ReplyDelivery(Protocol):
    def send(self, email_id: UUID) -> ReplyView: ...


class _NullTelegramEditTracker:
    """Keeps older callers compatible; production injects persistent storage."""

    def start(self, *, operator_id: int, email_id: UUID) -> None:
        return None

    def current_email_id(self, *, operator_id: int) -> UUID | None:
        return None

    def clear(self, *, operator_id: int) -> None:
        return None


@dataclass(frozen=True, slots=True)
class TelegramActionResult:
    callback_query_id: str | None
    message: str
    status: str
    reply_markup: dict[str, Any] | None = None


class TelegramActionService:
    def __init__(
        self,
        *,
        operator_id: int,
        decisions: ReplyDecisions,
        edit_sessions: EditSessions,
        delivery: ReplyDelivery,
        edit_tracker: TelegramEditTracker | None = None,
    ) -> None:
        self._operator_id = operator_id
        self._decisions = decisions
        self._edit_sessions = edit_sessions
        self._delivery = delivery
        self._edit_tracker = edit_tracker or _NullTelegramEditTracker()

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
            self._edit_tracker.clear(operator_id=self._operator_id)
            result = self._delivery.send(email_id)
            message = "پاسخ تأیید و ارسال شد."
        elif action == "reject":
            result = self._decisions.reject(email_id)
            self._edit_tracker.clear(operator_id=self._operator_id)
            message = "پاسخ رد شد."
        else:
            result = self._edit_sessions.begin(email_id)
            self._edit_tracker.start(
                operator_id=self._operator_id,
                email_id=email_id,
            )
            message = "متن پیشنهادی جدید را بنویسید و ارسال کنید."

        return TelegramActionResult(callback_id, message, result.status)

    def handle_text_message(self, update: dict) -> TelegramActionResult:
        message = update.get("message")
        if not isinstance(message, dict):
            raise InvalidTelegramAction("Telegram update has no message.")
        self._authorize(message.get("from"), message)

        text = message.get("text")
        if not isinstance(text, str) or not text.strip():
            raise InvalidTelegramAction("متن پاسخ نمی‌تواند خالی باشد.")
        email_id = self._edit_tracker.current_email_id(operator_id=self._operator_id)
        if email_id is None:
            raise NoActiveEditSession("No Telegram edit session is active.")

        revised_text = text.strip()
        result = self._decisions.edit(email_id, revised_text)
        return TelegramActionResult(
            callback_query_id=None,
            message=(
                "متن پیشنهادی جدید:\n\n"
                f"{revised_text}\n\n"
                "اگر مناسب است تأیید کنید؛ در غیر این صورت دوباره ویرایش کنید."
            ),
            status=result.status,
            reply_markup={
                "inline_keyboard": [
                    [
                        {
                            "text": "✅ تأیید و ارسال",
                            "callback_data": f"approve:{email_id}",
                        },
                        {
                            "text": "✏️ ویرایش دوباره",
                            "callback_data": f"edit:{email_id}",
                        },
                    ]
                ]
            },
        )

    def handle_edit_command(self, update: dict) -> TelegramActionResult:
        """Legacy command retained for compatibility with existing clients."""
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
