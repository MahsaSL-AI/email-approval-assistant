from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.providers.email_analysis import FakeEmailAnalyzer
from app.providers.imap import GmailImapClient, InboxConnectionError
from app.repositories.email import EmailRepository
from app.schemas.inbox import InboxSyncResponse
from app.services.email_ingestion import EmailIngestionService
from app.services.inbox_sync import InboxSyncService

router = APIRouter(prefix="/api/emails", tags=["emails"])


def get_inbox_sync_service() -> Generator[InboxSyncService, None, None]:
    settings = get_settings()
    username = settings.email_username
    password = (
        settings.email_app_password.get_secret_value()
        if settings.email_app_password
        else None
    )
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email integration is not configured.",
        )

    session = SessionLocal()
    try:
        inbox = GmailImapClient(
            host=settings.imap_host,
            port=settings.imap_port,
            username=username,
            app_password=password,
        )
        ingestion = EmailIngestionService(
            EmailRepository(session),
            FakeEmailAnalyzer(),
        )
        yield InboxSyncService(
            inbox=inbox,
            ingestion=ingestion,
            monitored_address=username,
        )
    finally:
        session.close()


@router.post("/sync", response_model=InboxSyncResponse)
def sync_inbox(
    service: Annotated[InboxSyncService, Depends(get_inbox_sync_service)],
) -> InboxSyncResponse:
    try:
        summary = service.sync()
    except InboxConnectionError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email inbox is temporarily unavailable.",
        ) from error
    return InboxSyncResponse.model_validate(summary, from_attributes=True)
