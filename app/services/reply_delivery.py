from datetime import datetime, timezone
from email.utils import make_msgid
from uuid import UUID

from app.domain.outbound_email import OutboundEmail
from app.domain.reply_state import (
    ReplyStatus,
    ensure_reply_can_be_sent,
    transition_reply,
)
from app.domain.reply_views import ReplyView
from app.models.email import ProcessingLog, ProcessingLogLevel, SuggestedReply
from app.providers.smtp import OutboundEmailProvider
from app.repositories.reply_workflow import ReplyWorkflowRepository
from app.services.reply_workflow import ReplyNotFoundError


class ReplyDeliveryFailed(RuntimeError):
    """Raised after a delivery attempt has been recorded as failed."""


class ReplyDeliveryAmbiguousError(RuntimeError):
    """Raised when a prior attempt may already have reached the recipient."""


class ReplySenderAccountMismatch(RuntimeError):
    """Raised when a stored email belongs to a different monitored inbox."""


class ReplyDeliveryService:
    def __init__(
        self,
        repository: ReplyWorkflowRepository,
        provider: OutboundEmailProvider,
        sender_address: str,
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._sender_address = sender_address

    def send(self, email_id: UUID) -> ReplyView:
        email = self._repository.get_email(email_id)
        if email is None or email.suggested_reply is None:
            raise ReplyNotFoundError(f"Reply for email {email_id} was not found.")

        if (
            email.recipient.strip().casefold()
            != self._sender_address.strip().casefold()
        ):
            raise ReplySenderAccountMismatch(
                "This email belongs to a different monitored account."
            )

        reply = email.suggested_reply
        ensure_reply_can_be_sent(reply.status)
        if reply.smtp_message_id is not None:
            raise ReplyDeliveryAmbiguousError(
                "A previous SMTP attempt requires manual reconciliation."
            )

        message_id = self._make_message_id(reply.id)
        reply.smtp_message_id = message_id
        email.processing_logs.append(
            self._log("reply_send_started", "SMTP delivery attempt reserved.")
        )
        self._repository.commit()

        outbound = OutboundEmail(
            sender=self._sender_address,
            recipient=email.sender,
            subject=self._reply_subject(email.subject),
            body_text=reply.text,
            message_id=message_id,
            in_reply_to=email.external_message_id,
        )
        try:
            self._provider.send(outbound)
        except Exception as error:
            reply.status = transition_reply(reply.status, ReplyStatus.FAILED)
            reply.failure_reason = "SMTP delivery did not complete."
            email.processing_logs.append(
                self._log(
                    "reply_send_failed",
                    f"SMTP delivery failed with {type(error).__name__}.",
                    ProcessingLogLevel.ERROR,
                )
            )
            self._repository.commit()
            raise ReplyDeliveryFailed(
                "Reply delivery did not complete; retry is disabled for safety."
            ) from error

        reply.status = transition_reply(reply.status, ReplyStatus.SENT)
        reply.sent_at = datetime.now(timezone.utc)
        reply.failure_reason = None
        email.processing_logs.append(
            self._log("reply_sent", "SMTP accepted the approved reply.")
        )
        self._repository.commit()
        return self._view(reply)

    def _make_message_id(self, reply_id: UUID) -> str:
        domain = self._sender_address.rpartition("@")[2] or "localhost"
        return make_msgid(idstring=str(reply_id), domain=domain)

    @staticmethod
    def _reply_subject(subject: str | None) -> str:
        normalized = (subject or "No subject").strip()
        if normalized.lower().startswith("re:"):
            return normalized
        return f"Re: {normalized}"

    @staticmethod
    def _view(reply: SuggestedReply) -> ReplyView:
        return ReplyView(
            email_id=reply.email_id,
            text=reply.text,
            status=reply.status.value,
            approved_at=reply.approved_at,
            rejected_at=reply.rejected_at,
            sent_at=reply.sent_at,
        )

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
