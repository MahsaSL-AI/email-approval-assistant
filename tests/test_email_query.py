from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.domain.reply_state import ReplyStatus
from app.models.email import (
    EmailAnalysis,
    EmailCategory,
    EmailMessage,
    EmailPriority,
    EmailProcessingStatus,
    SuggestedReply,
)
from app.repositories.email_query import EmailQueryRepository
from app.services.email_query import EmailNotFoundError, EmailQueryService


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


def add_email(session: Session, *, index: int) -> EmailMessage:
    record = EmailMessage(
        external_message_id=f"<query-{index}@example.test>",
        sender=f"customer{index}@example.test",
        recipient="business@example.test",
        subject=f"Request {index}",
        body_text=f"Synthetic body {index}",
        received_at=datetime(2026, 7, 31, tzinfo=timezone.utc)
        + timedelta(minutes=index),
        status=EmailProcessingStatus.ANALYZED,
    )
    record.analysis = EmailAnalysis(
        summary=f"Summary {index}",
        category=EmailCategory.SUPPORT,
        priority=EmailPriority.HIGH,
        language="en",
        sentiment="neutral",
        confidence=0.9,
    )
    record.suggested_reply = SuggestedReply(
        text=f"Reply {index}",
        status=ReplyStatus.PENDING,
    )
    session.add(record)
    session.commit()
    return record


def test_list_is_newest_first_and_paginated(session: Session) -> None:
    oldest = add_email(session, index=1)
    newest = add_email(session, index=2)
    service = EmailQueryService(EmailQueryRepository(session))

    first_page = service.list(page=1, page_size=1)
    second_page = service.list(page=2, page_size=1)

    assert first_page.total == 2
    assert first_page.items[0].id == newest.id
    assert first_page.items[0].category == "support"
    assert first_page.items[0].reply_status == "pending"
    assert second_page.items[0].id == oldest.id


def test_get_returns_flattened_email_analysis_and_reply(session: Session) -> None:
    record = add_email(session, index=3)
    service = EmailQueryService(EmailQueryRepository(session))

    result = service.get(record.id)

    assert result.external_message_id == "<query-3@example.test>"
    assert result.summary == "Summary 3"
    assert result.priority == "high"
    assert result.suggested_reply == "Reply 3"
    assert result.reply_status == "pending"


def test_get_missing_email_raises_domain_not_found(session: Session) -> None:
    service = EmailQueryService(EmailQueryRepository(session))

    with pytest.raises(EmailNotFoundError):
        service.get(uuid4())
