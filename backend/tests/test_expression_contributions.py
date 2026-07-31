from pathlib import Path

from fastapi.testclient import TestClient

from app.api.routes import contributions
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


def _student_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "student_demo", "password": "Demo123456"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_expression_sample_requires_consent_and_can_be_deleted(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(contributions, "_storage_dir", lambda: tmp_path)
    client = _client()
    headers = _student_headers(client)

    rejected = client.post(
        "/api/v1/contributions/expression-samples",
        headers=headers,
        data={"label": "HAPPY", "consent": "false"},
        files={"image": ("face.jpg", b"fake-image", "image/jpeg")},
    )
    assert rejected.status_code == 403

    accepted = client.post(
        "/api/v1/contributions/expression-samples",
        headers=headers,
        data={"label": "HAPPY", "consent": "true", "model_version": "test-v1"},
        files={"image": ("face.jpg", b"fake-image", "image/jpeg")},
    )
    assert accepted.status_code == 200
    sample_id = accepted.json()["sample_id"]
    assert (tmp_path / f"{sample_id}.jpg").exists()
    assert (tmp_path / f"{sample_id}.json").exists()

    deleted = client.delete(
        f"/api/v1/contributions/expression-samples/{sample_id}",
        headers=headers,
    )
    assert deleted.status_code == 200
    assert not (tmp_path / f"{sample_id}.jpg").exists()
    assert not (tmp_path / f"{sample_id}.json").exists()
