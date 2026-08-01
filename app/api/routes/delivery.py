from collections.abc import Generator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.domain.reply_state import InvalidReplyTransition
from app.providers.smtp import GmailSmtpProvider
from app.repositories.reply_workflow import ReplyWorkflowRepository
from app.schemas.reply import ReplyActionResponse
from app.services.reply_delivery import (
    ReplyDeliveryAmbiguousError,
    ReplyDeliveryFailed,
    ReplyDeliveryService,
)
from app.services.reply_workflow import ReplyNotFoundError

router = APIRouter(prefix="/api/emails", tags=["reply delivery"])


def get_reply_delivery_service() -> Generator[ReplyDeliveryService, None, None]:
    settings = get_settings()
    if settings.email_username is None or settings.email_app_password is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SMTP credentials are not configured.",
        )

    session = SessionLocal()
    try:
        provider = GmailSmtpProvider(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.email_username,
            app_password=settings.email_app_password.get_secret_value(),
            use_tls=settings.smtp_use_tls,
        )
        yield ReplyDeliveryService(
            ReplyWorkflowRepository(session),
            provider,
            settings.email_username,
        )
    finally:
        session.close()


@router.post("/{email_id}/send", response_model=ReplyActionResponse)
def send_reply(
    email_id: UUID,
    service: Annotated[ReplyDeliveryService, Depends(get_reply_delivery_service)],
) -> ReplyActionResponse:
    try:
        result = service.send(email_id)
    except ReplyNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reply was not found.",
        ) from error
    except (InvalidReplyTransition, ReplyDeliveryAmbiguousError) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except ReplyDeliveryFailed as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error
    return ReplyActionResponse.model_validate(result)
