"""二维码创建防刷：ASGI peer 限流 + 设备限制作为额外保护。

覆盖:
- 省略 / null / 空 device_id 时仍然限流
- 轮换 device_id 不能绕过 peer 额度
- 不同 peer 使用不同额度；伪造 X-Forwarded-For 不能改变归属
- 窗口边界与并发计数（假时间 + 隔离限流器，不使用 sleep）
- 被拒绝时不会创建会话

限流是单进程内的 ASGI peer 计数，不是跨实例全局配额。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.rate_limit import RateLimited, RequestRateLimiter
from app.main import create_app
from app.services.container import get_container, reset_container_for_tests

_QR_CREATE = "/api/v1/auth/qr/create"


def _client() -> TestClient:
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=False,
        auto_import_demo=False,
    )
    reset_container_for_tests(settings)
    return TestClient(create_app())


def _session_count() -> int:
    container = get_container()
    with container.db.query() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM qr_login_sessions").fetchone()[0])


def _create(client: TestClient, payload: dict | None = None):
    return client.post(_QR_CREATE, json=payload if payload is not None else {})


@pytest.mark.parametrize("payload", [{}, {"device_id": None}, {"device_id": ""}])
def test_qr_create_is_throttled_without_usable_device_id(payload: dict) -> None:
    """device_id 可选；省略 / null / 空串都不能绕过 peer 额度。"""
    client = _client()
    for _ in range(5):
        assert _create(client, payload).status_code == 200
    blocked = _create(client, payload)
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "QR_RATE_LIMITED"
    # 通用限流器的 retry_after 必须转成 Retry-After 头。
    assert 1 <= int(blocked.headers["retry-after"]) <= 10


def test_qr_create_peer_quota_survives_device_rotation() -> None:
    """轮换 device_id 仍受同一 peer 额度约束。"""
    client = _client()
    for index in range(5):
        assert _create(client, {"device_id": f"rotating-device-{index}"}).status_code == 200
    blocked = _create(client, {"device_id": "rotating-device-final"})
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "QR_RATE_LIMITED"


def test_qr_create_rejection_does_not_create_a_session() -> None:
    """被拒绝的请求不会走到清理 / 生成凭据 / 写库。"""
    client = _client()
    for _ in range(5):
        assert _create(client).status_code == 200
    assert _session_count() == 5
    for _ in range(3):
        assert _create(client).status_code == 429
    assert _session_count() == 5


def test_qr_create_peer_limit_ignores_forged_forwarded_headers() -> None:
    """非可信代理来源的 X-Forwarded-For 不能改变限流归属。"""
    import uvicorn

    settings = Settings(
        app_env="test", database_url="sqlite:///:memory:",
        auto_seed_demo_users=False, auto_import_demo=False,
    )
    reset_container_for_tests(settings)
    config = uvicorn.Config(create_app(), forwarded_allow_ips="127.0.0.1", log_config=None)
    config.load()
    client = TestClient(config.loaded_app)
    for index in range(5):
        assert client.post(
            _QR_CREATE, json={}, headers={"X-Forwarded-For": f"203.0.113.{index + 1}"}
        ).status_code == 200
    blocked = client.post(
        _QR_CREATE, json={}, headers={"X-Forwarded-For": "203.0.113.200"}
    )
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "QR_RATE_LIMITED"


def test_qr_create_separates_trusted_proxy_peers() -> None:
    """可信代理下不同真实客户端使用不同额度。"""
    import uvicorn

    settings = Settings(
        app_env="test", database_url="sqlite:///:memory:",
        auto_seed_demo_users=False, auto_import_demo=False,
    )
    reset_container_for_tests(settings)
    config = uvicorn.Config(create_app(), forwarded_allow_ips="testclient", log_config=None)
    config.load()
    client = TestClient(config.loaded_app)
    for _ in range(5):
        assert client.post(
            _QR_CREATE, json={}, headers={"X-Forwarded-For": "203.0.113.1"}
        ).status_code == 200
    assert client.post(
        _QR_CREATE, json={}, headers={"X-Forwarded-For": "203.0.113.1"}
    ).status_code == 429
    # 另一个真实客户端仍有自己的额度。
    assert client.post(
        _QR_CREATE, json={}, headers={"X-Forwarded-For": "203.0.113.2"}
    ).status_code == 200


def test_qr_limiter_counts_exactly_at_quota_under_concurrency() -> None:
    """并发计数：恰好 5 次通过，其余被拒绝。"""
    limiter = RequestRateLimiter(max_keys=8)

    def attempt(_: int) -> bool:
        try:
            limiter.check("qr_create", "peer", limit=5, window=10)
            return True
        except RateLimited:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(30))) == 5


def test_qr_limiter_window_boundary_frees_quota_at_exactly_window(monkeypatch) -> None:
    """窗口边界：满 10 秒才释放，9.999 秒仍受限；不使用 sleep。"""
    from app.core import rate_limit

    now = {"value": 100.0}
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: now["value"])
    limiter = RequestRateLimiter()
    for _ in range(5):
        limiter.check("qr_create", "peer", limit=5, window=10)
    with pytest.raises(RateLimited):
        limiter.check("qr_create", "peer", limit=5, window=10)
    now["value"] = 109.999
    with pytest.raises(RateLimited):
        limiter.check("qr_create", "peer", limit=5, window=10)
    now["value"] = 110.0
    limiter.check("qr_create", "peer", limit=5, window=10)


def test_default_window_stays_60_seconds_for_existing_callers(monkeypatch) -> None:
    """扩展 helper 不能改变其他调用方的默认窗口。"""
    from app.core import rate_limit

    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: 1000)
    limiter = RequestRateLimiter()
    for _ in range(5):
        limiter.check("login", "peer", limit=5)
    with pytest.raises(RateLimited) as excinfo:
        limiter.check("login", "peer", limit=5)
    assert excinfo.value.retry_after == 60
