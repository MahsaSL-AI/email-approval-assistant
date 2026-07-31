from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.reply_state import ReplyStatus


class EmailProcessingStatus(str, Enum):
    RECEIVED = "received"
    ANALYZED = "analyzed"
    NOTIFIED = "notified"
    FAILED = "failed"


class EmailCategory(str, Enum):
    SALES = "sales"
    SUPPORT = "support"
    COMPLAINT = "complaint"
    PAYMENT = "payment"
    LOGISTICS = "logistics"
    PARTNERSHIP = "partnership"
    SPAM = "spam"
    OTHER = "other"


class EmailPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ProcessingLogLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


def enum_column(enum_type: type[Enum], name: str) -> SqlEnum:
    return SqlEnum(
        enum_type,
        name=name,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda members: [member.value for member in members],
    )


class EmailMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "email_messages"

    external_message_id: Mapped[str] = mapped_column(
        String(998), nullable=False, unique=True
    )
    sender: Mapped[str] = mapped_column(String(320), nullable=False)
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(998))
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[EmailProcessingStatus] = mapped_column(
        enum_column(EmailProcessingStatus, "email_processing_status"),
        default=EmailProcessingStatus.RECEIVED,
        server_default=EmailProcessingStatus.RECEIVED.value,
        nullable=False,
    )
    failure_reason: Mapped[str | None] = mapped_column(Text)

    analysis: Mapped[EmailAnalysis | None] = relationship(
        back_populates="email",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    suggested_reply: Mapped[SuggestedReply | None] = relationship(
        back_populates="email",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    processing_logs: Mapped[list[ProcessingLog]] = relationship(
        back_populates="email",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_email_messages_status_received_at", "status", "received_at"),
    )


class EmailAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "email_analyses"

    email_id: Mapped[UUID] = mapped_column(
        ForeignKey("email_messages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[EmailCategory] = mapped_column(
        enum_column(EmailCategory, "email_category"), nullable=False
    )
    priority: Mapped[EmailPriority] = mapped_column(
        enum_column(EmailPriority, "email_priority"), nullable=False
    )
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    sentiment: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    email: Mapped[EmailMessage] = relationship(back_populates="analysis")

    __table_args__ = (
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="confidence_range",
        ),
        Index("ix_email_analyses_category_priority", "category", "priority"),
    )


class SuggestedReply(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "suggested_replies"

    email_id: Mapped[UUID] = mapped_column(
        ForeignKey("email_messages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ReplyStatus] = mapped_column(
        enum_column(ReplyStatus, "reply_status"),
        default=ReplyStatus.PENDING,
        server_default=ReplyStatus.PENDING.value,
        nullable=False,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    smtp_message_id: Mapped[str | None] = mapped_column(String(998), unique=True)
    failure_reason: Mapped[str | None] = mapped_column(Text)

    email: Mapped[EmailMessage] = relationship(back_populates="suggested_reply")

    __table_args__ = (Index("ix_suggested_replies_status", "status"),)


class ProcessingLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "processing_logs"

    email_id: Mapped[UUID] = mapped_column(
        ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False
    )
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[ProcessingLogLevel] = mapped_column(
        enum_column(ProcessingLogLevel, "processing_log_level"),
        default=ProcessingLogLevel.INFO,
        server_default=ProcessingLogLevel.INFO.value,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    email: Mapped[EmailMessage] = relationship(back_populates="processing_logs")

    __table_args__ = (
        Index("ix_processing_logs_email_created", "email_id", "created_at"),
    )
