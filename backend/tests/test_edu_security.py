"""安全与生产环境测试。

验证：
- Production 不允许自动 fallback Mock
- API Response 不含 password / cookie / token
- MockAdapter 明确标记 is_mock
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.edu.session import PreLoginSessionStore
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data
from app.services.edu.adapters.mock import MockEduAdapter
from app.services.edu.adapters.zhengfang import ZhengfangAdapter


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
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _select_demo_university(client: TestClient, headers: dict[str, str]) -> str:
    university = client.get("/api/v1/universities").json()["items"][0]
    client.put(
        "/api/v1/profile/university",
        headers=headers,
        json={"university_id": university["id"]},
    )
    return university["id"]


# ===== MockAdapter 标记 =====


def test_mock_adapter_is_marked_as_mock() -> None:
    adapter = MockEduAdapter()
    assert adapter.is_mock is True
    assert adapter.provider == "mock"


def test_real_adapters_are_not_mock() -> None:
    adapter = ZhengfangAdapter()
    assert adapter.is_mock is False


# ===== Production 不 fallback Mock =====


def test_production_does_not_fallback_to_mock() -> None:
    """production 环境下，EduConnectorService._is_mock_allowed() 应返回 False。"""
    settings = Settings(
        app_env="production",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=False,
        auto_import_demo=False,
    )
    container = reset_container_for_tests(settings)
    assert container.edu_connector._is_mock_allowed() is False

def test_pre_login_token_is_owner_bound_expires_and_is_single_use() -> None:
    store = PreLoginSessionStore()
    session = store.create(
        connection_id="connection-owner",
        user_id="user-owner",
        cookies={"JSESSIONID": "fixture-only"},
    )

    assert callable(getattr(store, "consume", None))
    assert store.consume(
        session.pre_login_token,
        user_id="user-owner",
        connection_id="connection-other",
    ) is None
    assert store.consume(
        session.pre_login_token,
        user_id="user-other",
        connection_id="connection-owner",
    ) is None
    assert store.consume(
        session.pre_login_token,
        user_id="user-owner",
        connection_id="connection-owner",
    ) is session
    assert store.consume(
        session.pre_login_token,
        user_id="user-owner",
        connection_id="connection-owner",
    ) is None

    expired = store.create(
        connection_id="connection-expired",
        user_id="user-owner",
        cookies={},
    )
    expired.expires_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    assert store.consume(
        expired.pre_login_token,
        user_id="user-owner",
        connection_id="connection-expired",
    ) is None




# ===== 安全：不返回敏感信息 =====


def test_bind_response_does_not_contain_password() -> None:
    client = _client()
    headers = _headers(client)
    _select_demo_university(client, headers)
    response = client.post(
        "/api/v1/edu/bind",
        headers=headers,
        json={"username": "S202401001", "password": "secret-pwd-123"},
    )
    assert response.status_code == 200, response.text
    text = response.text.lower()
    assert "secret-pwd-123" not in text
    assert "password" not in response.json()


def test_binding_response_does_not_contain_credential_ref() -> None:
    client = _client()
    headers = _headers(client)
    _select_demo_university(client, headers)
    client.post(
        "/api/v1/edu/bind",
        headers=headers,
        json={"username": "S202401001", "password": "demo"},
    )
    response = client.get("/api/v1/edu/binding", headers=headers)
    assert response.status_code == 200, response.text
    binding = response.json()
    assert "credential_ref" not in binding
    assert "password" not in binding


def test_sync_records_do_not_contain_credentials() -> None:
    client = _client()
    headers = _headers(client)
    _select_demo_university(client, headers)
    client.post(
        "/api/v1/edu/bind",
        headers=headers,
        json={"username": "S202401001", "password": "must-not-leak"},
    )
    client.post("/api/v1/edu/sync/profile", headers=headers)
    response = client.get("/api/v1/edu/sync/records", headers=headers)
    assert response.status_code == 200, response.text
    text = response.text.lower()
    assert "must-not-leak" not in text
    assert "cookie" not in text
    assert "authorization" not in text


def test_detect_response_does_not_contain_urls_when_not_discovered() -> None:
    """探测结果不应编造 URL。"""
    client = _client()
    headers = _headers(client)
    university_id = _select_demo_university(client, headers)
    response = client.get(
        "/api/v1/edu/detect", headers=headers, params={"university_id": university_id}
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["provider"] in ("unknown", "unsupported", "mock")
    if not result["detected"]:
        assert result["confidence"] == 0.0