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


def test_daily_goal_is_created_for_authenticated_user_and_persisted() -> None:
    client = _client()
    headers = _headers(client)

    initial = client.get("/api/v1/study/goals/daily", headers=headers)

    assert initial.status_code == 200
    assert initial.json()["target_minutes"] == 60

    updated = client.put(
        "/api/v1/study/goals/daily",
        headers=headers,
        json={"target_minutes": 90},
    )

    assert updated.status_code == 200
    assert updated.json()["target_minutes"] == 90
    assert client.get("/api/v1/study/goals/daily", headers=headers).json()["target_minutes"] == 90


def test_daily_goal_rejects_values_outside_supported_range() -> None:
    client = _client()
    headers = _headers(client)

    assert client.put(
        "/api/v1/study/goals/daily",
        headers=headers,
        json={"target_minutes": 14},
    ).status_code == 422
    assert client.put(
        "/api/v1/study/goals/daily",
        headers=headers,
        json={"target_minutes": 481},
    ).status_code == 422
