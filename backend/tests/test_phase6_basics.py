"""Phase 6A 基础设施验证：确认后端能启动且新 API 可路由。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.container import reset_container_for_tests


def _setup():
    settings = Settings(app_env="test", database_url="sqlite:///:memory:")
    container = reset_container_for_tests(settings)
    student = container.user_repository.create_user(
        username="student_test",
        password_hash=hash_password("Demo123456"),
        role="student",
        display_name="Test Student",
    )
    client = TestClient(create_app())
    resp = client.post("/api/v1/auth/login", json={"username": "student_test", "password": "Demo123456"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    return client, container, auth, student.id


def test_data_controls_list():
    """数据源控制列表返回所有默认源。"""
    client, _container, auth, _uid = _setup()
    resp = client.get("/api/v1/learner-state/data-controls", headers=auth)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "items" in data
    keys = {item["source_key"] for item in data["items"]}
    assert "CORE_STUDY" in keys
    assert "MODEL_SHADOW" in keys
    assert "PROACTIVE_SUGGESTIONS" in keys
    for item in data["items"]:
        assert item["status"] == "ENABLED"


def test_data_controls_pause_and_resume():
    """暂停和恢复数据源。"""
    client, _container, auth, _uid = _setup()
    resp = client.put(
        "/api/v1/learner-state/data-controls/CHAOXING",
        json={"status": "PAUSED", "idempotency_key": "pause-chaoxing-1"},
        headers=auth,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "PAUSED"
    resp = client.get("/api/v1/learner-state/data-controls", headers=auth)
    items = {item["source_key"]: item for item in resp.json()["items"]}
    assert items["CHAOXING"]["status"] == "PAUSED"
    resp = client.put(
        "/api/v1/learner-state/data-controls/CHAOXING",
        json={"status": "ENABLED", "idempotency_key": "resume-chaoxing-1"},
        headers=auth,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ENABLED"


def test_data_summary():
    """数据摘要返回固定字段。"""
    client, _container, auth, _uid = _setup()
    resp = client.get("/api/v1/learner-state/data-summary", headers=auth)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    for field in (
        "event_count", "snapshot_count",
        "correction_count", "learning_plan_count",
        "plan_feedback_count", "plan_evaluation_count", "shadow_run_count",
        "enabled_sources", "paused_sources",
        "estimator_versions", "planner_versions", "evaluator_versions",
    ):
        assert field in data, f"missing {field}"


def test_delete_state_only():
    """删除 STATE_ONLY 范围。"""
    client, _container, auth, _uid = _setup()
    resp = client.post(
        "/api/v1/learner-state/delete-request",
        json={"scope": "STATE_ONLY", "idempotency_key": "del-state-1"},
        headers=auth,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["scope"] == "STATE_ONLY"
    assert data["status"] == "COMPLETED"
    assert "before_counts" in data
    assert "after_counts" in data


def test_delete_status():
    """删除状态查询。"""
    client, _container, auth, _uid = _setup()
    client.post(
        "/api/v1/learner-state/delete-request",
        json={"scope": "STATE_ONLY", "idempotency_key": "del-1"},
        headers=auth,
    )
    resp = client.get("/api/v1/learner-state/delete-status", headers=auth)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["latest"] is not None
    assert data["latest"]["scope"] == "STATE_ONLY"


def test_model_transparency():
    """模型透明度返回非敏感能力状态。"""
    client, _container, auth, _uid = _setup()
    resp = client.get("/api/v1/learner-state/model-transparency", headers=auth)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "capabilities" in data
    assert len(data["capabilities"]) == 2
    for cap in data["capabilities"]:
        assert cap["campusmate_lm_status"] in (
            "SHADOW_ONLY", "BLOCKED", "ELIGIBLE_FOR_CANARY", "REVOKED"
        )
        assert "uses_real_model_inference" in cap
        assert "uses_fixed_prediction_file" in cap
    assert data["campusmate_lm_affects_production"] is False
    assert data["shadow_results_modify_plans"] is False


def test_corrections_empty_list():
    """空纠正列表。"""
    client, _container, auth, _uid = _setup()
    resp = client.get("/api/v1/learner-state/corrections", headers=auth)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_cross_user_404():
    """跨用户资源返回 404。"""
    settings = Settings(app_env="test", database_url="sqlite:///:memory:")
    container = reset_container_for_tests(settings)
    s1 = container.user_repository.create_user(
        username="s1", password_hash=hash_password("Demo123456"), role="student", display_name="S1"
    )
    s2 = container.user_repository.create_user(
        username="s2", password_hash=hash_password("Demo123456"), role="student", display_name="S2"
    )
    client = TestClient(create_app())
    r1 = client.post("/api/v1/auth/login", json={"username": "s1", "password": "Demo123456"})
    r2 = client.post("/api/v1/auth/login", json={"username": "s2", "password": "Demo123456"})
    auth1 = {"Authorization": f"Bearer {r1.json()['access_token']}"}
    auth2 = {"Authorization": f"Bearer {r2.json()['access_token']}"}
    resp = client.get("/api/v1/learner-state/corrections", headers=auth2)
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_admin_cannot_access_student_controls():
    """admin 不能操作学生控制 API。"""
    settings = Settings(app_env="test", database_url="sqlite:///:memory:")
    container = reset_container_for_tests(settings)
    container.user_repository.create_user(
        username="admin_test", password_hash=hash_password("Demo123456"), role="admin", display_name="Admin"
    )
    client = TestClient(create_app())
    resp = client.post("/api/v1/auth/login", json={"username": "admin_test", "password": "Demo123456"})
    auth = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    resp = client.get("/api/v1/learner-state/data-controls", headers=auth)
    assert resp.status_code == 403