from fastapi.testclient import TestClient

from app.api.routes.inbox import get_inbox_sync_service
from app.main import app
from app.services.inbox_sync import InboxSyncSummary


def test_sync_endpoint_returns_workflow_summary() -> None:
    app.dependency_overrides[get_inbox_sync_service] = lambda: FakeSyncService()
    try:
        response = TestClient(app).post("/api/emails/sync")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "fetched": 3,
        "processed": 1,
        "duplicates": 1,
        "failed": 1,
    }


class FakeSyncService:
    def sync(self) -> InboxSyncSummary:
        return InboxSyncSummary(
            fetched=3,
            processed=1,
            duplicates=1,
            failed=1,
        )
