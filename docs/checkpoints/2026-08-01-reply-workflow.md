# Reply workflow checkpoint — 2026-08-01

## Outcome

The human decision workflow is now available through application services and
FastAPI endpoints. An operator can edit a draft repeatedly, explicitly approve
it, or reject it.

## Enforced invariant

- The first edit changes `pending` to `editing`.
- Further edits keep the reply in `editing`.
- Editing never authorizes email delivery.
- Only an explicit approve action changes `pending` or `editing` to `approved`.
- A rejection changes `pending` or `editing` to terminal `rejected`.
- Approved, rejected, sent, and failed replies cannot return to editing.

## API surface

- `PUT /api/emails/{email_id}/reply`
- `POST /api/emails/{email_id}/approve`
- `POST /api/emails/{email_id}/reject`

## Verification evidence

- Git integrity: `git fsck --full` passed with no output.
- Working tree was clean before this milestone.
- Test suite: 67 tests passed.
- Ruff lint passed and 64 files matched Ruff formatting.
- Python bytecode compilation passed before this milestone.
- Docker Compose configuration validated.
- PostgreSQL container became healthy on host port `15433`.
- Alembic reported `20260731_01 (head)`.

## Known technical debt

- Project 2 is temporarily using Project 1's virtual environment for local
  checks. A dedicated environment will be created before final handoff.
- Starlette emits one upstream `TestClient` deprecation warning.
- SMTP sending and Telegram interaction are not implemented yet.

## Next step

Add an SMTP provider boundary and a send service that can only execute from an
`approved` reply, with failure-safe state and mocked delivery tests.
