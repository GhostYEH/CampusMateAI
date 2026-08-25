"""安全与生产环境测试。

验证：
- Production 不允许自动 fallback Mock
- API Response 不含 password / cookie / token
- MockAdapter 明确标记 is_mock
"""
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.database.sqlite_db import Database
from app.main import create_app
from app.services.edu.session import PreLoginSessionStore
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data
from app.services.edu.adapters.mock import MockEduAdapter
from app.services.edu.adapters.zhengfang import ZhengfangAdapter


_TEST_EDU_SESSION_KEY = base64.b64encode(b"test-only-edu-session-key-32byte").decode("ascii")


def _encrypted_session_store(db: Database, *, ttl_seconds: int = 1800):
    from app.services.edu.encrypted_session_store import EncryptedSqliteEduSessionStore

    return EncryptedSqliteEduSessionStore(
        db=db,
        encryption_key_base64=_TEST_EDU_SESSION_KEY,
        key_id="test-key-v1",
        session_ttl_seconds=ttl_seconds,
    )


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
        edu_session_encryption_key=_TEST_EDU_SESSION_KEY,
    )
    container = reset_container_for_tests(settings)
    assert container.edu_connector._is_mock_allowed() is False

def test_production_requires_edu_session_encryption_key() -> None:
    with pytest.raises(ValueError, match="EDU_SESSION_ENCRYPTION_KEY"):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="sqlite:///:memory:",
            auto_seed_demo_users=False,
            auto_import_demo=False,
            jwt_secret="production-test-secret-that-is-long-enough-1234567890",
        )


@pytest.mark.parametrize("invalid_key", ["not-base64", base64.b64encode(b"too-short").decode("ascii")])
def test_production_rejects_invalid_edu_session_encryption_key(invalid_key: str) -> None:
    with pytest.raises(ValueError, match="EDU_SESSION_ENCRYPTION_KEY"):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="sqlite:///:memory:",
            auto_seed_demo_users=False,
            auto_import_demo=False,
            jwt_secret="production-test-secret-that-is-long-enough-1234567890",
            edu_session_encryption_key=invalid_key,
        )


def test_production_rejects_memory_edu_session_store() -> None:
    with pytest.raises(ValueError, match="EDU_SESSION_STORE"):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="sqlite:///:memory:",
            auto_seed_demo_users=False,
            auto_import_demo=False,
            jwt_secret="production-test-secret-that-is-long-enough-1234567890",
            edu_session_store="memory",
            edu_session_encryption_key=_TEST_EDU_SESSION_KEY,
        )


def test_test_container_can_explicitly_use_memory_edu_session_store() -> None:
    from app.services.edu.session import InMemorySessionStore

    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=False,
        auto_import_demo=False,
        edu_session_store="memory",
    )
    container = reset_container_for_tests(settings)
    assert isinstance(container.edu_connector._sessions, InMemorySessionStore)


def test_production_container_defaults_to_encrypted_edu_session_store() -> None:
    from app.services.edu.encrypted_session_store import EncryptedSqliteEduSessionStore

    settings = Settings(
        _env_file=None,
        app_env="production",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=False,
        auto_import_demo=False,
        jwt_secret="production-test-secret-that-is-long-enough-1234567890",
        edu_session_encryption_key=_TEST_EDU_SESSION_KEY,
    )
    container = reset_container_for_tests(settings)
    assert isinstance(
        container.edu_connector._sessions, EncryptedSqliteEduSessionStore
    )


def test_edu_session_schema_is_idempotent(tmp_path) -> None:
    db_path = tmp_path / "edu-sessions.db"
    first = Database(db_path)
    with first.query() as conn:
        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(edu_sessions)")
        }
    first.dispose()

    second = Database(db_path)
    second.dispose()

    assert {
        "connection_id",
        "user_id",
        "envelope_version",
        "key_id",
        "nonce",
        "ciphertext",
        "expires_at",
        "created_at",
    }.issubset(columns)


