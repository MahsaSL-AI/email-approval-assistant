from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReplyEditRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)


class ReplyActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email_id: UUID
    text: str
    status: str
    approved_at: datetime | None
    rejected_at: datetime | None
    sent_at: datetime | None
