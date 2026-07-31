from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from app.api.routes.emails import get_email_query_service
from app.domain.email_views import EmailDetail, EmailListItem, EmailPage
from app.main import app
from app.services.email_query import EmailNotFoundError

EMAIL_ID = UUID("11111111-1111-4111-8111-111111111111")


def test_list_emails_returns_paginated_response() -> None:
    app.dependency_overrides[get_email_query_service] = lambda: FakeQueryService()
    try:
        response = TestClient(app).get("/api/emails?page=2&page_size=5")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 6
    assert payload["page"] == 2
    assert payload["page_size"] == 5
    assert payload["items"][0]["id"] == str(EMAIL_ID)
    assert payload["items"][0]["reply_status"] == "pending"


def test_get_email_returns_detail() -> None:
    app.dependency_overrides[get_email_query_service] = lambda: FakeQueryService()
    try:
        response = TestClient(app).get(f"/api/emails/{EMAIL_ID}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["subject"] == "Synthetic request"
    assert payload["summary"] == "Synthetic summary"
    assert payload["suggested_reply"] == "Synthetic reply"


def test_get_missing_email_returns_404() -> None:
    app.dependency_overrides[get_email_query_service] = lambda: FakeQueryService()
    try:
        response = TestClient(app).get(
            "/api/emails/22222222-2222-4222-8222-222222222222"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Email was not found."}


class FakeQueryService:
    def list(self, *, page: int, page_size: int) -> EmailPage:
        return EmailPage(
            items=[
                EmailListItem(
                    id=EMAIL_ID,
                    sender="customer@example.test",
                    subject="Synthetic request",
                    received_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
                    processing_status="analyzed",
                    category="support",
                    priority="high",
                    reply_status="pending",
                )
            ],
            total=6,
            page=page,
            page_size=page_size,
        )

    def get(self, email_id: UUID) -> EmailDetail:
        if email_id != EMAIL_ID:
            raise EmailNotFoundError
        return EmailDetail(
            id=EMAIL_ID,
            external_message_id="<synthetic@example.test>",
            sender="customer@example.test",
            recipient="business@example.test",
            subject="Synthetic request",
            body_text="Synthetic body",
            received_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
            processing_status="analyzed",
            failure_reason=None,
            summary="Synthetic summary",
            category="support",
            priority="high",
            language="en",
            sentiment="neutral",
            confidence=0.9,
            suggested_reply="Synthetic reply",
            reply_status="pending",
            approved_at=None,
            rejected_at=None,
            sent_at=None,
        )
