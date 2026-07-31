from collections.abc import Generator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.db.session import SessionLocal
from app.repositories.email_query import EmailQueryRepository
from app.schemas.email import EmailDetailResponse, EmailListResponse
from app.services.email_query import EmailNotFoundError, EmailQueryService

router = APIRouter(prefix="/api/emails", tags=["emails"])


def get_email_query_service() -> Generator[EmailQueryService, None, None]:
    session = SessionLocal()
    try:
        yield EmailQueryService(EmailQueryRepository(session))
    finally:
        session.close()


@router.get("", response_model=EmailListResponse)
def list_emails(
    service: Annotated[EmailQueryService, Depends(get_email_query_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> EmailListResponse:
    result = service.list(page=page, page_size=page_size)
    return EmailListResponse.model_validate(result)


@router.get("/{email_id}", response_model=EmailDetailResponse)
def get_email(
    email_id: UUID,
    service: Annotated[EmailQueryService, Depends(get_email_query_service)],
) -> EmailDetailResponse:
    try:
        result = service.get(email_id)
    except EmailNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email was not found.",
        ) from error
    return EmailDetailResponse.model_validate(result)
