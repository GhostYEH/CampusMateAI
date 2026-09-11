"""Phase 6A: 数据源控制测试。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.security import hash_password

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests


def _setup():
    settings = Settings(app_env="test", database_url="sqlite:///:memory:")
    container = reset_container_for_tests(settings)
    student = container.user_repository.create_user(
        username="dc_student", password_hash=hash_password("Demo123456"), role="student", display_name="S"
    )
    client = TestClient(create_app())
    resp = client.post("/api/v1/auth/login", json={"username": "dc_student", "password": "Demo123456"})
    auth = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    return client, container, auth, student.id


def test_list_all_sources():
    client, _c, auth, _u = _setup()
    resp = client.get("/api/v1/learner-state/data-controls", headers=auth)
    assert resp.status_code == 200
    keys = {item["source_key"] for item in resp.json()["items"]}
    expected = {"CORE_STUDY", "PERSONAL_TASK", "CHAOXING", "EDU", "PRACTICE", "MODEL_SHADOW", "PROACTIVE_SUGGESTIONS"}
    assert keys == expected


def test_pause_source():
    client, _c, auth, _u = _setup()
    resp = client.put(
        "/api/v1/learner-state/data-controls/CHAOXING",
        json={"status": "PAUSED", "idempotency_key": "p1"},
        headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "PAUSED"


def test_resume_source():
    client, _c, auth, _u = _setup()
    client.put("/api/v1/learner-state/data-controls/EDU", json={"status": "PAUSED", "idempotency_key": "p1"}, headers=auth)
    resp = client.put("/api/v1/learner-state/data-controls/EDU", json={"status": "ENABLED", "idempotency_key": "r1"}, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ENABLED"


def test_pause_model_shadow():
    client, _c, auth, _u = _setup()
    resp = client.put("/api/v1/learner-state/data-controls/MODEL_SHADOW", json={"status": "PAUSED", "idempotency_key": "ms1"}, headers=auth)
    assert resp.status_code == 200


def test_pause_proactive_suggestions():
    client, _c, auth, _u = _setup()
    resp = client.put("/api/v1/learner-state/data-controls/PROACTIVE_SUGGESTIONS", json={"status": "PAUSED", "idempotency_key": "ps1"}, headers=auth)
    assert resp.status_code == 200


def test_unsupported_source():
    client, _c, auth, _u = _setup()
    resp = client.put("/api/v1/learner-state/data-controls/UNKNOWN", json={"status": "PAUSED", "idempotency_key": "u1"}, headers=auth)
    assert resp.status_code in (400, 404)


def test_cross_user_isolated():
    settings = Settings(app_env="test", database_url="sqlite:///:memory:")
    container = reset_container_for_tests(settings)
    container.user_repository.create_user(username="dc_a", password_hash=hash_password("Demo123456"), role="student", display_name="A")
    container.user_repository.create_user(username="dc_b", password_hash=hash_password("Demo123456"), role="student", display_name="B")
    client = TestClient(create_app())
    ra = client.post("/api/v1/auth/login", json={"username": "dc_a", "password": "Demo123456"})
    rb = client.post("/api/v1/auth/login", json={"username": "dc_b", "password": "Demo123456"})
    auth_a = {"Authorization": f"Bearer {ra.json()['access_token']}"}
    auth_b = {"Authorization": f"Bearer {rb.json()['access_token']}"}
    client.put("/api/v1/learner-state/data-controls/CHAOXING", json={"status": "PAUSED", "idempotency_key": "a1"}, headers=auth_a)
    resp_b = client.get("/api/v1/learner-state/data-controls", headers=auth_b)
    for item in resp_b.json()["items"]:
        if item["source_key"] == "CHAOXING":
            assert item["status"] == "ENABLED"


def test_admin_forbidden():
    settings = Settings(app_env="test", database_url="sqlite:///:memory:")
    container = reset_container_for_tests(settings)
    container.user_repository.create_user(username="dc_admin", password_hash=hash_password("Demo123456"), role="admin", display_name="A")
    client = TestClient(create_app())
    resp = client.post("/api/v1/auth/login", json={"username": "dc_admin", "password": "Demo123456"})
    auth = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    r = client.get("/api/v1/learner-state/data-controls", headers=auth)
    assert r.status_code == 403