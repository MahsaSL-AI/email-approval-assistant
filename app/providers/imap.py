import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from imaplib import IMAP4_SSL
from typing import Protocol


class InboxConnectionError(RuntimeError):
    """Safe application error for IMAP connection or protocol failures."""


@dataclass(frozen=True, slots=True)
class RawInboxMessage:
    uid: str
    raw_message: bytes
    received_at: datetime


class InboxClient(Protocol):
    def fetch_unread(self) -> list[RawInboxMessage]: ...

    def mark_seen(self, uid: str) -> None: ...


class GmailImapClient:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        app_password: str,
        timeout_seconds: float = 20.0,
        connection_factory: Callable[..., IMAP4_SSL] = IMAP4_SSL,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._app_password = app_password
        self._timeout_seconds = timeout_seconds
        self._connection_factory = connection_factory

    def fetch_unread(self) -> list[RawInboxMessage]:
        connection = self._open_connection()
        try:
            self._expect_ok(
                connection.select("INBOX", readonly=True),
                "select inbox",
            )
            _, search_data = self._expect_ok(
                connection.uid("search", None, "UNSEEN"),
                "search unread email",
            )
            uids = search_data[0].split() if search_data and search_data[0] else []
            return [self._fetch_one(connection, uid) for uid in uids]
        except InboxConnectionError:
            raise
        except Exception as error:
            raise InboxConnectionError("Unable to read the Gmail inbox.") from error
        finally:
            self._logout_safely(connection)

    def mark_seen(self, uid: str) -> None:
        connection = self._open_connection()
        try:
            self._expect_ok(
                connection.select("INBOX", readonly=False),
                "select writable inbox",
            )
            self._expect_ok(
                connection.uid("store", uid, "+FLAGS.SILENT", r"(\Seen)"),
                "mark email as seen",
            )
        except InboxConnectionError:
            raise
        except Exception as error:
            raise InboxConnectionError("Unable to update the Gmail inbox.") from error
        finally:
            self._logout_safely(connection)

    def _open_connection(self) -> IMAP4_SSL:
        try:
            connection = self._connection_factory(
                self._host,
                self._port,
                timeout=self._timeout_seconds,
            )
            self._expect_ok(
                connection.login(self._username, self._app_password),
                "authenticate",
            )
            return connection
        except Exception as error:
            if isinstance(error, InboxConnectionError):
                raise
            raise InboxConnectionError("Unable to connect to Gmail.") from error

    def _fetch_one(self, connection: IMAP4_SSL, uid: bytes) -> RawInboxMessage:
        _, fetch_data = self._expect_ok(
            connection.uid("fetch", uid, "(BODY.PEEK[] INTERNALDATE)"),
            "fetch email",
        )
        response = next(
            (
                item
                for item in fetch_data
                if isinstance(item, tuple)
                and len(item) == 2
                and isinstance(item[1], bytes)
            ),
            None,
        )
        if response is None:
            raise InboxConnectionError("Gmail returned an invalid email payload.")
        metadata, raw_message = response
        return RawInboxMessage(
            uid=uid.decode("ascii"),
            raw_message=raw_message,
            received_at=_parse_internal_date(metadata),
        )

    @staticmethod
    def _expect_ok(
        response: tuple[str, list[object]],
        operation: str,
    ) -> tuple[str, list[object]]:
        status, data = response
        if status != "OK":
            raise InboxConnectionError(f"Gmail could not {operation}.")
        return status, data

    @staticmethod
    def _logout_safely(connection: IMAP4_SSL) -> None:
        try:
            connection.logout()
        except Exception:
            pass


_INTERNAL_DATE_PATTERN = re.compile(
    rb'INTERNALDATE "(?P<value>\d{1,2}-[A-Za-z]{3}-\d{4} '
    rb'\d{2}:\d{2}:\d{2} [+-]\d{4})"'
)


def _parse_internal_date(metadata: object) -> datetime:
    metadata_bytes = metadata if isinstance(metadata, bytes) else str(metadata).encode()
    match = _INTERNAL_DATE_PATTERN.search(metadata_bytes)
    if match is None:
        return datetime.now(timezone.utc)
    parsed = datetime.strptime(
        match.group("value").decode("ascii"),
        "%d-%b-%Y %H:%M:%S %z",
    )
    return parsed.astimezone(timezone.utc)
