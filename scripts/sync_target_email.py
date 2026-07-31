import argparse

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.processing.email_parser import EmailParseError, parse_inbound_email
from app.providers.email_analysis import FakeEmailAnalyzer
from app.providers.imap import GmailImapClient
from app.repositories.email import EmailRepository
from app.services.email_ingestion import EmailIngestionService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync exactly one unread test email selected by a body token."
    )
    parser.add_argument(
        "--body-token",
        required=True,
        help="A non-sensitive unique token expected in the synthetic email body.",
    )
    args = parser.parse_args()

    settings = get_settings()
    username = settings.email_username
    password = (
        settings.email_app_password.get_secret_value()
        if settings.email_app_password
        else None
    )
    if not username or not password:
        raise SystemExit("Email integration is not configured.")

    inbox = GmailImapClient(
        host=settings.imap_host,
        port=settings.imap_port,
        username=username,
        app_password=password,
    )
    matches = []
    parse_failures = 0
    for raw in inbox.fetch_unread():
        try:
            inbound = parse_inbound_email(
                raw.raw_message,
                monitored_address=username,
                fallback_received_at=raw.received_at,
            )
        except EmailParseError:
            parse_failures += 1
            continue
        if args.body_token in inbound.body_text:
            matches.append((raw, inbound))

    print(f"TARGET_MATCH_COUNT={len(matches)}")
    print(f"PARSE_FAILURE_COUNT={parse_failures}")
    if len(matches) != 1:
        raise SystemExit("Expected exactly one target email; nothing was changed.")

    raw, inbound = matches[0]
    with SessionLocal() as session:
        outcome = EmailIngestionService(
            EmailRepository(session),
            FakeEmailAnalyzer(),
        ).ingest(inbound)
    inbox.mark_seen(raw.uid)

    print("TARGET_SYNC_OK")
    print(f"CREATED={outcome.created}")
    print(f"STATUS={outcome.status}")


if __name__ == "__main__":
    main()
