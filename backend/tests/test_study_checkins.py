from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _client() -> TestClient:
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        auto_import_demo=False,
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    return TestClient(create_app())


def _headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "student_demo", "password": "Demo123456"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_checkin_is_persisted_and_daily_duplicate_is_idempotent() -> None:
    client = _client()
    headers = _headers(client)

    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["study_checkins_supported"] is True

    created = client.post(
        "/api/v1/study/checkins",
        headers=headers,
        json={"scene": "snow"},
    )

    assert created.status_code == 201
    assert created.json()["created"] is True
    assert created.json()["checkin"]["scene"] == "snow"

    duplicate = client.post(
        "/api/v1/study/checkins",
        headers=headers,
        json={"scene": "rain"},
    )

    assert duplicate.status_code == 200
    assert duplicate.json()["created"] is False
    assert duplicate.json()["checkin"]["scene"] == "snow"

    summary = client.get("/api/v1/study/checkins", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["total"] == 1
    assert summary.json()["today_checked"] is True
    assert summary.json()["items"][0]["scene"] == "snow"
