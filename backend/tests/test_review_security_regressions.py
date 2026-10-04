from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import re

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.rate_limit import RateLimited, RequestRateLimiter
from app.main import _build_origin_regex, create_app
from app.services.container import reset_container_for_tests
from app.services.edu.session import EduSession, InMemorySessionStore, PreLoginSession


@pytest.mark.parametrize("expiry", ["invalid", "", "2026-10-04T12:00:00"])
def test_broken_session_expiry_is_rejected(expiry):
    now = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
    assert EduSession("s", "u", "school", "provider", "type", expires_at=expiry).is_expired(now)
    assert PreLoginSession("p", "c", "u", expires_at=expiry).is_expired(now)


def test_session_expires_at_the_boundary_and_stores_evict_bad_expiry():
    now = datetime.now(timezone.utc)
    session = EduSession("s", "u", "school", "provider", "type", expires_at=now.isoformat())
    assert session.is_expired(now)
    session.expires_at = (now + timedelta(seconds=30)).isoformat()
    assert not session.is_expired(now)
    store = InMemorySessionStore()
    session = store.create_session(user_id="u", university_id="school", provider="p", system_type="t")
    session.expires_at = "broken"
    assert store.get_session(session.session_id) is None


def test_rate_limiter_allows_exact_quota_atomically_and_expires(monkeypatch):
    from app.core import rate_limit
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: 100)
    limiter = RequestRateLimiter(max_keys=4)

    def attempt(_):
        try:
            limiter.check("login", "peer", limit=5)
            return True
        except RateLimited as exc:
            assert exc.retry_after == 60
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(30))) == 5
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: 160)
    limiter.check("login", "peer", limit=5)
    for index in range(20):
        limiter.check("login", str(index), limit=5)
    assert len(limiter._requests) == 4


def _client():
    reset_container_for_tests(Settings(_env_file=None, app_env="test", auto_seed_demo_users=False, auto_import_demo=False))
    return TestClient(create_app())


def test_login_is_throttled_with_traceable_retry_after():
    client = _client()
    for _ in range(20):
        response = client.post("/api/v1/auth/login", json={"username": "missing", "password": "test-password"})
        assert response.status_code == 401
    blocked = client.post("/api/v1/auth/login", json={"username": "missing", "password": "test-password"})
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "RATE_LIMITED"
    assert blocked.json()["request_id"] == blocked.headers["x-request-id"]
    assert 1 <= int(blocked.headers["retry-after"]) <= 60


def test_uvicorn_trusted_proxy_separates_client_buckets_and_ignores_forged_chain():
    import uvicorn
    config = uvicorn.Config(_client().app, forwarded_allow_ips="testclient", log_config=None)
    config.load()
    client = TestClient(config.loaded_app)
    payload = {"username": "missing", "password": "test-password"}
    for _ in range(20):
        assert client.post("/api/v1/auth/login", json=payload, headers={"X-Forwarded-For": "203.0.113.1"}).status_code == 401
    assert client.post("/api/v1/auth/login", json=payload, headers={"X-Forwarded-For": "203.0.113.1"}).status_code == 429
    assert client.post("/api/v1/auth/login", json=payload, headers={"X-Forwarded-For": "203.0.113.2"}).status_code == 401
    # The proxy appends the real peer; a forged left-hand address cannot change the bucket.
    assert client.post("/api/v1/auth/login", json=payload, headers={"X-Forwarded-For": "203.0.113.99, 203.0.113.1"}).status_code == 429


def test_uvicorn_untrusted_peer_cannot_change_bucket_using_forwarded_headers():
    import uvicorn
    config = uvicorn.Config(_client().app, forwarded_allow_ips="127.0.0.1", log_config=None)
    config.load()
    client = TestClient(config.loaded_app)
    payload = {"username": "missing", "password": "test-password"}
    for index in range(20):
        assert client.post("/api/v1/auth/login", json=payload, headers={"X-Forwarded-For": f"203.0.113.{index + 1}"}).status_code == 401
    assert client.post("/api/v1/auth/login", json=payload, headers={"X-Forwarded-For": "203.0.113.100"}).status_code == 429


def test_chat_aliases_share_the_anonymous_limit():
    client = _client()
    for index in range(10):
        path = "/api/v1/counselor/chat" if index % 2 else "/api/v1/assistant/chat"
        response = client.post(path, json={"message": "你好", "stream": False})
        assert response.status_code == 200, response.text
    assert client.post("/api/v1/assistant/chat", json={"message": "你好"}).status_code == 429


def test_registration_is_throttled_before_creating_more_accounts():
    client = _client()
    payload = {"username": "review_student", "password": "Test-password-123", "role": "student"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    for _ in range(4):
        assert client.post("/api/v1/auth/register", json=payload).status_code == 409
    assert client.post("/api/v1/auth/register", json=payload).status_code == 429


@pytest.mark.parametrize("payload", [
    {"message": "x" * 20001},
    {"message": "hello", "conversation_id": "x" * 129},
    {"message": "hello", "recent_tasks": [{"id": "x"}] * 101},
    {"message": "hello", "recent_tasks": [{"id": "x" * 129}]},
])
def test_chat_rejects_unbounded_context_before_work(payload):
    response = _client().post("/api/v1/counselor/chat", json=payload)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_FAILED"


def test_cors_patterns_escape_literals_and_only_accept_numeric_ports():
    pattern = _build_origin_regex(["http://localhost:*", "https://a+b.example"])
    assert re.fullmatch(pattern, "http://localhost:3000")
    assert re.fullmatch(pattern, "https://a+b.example")
    assert not re.fullmatch(pattern, "https://aaab.example")
    assert not re.fullmatch(pattern, "http://localhost:3000.attacker.example")
    assert not re.fullmatch(_build_origin_regex([]), "https://example.com")


def test_unhandled_errors_have_cors_and_matching_request_id(monkeypatch):
    # 客户端依赖的是白名单回显分支，固定它才能不受部署环境 CORS_ORIGINS 影响
    monkeypatch.setattr(
        "app.main.get_settings",
        lambda: Settings(
            _env_file=None,
            app_env="test",
            cors_origins="http://localhost:*,http://127.0.0.1:*",
            auto_seed_demo_users=False,
            auto_import_demo=False,
        ),
    )
    app = create_app()

    @app.get("/review-error")
    def fail():
        raise RuntimeError("private error text")

    response = TestClient(app, raise_server_exceptions=False).get(
        "/review-error", headers={"Origin": "http://localhost:3000", "X-Request-ID": "review-error"},
    )
    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["x-request-id"] == response.json()["request_id"] == "review-error"
    assert {"X-Request-ID", "Retry-After"} <= set(response.headers["access-control-expose-headers"].split(", "))
    assert "private error text" not in response.text
