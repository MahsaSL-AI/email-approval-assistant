from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class InboundEmail:
    external_message_id: str
    sender: str
    recipient: str
    subject: str | None
    body_text: str
    received_at: datetime


@dataclass(frozen=True, slots=True)
class EmailAnalysisResult:
    summary: str
    category: str
    priority: str
    language: str
    sentiment: str
    confidence: float
    suggested_reply: str


@dataclass(frozen=True, slots=True)
class IngestionOutcome:
    email_id: UUID
    created: bool
    status: str
