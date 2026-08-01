# SMTP delivery checkpoint — 2026-08-01

## Outcome

Approved replies can now be delivered through a replaceable SMTP provider and
the `POST /api/emails/{email_id}/send` endpoint.

## Safety properties

- SMTP is rejected for every state except `approved`.
- The outbound message replies to the original sender and carries
  `In-Reply-To` and `References` headers.
- A Message-ID is reserved and persisted before the network call.
- Provider acceptance changes the state to `sent` and records `sent_at`.
- A provider error changes the state to terminal `failed` with a safe reason.
- A reserved Message-ID blocks automatic retry after an ambiguous interruption,
  preventing accidental duplicate replies.
- Credentials are injected through settings and never included in errors.

## Verification evidence

- 78 automated tests passed using a fake SMTP connection and fake delivery
  provider; no real email was sent.
- SMTP TLS/login/header behavior, refusal handling, state gating, success,
  failure, ambiguous retry, and API status mapping are covered.
- PostgreSQL remained healthy and Alembic was at `20260731_01 (head)` before
  this milestone.

## Next step

Build the Telegram notification and operator interaction boundary on top of the
same reply workflow. Live verification will require a bot token and authorized
operator ID.
