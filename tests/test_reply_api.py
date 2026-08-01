from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from app.api.routes.replies import get_reply_workflow_service
from app.domain.reply_state import InvalidReplyTransition
from app.domain.reply_views import ReplyView
from app.main import app
from app.services.reply_workflow import ReplyNotFoundError

EMAIL_ID = UUID("11111111-1111-4111-8111-111111111111")


class FakeReplyService:
    def edit(self, email_id: UUID, text: str) -> ReplyView:
        return self._view(email_id, text.strip(), "editing")

    def approve(self, email_id: UUID) -> ReplyView:
        return self._view(email_id, "Approved draft", "approved")

    def reject(self, email_id: UUID) -> ReplyView:
        return self._view(email_id, "Rejected draft", "rejected")

    @staticmethod
    def _view(email_id: UUID, text: str, status: str) -> ReplyView:
        now = datetime(2026, 8, 1, tzinfo=timezone.utc)
        return ReplyView(
            email_id=email_id,
            text=text,
            status=status,
            approved_at=now if status == "approved" else None,
            rejected_at=now if status == "rejected" else None,
            sent_at=None,
        )


def call(method: str, path: str, **kwargs):
    app.dependency_overrides[get_reply_workflow_service] = FakeReplyService
    try:
        return TestClient(app).request(method, path, **kwargs)
    finally:
        app.dependency_overrides.clear()


def test_edit_endpoint_keeps_reply_in_editing() -> None:
    response = call(
        "PUT",
        f"/api/emails/{EMAIL_ID}/reply",
        json={"text": " Revised draft "},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "editing"
    assert response.json()["text"] == "Revised draft"


def test_approve_endpoint_requires_explicit_action() -> None:
    response = call("POST", f"/api/emails/{EMAIL_ID}/approve")

    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_reject_endpoint_returns_rejected() -> None:
    response = call("POST", f"/api/emails/{EMAIL_ID}/reject")

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_empty_edit_is_rejected_by_validation() -> None:
    response = call("PUT", f"/api/emails/{EMAIL_ID}/reply", json={"text": ""})

    assert response.status_code == 422


def test_missing_reply_maps_to_404() -> None:
    class MissingReplyService(FakeReplyService):
        def approve(self, email_id: UUID) -> ReplyView:
            raise ReplyNotFoundError

    app.dependency_overrides[get_reply_workflow_service] = MissingReplyService
    try:
        response = TestClient(app).post(f"/api/emails/{EMAIL_ID}/approve")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_invalid_transition_maps_to_409() -> None:
    class InvalidReplyService(FakeReplyService):
        def approve(self, email_id: UUID) -> ReplyView:
            raise InvalidReplyTransition("Already rejected.")

    app.dependency_overrides[get_reply_workflow_service] = InvalidReplyService
    try:
        response = TestClient(app).post(f"/api/emails/{EMAIL_ID}/approve")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json() == {"detail": "Already rejected."}
