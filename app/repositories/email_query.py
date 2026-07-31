from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.email import EmailMessage


class EmailQueryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(
        self,
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[EmailMessage], int]:
        statement = (
            select(EmailMessage)
            .options(
                joinedload(EmailMessage.analysis),
                joinedload(EmailMessage.suggested_reply),
            )
            .order_by(EmailMessage.received_at.desc(), EmailMessage.id.desc())
            .offset(offset)
            .limit(limit)
        )
        items = list(self._session.scalars(statement).unique())
        total = (
            self._session.scalar(select(func.count()).select_from(EmailMessage)) or 0
        )
        return items, total

    def get(self, email_id: UUID) -> EmailMessage | None:
        statement = (
            select(EmailMessage)
            .options(
                joinedload(EmailMessage.analysis),
                joinedload(EmailMessage.suggested_reply),
            )
            .where(EmailMessage.id == email_id)
        )
        return self._session.scalars(statement).unique().one_or_none()
