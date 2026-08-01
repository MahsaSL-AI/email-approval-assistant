from datetime import datetime, timezone
from uuid import UUID

from app.domain.telegram_notification import TelegramEmailNotification
from app.models.email import (
    EmailProcessingStatus,
    ProcessingLog,
    ProcessingLogLevel,
)
from app.providers.telegram import TelegramProviderError
from app.repositories.email_notification import EmailNotificationRepository
from app.services.telegram_notification import TelegramNotificationService


class EmailNotificationFailed(RuntimeError):
    """Raised when a stored analyzed email could not be sent to Telegram."""


class StoredTelegramNotificationService:
    def __init__(
        self,
        repository: EmailNotificationRepository,
        notifier: TelegramNotificationService,
    ) -> None:
        self._repository = repository
        self._notifier = notifier

    def notify(self, email_id: UUID) -> bool:
        email = self._repository.get(email_id)
        if email is None:
            raise EmailNotificationFailed("Stored email was not found.")
        if email.status is EmailProcessingStatus.NOTIFIED:
            return False
        if (
            email.status is not EmailProcessingStatus.ANALYZED
            or email.analysis is None
            or email.suggested_reply is None
        ):
            raise EmailNotificationFailed("Email is not ready for notification.")

        notification = TelegramEmailNotification(
            email_id=email.id,
            sender=email.sender,
            subject=email.subject,
            received_at=email.received_at,
            summary=email.analysis.summary,
            category=email.analysis.category.value,
            priority=email.analysis.priority.value,
            suggested_reply=email.suggested_reply.text,
        )
        try:
            telegram_message_id = self._notifier.notify(notification)
        except TelegramProviderError as error:
            email.processing_logs.append(
                self._log(
                    "telegram_notification_failed",
                    "Telegram notification did not complete.",
                    ProcessingLogLevel.ERROR,
                )
            )
            self._repository.commit()
            raise EmailNotificationFailed(
                "Telegram notification is temporarily unavailable."
            ) from error

        email.status = EmailProcessingStatus.NOTIFIED
        email.processing_logs.append(
            self._log(
                "telegram_notified",
                f"Telegram accepted notification message {telegram_message_id}.",
            )
        )
        self._repository.commit()
        return True

    @staticmethod
    def _log(
        event: str,
        message: str,
        level: ProcessingLogLevel = ProcessingLogLevel.INFO,
    ) -> ProcessingLog:
        return ProcessingLog(
            event=event,
            message=message,
            level=level,
            created_at=datetime.now(timezone.utc),
        )
