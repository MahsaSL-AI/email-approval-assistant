import argparse
import sys
from pathlib import Path

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.providers.smtp import GmailSmtpProvider
from app.providers.telegram import TelegramProviderError
from app.providers.telegram_updates import TelegramUpdateProvider
from app.repositories.reply_workflow import ReplyWorkflowRepository
from app.services.reply_delivery import ReplyDeliveryService
from app.services.reply_edit_session import ReplyEditSessionService
from app.services.reply_workflow import ReplyWorkflowService
from app.services.telegram_actions import (
    InvalidTelegramAction,
    TelegramActionService,
)
from app.services.telegram_offset import TelegramOffsetStore
from app.services.telegram_update_processor import TelegramUpdateProcessor

DEFAULT_OFFSET_PATH = Path(".runtime/telegram_offset")


def run(*, once: bool = False, offset_path: Path = DEFAULT_OFFSET_PATH) -> None:
    settings = get_settings()
    token = (
        settings.telegram_bot_token.get_secret_value()
        if settings.telegram_bot_token
        else None
    )
    operator_id = settings.telegram_operator_id
    username = settings.email_username
    password = (
        settings.email_app_password.get_secret_value()
        if settings.email_app_password
        else None
    )
    if not token or operator_id is None:
        raise RuntimeError("Telegram credentials are not configured.")
    if not username or not password:
        raise RuntimeError("SMTP credentials are not configured.")

    updates = TelegramUpdateProvider(bot_token=token)
    offset_store = TelegramOffsetStore(offset_path)

    while True:
        offset = offset_store.load()
        batch = updates.get_updates(
            offset=offset,
            poll_timeout_seconds=0 if once else 25,
        )
        for update in sorted(batch, key=lambda item: item.get("update_id", -1)):
            update_id = update.get("update_id")
            if not isinstance(update_id, int):
                continue
            try:
                with SessionLocal() as session:
                    _build_processor(
                        session=session,
                        updates=updates,
                        operator_id=operator_id,
                        username=username,
                        password=password,
                        settings=settings,
                    ).process(update)
            except InvalidTelegramAction:
                pass
            finally:
                offset_store.save(update_id + 1)
        if once:
            return


def _build_processor(
    *,
    session,
    updates: TelegramUpdateProvider,
    operator_id: int,
    username: str,
    password: str,
    settings,
) -> TelegramUpdateProcessor:
    repository = ReplyWorkflowRepository(session)
    decisions = ReplyWorkflowService(repository)
    edit_sessions = ReplyEditSessionService(repository)
    delivery = ReplyDeliveryService(
        repository,
        GmailSmtpProvider(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=username,
            app_password=password,
            use_tls=settings.smtp_use_tls,
        ),
        username,
    )
    actions = TelegramActionService(
        operator_id=operator_id,
        decisions=decisions,
        edit_sessions=edit_sessions,
        delivery=delivery,
    )
    return TelegramUpdateProcessor(
        operator_id=operator_id,
        actions=actions,
        responder=updates,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Telegram update polling.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Fetch and process the currently queued updates, then exit.",
    )
    args = parser.parse_args()
    try:
        run(once=args.once)
    except (RuntimeError, TelegramProviderError, OSError, ValueError) as error:
        print(f"Telegram worker stopped safely: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