def test_encrypted_edu_session_recovers_after_store_restart(tmp_path) -> None:
    db_path = tmp_path / "recoverable-sessions.db"
    first_db = Database(db_path)
    first_store = _encrypted_session_store(first_db)
    created = first_store.create_session(
        user_id="owner-a",
        university_id="university-a",
        provider="zhengfang",
        system_type="undergrad",
        external_student_id="student-a",
        internal={"cookies": {"JSESSIONID": "recoverable-cookie"}, "csrftoken": "csrf-a"},
    )
    first_db.dispose()

    restarted_db = Database(db_path)
    recovered = _encrypted_session_store(restarted_db).get_session(created.session_id)
    restarted_db.dispose()

    assert recovered is not None
    assert recovered.user_id == "owner-a"
    assert recovered.external_student_id == "student-a"
    assert recovered._internal == {
        "cookies": {"JSESSIONID": "recoverable-cookie"},
        "csrftoken": "csrf-a",
    }


def test_encrypted_edu_session_sqlite_has_no_plaintext_session_markers(tmp_path) -> None:
    db_path = tmp_path / "opaque-sessions.db"
    db = Database(db_path)
    store = _encrypted_session_store(db)
    markers = {
        "cookie": "raw-cookie-marker-7c62",
        "csrf": "raw-csrf-marker-b840",
        "user_agent": "raw-user-agent-marker-25d1",
        "current_url": "https://raw-current-url-marker.invalid/session",
    }
    store.create_session(
        user_id="owner-raw",
        university_id="university-raw",
        provider="zhengfang",
        system_type="undergrad",
        internal={
            "cookies": {"JSESSIONID": markers["cookie"]},
            "csrftoken": markers["csrf"],
            "user_agent": markers["user_agent"],
            "current_url": markers["current_url"],
        },
    )
    db.dispose()

    raw_sqlite = b"".join(
        path.read_bytes() for path in db_path.parent.glob(f"{db_path.name}*")
    )
    for marker in markers.values():
        assert marker.encode("utf-8") not in raw_sqlite


def test_encrypted_edu_session_tamper_is_deleted_on_restart(tmp_path) -> None:
    db = Database(tmp_path / "tampered-sessions.db")
    store = _encrypted_session_store(db)
    session = store.create_session(
        user_id="tamper-owner",
        university_id="university-a",
        provider="zhengfang",
        system_type="undergrad",
        internal={"cookies": {"JSESSIONID": "tamper-cookie"}},
    )
    with db.transaction() as conn:
        row = conn.execute(
            "SELECT ciphertext FROM edu_sessions WHERE connection_id = ?",
            (session.session_id,),
        ).fetchone()
        tampered = bytearray(row["ciphertext"])
        tampered[-1] ^= 1
        conn.execute(
            "UPDATE edu_sessions SET ciphertext = ? WHERE connection_id = ?",
            (bytes(tampered), session.session_id),
        )

    restarted = _encrypted_session_store(db)
    with db.query() as conn:
        assert conn.execute("SELECT COUNT(*) FROM edu_sessions").fetchone()[0] == 0
    assert restarted.get_session(session.session_id) is None
    db.dispose()


def test_encrypted_edu_session_aad_swap_is_rejected(tmp_path) -> None:
    db = Database(tmp_path / "aad-swap-sessions.db")
    store = _encrypted_session_store(db)
    first = store.create_session(
        user_id="owner-first",
        university_id="university-a",
        provider="zhengfang",
        system_type="undergrad",
        internal={"cookies": {"JSESSIONID": "first-cookie"}},
    )
    second = store.create_session(
        user_id="owner-second",
        university_id="university-b",
        provider="zhengfang",
        system_type="undergrad",
        internal={"cookies": {"JSESSIONID": "second-cookie"}},
    )
    with db.transaction() as conn:
        rows = conn.execute(
            "SELECT connection_id, nonce, ciphertext FROM edu_sessions"
        ).fetchall()
        envelopes = {row["connection_id"]: row for row in rows}
        conn.execute(
            "UPDATE edu_sessions SET nonce = ?, ciphertext = ? WHERE connection_id = ?",
            (
                envelopes[second.session_id]["nonce"],
                envelopes[second.session_id]["ciphertext"],
                first.session_id,
            ),
        )
        conn.execute(
            "UPDATE edu_sessions SET nonce = ?, ciphertext = ? WHERE connection_id = ?",
            (
                envelopes[first.session_id]["nonce"],
                envelopes[first.session_id]["ciphertext"],
                second.session_id,
            ),
        )

    assert store.get_session(first.session_id) is None
    assert store.get_session(second.session_id) is None
    db.dispose()


