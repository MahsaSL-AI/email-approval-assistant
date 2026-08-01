import argparse
import sys
import time

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.providers.factory import build_email_analyzer
from app.providers.imap import GmailImapClient, InboxConnectionError
from app.providers.telegram import TelegramBotApiProvider, TelegramProviderError
from app.repositories.email import EmailRepository
from app.repositories.email_notification import EmailNotificationRepository
from app.services.email_ingestion import EmailIngestionService
from app.services.inbox_sync import InboxSyncService
from app.services.stored_telegram_notification import (
    StoredTelegramNotificationService,
)
from app.services.telegram_notification import TelegramNotificationService


def run(*, once: bool = False, interval_seconds: float = 30.0) -> None:
    if interval_seconds < 5 and not once:
        raise ValueError("Email polling interval must be at least 5 seconds.")

    while True:
        summary = sync_once()
        print(
            "Inbox sync completed: "
            f"fetched={summary.fetched}, "
            f"processed={summary.processed}, "
            f"duplicates={summary.duplicates}, "
            f"failed={summary.failed}"
        )
        if once:
            return
        time.sleep(interval_seconds)


def sync_once():
    settings = get_settings()
    username = settings.email_username
    password = (
        settings.email_app_password.get_secret_value()
        if settings.email_app_password
        else None
    )
    token = (
        settings.telegram_bot_token.get_secret_value()
        if settings.telegram_bot_token
        else None
    )
    operator_id = settings.telegram_operator_id
    if not username or not password:
        raise RuntimeError("Email credentials are not configured.")
    if not token or operator_id is None:
        raise RuntimeError("Telegram credentials are not configured.")

    with SessionLocal() as session:
        notification = StoredTelegramNotificationService(
            EmailNotificationRepository(session),
            TelegramNotificationService(
                TelegramBotApiProvider(bot_token=token),
                operator_id,
            ),
        )
        service = InboxSyncService(
            inbox=GmailImapClient(
                host=settings.imap_host,
                port=settings.imap_port,
                username=username,
                app_password=password,
            ),
            ingestion=EmailIngestionService(
                EmailRepository(session),
                build_email_analyzer(settings),
            ),
            monitored_address=username,
            notification=notification,
        )
        return service.sync()


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll Gmail for new emails.")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=30.0)
    args = parser.parse_args()
    try:
        run(once=args.once, interval_seconds=args.interval)
    except (
        RuntimeError,
        ValueError,
        InboxConnectionError,
        TelegramProviderError,
        OSError,
    ) as error:
        print(f"Email worker stopped safely: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
