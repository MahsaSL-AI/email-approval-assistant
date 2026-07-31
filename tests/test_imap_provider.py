from datetime import datetime, timezone

import pytest

from app.providers.imap import GmailImapClient, InboxConnectionError

RAW_ONE = b"Message-ID: <one@example.test>\r\nFrom: sender@example.test\r\n\r\nFirst"
RAW_TWO = b"Message-ID: <two@example.test>\r\nFrom: sender@example.test\r\n\r\nSecond"


def make_client(connection: object) -> GmailImapClient:
    return GmailImapClient(
        host="imap.gmail.test",
        port=993,
        username="test@example.test",
        app_password="synthetic-app-password",
        connection_factory=lambda *args, **kwargs: connection,
    )


def test_fetch_unread_uses_peek_and_returns_raw_messages() -> None:
    connection = FakeImapConnection()

    messages = make_client(connection).fetch_unread()

    assert [message.uid for message in messages] == ["101", "102"]
    assert [message.raw_message for message in messages] == [RAW_ONE, RAW_TWO]
    assert messages[0].received_at == datetime(2026, 7, 31, 10, 30, tzinfo=timezone.utc)
    fetch_calls = [call for call in connection.uid_calls if call[0] == "fetch"]
    assert fetch_calls == [
        ("fetch", b"101", "(BODY.PEEK[] INTERNALDATE)"),
        ("fetch", b"102", "(BODY.PEEK[] INTERNALDATE)"),
    ]
    assert connection.select_calls == [("INBOX", True)]
    assert connection.logged_out is True


def test_empty_unread_search_returns_empty_list() -> None:
    connection = FakeImapConnection(search_data=b"")

    messages = make_client(connection).fetch_unread()

    assert messages == []
    assert not any(call[0] == "fetch" for call in connection.uid_calls)


def test_mark_seen_uses_uid_store_on_writable_inbox() -> None:
    connection = FakeImapConnection()

    make_client(connection).mark_seen("101")

    assert connection.select_calls == [("INBOX", False)]
    assert ("store", "101", "+FLAGS.SILENT", r"(\Seen)") in connection.uid_calls
    assert connection.logged_out is True


def test_protocol_failure_becomes_safe_error_and_logs_out() -> None:
    connection = FakeImapConnection(select_status="NO")

    with pytest.raises(InboxConnectionError, match="select inbox"):
        make_client(connection).fetch_unread()

    assert connection.logged_out is True


def test_login_failure_does_not_expose_password() -> None:
    connection = FakeImapConnection(login_status="NO")

    with pytest.raises(InboxConnectionError) as error_info:
        make_client(connection).fetch_unread()

    assert "synthetic-app-password" not in str(error_info.value)


class FakeImapConnection:
    def __init__(
        self,
        *,
        login_status: str = "OK",
        select_status: str = "OK",
        search_data: bytes = b"101 102",
    ) -> None:
        self.login_status = login_status
        self.select_status = select_status
        self.search_data = search_data
        self.select_calls: list[tuple[str, bool]] = []
        self.uid_calls: list[tuple[object, ...]] = []
        self.logged_out = False

    def login(self, username: str, password: str):
        del username, password
        return self.login_status, [b"login"]

    def select(self, mailbox: str, readonly: bool = False):
        self.select_calls.append((mailbox, readonly))
        return self.select_status, [b"2"]

    def uid(self, command: str, *args: object):
        self.uid_calls.append((command, *args))
        if command == "search":
            return "OK", [self.search_data]
        if command == "fetch":
            uid = args[0]
            raw_message = RAW_ONE if uid == b"101" else RAW_TWO
            metadata = (
                b'1 (UID 101 INTERNALDATE "31-Jul-2026 14:00:00 +0330" BODY[] {10}'
            )
            return "OK", [(metadata, raw_message), b")"]
        if command == "store":
            return "OK", [b""]
        raise AssertionError(f"Unexpected UID command: {command}")

    def logout(self):
        self.logged_out = True
        return "BYE", [b"logout"]
