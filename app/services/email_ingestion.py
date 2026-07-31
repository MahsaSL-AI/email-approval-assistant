from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.domain.email import InboundEmail, IngestionOutcome
from app.domain.reply_state import ReplyStatus
from app.models.email import (
    EmailAnalysis,
    EmailCategory,
    EmailMessage,
    EmailPriority,
    EmailProcessingStatus,
    ProcessingLog,
    ProcessingLogLevel,
    SuggestedReply,
)
from app.providers.email_analysis import EmailAnalyzer
from app.repositories.email import EmailRepository


class EmailAnalysisFailed(RuntimeError):
    """Safe application error for an unavailable or invalid AI analysis."""


class EmailIngestionService:
    def __init__(
        self,
        repository: EmailRepository,
        analyzer: EmailAnalyzer,
    ) -> None:
        self._repository = repository
        self._analyzer = analyzer

    def ingest(self, inbound: InboundEmail) -> IngestionOutcome:
        existing = self._repository.get_by_external_message_id(
            inbound.external_message_id
        )
        if existing is not None:
            return self._existing_outcome(existing)

        email = EmailMessage(
            external_message_id=inbound.external_message_id,
            sender=inbound.sender,
            recipient=inbound.recipient,
            subject=inbound.subject,
            body_text=inbound.body_text,
            received_at=inbound.received_at,
            status=EmailProcessingStatus.RECEIVED,
        )
        email.processing_logs.append(
            self._log("email_received", "Email stored before AI analysis.")
        )
        self._repository.add(email)

        try:
            self._repository.commit()
        except IntegrityError:
            self._repository.rollback()
            concurrent = self._repository.get_by_external_message_id(
                inbound.external_message_id
            )
            if concurrent is None:
                raise
            return self._existing_outcome(concurrent)

        try:
            result = self._analyzer.analyze(inbound)
            category = EmailCategory(result.category)
            priority = EmailPriority(result.priority)
        except Exception as error:
            email.status = EmailProcessingStatus.FAILED
            email.failure_reason = "AI analysis failed."
            email.processing_logs.append(
                self._log(
                    "analysis_failed",
                    f"AI analysis failed with {type(error).__name__}.",
                    ProcessingLogLevel.ERROR,
                )
            )
            self._repository.commit()
            raise EmailAnalysisFailed(
                "Email analysis is temporarily unavailable."
            ) from error

        email.analysis = EmailAnalysis(
            summary=result.summary,
            category=category,
            priority=priority,
            language=result.language,
            sentiment=result.sentiment,
            confidence=result.confidence,
        )
        email.suggested_reply = SuggestedReply(
            text=result.suggested_reply,
            status=ReplyStatus.PENDING,
        )
        email.status = EmailProcessingStatus.ANALYZED
        email.processing_logs.append(
            self._log("email_analyzed", "Email analysis and reply draft stored.")
        )
        self._repository.commit()

        return IngestionOutcome(
            email_id=email.id,
            created=True,
            status=email.status.value,
        )

    @staticmethod
    def _existing_outcome(email: EmailMessage) -> IngestionOutcome:
        return IngestionOutcome(
            email_id=email.id,
            created=False,
            status=email.status.value,
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
