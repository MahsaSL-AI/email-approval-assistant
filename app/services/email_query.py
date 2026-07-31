from uuid import UUID

from app.domain.email_views import EmailDetail, EmailListItem, EmailPage
from app.models.email import EmailMessage
from app.repositories.email_query import EmailQueryRepository


class EmailNotFoundError(LookupError):
    """Raised when a public email identifier does not exist."""


class EmailQueryService:
    def __init__(self, repository: EmailQueryRepository) -> None:
        self._repository = repository

    def list(self, *, page: int, page_size: int) -> EmailPage:
        records, total = self._repository.list(
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return EmailPage(
            items=[self._to_list_item(record) for record in records],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get(self, email_id: UUID) -> EmailDetail:
        record = self._repository.get(email_id)
        if record is None:
            raise EmailNotFoundError(f"Email {email_id} was not found.")
        analysis = record.analysis
        reply = record.suggested_reply
        return EmailDetail(
            id=record.id,
            external_message_id=record.external_message_id,
            sender=record.sender,
            recipient=record.recipient,
            subject=record.subject,
            body_text=record.body_text,
            received_at=record.received_at,
            processing_status=record.status.value,
            failure_reason=record.failure_reason,
            summary=analysis.summary if analysis else None,
            category=analysis.category.value if analysis else None,
            priority=analysis.priority.value if analysis else None,
            language=analysis.language if analysis else None,
            sentiment=analysis.sentiment if analysis else None,
            confidence=analysis.confidence if analysis else None,
            suggested_reply=reply.text if reply else None,
            reply_status=reply.status.value if reply else None,
            approved_at=reply.approved_at if reply else None,
            rejected_at=reply.rejected_at if reply else None,
            sent_at=reply.sent_at if reply else None,
        )

    @staticmethod
    def _to_list_item(record: EmailMessage) -> EmailListItem:
        analysis = record.analysis
        reply = record.suggested_reply
        return EmailListItem(
            id=record.id,
            sender=record.sender,
            subject=record.subject,
            received_at=record.received_at,
            processing_status=record.status.value,
            category=analysis.category.value if analysis else None,
            priority=analysis.priority.value if analysis else None,
            reply_status=reply.status.value if reply else None,
        )
