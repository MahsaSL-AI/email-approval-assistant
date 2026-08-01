from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from app.api.routes.delivery import get_reply_delivery_service
from app.domain.reply_state import InvalidReplyTransition
from app.domain.reply_views import ReplyView
from app.main import app
from app.services.reply_delivery import ReplyDeliveryFailed

EMAIL_ID = UUID("11111111-1111-4111-8111-111111111111")


class FakeDeliveryService:
    def send(self, email_id: UUID) -> ReplyView:
        now = datetime(2026, 8, 1, tzinfo=timezone.utc)
        return ReplyView(
            email_id=email_id,
            text="Approved reply",
            status="sent",
            approved_at=now,
            rejected_at=None,
            sent_at=now,
        )


def test_send_endpoint_returns_sent_after_acceptance() -> None:
    app.dependency_overrides[get_reply_delivery_service] = FakeDeliveryService
    try:
        response = TestClient(app).post(f"/api/emails/{EMAIL_ID}/send")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "sent"


def test_unapproved_send_maps_to_conflict() -> None:
    class UnapprovedService(FakeDeliveryService):
        def send(self, email_id: UUID) -> ReplyView:
            raise InvalidReplyTransition("SMTP send requires approved status.")

    app.dependency_overrides[get_reply_delivery_service] = UnapprovedService
    try:
        response = TestClient(app).post(f"/api/emails/{EMAIL_ID}/send")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409


def test_delivery_failure_maps_to_bad_gateway() -> None:
    class FailedDeliveryService(FakeDeliveryService):
        def send(self, email_id: UUID) -> ReplyView:
            raise ReplyDeliveryFailed("Delivery failed safely.")

    app.dependency_overrides[get_reply_delivery_service] = FailedDeliveryService
    try:
        response = TestClient(app).post(f"/api/emails/{EMAIL_ID}/send")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json() == {"detail": "Delivery failed safely."}
