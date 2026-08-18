"""QR 扫码登录与可信设备完整生命周期及安全边界测试。

覆盖:
- 完整生命周期: create → scan → confirm → exchange
- 状态机安全: 过期/取消/重复扫描/用户不一致/重放
- browser_token 隔离
- trusted device 自动登录/过期/撤销/停用
- logout 撤销 trusted device
- QR payload 解析协议
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.qr_payload import build_qr_payload, parse_qr_payload
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _client() -> TestClient:
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        auto_import_demo=False,
        qr_login_expire_seconds=120,
        trusted_device_expire_days=30,
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    return TestClient(create_app())


def _login(client: TestClient, username: str) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Demo123456"},
    )
    assert resp.status_code == 200, f"login failed for {username}: {resp.text}"
    data = resp.json()
    return {
        "Authorization": f"Bearer {data['access_token']}",
        "_refresh_token": data["refresh_token"],
        "_access_token": data["access_token"],
    }


def _qr_create(client: TestClient, device_id: str = "test-device-001") -> dict:
    resp = client.post(
        "/api/v1/auth/qr/create",
        json={"device_id": device_id, "browser_name": "Chrome", "os_name": "Windows"},
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"},
    )
    assert resp.status_code == 200, f"qr create failed: {resp.text}"
    return resp.json()


def _parse_payload(qr_payload: str) -> dict:
    parsed = parse_qr_payload(qr_payload)
    assert parsed is not None, "qr_payload should parse"
    return {"session_id": parsed.session_id, "scan_token": parsed.scan_token}


# ===== QR Payload 协议测试 =====


def test_qr_payload_roundtrip() -> None:
    payload = build_qr_payload("qrs_abcdef1234567890", "st_" + "a" * 40)
    parsed = parse_qr_payload(payload)
    assert parsed is not None
    assert parsed.session_id == "qrs_abcdef1234567890"
    assert parsed.scan_token == "st_" + "a" * 40
    assert parsed.version == 1


def test_qr_payload_rejects_invalid() -> None:
    assert parse_qr_payload("https://example.com") is None
    assert parse_qr_payload("campusmate://auth/other?v=1&sid=x&token=y") is None
    assert parse_qr_payload("campusmate://auth/web-login?v=2&sid=x&token=y") is None
    assert parse_qr_payload("campusmate://auth/web-login?v=1&sid=&token=y") is None
    assert parse_qr_payload("") is None
    assert parse_qr_payload("not-a-url") is None
    # scan_token 太短
    assert parse_qr_payload("campusmate://auth/web-login?v=1&sid=short&token=short") is None


# ===== 完整生命周期 =====


def test_full_qr_login_lifecycle() -> None:
    client = _client()
    # 手机登录
    mobile_h = _login(client, "student_demo")
    # Web 创建 QR
    qr = _qr_create(client)
    parsed = _parse_payload(qr["qr_payload"])
    assert qr["status"] == "PENDING"
    assert qr["browser_token"]  # browser_token 不在 qr_payload 中
    assert qr["browser_token"] not in qr["qr_payload"]
    # Web 查询状态 — PENDING
    status_resp = client.get(
        f"/api/v1/auth/qr/{parsed['session_id']}/status",
        headers={"x-browser-token": qr["browser_token"]},
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "PENDING"
    # 手机扫码
    scan_resp = client.post(
        "/api/v1/auth/qr/scan",
        json=parsed,
        headers={"Authorization": mobile_h["Authorization"]},
    )
    assert scan_resp.status_code == 200, scan_resp.text
    assert scan_resp.json()["status"] == "SCANNED"
    assert scan_resp.json()["browser_name"] == "Chrome"
    assert scan_resp.json()["os_name"] == "Windows"
    # Web 查询状态 — SCANNED
    status_resp = client.get(
        f"/api/v1/auth/qr/{parsed['session_id']}/status",
        headers={"x-browser-token": qr["browser_token"]},
    )
    assert status_resp.json()["status"] == "SCANNED"
    # 手机确认
    confirm_resp = client.post(
        "/api/v1/auth/qr/confirm",
        json={**parsed, "trust_device": False},
        headers={"Authorization": mobile_h["Authorization"]},
    )
    assert confirm_resp.status_code == 200, confirm_resp.text
    assert confirm_resp.json()["status"] == "CONFIRMED"
    # Web 查询状态 — CONFIRMED
    status_resp = client.get(
        f"/api/v1/auth/qr/{parsed['session_id']}/status",
        headers={"x-browser-token": qr["browser_token"]},
    )
    assert status_resp.json()["status"] == "CONFIRMED"
    # Web exchange
    exchange_resp = client.post(
        "/api/v1/auth/qr/exchange",
        json={"session_id": parsed["session_id"], "browser_token": qr["browser_token"]},
    )
    assert exchange_resp.status_code == 200, exchange_resp.text
    tokens = exchange_resp.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    assert tokens["user"]["username"] == "student_demo"
    # Web 查询状态 — CONSUMED
    status_resp = client.get(
        f"/api/v1/auth/qr/{parsed['session_id']}/status",
        headers={"x-browser-token": qr["browser_token"]},
    )
    assert status_resp.json()["status"] == "CONSUMED"


# ===== 安全边界 =====


def test_qr_payload_does_not_contain_user_id_or_jwt() -> None:
    client = _client()
    qr = _qr_create(client)
    payload_str = qr["qr_payload"]
    # 不含 user_id / access / password 等敏感词
    assert "user" not in payload_str.lower()
    assert "password" not in payload_str.lower()
    # browser_token 不在 payload 中
    assert qr["browser_token"] not in payload_str


def test_status_without_browser_token_rejected() -> None:
    client = _client()
    qr = _qr_create(client)
    parsed = _parse_payload(qr["qr_payload"])
    # 无 browser_token
    resp = client.get(f"/api/v1/auth/qr/{parsed['session_id']}/status")
    assert resp.status_code == 401
    # 错误 browser_token
    resp = client.get(
        f"/api/v1/auth/qr/{parsed['session_id']}/status",
        headers={"x-browser-token": "wrong-token"},
    )
    assert resp.status_code == 401


def test_scan_requires_auth() -> None:
    client = _client()
    qr = _qr_create(client)
    parsed = _parse_payload(qr["qr_payload"])
    resp = client.post("/api/v1/auth/qr/scan", json=parsed)
    assert resp.status_code == 401


def test_confirm_requires_auth() -> None:
    client = _client()
    qr = _qr_create(client)
    parsed = _parse_payload(qr["qr_payload"])
    resp = client.post("/api/v1/auth/qr/confirm", json={**parsed, "trust_device": False})
    assert resp.status_code == 401


def test_double_scan_same_user_idempotent() -> None:
    client = _client()
    mobile_h = _login(client, "student_demo")
    qr = _qr_create(client)
    parsed = _parse_payload(qr["qr_payload"])
    # 第一次扫码
    r1 = client.post("/api/v1/auth/qr/scan", json=parsed, headers={"Authorization": mobile_h["Authorization"]})
    assert r1.status_code == 200
    # 同一用户重复扫码 — 幂等
    r2 = client.post("/api/v1/auth/qr/scan", json=parsed, headers={"Authorization": mobile_h["Authorization"]})
    assert r2.status_code == 200
    assert r2.json()["status"] == "SCANNED"


def test_scan_by_different_user_after_scanned_rejected() -> None:
    client = _client()
    h1 = _login(client, "student_demo")
    h2 = _login(client, "admin_demo")
    qr = _qr_create(client)
    parsed = _parse_payload(qr["qr_payload"])
    # A 扫码
    r1 = client.post("/api/v1/auth/qr/scan", json=parsed, headers={"Authorization": h1["Authorization"]})
    assert r1.status_code == 200
    # B 尝试扫码同一二维码
    r2 = client.post("/api/v1/auth/qr/scan", json=parsed, headers={"Authorization": h2["Authorization"]})
    assert r2.status_code == 409
    assert r2.json()["code"] == "QR_ALREADY_SCANNED"


def test_confirm_by_different_user_rejected() -> None:
    client = _client()
    h1 = _login(client, "student_demo")
    h2 = _login(client, "admin_demo")
    qr = _qr_create(client)
    parsed = _parse_payload(qr["qr_payload"])
    # A 扫码
    client.post("/api/v1/auth/qr/scan", json=parsed, headers={"Authorization": h1["Authorization"]})
    # B 尝试确认
    r = client.post(
        "/api/v1/auth/qr/confirm",
        json={**parsed, "trust_device": False},
        headers={"Authorization": h2["Authorization"]},
    )
    assert r.status_code == 403
    assert r.json()["code"] == "QR_USER_MISMATCH"


def test_exchange_before_confirmed_rejected() -> None:
    client = _client()
    qr = _qr_create(client)
    parsed = _parse_payload(qr["qr_payload"])
    # 未确认时 exchange
    r = client.post(
        "/api/v1/auth/qr/exchange",
        json={"session_id": parsed["session_id"], "browser_token": qr["browser_token"]},
    )
    assert r.status_code == 409
    assert r.json()["code"] == "QR_NOT_CONFIRMED"


def test_double_exchange_rejected() -> None:
    client = _client()
    mobile_h = _login(client, "student_demo")
    qr = _qr_create(client)
    parsed = _parse_payload(qr["qr_payload"])
    client.post("/api/v1/auth/qr/scan", json=parsed, headers={"Authorization": mobile_h["Authorization"]})
    client.post(
        "/api/v1/auth/qr/confirm",
        json={**parsed, "trust_device": False},
        headers={"Authorization": mobile_h["Authorization"]},
    )
    # 第一次 exchange
    r1 = client.post(
        "/api/v1/auth/qr/exchange",
        json={"session_id": parsed["session_id"], "browser_token": qr["browser_token"]},
    )
    assert r1.status_code == 200
    # 第二次 exchange — 重放
    r2 = client.post(
        "/api/v1/auth/qr/exchange",
        json={"session_id": parsed["session_id"], "browser_token": qr["browser_token"]},
    )
    assert r2.status_code == 409
    assert r2.json()["code"] == "QR_ALREADY_CONSUMED"


def test_exchange_with_wrong_browser_token_rejected() -> None:
    client = _client()
    mobile_h = _login(client, "student_demo")
    qr = _qr_create(client)
    parsed = _parse_payload(qr["qr_payload"])
    client.post("/api/v1/auth/qr/scan", json=parsed, headers={"Authorization": mobile_h["Authorization"]})
    client.post(
        "/api/v1/auth/qr/confirm",
        json={**parsed, "trust_device": False},
        headers={"Authorization": mobile_h["Authorization"]},
    )
    r = client.post(
        "/api/v1/auth/qr/exchange",
        json={"session_id": parsed["session_id"], "browser_token": "wrong-browser-token-aaaaaaaaaaaaaaaaaaaaaaa"},
    )
    assert r.status_code == 401
    assert r.json()["code"] == "QR_BROWSER_TOKEN_INVALID"


def test_cancel_after_scan() -> None:
    client = _client()
    mobile_h = _login(client, "student_demo")
    qr = _qr_create(client)
    parsed = _parse_payload(qr["qr_payload"])
    client.post("/api/v1/auth/qr/scan", json=parsed, headers={"Authorization": mobile_h["Authorization"]})
    # 取消
    r = client.post(
        "/api/v1/auth/qr/cancel",
        json=parsed,
        headers={"Authorization": mobile_h["Authorization"]},
    )
    assert r.status_code == 200
    # 状态变为 CANCELLED
    status = client.get(
        f"/api/v1/auth/qr/{parsed['session_id']}/status",
        headers={"x-browser-token": qr["browser_token"]},
    )
    assert status.json()["status"] == "CANCELLED"
    # 取消后不能 exchange
    r = client.post(
        "/api/v1/auth/qr/exchange",
        json={"session_id": parsed["session_id"], "browser_token": qr["browser_token"]},
    )
    assert r.status_code == 409
    assert r.json()["code"] == "QR_CANCELLED"


def test_cancel_after_confirm_rejected() -> None:
    client = _client()
    mobile_h = _login(client, "student_demo")
    qr = _qr_create(client)
    parsed = _parse_payload(qr["qr_payload"])
    client.post("/api/v1/auth/qr/scan", json=parsed, headers={"Authorization": mobile_h["Authorization"]})
    client.post(
        "/api/v1/auth/qr/confirm",
        json={**parsed, "trust_device": False},
        headers={"Authorization": mobile_h["Authorization"]},
    )
    r = client.post(
        "/api/v1/auth/qr/cancel",
        json=parsed,
        headers={"Authorization": mobile_h["Authorization"]},
    )
    assert r.status_code == 409


def test_scan_token_mismatch_rejected() -> None:
    client = _client()
    mobile_h = _login(client, "student_demo")
    qr = _qr_create(client)
    parsed = _parse_payload(qr["qr_payload"])
    # 错误 scan_token
    r = client.post(
        "/api/v1/auth/qr/scan",
        json={"session_id": parsed["session_id"], "scan_token": "wrong-scan-token-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
        headers={"Authorization": mobile_h["Authorization"]},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "QR_INVALID"


def test_nonexistent_session_rejected() -> None:
    client = _client()
    mobile_h = _login(client, "student_demo")
    r = client.post(
        "/api/v1/auth/qr/scan",
        json={"session_id": "qrs_nonexistent00000000", "scan_token": "st_" + "a" * 40},
        headers={"Authorization": mobile_h["Authorization"]},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "QR_INVALID"


# ===== Trusted Device 测试 =====


def test_trusted_device_created_on_confirm_with_trust() -> None:
    client = _client()
    mobile_h = _login(client, "student_demo")
    qr = _qr_create(client)
    parsed = _parse_payload(qr["qr_payload"])
    client.post("/api/v1/auth/qr/scan", json=parsed, headers={"Authorization": mobile_h["Authorization"]})
    client.post(
        "/api/v1/auth/qr/confirm",
        json={**parsed, "trust_device": True},
        headers={"Authorization": mobile_h["Authorization"]},
    )
    # exchange — 应设置 trusted device cookie
    r = client.post(
        "/api/v1/auth/qr/exchange",
        json={"session_id": parsed["session_id"], "browser_token": qr["browser_token"]},
    )
    assert r.status_code == 200
    # 验证 cookie 已设置
    cookies = r.cookies
    assert "campus_trusted_device" in cookies


def test_trusted_device_auto_login() -> None:
    client = _client()
    mobile_h = _login(client, "student_demo")
    qr = _qr_create(client)
    parsed = _parse_payload(qr["qr_payload"])
    client.post("/api/v1/auth/qr/scan", json=parsed, headers={"Authorization": mobile_h["Authorization"]})
    client.post(
        "/api/v1/auth/qr/confirm",
        json={**parsed, "trust_device": True},
        headers={"Authorization": mobile_h["Authorization"]},
    )
    # exchange 获取 cookie
    exchange_resp = client.post(
        "/api/v1/auth/qr/exchange",
        json={"session_id": parsed["session_id"], "browser_token": qr["browser_token"]},
    )
    assert exchange_resp.status_code == 200
    # 用 cookie 自动登录
    auto_resp = client.post(
        "/api/v1/auth/trusted-device/auto-login",
        json={"device_id": "test-device-001"},
    )
    assert auto_resp.status_code == 200, auto_resp.text
    assert auto_resp.json()["user"]["username"] == "student_demo"


def test_trusted_device_not_created_without_trust() -> None:
    client = _client()
    mobile_h = _login(client, "student_demo")
    qr = _qr_create(client)
    parsed = _parse_payload(qr["qr_payload"])
    client.post("/api/v1/auth/qr/scan", json=parsed, headers={"Authorization": mobile_h["Authorization"]})
    client.post(
        "/api/v1/auth/qr/confirm",
        json={**parsed, "trust_device": False},
        headers={"Authorization": mobile_h["Authorization"]},
    )
    r = client.post(
        "/api/v1/auth/qr/exchange",
        json={"session_id": parsed["session_id"], "browser_token": qr["browser_token"]},
    )
    assert r.status_code == 200
    # 不应有 cookie
    assert "campus_trusted_device" not in r.cookies


def test_logout_revokes_trusted_device() -> None:
    client = _client()
    mobile_h = _login(client, "student_demo")
    qr = _qr_create(client)
    parsed = _parse_payload(qr["qr_payload"])
    client.post("/api/v1/auth/qr/scan", json=parsed, headers={"Authorization": mobile_h["Authorization"]})
    client.post(
        "/api/v1/auth/qr/confirm",
        json={**parsed, "trust_device": True},
        headers={"Authorization": mobile_h["Authorization"]},
    )
    exchange_resp = client.post(
        "/api/v1/auth/qr/exchange",
        json={"session_id": parsed["session_id"], "browser_token": qr["browser_token"]},
    )
    web_tokens = exchange_resp.json()
    # 用 web token 登出
    logout_resp = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": web_tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {web_tokens['access_token']}"},
    )
    assert logout_resp.status_code == 200
    # logout 后 trusted device cookie 应被清除，自动登录应失败
    auto_resp = client.post(
        "/api/v1/auth/trusted-device/auto-login",
        json={"device_id": "test-device-001"},
    )
    assert auto_resp.status_code == 401


def test_user_deactivation_revokes_trusted_device() -> None:
    client = _client()
    admin_h = _login(client, "admin_demo")
    mobile_h = _login(client, "student_demo")
    qr = _qr_create(client)
    parsed = _parse_payload(qr["qr_payload"])
    client.post("/api/v1/auth/qr/scan", json=parsed, headers={"Authorization": mobile_h["Authorization"]})
    client.post(
        "/api/v1/auth/qr/confirm",
        json={**parsed, "trust_device": True},
        headers={"Authorization": mobile_h["Authorization"]},
    )
    exchange_resp = client.post(
        "/api/v1/auth/qr/exchange",
        json={"session_id": parsed["session_id"], "browser_token": qr["browser_token"]},
    )
    web_user = exchange_resp.json()["user"]
    # admin 停用该用户
    deactivate_resp = client.patch(
        f"/api/v1/auth/admin/users/{web_user['id']}",
        json={"is_active": False},
        headers={"Authorization": admin_h["Authorization"]},
    )
    assert deactivate_resp.status_code == 200
    # 停用后 trusted device 自动登录应失败
    auto_resp = client.post(
        "/api/v1/auth/trusted-device/auto-login",
        json={"device_id": "test-device-001"},
    )
    assert auto_resp.status_code == 401


def test_trusted_device_auto_login_without_cookie_rejected() -> None:
    client = _client()
    r = client.post("/api/v1/auth/trusted-device/auto-login", json={"device_id": "x"})
    assert r.status_code == 401
    assert r.json()["code"] == "TRUSTED_DEVICE_INVALID"


def test_list_trusted_devices() -> None:
    client = _client()
    mobile_h = _login(client, "student_demo")
    qr = _qr_create(client)
    parsed = _parse_payload(qr["qr_payload"])
    client.post("/api/v1/auth/qr/scan", json=parsed, headers={"Authorization": mobile_h["Authorization"]})
    client.post(
        "/api/v1/auth/qr/confirm",
        json={**parsed, "trust_device": True},
        headers={"Authorization": mobile_h["Authorization"]},
    )
    exchange_resp = client.post(
        "/api/v1/auth/qr/exchange",
        json={"session_id": parsed["session_id"], "browser_token": qr["browser_token"]},
    )
    web_tokens = exchange_resp.json()
    # 列出可信设备
    r = client.get(
        "/api/v1/auth/trusted-devices",
        headers={"Authorization": f"Bearer {web_tokens['access_token']}"},
    )
    assert r.status_code == 200
    devices = r.json()["devices"]
    assert len(devices) >= 1
    assert devices[0]["browser_name"] == "Chrome"


# ===== QR 过期测试 =====


def test_expired_qr_cannot_be_scanned() -> None:
    """模拟过期：直接操作数据库设置过期时间。"""
    client = _client()
    mobile_h = _login(client, "student_demo")
    qr = _qr_create(client)
    parsed = _parse_payload(qr["qr_payload"])
    # 直接将 expires_at 设为过去
    from app.services.container import get_container
    container = get_container()
    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    with container.db.transaction() as conn:
        conn.execute(
            "UPDATE qr_login_sessions SET expires_at = ? WHERE id = ?",
            (past, parsed["session_id"]),
        )
    # 扫码应被拒绝
    r = client.post(
        "/api/v1/auth/qr/scan",
        json=parsed,
        headers={"Authorization": mobile_h["Authorization"]},
    )
    assert r.status_code == 410
    assert r.json()["code"] == "QR_EXPIRED"


def test_expired_qr_cannot_be_exchanged() -> None:
    client = _client()
    mobile_h = _login(client, "student_demo")
    qr = _qr_create(client)
    parsed = _parse_payload(qr["qr_payload"])
    client.post("/api/v1/auth/qr/scan", json=parsed, headers={"Authorization": mobile_h["Authorization"]})
    client.post(
        "/api/v1/auth/qr/confirm",
        json={**parsed, "trust_device": False},
        headers={"Authorization": mobile_h["Authorization"]},
    )
    # 设置过期
    from app.services.container import get_container
    container = get_container()
    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    with container.db.transaction() as conn:
        conn.execute(
            "UPDATE qr_login_sessions SET expires_at = ? WHERE id = ?",
            (past, parsed["session_id"]),
        )
    r = client.post(
        "/api/v1/auth/qr/exchange",
        json={"session_id": parsed["session_id"], "browser_token": qr["browser_token"]},
    )
    assert r.status_code == 410
    assert r.json()["code"] == "QR_EXPIRED"


# ===== 防刷测试 =====


def test_qr_create_rate_limit() -> None:
    """同一 device_id 短时间内频繁创建应被限制。"""
    client = _client()
    # 默认窗口 10 秒内最多 5 次
    for i in range(5):
        r = _qr_create(client)
        assert r["status"] == "PENDING"
    # 第 6 次应被限制
    r = client.post("/api/v1/auth/qr/create", json={"device_id": "test-device-001"})
    assert r.status_code == 429
    assert r.json()["code"] == "QR_RATE_LIMITED"


# ===== 浏览器重启 / logout 后自动登录语义测试 =====


def _shared_app() -> tuple:
    """创建一个共享 app + 已登录学生 headers，用于多 TestClient 场景。"""
    from fastapi import FastAPI

    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        auto_import_demo=False,
        qr_login_expire_seconds=120,
        trusted_device_expire_days=30,
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    app = create_app()
    return app


def test_trusted_device_auto_login_after_browser_restart() -> None:
    """场景1: trusted device → 浏览器完全重启 → cookie 仍在 → 自动登录成功。

    用两个独立 TestClient 实例模拟：
    - client_a: 完成扫码登录 + exchange，拿到 trusted device cookie
    - client_b: 全新实例（模拟浏览器重启），手动传入 cookie → auto-login 成功
    """
    app = _shared_app()
    client_a = TestClient(app)
    mobile_h = _login(client_a, "student_demo")
    qr = _qr_create(client_a)
    parsed = _parse_payload(qr["qr_payload"])
    client_a.post("/api/v1/auth/qr/scan", json=parsed, headers={"Authorization": mobile_h["Authorization"]})
    client_a.post(
        "/api/v1/auth/qr/confirm",
        json={**parsed, "trust_device": True},
        headers={"Authorization": mobile_h["Authorization"]},
    )
    exchange_resp = client_a.post(
        "/api/v1/auth/qr/exchange",
        json={"session_id": parsed["session_id"], "browser_token": qr["browser_token"]},
    )
    assert exchange_resp.status_code == 200
    # 提取 trusted device cookie
    cookie_value = exchange_resp.cookies.get("campus_trusted_device")
    assert cookie_value, "exchange should set campus_trusted_device cookie"
    # 模拟浏览器重启：全新 TestClient，手动传入 cookie
    client_b = TestClient(app)
    auto_resp = client_b.post(
        "/api/v1/auth/trusted-device/auto-login",
        json={"device_id": "test-device-001"},
        cookies={"campus_trusted_device": cookie_value},
    )
    assert auto_resp.status_code == 200, auto_resp.text
    assert auto_resp.json()["user"]["username"] == "student_demo"


def test_explicit_logout_blocks_auto_login_after_browser_restart() -> None:
    """场景2: explicit logout → trusted device 被撤销 → 浏览器重启 → auto-login 失败。

    关键语义：用户点击退出登录后，即使浏览器重启，绝对不能再次自动登录。
    """
    app = _shared_app()
    client_a = TestClient(app)
    mobile_h = _login(client_a, "student_demo")
    qr = _qr_create(client_a)
    parsed = _parse_payload(qr["qr_payload"])
    client_a.post("/api/v1/auth/qr/scan", json=parsed, headers={"Authorization": mobile_h["Authorization"]})
    client_a.post(
        "/api/v1/auth/qr/confirm",
        json={**parsed, "trust_device": True},
        headers={"Authorization": mobile_h["Authorization"]},
    )
    exchange_resp = client_a.post(
        "/api/v1/auth/qr/exchange",
        json={"session_id": parsed["session_id"], "browser_token": qr["browser_token"]},
    )
    web_tokens = exchange_resp.json()
    cookie_value = exchange_resp.cookies.get("campus_trusted_device")
    assert cookie_value, "exchange should set cookie"
    # 用户明确点击退出登录
    logout_resp = client_a.post(
        "/api/v1/auth/logout",
        json={"refresh_token": web_tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {web_tokens['access_token']}"},
    )
    assert logout_resp.status_code == 200
    # 模拟浏览器重启：尝试用旧 cookie 自动登录（即使浏览器非法保留了 cookie）
    client_b = TestClient(app)
    auto_resp = client_b.post(
        "/api/v1/auth/trusted-device/auto-login",
        json={"device_id": "test-device-001"},
        cookies={"campus_trusted_device": cookie_value},
    )
    assert auto_resp.status_code == 401, "logout 后即使保留旧 cookie 也不能自动登录"
    # 错误码应为 TRUSTED_DEVICE_REVOKED（后端撤销了记录）
    assert auto_resp.json()["code"] == "TRUSTED_DEVICE_REVOKED"
    # 模拟浏览器重启且 cookie 已被正确清除（正常浏览器行为）
    client_c = TestClient(app)
    auto_resp_no_cookie = client_c.post(
        "/api/v1/auth/trusted-device/auto-login",
        json={"device_id": "test-device-001"},
    )
    assert auto_resp_no_cookie.status_code == 401
    assert auto_resp_no_cookie.json()["code"] == "TRUSTED_DEVICE_INVALID"