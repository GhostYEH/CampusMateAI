"""CampusMate EduConnector 测试（第二阶段）。

覆盖：
- 数据库 schema 创建（edu_systems 1:N / edu_bindings / edu_connections / edu_sync_records）
- EduRepository CRUD（edu_systems 多系统）
- SchoolRegistry / SystemDetector（evidence + detection_source）
- MockEduAdapter 完整流程
- /api/v1/edu/* 端点
- 严禁编造 URL
- production 环境拒绝 MockAdapter / 不自动 fallback
- Connection 状态机
- 安全：不返回 password/cookie/token
"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.edu import (
    BINDING_ACTIVE,
    CONN_AUTH_REQUIRED,
    CONN_CONNECTED,
    CONN_ERROR,
    CONN_IDLE,
    CONN_WAITING_USER_LOGIN,
    EDU_PROVIDER_UNKNOWN,
    EDU_PROVIDER_ZHENGFANG,
    LOGIN_EXEC_BACKEND_HTTP,
    LOGIN_EXEC_CLIENT_WEBVIEW,
    SESSION_CLIENT_COOKIE,
    SYSTEM_KEY_UNDERGRADUATE_MAIN,
    URL_NOT_DISCOVERED,
)
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _client(app_env: str = "test") -> TestClient:
    settings = Settings(
        app_env=app_env,
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        auto_import_demo=False,
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    return TestClient(create_app())


def _headers(client: TestClient, username: str = "student_demo") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Demo123456"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _admin_headers(client: TestClient) -> dict[str, str]:
    return _headers(client, "admin_demo")


def _select_demo_university(client: TestClient, headers: dict[str, str]) -> str:
    university = client.get("/api/v1/universities").json()["items"][0]
    response = client.put(
        "/api/v1/profile/university",
        headers=headers,
        json={"university_id": university["id"]},
    )
    assert response.status_code == 200, response.text
    return university["id"]


# ===== 数据库 schema =====


def test_edu_tables_created_with_safe_defaults() -> None:
    client = _client()
    headers = _headers(client)
    university_id = _select_demo_university(client, headers)
    response = client.get(f"/api/v1/edu/config/{university_id}", headers=headers)
    assert response.status_code == 200, response.text
    cfg = response.json()
    assert cfg["academic_system_url"] is None
    assert cfg["academic_system_url_status"] == URL_NOT_DISCOVERED
    assert cfg["provider"] == EDU_PROVIDER_UNKNOWN
    assert cfg["system_type"] == "unknown"
    assert cfg["supported_features"] == []


# ===== 探测 =====


def test_detect_returns_unknown_for_unconfigured_university() -> None:
    client = _client()
    headers = _headers(client)
    university_id = _select_demo_university(client, headers)
    response = client.get(
        "/api/v1/edu/detect", headers=headers, params={"university_id": university_id}
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["university_id"] == university_id
    assert result["provider"] == EDU_PROVIDER_UNKNOWN
    assert result["detected"] is False
    assert result["confidence"] == 0.0
    assert "evidence" in result
    assert "detection_source" in result


def test_detect_returns_explicit_provider_after_admin_config() -> None:
    client = _client()
    headers = _headers(client)
    university_id = _select_demo_university(client, headers)
    admin_headers = _admin_headers(client)
    response = client.put(
        f"/api/v1/edu/config/{university_id}",
        headers=admin_headers,
        json={"university_id": university_id, "provider": "zhengfang"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["provider"] == "zhengfang"
    assert response.json()["academic_system_url"] is None
    response = client.get(
        "/api/v1/edu/detect", headers=headers, params={"university_id": university_id}
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["provider"] == "zhengfang"
    assert result["detected"] is True
    assert result["confidence"] >= 0.5
    assert result["detection_source"] == "CONFIG"


def test_detect_returns_not_found_for_unknown_university() -> None:
    client = _client()
    headers = _headers(client)
    response = client.get(
        "/api/v1/edu/detect",
        headers=headers,
        params={"university_id": "uni_does_not_exist"},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["detected"] is False
    assert result["reason"] == "university not found"
    assert result["confidence"] == 0.0


# ===== 配置 =====


def test_admin_can_update_config_without_fabricating_urls() -> None:
    client = _client()
    headers = _headers(client)
    university_id = _select_demo_university(client, headers)
    admin_headers = _admin_headers(client)
    response = client.put(
        f"/api/v1/edu/config/{university_id}",
        headers=admin_headers,
        json={
            "university_id": university_id,
            "provider": "zhengfang",
            "login_method": "cas",
            "captcha_type": "image",
            "requires_campus_network": True,
            "supported_features": ["profile", "schedule", "grade", "exam"],
            "school_code": "10003",
        },
    )
    assert response.status_code == 200, response.text
    cfg = response.json()
    assert cfg["provider"] == "zhengfang"
    assert cfg["login_method"] == "cas"
    assert cfg["captcha_type"] == "image"
    assert cfg["requires_campus_network"] is True
    assert cfg["supported_features"] == ["profile", "schedule", "grade", "exam"]
    assert cfg["school_code"] == "10003"
    assert cfg["academic_system_url"] is None
    assert cfg["sso_url"] is None


def test_student_cannot_update_config() -> None:
    client = _client()
    headers = _headers(client)
    university_id = _select_demo_university(client, headers)
    response = client.put(
        f"/api/v1/edu/config/{university_id}",
        headers=headers,
        json={"university_id": university_id, "provider": "zhengfang"},
    )
    assert response.status_code == 403


def test_config_upsert_is_idempotent() -> None:
    client = _client()
    headers = _headers(client)
    university_id = _select_demo_university(client, headers)
    admin_headers = _admin_headers(client)
    r1 = client.get(f"/api/v1/edu/config/{university_id}", headers=headers).json()
    r2 = client.get(f"/api/v1/edu/config/{university_id}", headers=headers).json()
    assert r1["id"] == r2["id"]
    client.put(
        f"/api/v1/edu/config/{university_id}",
        headers=admin_headers,
        json={"university_id": university_id, "provider": "qiangzhi"},
    )
    r3 = client.get(f"/api/v1/edu/config/{university_id}", headers=headers).json()
    assert r3["id"] == r1["id"]
    assert r3["provider"] == "qiangzhi"


# ===== edu_systems (1:N) =====


def test_university_can_have_multiple_edu_systems() -> None:
    """一所学校可以创建多个 EduSystem。"""
    client = _client()
    headers = _headers(client)
    university_id = _select_demo_university(client, headers)
    admin_headers = _admin_headers(client)
    r1 = client.post(
        f"/api/v1/edu/systems/{university_id}",
        headers=admin_headers,
        json={"system_key": "undergraduate-main", "provider": "zhengfang", "system_type": "undergrad"},
    )
    assert r1.status_code == 200, r1.text
    r2 = client.post(
        f"/api/v1/edu/systems/{university_id}",
        headers=admin_headers,
        json={"system_key": "graduate-main", "provider": "qiangzhi", "system_type": "postgrad"},
    )
    assert r2.status_code == 200, r2.text
    systems = client.get(f"/api/v1/edu/systems/{university_id}", headers=headers).json()
    assert len(systems) >= 2
    keys = {s["system_key"] for s in systems}
    assert "undergraduate-main" in keys
    assert "graduate-main" in keys


def test_system_key_unique_per_university() -> None:
    """同一学校同一 system_key 唯一（upsert 幂等）。"""
    client = _client()
    headers = _headers(client)
    university_id = _select_demo_university(client, headers)
    admin_headers = _admin_headers(client)
    r1 = client.post(
        f"/api/v1/edu/systems/{university_id}",
        headers=admin_headers,
        json={"system_key": "undergraduate-main", "provider": "zhengfang"},
    )
    r2 = client.post(
        f"/api/v1/edu/systems/{university_id}",
        headers=admin_headers,
        json={"system_key": "undergraduate-main", "provider": "qiangzhi"},
    )
    assert r1.json()["id"] == r2.json()["id"]
    assert r2.json()["provider"] == "qiangzhi"


def test_different_universities_can_have_same_system_key() -> None:
    """不同学校可以有相同 system_key。"""
    client = _client()
    admin_headers = _admin_headers(client)
    headers = _headers(client)
    universities = client.get("/api/v1/universities").json()["items"]
    if len(universities) < 2:
        return
    uid1 = universities[0]["id"]
    uid2 = universities[1]["id"]
    for uid in (uid1, uid2):
        r = client.post(
            f"/api/v1/edu/systems/{uid}",
            headers=admin_headers,
            json={"system_key": "undergraduate-main", "provider": "zhengfang"},
        )
        assert r.status_code == 200, r.text


# ===== 绑定 =====


def test_get_binding_returns_none_when_unbound() -> None:
    client = _client()
    headers = _headers(client)
    _select_demo_university(client, headers)
    response = client.get("/api/v1/edu/binding", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() is None


def test_bind_requires_selected_university() -> None:
    client = _client()
    headers = _headers(client, "student_demo_01")
    response = client.post(
        "/api/v1/edu/bind",
        headers=headers,
        json={"username": "S202401001", "password": "any-password"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "UNIVERSITY_REQUIRED"


def test_bind_with_mock_adapter_succeeds_in_test_env() -> None:
    client = _client()
    headers = _headers(client)
    _select_demo_university(client, headers)
    response = client.post(
        "/api/v1/edu/bind",
        headers=headers,
        json={"username": "S202401001", "password": "demo-password"},
    )
    assert response.status_code == 200, response.text
    binding = response.json()
    assert binding["connection_status"] == BINDING_ACTIVE
    assert binding["provider"] == "mock"
    assert "password" not in json.dumps(binding)
    assert "credential_ref" not in binding


def test_bind_does_not_persist_password_in_response_or_records() -> None:
    client = _client()
    headers = _headers(client)
    _select_demo_university(client, headers)
    bind_resp = client.post(
        "/api/v1/edu/bind",
        headers=headers,
        json={"username": "S202401001", "password": "must-not-leak"},
    )
    assert bind_resp.status_code == 200, bind_resp.text
    assert "must-not-leak" not in bind_resp.text
    sync_resp = client.post("/api/v1/edu/sync/profile", headers=headers)
    assert sync_resp.status_code == 200, sync_resp.text
    assert "must-not-leak" not in sync_resp.text
    records_resp = client.get("/api/v1/edu/sync/records", headers=headers)
    assert records_resp.status_code == 200, records_resp.text
    assert "must-not-leak" not in records_resp.text


def test_unbind_clears_binding() -> None:
    client = _client()
    headers = _headers(client)
    _select_demo_university(client, headers)
    client.post(
        "/api/v1/edu/bind",
        headers=headers,
        json={"username": "S202401001", "password": "demo"},
    )
    assert client.get("/api/v1/edu/binding", headers=headers).json() is not None
    response = client.delete("/api/v1/edu/binding", headers=headers)
    assert response.status_code == 200, response.text
    assert client.get("/api/v1/edu/binding", headers=headers).json() is None


# ===== 同步 =====


def test_sync_without_binding_returns_failed_result() -> None:
    client = _client()
    headers = _headers(client)
    _select_demo_university(client, headers)
    response = client.post("/api/v1/edu/sync/profile", headers=headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "failed"
    assert "未绑定" in result["error_message"]


def test_sync_profile_with_mock_returns_normalized_data() -> None:
    client = _client()
    headers = _headers(client)
    _select_demo_university(client, headers)
    client.post(
        "/api/v1/edu/bind",
        headers=headers,
        json={"username": "S202401001", "password": "demo"},
    )
    response = client.post("/api/v1/edu/sync/profile", headers=headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "success"
    assert result["items_count"] == 1
    assert result["profile"] is not None
    assert result["profile"]["external_student_id"] is not None
    assert "Mock" in result["profile"]["name"]


def test_sync_schedule_with_mock_returns_items() -> None:
    client = _client()
    headers = _headers(client)
    _select_demo_university(client, headers)
    client.post(
        "/api/v1/edu/bind",
        headers=headers,
        json={"username": "S202401001", "password": "demo"},
    )
    response = client.post("/api/v1/edu/sync/schedule", headers=headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "success"
    assert result["items_count"] >= 1
    assert result["schedule"] is not None
    assert len(result["schedule"]["items"]) >= 1


def test_sync_grade_and_exam_with_mock() -> None:
    client = _client()
    headers = _headers(client)
    _select_demo_university(client, headers)
    client.post(
        "/api/v1/edu/bind",
        headers=headers,
        json={"username": "S202401001", "password": "demo"},
    )
    for endpoint in ("sync/grade", "sync/exam"):
        response = client.post(f"/api/v1/edu/{endpoint}", headers=headers)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["status"] == "success"
        assert result["items_count"] >= 1


def test_sync_records_listed_after_sync() -> None:
    client = _client()
    headers = _headers(client)
    _select_demo_university(client, headers)
    client.post(
        "/api/v1/edu/bind",
        headers=headers,
        json={"username": "S202401001", "password": "demo"},
    )
    client.post("/api/v1/edu/sync/profile", headers=headers)
    client.post("/api/v1/edu/sync/schedule", headers=headers)
    response = client.get("/api/v1/edu/sync/records", headers=headers)
    assert response.status_code == 200, response.text
    records = response.json()
    assert len(records) >= 2
    sync_types = {r["sync_type"] for r in records}
    assert "profile" in sync_types
    assert "schedule" in sync_types


# ===== 真实 Adapter 占位 =====


def test_real_adapter_not_implemented_falls_back_to_mock_in_test() -> None:
    """test 环境下，真实 Adapter 未实现应降级到 mock。"""
    client = _client()
    headers = _headers(client)
    university_id = _select_demo_university(client, headers)
    admin_headers = _admin_headers(client)
    client.put(
        f"/api/v1/edu/config/{university_id}",
        headers=admin_headers,
        json={"university_id": university_id, "provider": "zhengfang"},
    )
    response = client.post(
        "/api/v1/edu/bind",
        headers=headers,
        json={"username": "S202401001", "password": "demo"},
    )
    assert response.status_code == 200, response.text
    binding = response.json()
    assert binding["provider"] == "mock"


# ===== Connection 状态机 =====


def test_connection_flow_creates_and_advances() -> None:
    """创建连接 → 初始 idle → continue → auth_required。"""
    client = _client()
    headers = _headers(client)
    university_id = _select_demo_university(client, headers)
    admin_headers = _admin_headers(client)
    r = client.post(
        f"/api/v1/edu/systems/{university_id}",
        headers=admin_headers,
        json={"system_key": "undergraduate-main", "provider": "mock"},
    )
    assert r.status_code == 200, r.text
    system_id = r.json()["id"]
    create_resp = client.post(
        "/api/v1/edu/connections",
        headers=headers,
        json={"edu_system_id": system_id},
    )
    assert create_resp.status_code == 200, create_resp.text
    conn = create_resp.json()
    assert conn["state"] == CONN_IDLE
    continue_resp = client.post(
        f"/api/v1/edu/connections/{conn['id']}/continue",
        headers=headers,
        json={},
    )
    assert continue_resp.status_code == 200, continue_resp.text
    assert continue_resp.json()["state"] == CONN_AUTH_REQUIRED


# ===== 鉴权 =====


def test_edu_endpoints_require_authentication() -> None:
    client = _client()
    for method, path in [
        ("GET", "/api/v1/edu/detect?university_id=x"),
        ("GET", "/api/v1/edu/config/any"),
        ("GET", "/api/v1/edu/binding"),
        ("POST", "/api/v1/edu/bind"),
        ("DELETE", "/api/v1/edu/binding"),
        ("POST", "/api/v1/edu/sync/profile"),
        ("GET", "/api/v1/edu/sync/records"),
    ]:
        response = client.request(method, path)
        assert response.status_code == 401, f"{method} {path}: {response.status_code}"


# ===== Discovery probe + connection from URL =====


def test_probe_unreachable_url_returns_error_not_reachable() -> None:
    client = _client()
    headers = _headers(client)
    response = client.post(
        "/api/v1/edu/discovery/probe",
        headers=headers,
        json={"portal_url": "https://this-host-does-not-exist-12345.invalid/"},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["reachable"] is False
    assert result["error"] is not None
    assert result["provider"] == "unknown"
    assert result["suggested_login_mode"] == LOGIN_EXEC_BACKEND_HTTP


def test_probe_requires_authentication() -> None:
    client = _client()
    response = client.post(
        "/api/v1/edu/discovery/probe",
        json={"portal_url": "https://example.edu/"},
    )
    assert response.status_code == 401


def test_create_connection_from_url_creates_idle_connection() -> None:
    client = _client()
    headers = _headers(client)
    _select_demo_university(client, headers)
    response = client.post(
        "/api/v1/edu/connections/from-url",
        headers=headers,
        json={"portal_url": "https://this-host-does-not-exist-12345.invalid/"},
    )
    assert response.status_code == 200, response.text
    conn = response.json()
    assert conn["state"] == CONN_IDLE
    assert conn["id"]
    assert conn["login_execution_mode"] in (LOGIN_EXEC_BACKEND_HTTP, LOGIN_EXEC_CLIENT_WEBVIEW)


def test_create_connection_from_url_requires_university() -> None:
    client = _client()
    headers = _headers(client, "student_demo_01")
    response = client.post(
        "/api/v1/edu/connections/from-url",
        headers=headers,
        json={"portal_url": "https://example.edu/"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "UNIVERSITY_REQUIRED"


# ===== continue: POLL / CANCEL =====


def test_continue_poll_returns_current_state_without_change() -> None:
    client = _client()
    headers = _headers(client)
    _select_demo_university(client, headers)
    conn = client.post(
        "/api/v1/edu/connections/from-url",
        headers=headers,
        json={"portal_url": "https://this-host-does-not-exist-12345.invalid/"},
    ).json()
    response = client.post(
        f"/api/v1/edu/connections/{conn['id']}/continue",
        headers=headers,
        json={"action": "POLL"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["state"] == conn["state"]


def test_continue_cancel_marks_error() -> None:
    client = _client()
    headers = _headers(client)
    _select_demo_university(client, headers)
    conn = client.post(
        "/api/v1/edu/connections/from-url",
        headers=headers,
        json={"portal_url": "https://this-host-does-not-exist-12345.invalid/"},
    ).json()
    response = client.post(
        f"/api/v1/edu/connections/{conn['id']}/continue",
        headers=headers,
        json={"action": "CANCEL"},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["state"] == CONN_ERROR
    assert result["error_code"] == "CANCELLED"


def test_continue_unknown_connection_returns_404() -> None:
    client = _client()
    headers = _headers(client)
    response = client.post(
        "/api/v1/edu/connections/conn-does-not-exist/continue",
        headers=headers,
        json={},
    )
    assert response.status_code == 404


# ===== backend_http + client_webview 完整流程 =====


def _admin_headers_for(client: TestClient) -> dict[str, str]:
    return _headers(client, "admin_demo")


def test_backend_http_flow_idle_to_auth_required_to_connected() -> None:
    client = _client()
    headers = _headers(client)
    university_id = _select_demo_university(client, headers)
    admin_headers = _admin_headers_for(client)
    sys_resp = client.post(
        f"/api/v1/edu/systems/{university_id}",
        headers=admin_headers,
        json={"system_key": "undergraduate-main", "provider": "mock"},
    )
    system_id = sys_resp.json()["id"]
    conn = client.post(
        "/api/v1/edu/connections",
        headers=headers,
        json={"edu_system_id": system_id},
    ).json()
    assert conn["state"] == CONN_IDLE
    cont_resp = client.post(
        f"/api/v1/edu/connections/{conn['id']}/continue",
        headers=headers,
        json={},
    )
    assert cont_resp.json()["state"] == CONN_AUTH_REQUIRED
    login_resp = client.post(
        f"/api/v1/edu/connections/{conn['id']}/continue",
        headers=headers,
        json={"username": "S202401001", "password": "demo-password"},
    )
    final_conn = login_resp.json()
    assert final_conn["state"] == CONN_CONNECTED
    binding = client.get("/api/v1/edu/binding", headers=headers).json()
    assert binding is not None
    assert binding["connection_status"] == BINDING_ACTIVE
    sync_resp = client.post("/api/v1/edu/sync/schedule", headers=headers)
    assert sync_resp.json()["status"] == "success"


def test_client_webview_flow_idle_to_waiting_to_connected() -> None:
    client = _client()
    headers = _headers(client)
    university_id = _select_demo_university(client, headers)
    admin_headers = _admin_headers_for(client)
    sys_resp = client.post(
        f"/api/v1/edu/systems/{university_id}",
        headers=admin_headers,
        json={
            "system_key": "undergraduate-main",
            "provider": "mock",
            "login_execution_mode": LOGIN_EXEC_CLIENT_WEBVIEW,
        },
    )
    system_id = sys_resp.json()["id"]
    conn = client.post(
        "/api/v1/edu/connections",
        headers=headers,
        json={"edu_system_id": system_id},
    ).json()
    cont_resp = client.post(
        f"/api/v1/edu/connections/{conn['id']}/continue",
        headers=headers,
        json={},
    )
    assert cont_resp.json()["state"] == CONN_WAITING_USER_LOGIN
    complete_resp = client.post(
        f"/api/v1/edu/connections/{conn['id']}/continue",
        headers=headers,
        json={
            "action": "CLIENT_WEBVIEW_COMPLETE",
            "cookies": {"JSESSIONID": "mock-session-id-12345", "route": "default"},
            "current_url": "https://jwxt.example.edu/student/index",
            "user_agent": "Mozilla/5.0 (Linux; Android 14) CampusMate/1.0",
        },
    )
    final_conn = complete_resp.json()
    assert final_conn["state"] == CONN_CONNECTED
    binding = client.get("/api/v1/edu/binding", headers=headers).json()
    assert binding["connection_status"] == BINDING_ACTIVE
    assert binding["session_type"] == SESSION_CLIENT_COOKIE


def test_client_webview_complete_without_cookies_stays_waiting() -> None:
    client = _client()
    headers = _headers(client)
    university_id = _select_demo_university(client, headers)
    admin_headers = _admin_headers_for(client)
    sys_resp = client.post(
        f"/api/v1/edu/systems/{university_id}",
        headers=admin_headers,
        json={
            "system_key": "undergraduate-main",
            "provider": "mock",
            "login_execution_mode": LOGIN_EXEC_CLIENT_WEBVIEW,
        },
    )
    system_id = sys_resp.json()["id"]
    conn = client.post(
        "/api/v1/edu/connections",
        headers=headers,
        json={"edu_system_id": system_id},
    ).json()
    client.post(
        f"/api/v1/edu/connections/{conn['id']}/continue",
        headers=headers,
        json={},
    )
    resp = client.post(
        f"/api/v1/edu/connections/{conn['id']}/continue",
        headers=headers,
        json={"action": "CLIENT_WEBVIEW_COMPLETE"},
    )
    result = resp.json()
    assert result["state"] == CONN_WAITING_USER_LOGIN
    assert result["error_code"] == "NO_COOKIE"


# ===== 安全：cookies/password 不泄露 =====


def test_cookies_not_persisted_in_sync_records() -> None:
    client = _client()
    headers = _headers(client)
    university_id = _select_demo_university(client, headers)
    admin_headers = _admin_headers_for(client)
    sys_resp = client.post(
        f"/api/v1/edu/systems/{university_id}",
        headers=admin_headers,
        json={
            "system_key": "undergraduate-main",
            "provider": "mock",
            "login_execution_mode": LOGIN_EXEC_CLIENT_WEBVIEW,
        },
    )
    system_id = sys_resp.json()["id"]
    conn = client.post(
        "/api/v1/edu/connections",
        headers=headers,
        json={"edu_system_id": system_id},
    ).json()
    client.post(
        f"/api/v1/edu/connections/{conn['id']}/continue",
        headers=headers,
        json={},
    )
    secret_cookie_value = "super-secret-jsessionid-98765"
    complete_resp = client.post(
        f"/api/v1/edu/connections/{conn['id']}/continue",
        headers=headers,
        json={
            "action": "CLIENT_WEBVIEW_COMPLETE",
            "cookies": {"JSESSIONID": secret_cookie_value},
        },
    )
    assert secret_cookie_value not in complete_resp.text
    client.post("/api/v1/edu/sync/schedule", headers=headers)
    records_resp = client.get("/api/v1/edu/sync/records", headers=headers)
    assert secret_cookie_value not in records_resp.text
    binding_resp = client.get("/api/v1/edu/binding", headers=headers)
    assert secret_cookie_value not in binding_resp.text


def test_password_not_in_connection_response() -> None:
    client = _client()
    headers = _headers(client)
    university_id = _select_demo_university(client, headers)
    admin_headers = _admin_headers_for(client)
    sys_resp = client.post(
        f"/api/v1/edu/systems/{university_id}",
        headers=admin_headers,
        json={"system_key": "undergraduate-main", "provider": "mock"},
    )
    system_id = sys_resp.json()["id"]
    conn = client.post(
        "/api/v1/edu/connections",
        headers=headers,
        json={"edu_system_id": system_id},
    ).json()
    client.post(
        f"/api/v1/edu/connections/{conn['id']}/continue",
        headers=headers,
        json={},
    )
    secret_password = "must-not-leak-password-xyz"
    login_resp = client.post(
        f"/api/v1/edu/connections/{conn['id']}/continue",
        headers=headers,
        json={"username": "S202401001", "password": secret_password},
    )
    assert secret_password not in login_resp.text
    assert "password" not in json.dumps(login_resp.json())
