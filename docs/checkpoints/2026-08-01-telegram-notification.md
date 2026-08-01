# Telegram notification boundary — 2026-08-01

## Outcome

The application can format an analyzed email for one Telegram operator and send
it through a replaceable Bot API provider.

The notification contains sender, original subject, received time, AI summary,
category, priority, suggested reply, and inline Approve, Reject, and Edit
buttons. Every callback carries the email UUID and remains below Telegram's
callback data limit.

## Verification evidence

- 84 automated tests passed with an HTTP mock; no real Telegram token was used.
- Tests cover message context, missing subject, button callback data, Bot API
  payload, message ID extraction, HTTP errors, invalid Bot API results, and
  secret-safe exceptions.
- Ruff lint passed; formatting was applied to the one reported test file.

## Remaining Telegram work

- Trigger the notification after successful ingestion.
- Poll or receive Bot API updates.
- Authorize the single configured operator.
- Handle Approve, Reject, and Edit callbacks and call `answerCallbackQuery`.
- Keep Edit in `editing` until a later explicit Approve action.
- Perform a live synthetic Telegram test with local ignored credentials.

## External setup needed later

A Telegram bot token and the authorized operator's numeric Telegram ID must be
placed only in the ignored local `.env` file.
