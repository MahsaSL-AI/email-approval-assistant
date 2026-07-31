from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class EmailListItem:
    id: UUID
    sender: str
    subject: str | None
    received_at: datetime
    processing_status: str
    category: str | None
    priority: str | None
    reply_status: str | None


@dataclass(frozen=True, slots=True)
class EmailDetail:
    id: UUID
    external_message_id: str
    sender: str
    recipient: str
    subject: str | None
    body_text: str
    received_at: datetime
    processing_status: str
    failure_reason: str | None
    summary: str | None
    category: str | None
    priority: str | None
    language: str | None
    sentiment: str | None
    confidence: float | None
    suggested_reply: str | None
    reply_status: str | None
    approved_at: datetime | None
    rejected_at: datetime | None
    sent_at: datetime | None


@dataclass(frozen=True, slots=True)
class EmailPage:
    items: list[EmailListItem]
    total: int
    page: int
    page_size: int
