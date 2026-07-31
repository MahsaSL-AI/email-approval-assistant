from datetime import datetime, timezone
from email.message import EmailMessage

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.domain.email import EmailAnalysisResult, InboundEmail
from app.models.email import EmailMessage as EmailRecord
from app.providers.email_analysis import FakeEmailAnalyzer
from app.providers.imap import InboxConnectionError, RawInboxMessage
from app.repositories.email import EmailRepository
from app.services.email_ingestion import EmailIngestionService
from app.services.inbox_sync import InboxSyncService


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


def raw_email(message_id: str = "<sync-1@example.test>") -> RawInboxMessage:
    message = EmailMessage()
    message["Message-ID"] = message_id
    message["From"] = "customer@example.test"
    message["To"] = "business@example.test"
    message["Subject"] = "Support request"
    message.set_content("Please help with my order.")
    return RawInboxMessage(
        uid="501",
        raw_message=message.as_bytes(),
        received_at=datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc),
    )


def make_sync(
    session: Session,
    inbox: object,
    analyzer: object | None = None,
) -> InboxSyncService:
    ingestion = EmailIngestionService(
        EmailRepository(session),
        analyzer or FakeEmailAnalyzer(),
    )
    return InboxSyncService(
        inbox=inbox,
        ingestion=ingestion,
        monitored_address="business@example.test",
    )


def test_sync_processes_email_then_marks_it_seen(session: Session) -> None:
    inbox = FakeInbox([raw_email()])

    summary = make_sync(session, inbox).sync()

    assert summary.fetched == 1
    assert summary.processed == 1
    assert summary.duplicates == 0
    assert summary.failed == 0
    assert inbox.seen_uids == ["501"]
    assert session.scalar(select(func.count()).select_from(EmailRecord)) == 1


def test_repeated_unread_email_is_deduplicated_but_marked_seen(
    session: Session,
) -> None:
    inbox = FakeInbox([raw_email()])
    sync = make_sync(session, inbox)
    sync.sync()

    summary = sync.sync()

    assert summary.processed == 0
    assert summary.duplicates == 1
    assert inbox.seen_uids == ["501", "501"]
    assert session.scalar(select(func.count()).select_from(EmailRecord)) == 1


def test_analysis_failure_is_persisted_and_message_is_marked_seen(
    session: Session,
) -> None:
    inbox = FakeInbox([raw_email()])

    summary = make_sync(session, inbox, FailingAnalyzer()).sync()

    assert summary.failed == 1
    assert inbox.seen_uids == ["501"]
    email = session.scalars(select(EmailRecord)).one()
    assert email.status.value == "failed"


def test_parse_failure_remains_unread_for_diagnosis(session: Session) -> None:
    inbox = FakeInbox(
        [
            RawInboxMessage(
                uid="broken",
                raw_message=b"From: customer@example.test\r\n\r\nNo message id",
                received_at=datetime.now(timezone.utc),
            )
        ]
    )

    summary = make_sync(session, inbox).sync()

    assert summary.failed == 1
    assert inbox.seen_uids == []
    assert session.scalar(select(func.count()).select_from(EmailRecord)) == 0


def test_seen_failure_does_not_repeat_analysis(session: Session) -> None:
    analyzer = CountingAnalyzer()
    inbox = FakeInbox([raw_email()], fail_mark_seen=True)
    sync = make_sync(session, inbox, analyzer)

    first = sync.sync()
    second = sync.sync()

    assert first.failed == 1
    assert second.duplicates == 1
    assert second.failed == 1
    assert analyzer.call_count == 1


class FakeInbox:
    def __init__(
        self,
        messages: list[RawInboxMessage],
        *,
        fail_mark_seen: bool = False,
    ) -> None:
        self.messages = messages
        self.fail_mark_seen = fail_mark_seen
        self.seen_uids: list[str] = []

    def fetch_unread(self) -> list[RawInboxMessage]:
        return self.messages

    def mark_seen(self, uid: str) -> None:
        if self.fail_mark_seen:
            raise InboxConnectionError("synthetic seen failure")
        self.seen_uids.append(uid)


class FailingAnalyzer:
    def analyze(self, email: InboundEmail) -> EmailAnalysisResult:
        raise TimeoutError("synthetic analysis timeout")


class CountingAnalyzer:
    def __init__(self) -> None:
        self.call_count = 0

    def analyze(self, email: InboundEmail) -> EmailAnalysisResult:
        self.call_count += 1
        return FakeEmailAnalyzer().analyze(email)
