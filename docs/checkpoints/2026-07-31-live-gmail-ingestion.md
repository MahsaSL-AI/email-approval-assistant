# Live Gmail ingestion checkpoint — 2026-07-31

## Outcome

The first real Gmail-to-PostgreSQL ingestion completed successfully using the
local deterministic fake analyzer. The targeted synthetic message was selected
without touching five unrelated unread messages.

## Safety controls

- The initial unrestricted sync was stopped because six unread messages existed
  instead of the expected one.
- A reusable script selected exactly one unread message by a non-sensitive body
  token and aborted unless the match count was exactly one.
- No credential, sender, recipient, Message-ID, or email body was printed.
- Gmail fetching used `BODY.PEEK[]`; only the selected synthetic message was
  explicitly marked seen after database persistence.

## Verification evidence

- Gmail IMAP authentication and unread search succeeded with the configured App
  Password.
- Target match count: 1; parse failures: 0.
- The ingestion outcome was newly created with `analyzed` status.
- PostgreSQL contains one email, one analysis, one suggested reply, and two
  processing logs.
- The stored analysis uses fake-provider category `other` and priority `normal`.
- The reply state is `pending`, so SMTP remains forbidden.
- Gmail unread count decreased from six to five, proving only the target message
  was marked seen.
- PostgreSQL migration upgrade/downgrade/upgrade passed and the database is at
  revision `20260731_01 (head)`.

## Limitation

This checkpoint validates live IMAP and real persistence, but not semantic AI,
Telegram notification, human approval, or SMTP sending.

## Next smallest step

Implement email list/detail APIs, then add the structured real AI provider
behind the existing replaceable analyzer boundary.
