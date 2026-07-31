# AI Email Approval Assistant

A human-in-the-loop email automation service that analyzes incoming business
email, proposes replies in Telegram, and sends only after explicit approval.

## Current milestone

The initial walking skeleton includes:

- a FastAPI application factory;
- environment-based configuration with secret-safe placeholders;
- a typed health endpoint;
- the reply-state domain rules that prevent pre-approval sending;
- unit and API tests;
- Docker and PostgreSQL development scaffolding.

Live Gmail, AI, Telegram, SMTP, persistence, and migrations are intentionally
deferred to later vertical slices.

## Local setup

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/health` or
`http://127.0.0.1:8000/docs`.

Never put a real Gmail password in `.env`. The test account must use its Google
App Password, and `.env` must remain untracked.

## Verification

```bash
pytest -q
ruff check .
ruff format --check .
```

## Docker Compose

```bash
docker compose up --build
```

The API is exposed at `http://127.0.0.1:8001` and PostgreSQL at host port
`15433`, which avoids conflicting with Project 1.
