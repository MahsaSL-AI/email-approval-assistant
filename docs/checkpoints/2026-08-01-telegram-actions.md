# Telegram action logic — 2026-08-01

## Outcome

Telegram callback and edit-command logic now maps operator actions onto the
existing reply workflow.

- Approve explicitly transitions the draft and then invokes SMTP delivery.
- Reject never invokes delivery.
- Edit starts or preserves `editing` without authorizing delivery.
- `/edit <email-id> <revised reply>` saves another revision and remains
  `editing` until a later Approve callback.
- Both the sender ID and private chat ID must match the configured operator.
- Malformed callback data, UUIDs, and edit commands are rejected before any
  state change.

## Verification evidence

- 95 automated tests passed before this checkpoint.
- Tests cover action routing, ordering of approve-before-send, rejection,
  editing, repeated edit sessions, unauthorized users, malformed callback data,
  malformed commands, and terminal-state protection.

## Remaining integration

The pure action logic still needs a Bot API update adapter that calls
`getUpdates`, `answerCallbackQuery`, and sends action-result messages. Live
integration also requires local ignored Telegram credentials.
