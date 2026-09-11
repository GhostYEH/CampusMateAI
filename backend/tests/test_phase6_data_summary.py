"""Phase 6A: 数据摘要测试。"""
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
        username="sum_student", password_hash=hash_password("Demo123456"), role="student", display_name="S"
    )
    client = TestClient(create_app())
    resp = client.post("/api/v1/auth/login", json={"username": "sum_student", "password": "Demo123456"})
    auth = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    return client, container, auth, student.id


def test_summary_fields():
    client, _c, auth, _u = _setup()
    resp = client.get("/api/v1/learner-state/data-summary", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    expected = {
        "event_count", "snapshot_count", "knowledge_snapshot_count",
        "misconception_count", "correction_count", "learning_plan_count",
        "plan_feedback_count", "plan_evaluation_count", "shadow_run_count",
        "enabled_sources", "paused_sources", "oldest_recorded_at",
        "newest_recorded_at", "estimator_versions", "planner_versions",
        "evaluator_versions",
    }
    assert expected.issubset(set(data.keys()))


def test_summary_no_sensitive():
    client, _c, auth, _u = _setup()
    resp = client.get("/api/v1/learner-state/data-summary", headers=auth)
    data = resp.json()
    for forbidden in ("payload", "source_id", "prompt", "table_name", "raw", "content", "answer", "token"):
        assert forbidden not in data


def test_summary_sources_partition():
    client, _c, auth, _u = _setup()
    resp = client.get("/api/v1/learner-state/data-summary", headers=auth)
    data = resp.json()
    enabled = set(data["enabled_sources"])
    paused = set(data["paused_sources"])
    assert enabled.isdisjoint(paused)


def test_summary_after_pause():
    client, _c, auth, _u = _setup()
    client.put("/api/v1/learner-state/data-controls/CHAOXING", json={"status": "PAUSED", "idempotency_key": "p1"}, headers=auth)
    resp = client.get("/api/v1/learner-state/data-summary", headers=auth)
    data = resp.json()
    assert "CHAOXING" in data["paused_sources"]
    assert "CHAOXING" not in data["enabled_sources"]


def test_admin_forbidden():
    settings = Settings(app_env="test", database_url="sqlite:///:memory:")
    container = reset_container_for_tests(settings)
    container.user_repository.create_user(username="sum_admin", password_hash=hash_password("Demo123456"), role="admin", display_name="A")
    client = TestClient(create_app())
    resp = client.post("/api/v1/auth/login", json={"username": "sum_admin", "password": "Demo123456"})
    auth = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    r = client.get("/api/v1/learner-state/data-summary", headers=auth)
    assert r.status_code == 403