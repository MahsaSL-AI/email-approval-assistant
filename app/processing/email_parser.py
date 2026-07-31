from datetime import datetime, timezone
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import parseaddr, parsedate_to_datetime
from html.parser import HTMLParser

from app.domain.email import InboundEmail


class EmailParseError(ValueError):
    """Raised when a raw message cannot become a safe domain email."""


def parse_inbound_email(
    raw_message: bytes,
    *,
    monitored_address: str,
    fallback_received_at: datetime,
) -> InboundEmail:
    message = message_from_bytes(raw_message, policy=policy.default)

    message_id = _required_header(message, "Message-ID")
    sender = parseaddr(_required_header(message, "From"))[1]
    if not sender:
        raise EmailParseError("Email sender is missing or invalid.")

    recipient = parseaddr(message.get("To", ""))[1] or monitored_address
    subject = _optional_text(message.get("Subject"))
    body_text = _extract_body(message)
    if not body_text:
        raise EmailParseError("Email body is empty or unsupported.")

    received_at = _parse_received_at(message.get("Date"), fallback_received_at)
    return InboundEmail(
        external_message_id=message_id,
        sender=sender,
        recipient=recipient,
        subject=subject,
        body_text=body_text,
        received_at=received_at,
    )


def _required_header(message: EmailMessage, name: str) -> str:
    value = _optional_text(message.get(name))
    if value is None:
        raise EmailParseError(f"Required {name} header is missing.")
    return value


def _optional_text(value: object | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).split())
    return normalized or None


def _extract_body(message: EmailMessage) -> str:
    plain_parts: list[str] = []
    html_parts: list[str] = []

    parts = message.walk() if message.is_multipart() else [message]
    for part in parts:
        if part.is_multipart() or part.get_content_disposition() == "attachment":
            continue
        content_type = part.get_content_type()
        if content_type not in {"text/plain", "text/html"}:
            continue
        try:
            content = part.get_content()
        except (LookupError, UnicodeError) as error:
            raise EmailParseError("Email body encoding is invalid.") from error
        if not isinstance(content, str):
            continue
        if content_type == "text/plain":
            plain_parts.append(content)
        else:
            html_parts.append(content)

    selected = "\n".join(plain_parts)
    if not selected and html_parts:
        selected = _html_to_text("\n".join(html_parts))
    return _normalize_body(selected)


def _normalize_body(value: str) -> str:
    lines = [" ".join(line.split()) for line in value.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _html_to_text(value: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(value)
    parser.close()
    return " ".join(parser.text_parts)


def _parse_received_at(
    date_header: object | None,
    fallback: datetime,
) -> datetime:
    fallback_utc = _ensure_aware_utc(fallback)
    if date_header is None:
        return fallback_utc
    try:
        parsed = parsedate_to_datetime(str(date_header))
    except (TypeError, ValueError, OverflowError):
        return fallback_utc
    return _ensure_aware_utc(parsed)


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs
        if tag.lower() in {"script", "style"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        normalized = " ".join(data.split())
        if normalized:
            self.text_parts.append(normalized)
