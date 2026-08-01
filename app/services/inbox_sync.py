from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.processing.email_parser import EmailParseError, parse_inbound_email
from app.providers.imap import InboxClient, InboxConnectionError
from app.services.email_ingestion import EmailAnalysisFailed, EmailIngestionService
from app.services.stored_telegram_notification import EmailNotificationFailed


class EmailNotificationSink(Protocol):
    def notify(self, email_id: UUID) -> bool: ...


@dataclass(frozen=True, slots=True)
class InboxSyncSummary:
    fetched: int
    processed: int
    duplicates: int
    failed: int


class InboxSyncService:
    def __init__(
        self,
        *,
        inbox: InboxClient,
        ingestion: EmailIngestionService,
        monitored_address: str,
        notification: EmailNotificationSink | None = None,
    ) -> None:
        self._inbox = inbox
        self._ingestion = ingestion
        self._monitored_address = monitored_address
        self._notification = notification

    def sync(self) -> InboxSyncSummary:
        raw_messages = self._inbox.fetch_unread()
        processed = 0
        duplicates = 0
        failed = 0

        for raw in raw_messages:
            try:
                inbound = parse_inbound_email(
                    raw.raw_message,
                    monitored_address=self._monitored_address,
                    fallback_received_at=raw.received_at,
                )
            except EmailParseError:
                failed += 1
                continue

            try:
                outcome = self._ingestion.ingest(inbound)
            except EmailAnalysisFailed:
                failed += 1
                self._mark_seen_or_count_failure(raw.uid)
                continue

            if outcome.created:
                processed += 1
            else:
                duplicates += 1

            if self._notification is not None and outcome.status == "analyzed":
                try:
                    self._notification.notify(outcome.email_id)
                except EmailNotificationFailed:
                    failed += 1
                    continue

            try:
                self._inbox.mark_seen(raw.uid)
            except InboxConnectionError:
                failed += 1

        return InboxSyncSummary(
            fetched=len(raw_messages),
            processed=processed,
            duplicates=duplicates,
            failed=failed,
        )

    def _mark_seen_or_count_failure(self, uid: str) -> bool:
        try:
            self._inbox.mark_seen(uid)
        except InboxConnectionError:
            return False
        return True
