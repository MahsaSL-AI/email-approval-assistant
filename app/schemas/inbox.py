from pydantic import BaseModel, Field


class InboxSyncResponse(BaseModel):
    fetched: int = Field(ge=0)
    processed: int = Field(ge=0)
    duplicates: int = Field(ge=0)
    failed: int = Field(ge=0)
