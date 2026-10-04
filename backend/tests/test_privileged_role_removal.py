import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import create_access_token, decode_jwt, hash_password
from app.main import create_app
from app.services.container import reset_container_for_tests


@pytest.fixture
def env():
    settings = Settings(_env_file=None, app_env="test", auto_seed_demo_users=False, auto_import_demo=False)
    container = reset_container_for_tests(settings)
    return TestClient(create_app()), container


def test_removed_management_operations_are_absent_from_openapi_and_router(env):
    client, _ = env
    paths = client.app.openapi()["paths"]
    assert not any("/admin/" in path for path in paths)
    removed = [
        ("post", "/api/v1/courses"), ("patch", "/api/v1/courses/{course_id}"),
        ("put", "/api/v1/edu/config/{university_id}"), ("post", "/api/v1/edu/systems/{university_id}"),
        ("get", "/api/v1/edu/discovery/candidates"),
        ("post", "/api/v1/edu/discovery/candidates/{school_code}/review"),
        ("get", "/api/v1/edu/discovery/stats"),
        ("post", "/api/v1/knowledge/documents"), ("delete", "/api/v1/knowledge/documents/{document_id}"),
        ("post", "/api/v1/knowledge/rebuild"), ("post", "/api/v1/knowledge/manage/{action}"),
    ]
    for method, path in removed:
        assert method not in paths.get(path, {})
    for path in ("/api/v1/auth/admin/users", "/api/v1/admin/community/posts", "/api/v1/admin/community/reports",
                 "/api/v1/admin/home-banners", "/api/v1/admin/agent-runtime/overview"):
        assert client.get(path).status_code == 404


@pytest.mark.parametrize("role", ["admin", "teacher"])
def test_historical_roles_and_tokens_receive_only_student_access(env, role):
    client, c = env
    account = c.user_repository.create_user(username="legacy_user", password_hash=hash_password("Test-password-123"))
    with c.db.transaction() as conn:
        conn.execute("UPDATE users SET role=? WHERE id=?", (role, account.id))
    token, _ = create_access_token(account.id, role, c.settings.jwt_secret)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/auth/me", headers=headers).json()["user"]["role"] == "student"
    assert client.get("/api/v1/community/posts", headers=headers).status_code == 409
    pair = client.post("/api/v1/auth/login", json={"username": "legacy_user", "password": "Test-password-123"}).json()
    assert pair["user"]["role"] == "student"
    assert decode_jwt(pair["access_token"], c.settings.jwt_secret).role == "student"
    assert decode_jwt(pair["refresh_token"], c.settings.jwt_secret).role == "student"
    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]}).json()
    assert refreshed["user"]["role"] == "student"
    assert c.user_repository.get_user_by_id(account.id).role == "student"
    with c.db.query() as conn:
        assert conn.execute("SELECT role FROM users WHERE id=?", (account.id,)).fetchone()["role"] == role


def test_registration_repository_and_profile_cannot_create_or_restore_admin(env):
    client, c = env
    payload = {"username": "ordinary_user", "password": "Test-password-123", "role": "admin"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 422
    with pytest.raises(ValueError):
        c.user_repository.create_user(username="privileged", password_hash="unused", role="admin")
    payload["role"] = "student"
    created = client.post("/api/v1/auth/register", json=payload).json()
    pair = client.post("/api/v1/auth/login", json=payload).json()
    headers = {"Authorization": f"Bearer {pair['access_token']}"}
    assert client.patch("/api/v1/auth/me", headers=headers, json={"role": "admin"}).status_code == 422
    assert client.patch("/api/v1/auth/me", headers=headers, json={"is_active": False}).status_code == 422
    updated = client.patch("/api/v1/auth/me", headers=headers, json={"display_name": "同学", "college": "学院"})
    assert updated.status_code == 200
    assert updated.json()["role"] == "student"
    assert c.user_repository.get_user_by_id(created["id"]).display_name == "同学"
