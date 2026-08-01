# Live end-to-end verification — 2026-08-01

## Goal

Verify the complete human-in-the-loop path with real Telegram and Gmail
transports while keeping the recipient controlled and avoiding unrelated inbox
messages.

## Verified journey

1. A stored analyzed email was delivered to the authorized Telegram operator.
2. Pressing Edit moved the reply to `editing` without approval or SMTP use.
3. The bot requested an ordinary text message instead of an `/edit` command.
4. Each submitted revision was shown with Approve & Send and Edit Again buttons.
5. A second edit remained `editing`; no `sent_at` or SMTP Message-ID existed.
6. A separate self-addressed Gmail demo record was used for safe delivery.
7. Telegram approval moved the reply through `approved` to `sent`.
8. PostgreSQL stored `sent_at` and the reserved SMTP Message-ID with no failure.
9. The edit session was removed after approval.
10. The reply was observed in Gmail and only that controlled test message was
    marked read afterward.

## Reliability finding

A temporary network failure initially stopped Telegram long polling. The worker
now catches transient Telegram provider errors, waits briefly, and retries from
the persisted offset. The queued operator message was processed after restart
without duplication.

## Evidence

- Alembic revision: `20260801_02 (head)`
- Automated tests: `120 passed`
- Ruff check: passed
- Ruff format check: passed
- Python compilation: passed
- Telegram worker: live with no current error output
- Unrelated unread Gmail messages changed: `0`

No credentials, email addresses, message bodies, Telegram IDs, or SMTP IDs are
recorded in this checkpoint.
