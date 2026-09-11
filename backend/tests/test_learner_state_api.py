from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _client():
    container = reset_container_for_tests(
        Settings(
            app_env="test",
            database_url="sqlite:///:memory:",
            auto_seed_demo_users=True,
            auto_import_demo=False,
            llm_provider="none",
        )
    )
    seed_demo_data(container, force=True)
    return container, TestClient(create_app())


def _login(client, username):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Demo123456"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_learner_state_api_requires_student_auth_and_never_returns_raw_payload():
    container, client = _client()
    assert client.get("/api/v1/learner-state/snapshots").status_code == 401
    headers = _login(client, "student_demo")
    response = client.get("/api/v1/learner-state/snapshots", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    assert all("payload" not in item for item in body["items"])
    assert all("mastered" not in str(item).lower() for item in body["items"])
    evidence = client.get(
        f"/api/v1/learner-state/snapshots/{body['items'][0]['snapshot_id']}/evidence",
        headers=headers,
    )
    assert evidence.status_code == 200
    assert all("source_id" not in item and "row_id" not in item for item in evidence.json()["items"])


def test_learner_state_api_rejects_admin_and_cross_user_snapshot_is_404():
    container, client = _client()
    admin_headers = _login(client, "admin_demo")
    assert client.get("/api/v1/learner-state/snapshots", headers=admin_headers).status_code == 403
    student_headers = _login(client, "student_demo")
    response = client.get("/api/v1/learner-state/snapshots", headers=student_headers)
    snapshot_id = response.json()["items"][0]["snapshot_id"]
    other_headers = _login(client, "student_demo_01")
    assert client.get(
        f"/api/v1/learner-state/snapshots/{snapshot_id}/evidence",
        headers=other_headers,
    ).status_code == 404
