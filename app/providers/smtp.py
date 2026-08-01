import smtplib
from email.message import EmailMessage
from typing import Protocol

from app.domain.outbound_email import OutboundEmail


class OutboundEmailError(RuntimeError):
    """Safe boundary error for SMTP delivery failures."""


class OutboundEmailProvider(Protocol):
    def send(self, outbound: OutboundEmail) -> None: ...


class GmailSmtpProvider:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        app_password: str,
        use_tls: bool = True,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._app_password = app_password
        self._use_tls = use_tls
        self._timeout_seconds = timeout_seconds

    def send(self, outbound: OutboundEmail) -> None:
        message = self._build_message(outbound)
        try:
            with smtplib.SMTP(
                self._host,
                self._port,
                timeout=self._timeout_seconds,
            ) as connection:
                connection.ehlo()
                if self._use_tls:
                    connection.starttls()
                    connection.ehlo()
                connection.login(self._username, self._app_password)
                refused = connection.send_message(message)
        except (OSError, smtplib.SMTPException) as error:
            raise OutboundEmailError("SMTP delivery did not complete.") from error

        if refused:
            raise OutboundEmailError("SMTP refused one or more recipients.")

    @staticmethod
    def _build_message(outbound: OutboundEmail) -> EmailMessage:
        message = EmailMessage()
        message["From"] = outbound.sender
        message["To"] = outbound.recipient
        message["Subject"] = outbound.subject
        message["Message-ID"] = outbound.message_id
        message["In-Reply-To"] = outbound.in_reply_to
        message["References"] = outbound.in_reply_to
        message.set_content(outbound.body_text)
        return message