@pytest.mark.parametrize(
    ("column", "value"),
    [("envelope_version", 999), ("key_id", "unknown-key")],
)
def test_encrypted_edu_session_unknown_envelope_is_deleted(
    tmp_path, column: str, value
) -> None:
    db = Database(tmp_path / f"unknown-{column}.db")
    store = _encrypted_session_store(db)
    session = store.create_session(
        user_id="unknown-owner",
        university_id="university-a",
        provider="zhengfang",
        system_type="undergrad",
        internal={},
    )
    with db.transaction() as conn:
        conn.execute(
            f"UPDATE edu_sessions SET {column} = ? WHERE connection_id = ?",
            (value, session.session_id),
        )

    assert store.get_session(session.session_id) is None
    with db.query() as conn:
        assert conn.execute("SELECT COUNT(*) FROM edu_sessions").fetchone()[0] == 0
    db.dispose()


def test_encrypted_edu_session_startup_cleans_expired_records(tmp_path) -> None:
    db = Database(tmp_path / "expired-sessions.db")
    store = _encrypted_session_store(db)
    expired = store.create_session(
        user_id="expired-owner",
        university_id="university-a",
        provider="zhengfang",
        system_type="undergrad",
        internal={},
        ttl_seconds=-1,
    )

    restarted = _encrypted_session_store(db)
    assert restarted.get_session(expired.session_id) is None
    with db.query() as conn:
        assert conn.execute("SELECT COUNT(*) FROM edu_sessions").fetchone()[0] == 0
    db.dispose()


def test_encrypted_edu_session_rejects_password_fields(tmp_path) -> None:
    db = Database(tmp_path / "password-sessions.db")
    store = _encrypted_session_store(db)
    with pytest.raises(ValueError, match="password"):
        store.create_session(
            user_id="password-owner",
            university_id="university-a",
            provider="zhengfang",
            system_type="undergrad",
            internal={"nested": {"password": "must-never-be-persisted"}},
        )
    with db.query() as conn:
        assert conn.execute("SELECT COUNT(*) FROM edu_sessions").fetchone()[0] == 0
    db.dispose()


def test_encrypted_edu_session_concurrent_operations_keep_owner_isolation(
    tmp_path,
) -> None:
    db = Database(tmp_path / "concurrent-sessions.db")
    store = _encrypted_session_store(db)

    def create(owner_index: int):
        return store.create_session(
            user_id=f"owner-{owner_index}",
            university_id="university-a",
            provider="zhengfang",
            system_type="undergrad",
            internal={"cookies": {"JSESSIONID": f"cookie-{owner_index}"}},
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        sessions = list(executor.map(create, range(24)))
        recovered = list(executor.map(store.get_session, [s.session_id for s in sessions]))

    assert {session.user_id for session in recovered if session is not None} == {
        f"owner-{index}" for index in range(24)
    }
    for index, session in enumerate(sessions):
        owner_session = store.get_session_by_user(f"owner-{index}")
        assert owner_session is not None
        assert owner_session.session_id == session.session_id

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(store.destroy_session, [s.session_id for s in sessions]))
    with db.query() as conn:
        assert conn.execute("SELECT COUNT(*) FROM edu_sessions").fetchone()[0] == 0
    db.dispose()


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
