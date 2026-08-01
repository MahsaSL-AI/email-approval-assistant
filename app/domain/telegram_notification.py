from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TelegramEmailNotification:
    email_id: UUID
    sender: str
    subject: str | None
    received_at: datetime
    summary: str
    category: str
    priority: str
    suggested_reply: str
