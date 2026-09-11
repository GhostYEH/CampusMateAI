"""Phase 6A: 世界模型删除测试。"""
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
        username="del_student", password_hash=hash_password("Demo123456"), role="student", display_name="S"
    )
    client = TestClient(create_app())
    resp = client.post("/api/v1/auth/login", json={"username": "del_student", "password": "Demo123456"})
    auth = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    return client, container, auth, student.id


def test_delete_state_only():
    client, _c, auth, _u = _setup()
    resp = client.post("/api/v1/learner-state/delete-request", json={"scope": "STATE_ONLY", "idempotency_key": "d1"}, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["status"] == "COMPLETED"
    assert resp.json()["scope"] == "STATE_ONLY"


def test_delete_events_and_state():
    client, _c, auth, _u = _setup()
    resp = client.post("/api/v1/learner-state/delete-request", json={"scope": "EVENTS_AND_STATE", "idempotency_key": "d2"}, headers=auth)
    assert resp.status_code == 200


def test_delete_knowledge_only():
    client, _c, auth, _u = _setup()
    resp = client.post("/api/v1/learner-state/delete-request", json={"scope": "KNOWLEDGE_ONLY", "idempotency_key": "d3"}, headers=auth)
    assert resp.status_code == 200


def test_delete_plans_only():
    client, _c, auth, _u = _setup()
    resp = client.post("/api/v1/learner-state/delete-request", json={"scope": "PLANS_ONLY", "idempotency_key": "d4"}, headers=auth)
    assert resp.status_code == 200


def test_delete_model_shadow_only():
    client, _c, auth, _u = _setup()
    resp = client.post("/api/v1/learner-state/delete-request", json={"scope": "MODEL_SHADOW_ONLY", "idempotency_key": "d5"}, headers=auth)
    assert resp.status_code == 200


def test_delete_all_learner_model_data():
    client, _c, auth, _u = _setup()
    resp = client.post("/api/v1/learner-state/delete-request", json={"scope": "ALL_LEARNER_MODEL_DATA", "idempotency_key": "d6"}, headers=auth)
    assert resp.status_code == 200


def test_delete_idempotent():
    """重复删除保持幂等。"""
    client, _c, auth, _u = _setup()
    r1 = client.post("/api/v1/learner-state/delete-request", json={"scope": "STATE_ONLY", "idempotency_key": "idem1"}, headers=auth)
    r2 = client.post("/api/v1/learner-state/delete-request", json={"scope": "STATE_ONLY", "idempotency_key": "idem2"}, headers=auth)
    assert r1.status_code == 200
    assert r2.status_code == 200


def test_delete_status():
    client, _c, auth, _u = _setup()
    client.post("/api/v1/learner-state/delete-request", json={"scope": "STATE_ONLY", "idempotency_key": "ds1"}, headers=auth)
    resp = client.get("/api/v1/learner-state/delete-status", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["latest"] is not None


def test_delete_counts_no_table_names():
    """计数摘要不暴露内部表名。"""
    client, _c, auth, _u = _setup()
    resp = client.post("/api/v1/learner-state/delete-request", json={"scope": "STATE_ONLY", "idempotency_key": "ct1"}, headers=auth)
    data = resp.json()
    for key in data["before_counts"]:
        assert "table" not in key.lower()
        assert "sql" not in key.lower()


def test_delete_does_not_remove_account():
    """删除不影响用户账号。"""
    client, _c, auth, _u = _setup()
    client.post("/api/v1/learner-state/delete-request", json={"scope": "ALL_LEARNER_MODEL_DATA", "idempotency_key": "acc1"}, headers=auth)
    resp = client.get("/api/v1/learner-state/data-summary", headers=auth)
    assert resp.status_code == 200


def test_admin_forbidden():
    settings = Settings(app_env="test", database_url="sqlite:///:memory:")
    container = reset_container_for_tests(settings)
    container.user_repository.create_user(username="del_admin", password_hash=hash_password("Demo123456"), role="admin", display_name="A")
    client = TestClient(create_app())
    resp = client.post("/api/v1/auth/login", json={"username": "del_admin", "password": "Demo123456"})
    auth = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    r = client.post("/api/v1/learner-state/delete-request", json={"scope": "STATE_ONLY", "idempotency_key": "a1"}, headers=auth)
    assert r.status_code == 403