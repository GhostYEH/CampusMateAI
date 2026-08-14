from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _client() -> TestClient:
    settings = Settings(app_env="test", database_url="sqlite:///:memory:", auto_seed_demo_users=True, auto_import_demo=False)
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    return TestClient(create_app())


def _headers(client: TestClient, username: str = "student_demo") -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": "Demo123456"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_provider_list_truthfully_marks_demo_university_unsupported() -> None:
    """[deprecated 兼容层] 委托 EduConnector.detect，demo 大学未配置 → unknown/unsupported。"""
    client = _client()
    response = client.get("/api/v1/academic/providers", headers=_headers(client))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["items"][0]["university_id"] == "uni_demo_university"
    assert data["items"][0]["status"] == "unsupported"
    assert data["items"][0]["supports"] == []


def test_academic_status_has_no_binding_and_never_exposes_credentials() -> None:
    client = _client()
    response = client.get("/api/v1/academic/status", headers=_headers(client))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["last_synced_at"] is None
    assert data["external_student_id"] is None
    serialized = response.text.lower()
    assert "password" not in serialized
    assert "credential_ref" not in serialized


def test_bind_rejects_unsupported_provider_without_persisting_password() -> None:
    client = _client()
    response = client.post(
        "/api/v1/academic/bind",
        headers=_headers(client),
        json={"username": "student-number", "password": "must-not-persist"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "ACADEMIC_UNSUPPORTED"
    assert "must-not-persist" not in response.text


def test_academic_requires_selected_university() -> None:
    client = _client()
    response = client.get("/api/v1/academic/status", headers=_headers(client, "student_demo_01"))
    assert response.status_code == 409
    assert response.json()["code"] == "UNIVERSITY_REQUIRED"
