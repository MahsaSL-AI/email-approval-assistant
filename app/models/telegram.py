from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class TelegramEditSession(TimestampMixin, Base):
    """The email currently being edited by a Telegram operator."""

    __tablename__ = "telegram_edit_sessions"

    operator_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email_id: Mapped[UUID] = mapped_column(
        ForeignKey("email_messages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
