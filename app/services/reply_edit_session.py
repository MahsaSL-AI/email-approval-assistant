from datetime import datetime, timezone
from uuid import UUID

from app.domain.reply_state import ReplyStatus, transition_reply
from app.domain.reply_views import ReplyView
from app.models.email import ProcessingLog, ProcessingLogLevel, SuggestedReply
from app.repositories.reply_workflow import ReplyWorkflowRepository
from app.services.reply_workflow import ReplyNotFoundError


class ReplyEditSessionService:
    def __init__(self, repository: ReplyWorkflowRepository) -> None:
        self._repository = repository

    def begin(self, email_id: UUID) -> ReplyView:
        email = self._repository.get_email(email_id)
        if email is None or email.suggested_reply is None:
            raise ReplyNotFoundError(f"Reply for email {email_id} was not found.")

        reply = email.suggested_reply
        if reply.status is ReplyStatus.PENDING:
            reply.status = transition_reply(reply.status, ReplyStatus.EDITING)
        elif reply.status is not ReplyStatus.EDITING:
            transition_reply(reply.status, ReplyStatus.EDITING)

        email.processing_logs.append(
            ProcessingLog(
                event="reply_editing_started",
                message="Operator started editing the reply draft.",
                level=ProcessingLogLevel.INFO,
                created_at=datetime.now(timezone.utc),
            )
        )
        self._repository.commit()
        return self._view(reply)

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
