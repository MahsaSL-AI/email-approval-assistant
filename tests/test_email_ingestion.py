from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.domain.email import EmailAnalysisResult, InboundEmail
from app.models.email import (
    EmailAnalysis,
    EmailMessage,
    EmailProcessingStatus,
    ProcessingLog,
    SuggestedReply,
)
from app.providers.email_analysis import FakeEmailAnalyzer
from app.repositories.email import EmailRepository
from app.services.email_ingestion import EmailAnalysisFailed, EmailIngestionService


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as database_session:
        yield database_session


def make_email(message_id: str = "<customer-1@example.test>") -> InboundEmail:
    return InboundEmail(
        external_message_id=message_id,
        sender="customer@example.test",
        recipient="business@example.test",
        subject="Order status",
        body_text="Please tell me when my order will arrive.",
        received_at=datetime(2026, 7, 31, 8, 30, tzinfo=timezone.utc),
    )


def scalar_count(session: Session, model: type[object]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_ingest_persists_email_analysis_reply_and_logs(session: Session) -> None:
    service = EmailIngestionService(
        EmailRepository(session),
        FakeEmailAnalyzer(),
    )

    outcome = service.ingest(make_email())

    assert outcome.created is True
    assert outcome.status == "analyzed"
    assert scalar_count(session, EmailMessage) == 1
    assert scalar_count(session, EmailAnalysis) == 1
    assert scalar_count(session, SuggestedReply) == 1
    assert scalar_count(session, ProcessingLog) == 2


def test_duplicate_message_id_is_not_analyzed_twice(session: Session) -> None:
    analyzer = CountingAnalyzer()
    service = EmailIngestionService(EmailRepository(session), analyzer)

    first = service.ingest(make_email())
    duplicate = service.ingest(make_email())

    assert first.created is True
    assert duplicate.created is False
    assert duplicate.email_id == first.email_id
    assert analyzer.call_count == 1
    assert scalar_count(session, EmailMessage) == 1
    assert scalar_count(session, ProcessingLog) == 2


def test_analysis_failure_keeps_email_with_visible_failed_state(
    session: Session,
) -> None:
    service = EmailIngestionService(
        EmailRepository(session),
        FailingAnalyzer(),
    )

    with pytest.raises(EmailAnalysisFailed, match="temporarily unavailable"):
        service.ingest(make_email())

    email = session.scalars(select(EmailMessage)).one()
    assert email.status is EmailProcessingStatus.FAILED
    assert email.failure_reason == "AI analysis failed."
    assert scalar_count(session, EmailAnalysis) == 0
    assert scalar_count(session, SuggestedReply) == 0
    assert scalar_count(session, ProcessingLog) == 2


class CountingAnalyzer:
    def __init__(self) -> None:
        self.call_count = 0

    def analyze(self, email: InboundEmail) -> EmailAnalysisResult:
        self.call_count += 1
        return FakeEmailAnalyzer().analyze(email)


class FailingAnalyzer:
    def analyze(self, email: InboundEmail) -> EmailAnalysisResult:
        raise TimeoutError("synthetic provider timeout")
