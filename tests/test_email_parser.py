from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import pytest

from app.processing.email_parser import EmailParseError, parse_inbound_email

FALLBACK_TIME = datetime(2026, 7, 31, 10, 0, tzinfo=timezone.utc)


def base_message() -> EmailMessage:
    message = EmailMessage()
    message["Message-ID"] = "<customer-42@example.test>"
    message["From"] = "Customer <customer@example.test>"
    message["To"] = "Business <business@example.test>"
    message["Subject"] = "Order status"
    message["Date"] = "Fri, 31 Jul 2026 14:00:00 +0330"
    return message


def parse(message: EmailMessage):
    return parse_inbound_email(
        message.as_bytes(),
        monitored_address="fallback@example.test",
        fallback_received_at=FALLBACK_TIME,
    )


def test_parses_plain_text_email_and_normalizes_time() -> None:
    message = base_message()
    message.set_content("Hello,\n\n  when will my order arrive?  ")

    result = parse(message)

    assert result.external_message_id == "<customer-42@example.test>"
    assert result.sender == "customer@example.test"
    assert result.recipient == "business@example.test"
    assert result.subject == "Order status"
    assert result.body_text == "Hello,\nwhen will my order arrive?"
    assert result.received_at == datetime(2026, 7, 31, 10, 30, tzinfo=timezone.utc)


def test_prefers_plain_text_over_html_alternative() -> None:
    message = base_message()
    message.set_content("Plain version")
    message.add_alternative("<p>HTML version</p>", subtype="html")

    result = parse(message)

    assert result.body_text == "Plain version"


def test_extracts_text_from_html_and_ignores_script_and_style() -> None:
    message = base_message()
    message.set_content(
        "<style>.secret {display:none}</style>"
        "<p>Payment <strong>failed</strong>.</p>"
        "<script>stealCredentials()</script>",
        subtype="html",
    )

    result = parse(message)

    assert result.body_text == "Payment failed ."
    assert "secret" not in result.body_text
    assert "stealCredentials" not in result.body_text


def test_ignores_text_attachment() -> None:
    message = base_message()
    message.set_content("Main request")
    message.add_attachment(
        "Private attachment text",
        subtype="plain",
        filename="private.txt",
    )

    result = parse(message)

    assert result.body_text == "Main request"


def test_missing_subject_is_allowed() -> None:
    message = base_message()
    del message["Subject"]
    message.set_content("I need help")

    result = parse(message)

    assert result.subject is None


def test_missing_to_header_uses_monitored_address() -> None:
    message = base_message()
    del message["To"]
    message.set_content("I need help")

    result = parse(message)

    assert result.recipient == "fallback@example.test"


def test_invalid_date_uses_aware_fallback() -> None:
    message = base_message()
    message.replace_header("Date", "not a date")
    message.set_content("I need help")
    naive_fallback = datetime(2026, 7, 31, 10, 0)

    result = parse_inbound_email(
        message.as_bytes(),
        monitored_address="fallback@example.test",
        fallback_received_at=naive_fallback,
    )

    assert result.received_at == naive_fallback.replace(tzinfo=timezone.utc)


def test_date_with_offset_is_converted_to_utc() -> None:
    message = base_message()
    message.replace_header("Date", "Fri, 31 Jul 2026 10:00:00 -0400")
    message.set_content("I need help")

    result = parse(message)

    expected = datetime(2026, 7, 31, 10, 0, tzinfo=timezone(-timedelta(hours=4)))
    assert result.received_at == expected.astimezone(timezone.utc)


@pytest.mark.parametrize("required_header", ["Message-ID", "From"])
def test_missing_required_header_is_rejected(required_header: str) -> None:
    message = base_message()
    del message[required_header]
    message.set_content("I need help")

    with pytest.raises(EmailParseError, match="Required|sender"):
        parse(message)


def test_empty_body_is_rejected() -> None:
    message = base_message()
    message.set_content("   \n")

    with pytest.raises(EmailParseError, match="body is empty"):
        parse(message)
