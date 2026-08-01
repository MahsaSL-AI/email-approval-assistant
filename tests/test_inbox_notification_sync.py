from datetime import datetime, timezone
from email.message import EmailMessage

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.email import EmailMessage as EmailRecord
from app.models.email import EmailProcessingStatus
from app.providers.email_analysis import FakeEmailAnalyzer
from app.providers.imap import RawInboxMessage
from app.repositories.email import EmailRepository
from app.services.email_ingestion import EmailIngestionService
from app.services.inbox_sync import InboxSyncService
from app.services.stored_telegram_notification import EmailNotificationFailed


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


def raw_email() -> RawInboxMessage:
    message = EmailMessage()
    message["Message-ID"] = "<telegram-sync@example.test>"
    message["From"] = "customer@example.test"
    message["To"] = "business@example.test"
    message["Subject"] = "Support request"
    message.set_content("Please help with my order.")
    return RawInboxMessage(
        uid="telegram-501",
        raw_message=message.as_bytes(),
        received_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )


class FakeInbox:
    def __init__(self) -> None:
        self.seen_uids = []

    def fetch_unread(self) -> list[RawInboxMessage]:
        return [raw_email()]

    def mark_seen(self, uid: str) -> None:
        self.seen_uids.append(uid)


class RecordingNotification:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.email_ids = []

    def notify(self, email_id) -> bool:
        self.email_ids.append(email_id)
        if self.fail:
            raise EmailNotificationFailed("synthetic Telegram outage")
        return True


def make_sync(
    session: Session,
    inbox: FakeInbox,
    notification: RecordingNotification,
) -> InboxSyncService:
    return InboxSyncService(
        inbox=inbox,
        ingestion=EmailIngestionService(
            EmailRepository(session),
            FakeEmailAnalyzer(),
        ),
        monitored_address="business@example.test",
        notification=notification,
    )


def test_email_is_marked_seen_only_after_notification_succeeds(
    session: Session,
) -> None:
    inbox = FakeInbox()
    notification = RecordingNotification()

    summary = make_sync(session, inbox, notification).sync()

    assert summary.processed == 1
    assert summary.failed == 0
    assert len(notification.email_ids) == 1
    assert inbox.seen_uids == ["telegram-501"]


def test_notification_failure_leaves_gmail_message_unread_for_retry(
    session: Session,
) -> None:
    inbox = FakeInbox()
    notification = RecordingNotification(fail=True)

    summary = make_sync(session, inbox, notification).sync()

    assert summary.processed == 1
    assert summary.failed == 1
    assert inbox.seen_uids == []


def test_notified_duplicate_is_marked_seen_without_duplicate_notification(
    session: Session,
) -> None:
    inbox = FakeInbox()
    first_notification = RecordingNotification()
    sync = make_sync(session, inbox, first_notification)
    sync.sync()
    stored = session.scalars(select(EmailRecord)).one()
    stored.status = EmailProcessingStatus.NOTIFIED
    session.commit()
    second_notification = RecordingNotification()

    summary = make_sync(session, inbox, second_notification).sync()

    assert summary.duplicates == 1
    assert second_notification.email_ids == []
    assert inbox.seen_uids == ["telegram-501", "telegram-501"]
