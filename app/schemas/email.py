from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EmailListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sender: str
    subject: str | None
    received_at: datetime
    processing_status: str
    category: str | None
    priority: str | None
    reply_status: str | None


class EmailListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[EmailListItemResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class EmailDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
