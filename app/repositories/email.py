from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.email import EmailMessage


class EmailRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_external_message_id(
        self,
        external_message_id: str,
    ) -> EmailMessage | None:
        statement = select(EmailMessage).where(
            EmailMessage.external_message_id == external_message_id
        )
        return self._session.scalars(statement).one_or_none()

    def add(self, email: EmailMessage) -> None:
        self._session.add(email)

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
