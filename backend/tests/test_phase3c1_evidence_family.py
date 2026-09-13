from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


SAFE_EVIDENCE_FIELDS = {
    "evidence_kind", "source_category", "event_id", "event_type", "occurred_at",
    "data_quality", "role", "explanation_code",
}


def _setup():
    container = reset_container_for_tests(
        Settings(
            app_env="test", database_url="sqlite:///:memory:",
            auto_seed_demo_users=True, auto_import_demo=False, llm_provider="none",
        )
    )
    seed_demo_data(container, force=True)
    return container, TestClient(create_app())


def _login(client, username):
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": "Demo123456"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_core_snapshot_evidence_query_remains_successful():
    container, client = _setup()
    headers = _login(client, "student_demo")
    snapshot = client.get("/api/v1/learner-state/snapshots", headers=headers).json()["items"][0]

    response = client.get(
        f"/api/v1/learner-state/snapshots/{snapshot['snapshot_id']}/evidence",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["page"] == 1
    assert response.json()["page_size"] == 50


def test_snapshot_evidence_unknown_id_is_404():
    container, client = _setup()

    unknown = client.get(
        "/api/v1/learner-state/snapshots/not-a-real-snapshot/evidence",
        headers=_login(client, "student_demo"),
    )

    assert unknown.status_code == 404
