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


def test_study_session_persists_its_mode() -> None:
    client = _client()
    headers = _headers(client)

    created = client.post(
        "/api/v1/study/sessions",
        headers=headers,
        json={"mode": "short_break"},
    )

    assert created.status_code == 201
    assert created.json()["mode"] == "short_break"
    assert client.get("/api/v1/study/sessions", headers=headers).json()[0]["mode"] == "short_break"


def test_study_session_rejects_an_unknown_mode() -> None:
    client = _client()

    response = client.post(
        "/api/v1/study/sessions",
        headers=_headers(client),
        json={"mode": "nap"},
    )

    assert response.status_code == 422
