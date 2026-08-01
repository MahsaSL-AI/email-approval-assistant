# Telegram live transport checkpoint — 2026-08-01

## Outcome

The Telegram Bot API transport and automation workers are implemented without
starting unrestricted live inbox processing.

## Implemented behavior

- Long-poll `getUpdates` requests accept a persisted offset and only request
  message and callback-query updates.
- Callback queries are answered so Telegram clients stop showing progress.
- Result messages are sent to the single authorized private operator.
- Runtime offsets are written atomically under ignored `.runtime/` state.
- Business actions remain committed even when Telegram acknowledgement fails;
  replay is avoided because a repeated approval could otherwise duplicate an
  email delivery.
- Successful ingestion sends the analysis and draft to Telegram before Gmail is
  marked seen.
- A temporary Telegram failure leaves the Gmail message unread and the database
  record analyzed so the next poll can retry.
- Already-notified duplicate emails are marked seen without another Telegram
  notification.
- Docker Compose contains opt-in `email-worker` and `telegram-bot` services under
  the `automation` profile.

## Verification evidence

- 114 tests passed.
- Ruff lint and format checks passed for 96 files.
- Python compilation passed for app, tests, and scripts.
- `docker compose --profile automation config --quiet` passed.
- The bot token was detected in ignored `.env` without printing it.
- No private `/start` update was available yet, so the numeric operator ID and
  live Bot API acknowledgement remain pending.

## Safety hold

The automation profile has not been started because five unrelated unread Gmail
messages remain in the test inbox. They must be marked read or otherwise removed
from the unread set before unrestricted polling is enabled.
