from uuid import UUID

from sqlalchemy.orm import Session

from app.models.telegram import TelegramEditSession


class TelegramEditSessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def start(self, *, operator_id: int, email_id: UUID) -> None:
        edit_session = self._session.get(TelegramEditSession, operator_id)
        if edit_session is None:
            edit_session = TelegramEditSession(
                operator_id=operator_id,
                email_id=email_id,
            )
            self._session.add(edit_session)
        else:
            edit_session.email_id = email_id
        self._session.commit()

    def current_email_id(self, *, operator_id: int) -> UUID | None:
        edit_session = self._session.get(TelegramEditSession, operator_id)
        return edit_session.email_id if edit_session is not None else None

    def clear(self, *, operator_id: int) -> None:
        edit_session = self._session.get(TelegramEditSession, operator_id)
        if edit_session is not None:
            self._session.delete(edit_session)
            self._session.commit()
