from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.email import EmailMessage


class ReplyWorkflowRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_email(self, email_id: UUID) -> EmailMessage | None:
        statement = (
            select(EmailMessage)
            .options(joinedload(EmailMessage.suggested_reply))
            .where(EmailMessage.id == email_id)
        )
        return self._session.scalars(statement).unique().one_or_none()

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
