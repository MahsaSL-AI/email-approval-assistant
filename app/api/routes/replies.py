from collections.abc import Callable, Generator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.db.session import SessionLocal
from app.domain.reply_state import InvalidReplyTransition
from app.domain.reply_views import ReplyView
from app.repositories.reply_workflow import ReplyWorkflowRepository
from app.schemas.reply import ReplyActionResponse, ReplyEditRequest
from app.services.reply_workflow import (
    EmptyReplyError,
    ReplyNotFoundError,
    ReplyWorkflowService,
)

router = APIRouter(prefix="/api/emails", tags=["reply workflow"])


def get_reply_workflow_service() -> Generator[ReplyWorkflowService, None, None]:
    session = SessionLocal()
    try:
        yield ReplyWorkflowService(ReplyWorkflowRepository(session))
    finally:
        session.close()


@router.put("/{email_id}/reply", response_model=ReplyActionResponse)
def edit_reply(
    email_id: UUID,
    payload: ReplyEditRequest,
    service: Annotated[ReplyWorkflowService, Depends(get_reply_workflow_service)],
) -> ReplyActionResponse:
    return _run_reply_action(lambda: service.edit(email_id, payload.text))


@router.post("/{email_id}/approve", response_model=ReplyActionResponse)
def approve_reply(
    email_id: UUID,
    service: Annotated[ReplyWorkflowService, Depends(get_reply_workflow_service)],
) -> ReplyActionResponse:
    return _run_reply_action(lambda: service.approve(email_id))


@router.post("/{email_id}/reject", response_model=ReplyActionResponse)
def reject_reply(
    email_id: UUID,
    service: Annotated[ReplyWorkflowService, Depends(get_reply_workflow_service)],
) -> ReplyActionResponse:
    return _run_reply_action(lambda: service.reject(email_id))


def _run_reply_action(action: Callable[[], ReplyView]) -> ReplyActionResponse:
    try:
        result = action()
    except ReplyNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reply was not found.",
        ) from error
    except (InvalidReplyTransition, EmptyReplyError) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return ReplyActionResponse.model_validate(result)
