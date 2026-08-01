from app.domain.telegram_notification import TelegramEmailNotification
from app.providers.telegram import TelegramProvider


class TelegramNotificationService:
    def __init__(self, provider: TelegramProvider, operator_id: int) -> None:
        self._provider = provider
        self._operator_id = operator_id

    def notify(self, notification: TelegramEmailNotification) -> int:
        return self._provider.send_message(
            chat_id=self._operator_id,
            text=self._format(notification),
            reply_markup=self._keyboard(notification),
        )

    @staticmethod
    def _format(notification: TelegramEmailNotification) -> str:
        subject = notification.subject or "(no subject)"
        received_at = notification.received_at.isoformat()
        return "\n".join(
            [
                "New email requires review",
                "",
                f"From: {notification.sender}",
                f"Subject: {subject}",
                f"Received: {received_at}",
                f"Category: {notification.category}",
                f"Priority: {notification.priority}",
                "",
                "Summary:",
                notification.summary,
                "",
                "Suggested reply:",
                notification.suggested_reply,
            ]
        )

    @staticmethod
    def _keyboard(notification: TelegramEmailNotification) -> dict:
        email_id = str(notification.email_id)
        return {
            "inline_keyboard": [
                [
                    {
                        "text": "Approve",
                        "callback_data": f"approve:{email_id}",
                    },
                    {
                        "text": "Reject",
                        "callback_data": f"reject:{email_id}",
                    },
                ],
                [
                    {
                        "text": "Edit",
                        "callback_data": f"edit:{email_id}",
                    }
                ],
            ]
        }
