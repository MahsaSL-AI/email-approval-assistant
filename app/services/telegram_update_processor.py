from dataclasses import dataclass
from typing import Protocol

from app.domain.reply_state import InvalidReplyTransition
from app.providers.telegram import TelegramProviderError
from app.services.reply_delivery import (
    ReplyDeliveryAmbiguousError,
    ReplyDeliveryFailed,
)
from app.services.reply_workflow import EmptyReplyError, ReplyNotFoundError
from app.services.telegram_actions import (
    InvalidTelegramAction,
    TelegramActionResult,
    TelegramActionService,
    UnauthorizedTelegramOperator,
)


class TelegramUpdateResponder(Protocol):
    def answer_callback_query(
        self,
        *,
        callback_query_id: str,
        text: str,
        show_alert: bool = False,
    ) -> None: ...

    def send_text(self, *, chat_id: int, text: str) -> int: ...


@dataclass(frozen=True, slots=True)
class TelegramUpdateOutcome:
    update_id: int
    handled: bool
    status: str


class TelegramUpdateProcessor:
    def __init__(
        self,
        *,
        operator_id: int,
        actions: TelegramActionService,
        responder: TelegramUpdateResponder,
    ) -> None:
        self._operator_id = operator_id
        self._actions = actions
        self._responder = responder

    def process(self, update: dict) -> TelegramUpdateOutcome:
        update_id = update.get("update_id")
        if not isinstance(update_id, int):
            raise InvalidTelegramAction("Telegram update ID is invalid.")

        try:
            if "callback_query" in update:
                result = self._actions.handle_callback(update)
                self._respond_to_callback(result)
                return TelegramUpdateOutcome(update_id, True, result.status)

            message = update.get("message")
            text = message.get("text") if isinstance(message, dict) else None
            if isinstance(text, str) and text.startswith("/edit "):
                result = self._actions.handle_edit_command(update)
                self._send_result(result)
                return TelegramUpdateOutcome(update_id, True, result.status)

            if text == "/start":
                self._authorize_start(message)
                self._best_effort_send("Email approval bot is connected and ready.")
                return TelegramUpdateOutcome(update_id, True, "ready")

            return TelegramUpdateOutcome(update_id, False, "ignored")
        except UnauthorizedTelegramOperator:
            self._best_effort_callback_error(update, "Unauthorized action.")
            return TelegramUpdateOutcome(update_id, False, "unauthorized")
        except (
            InvalidTelegramAction,
            InvalidReplyTransition,
            ReplyNotFoundError,
            EmptyReplyError,
            ReplyDeliveryAmbiguousError,
            ReplyDeliveryFailed,
        ) as error:
            safe_message = str(error) or "Action could not be completed."
            self._best_effort_callback_error(update, safe_message)
            if "message" in update:
                self._best_effort_send(safe_message)
            return TelegramUpdateOutcome(update_id, True, "failed")

    def _respond_to_callback(self, result: TelegramActionResult) -> None:
        if result.callback_query_id is None:
            return
        try:
            self._responder.answer_callback_query(
                callback_query_id=result.callback_query_id,
                text=result.message,
            )
            self._responder.send_text(
                chat_id=self._operator_id,
                text=result.message,
            )
        except TelegramProviderError:
            # The business action is already committed. Replaying it could send
            # a duplicate email, so acknowledgement is intentionally best effort.
            return

    def _send_result(self, result: TelegramActionResult) -> None:
        self._best_effort_send(result.message)

    def _authorize_start(self, message: object) -> None:
        if not isinstance(message, dict):
            raise UnauthorizedTelegramOperator
        sender = message.get("from")
        chat = message.get("chat")
        sender_id = sender.get("id") if isinstance(sender, dict) else None
        chat_id = chat.get("id") if isinstance(chat, dict) else None
        if sender_id != self._operator_id or chat_id != self._operator_id:
            raise UnauthorizedTelegramOperator

    def _best_effort_callback_error(self, update: dict, message: str) -> None:
        callback = update.get("callback_query")
        callback_id = callback.get("id") if isinstance(callback, dict) else None
        if not isinstance(callback_id, str):
            return
        try:
            self._responder.answer_callback_query(
                callback_query_id=callback_id,
                text=message,
                show_alert=True,
            )
        except TelegramProviderError:
            return

    def _best_effort_send(self, message: str) -> None:
        try:
            self._responder.send_text(chat_id=self._operator_id, text=message)
        except TelegramProviderError:
            return
