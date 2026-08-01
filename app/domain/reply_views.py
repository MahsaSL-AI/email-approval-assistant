from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ReplyView:
    email_id: UUID
    text: str
    status: str
    approved_at: datetime | None
    rejected_at: datetime | None
    sent_at: datetime | None
