import smtplib

import pytest

from app.domain.outbound_email import OutboundEmail
from app.providers.smtp import GmailSmtpProvider, OutboundEmailError


class FakeSmtpConnection:
    def __init__(self, refused=None, failure: Exception | None = None) -> None:
        self.refused = refused or {}
        self.failure = failure
        self.calls: list[object] = []
        self.message = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def ehlo(self) -> None:
        self.calls.append("ehlo")

    def starttls(self) -> None:
        self.calls.append("starttls")

    def login(self, username: str, password: str) -> None:
        self.calls.append(("login", username, password))

    def send_message(self, message):
        if self.failure:
            raise self.failure
        self.message = message
        self.calls.append("send_message")
        return self.refused


def outbound() -> OutboundEmail:
    return OutboundEmail(
        sender="business@example.test",
        recipient="customer@example.test",
        subject="Re: Request",
        body_text="Approved response",
        message_id="<reply-1@example.test>",
        in_reply_to="<original@example.test>",
    )


def test_smtp_provider_uses_tls_and_threading_headers(monkeypatch) -> None:
    connection = FakeSmtpConnection()
    monkeypatch.setattr(smtplib, "SMTP", lambda *args, **kwargs: connection)
    provider = GmailSmtpProvider(
        host="smtp.example.test",
        port=587,
        username="business@example.test",
        app_password="synthetic-secret",
    )

    provider.send(outbound())

    assert connection.calls == [
        "ehlo",
        "starttls",
        "ehlo",
        ("login", "business@example.test", "synthetic-secret"),
        "send_message",
    ]
    assert connection.message["In-Reply-To"] == "<original@example.test>"
    assert connection.message["References"] == "<original@example.test>"


def test_smtp_provider_returns_safe_error_without_password(monkeypatch) -> None:
    connection = FakeSmtpConnection(failure=smtplib.SMTPServerDisconnected())
    monkeypatch.setattr(smtplib, "SMTP", lambda *args, **kwargs: connection)
    provider = GmailSmtpProvider(
        host="smtp.example.test",
        port=587,
        username="business@example.test",
        app_password="synthetic-secret",
    )

    with pytest.raises(OutboundEmailError) as error_info:
        provider.send(outbound())

    assert "synthetic-secret" not in str(error_info.value)


def test_smtp_provider_rejects_partial_recipient_failure(monkeypatch) -> None:
    connection = FakeSmtpConnection(
        refused={"customer@example.test": (550, b"rejected")}
    )
    monkeypatch.setattr(smtplib, "SMTP", lambda *args, **kwargs: connection)
    provider = GmailSmtpProvider(
        host="smtp.example.test",
        port=587,
        username="business@example.test",
        app_password="synthetic-secret",
    )

    with pytest.raises(OutboundEmailError, match="refused"):
        provider.send(outbound())
