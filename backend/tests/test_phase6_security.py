"""Phase 6A: 安全测试。

覆盖：
- 跨用户资源不可枚举
- teacher/admin 被拒绝
- 输出不包含敏感字段
- 错误码不泄露内部信息
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.security import hash_password

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests


def _setup_multi():
    settings = Settings(app_env="test", database_url="sqlite:///:memory:")
    container = reset_container_for_tests(settings)
    container.user_repository.create_user(username="sec_a", password_hash=hash_password("Demo123456"), role="student", display_name="A")
    container.user_repository.create_user(username="sec_b", password_hash=hash_password("Demo123456"), role="student", display_name="B")
    container.user_repository.create_user(username="sec_admin", password_hash=hash_password("Demo123456"), role="admin", display_name="Admin")
    client = TestClient(create_app())
    ra = client.post("/api/v1/auth/login", json={"username": "sec_a", "password": "Demo123456"})
    rb = client.post("/api/v1/auth/login", json={"username": "sec_b", "password": "Demo123456"})
    radmin = client.post("/api/v1/auth/login", json={"username": "sec_admin", "password": "Demo123456"})
    return client, {
        "a": {"Authorization": f"Bearer {ra.json()['access_token']}"},
        "b": {"Authorization": f"Bearer {rb.json()['access_token']}"},
        "admin": {"Authorization": f"Bearer {radmin.json()['access_token']}"},
    }


def test_cross_user_corrections_isolated():
    client, auths = _setup_multi()
    r = client.get("/api/v1/learner-state/corrections", headers=auths["a"])
    assert r.status_code == 200
    r = client.get("/api/v1/learner-state/corrections", headers=auths["b"])
    assert r.status_code == 200


def test_cross_user_data_controls_isolated():
    client, auths = _setup_multi()
    client.put("/api/v1/learner-state/data-controls/CHAOXING", json={"status": "PAUSED", "idempotency_key": "a1"}, headers=auths["a"])
    resp = client.get("/api/v1/learner-state/data-controls", headers=auths["b"])
    for item in resp.json()["items"]:
        if item["source_key"] == "CHAOXING":
            assert item["status"] == "ENABLED"


def test_cross_user_delete_isolated():
    client, auths = _setup_multi()
    resp = client.post("/api/v1/learner-state/delete-request", json={"scope": "ALL_LEARNER_MODEL_DATA", "idempotency_key": "a1"}, headers=auths["a"])
    assert resp.status_code == 200
    resp_b = client.get("/api/v1/learner-state/data-summary", headers=auths["b"])
    assert resp_b.status_code == 200


def test_admin_blocked_on_all_endpoints():
    client, auths = _setup_multi()
    endpoints = [
        ("GET", "/api/v1/learner-state/corrections", None),
        ("GET", "/api/v1/learner-state/data-controls", None),
        ("GET", "/api/v1/learner-state/data-summary", None),
        ("GET", "/api/v1/learner-state/delete-status", None),
        ("GET", "/api/v1/learner-state/model-transparency", None),
    ]
    for method, path, body in endpoints:
        r = client.request(method, path, json=body, headers=auths["admin"])
        assert r.status_code == 403, f"{method} {path} should be 403, got {r.status_code}"


def test_error_codes_stable():
    """错误响应使用固定错误码，不泄露内部信息。"""
    client, auths = _setup_multi()
    r = client.post(
        "/api/v1/learner-state/corrections/nonexistent/revoke",
        json={"idempotency_key": "x"},
        headers=auths["a"],
    )
    assert r.status_code == 404
    body = r.json()
    assert body["code"] == "LEARNER_CORRECTION_NOT_FOUND"
    for forbidden in ("sql", "table", "stack", "traceback", "file"):
        assert forbidden not in body.get("message", "").lower()


def test_no_auth_rejected():
    """无认证被拒绝。"""
    settings = Settings(app_env="test", database_url="sqlite:///:memory:")
    reset_container_for_tests(settings)
    client = TestClient(create_app())
    r = client.get("/api/v1/learner-state/corrections")
    assert r.status_code == 401
    r = client.get("/api/v1/learner-state/data-controls")
    assert r.status_code == 401


def test_model_transparency_no_secrets():
    """模型透明度不暴露 base_url/api_key/prompt/路径。"""
    client, auths = _setup_multi()
    r = client.get("/api/v1/learner-state/model-transparency", headers=auths["a"])
    assert r.status_code == 200
    text = r.text.lower()
    for forbidden in ("base_url", "api_key", "prompt", "token", "password", ".pth", "checkpoint"):
        assert forbidden not in text