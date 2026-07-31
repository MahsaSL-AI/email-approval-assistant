from dataclasses import dataclass

from app.processing.email_parser import EmailParseError, parse_inbound_email
from app.providers.imap import InboxClient, InboxConnectionError
from app.services.email_ingestion import EmailAnalysisFailed, EmailIngestionService


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
    ) -> None:
        self._inbox = inbox
        self._ingestion = ingestion
        self._monitored_address = monitored_address

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
