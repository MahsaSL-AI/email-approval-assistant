from datetime import datetime, timezone
from uuid import UUID

from app.domain.reply_state import ReplyStatus, transition_reply
from app.domain.reply_views import ReplyView
from app.models.email import ProcessingLog, ProcessingLogLevel, SuggestedReply
from app.repositories.reply_workflow import ReplyWorkflowRepository


class ReplyNotFoundError(LookupError):
    """Raised when an email or its generated reply does not exist."""


class EmptyReplyError(ValueError):
    """Raised when an operator tries to save an empty reply."""


class ReplyWorkflowService:
    def __init__(self, repository: ReplyWorkflowRepository) -> None:
        self._repository = repository

    def edit(self, email_id: UUID, text: str) -> ReplyView:
        email, reply = self._get_reply(email_id)
        normalized = text.strip()
        if not normalized:
            raise EmptyReplyError("Reply text cannot be empty.")

        if reply.status is ReplyStatus.PENDING:
            reply.status = transition_reply(reply.status, ReplyStatus.EDITING)
        elif reply.status is not ReplyStatus.EDITING:
            transition_reply(reply.status, ReplyStatus.EDITING)

        reply.text = normalized
        email.processing_logs.append(
            self._log("reply_edited", "Operator edited the reply draft.")
        )
        self._repository.commit()
        return self._view(reply)

    def approve(self, email_id: UUID) -> ReplyView:
        email, reply = self._get_reply(email_id)
        reply.status = transition_reply(reply.status, ReplyStatus.APPROVED)
        reply.approved_at = datetime.now(timezone.utc)
        email.processing_logs.append(
            self._log("reply_approved", "Operator approved the reply draft.")
        )
        self._repository.commit()
        return self._view(reply)

    def reject(self, email_id: UUID) -> ReplyView:
        email, reply = self._get_reply(email_id)
        reply.status = transition_reply(reply.status, ReplyStatus.REJECTED)
        reply.rejected_at = datetime.now(timezone.utc)
        email.processing_logs.append(
            self._log("reply_rejected", "Operator rejected the reply draft.")
        )
        self._repository.commit()
        return self._view(reply)

    def _get_reply(self, email_id: UUID):
        email = self._repository.get_email(email_id)
        if email is None or email.suggested_reply is None:
            raise ReplyNotFoundError(f"Reply for email {email_id} was not found.")
        return email, email.suggested_reply

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
    def _log(event: str, message: str) -> ProcessingLog:
        return ProcessingLog(
            event=event,
            message=message,
            level=ProcessingLogLevel.INFO,
            created_at=datetime.now(timezone.utc),
        )
