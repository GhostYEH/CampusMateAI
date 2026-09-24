"""公开注册和管理员建号共享创建流程时的接口契约。"""

from secrets import token_urlsafe

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.container import reset_container_for_tests


def _client_and_admin_headers() -> tuple[TestClient, dict[str, str]]:
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=False,
        auto_import_demo=False,
    )
    container = reset_container_for_tests(settings)
    admin_password = token_urlsafe(12)
    container.user_repository.create_user(
        username="creation_test_admin",
        password_hash=hash_password(admin_password),
        role="admin",
    )
    client = TestClient(create_app())
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "creation_test_admin", "password": admin_password},
    )
    assert login.status_code == 200
    return client, {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_register_and_admin_create_preserve_user_fields_and_login() -> None:
    client, admin_headers = _client_and_admin_headers()
    common = {
        "password": token_urlsafe(12),
        "display_name": "测试同学",
        "college": "计算机学院",
        "major": "软件工程",
        "grade": "2026",
    }
    for url, headers, username, student_number in (
        ("/api/v1/auth/register", {}, "public_student", "S1001"),
        ("/api/v1/auth/admin/users", admin_headers, "admin_student", "S1002"),
    ):
        response = client.post(
            url,
            headers=headers,
            json={**common, "username": username, "role": "student", "student_number": student_number},
        )
        assert response.status_code == 201, response.text
        user = response.json()
        assert user["username"] == username
        assert user["student_number"] == student_number
        assert user["college"] == common["college"]
        assert "password_hash" not in user
        assert client.post(
            "/api/v1/auth/login", json={"username": username, "password": common["password"]}
        ).status_code == 200

    admin = client.post(
        "/api/v1/auth/admin/users",
        headers=admin_headers,
        json={"username": "created_admin", "password": common["password"], "role": "admin"},
    )
    assert admin.status_code == 201, admin.text
    assert admin.json()["role"] == "admin"


def test_creation_rejects_duplicate_identifiers_and_invalid_role_fields() -> None:
    client, admin_headers = _client_and_admin_headers()
    base = {"password": token_urlsafe(12), "role": "student"}
    created = client.post(
        "/api/v1/auth/register",
        json={**base, "username": "first_student", "student_number": "S2001"},
    )
    assert created.status_code == 201

    for url, headers in (
        ("/api/v1/auth/register", {}),
        ("/api/v1/auth/admin/users", admin_headers),
    ):
        duplicate_name = client.post(
            url, headers=headers, json={**base, "username": "first_student"}
        )
        assert duplicate_name.status_code == 409
        assert duplicate_name.json()["code"] == "USERNAME_EXISTS"

        duplicate_number = client.post(
            url,
            headers=headers,
            json={**base, "username": f"other_{len(url)}", "student_number": "S2001"},
        )
        assert duplicate_number.status_code == 409
        assert duplicate_number.json()["code"] == "STUDENT_NUMBER_EXISTS"

        invalid_student = client.post(
            url,
            headers=headers,
            json={**base, "username": f"teacher_{len(url)}", "teacher_number": "T2001"},
        )
        assert invalid_student.status_code == 422

    invalid_admin = client.post(
        "/api/v1/auth/admin/users",
        headers=admin_headers,
        json={**base, "username": "invalid_admin", "role": "admin", "student_number": "S3001"},
    )
    assert invalid_admin.status_code == 422

    invalid_admin_teacher = client.post(
        "/api/v1/auth/admin/users",
        headers=admin_headers,
        json={**base, "username": "invalid_admin_teacher", "role": "admin", "teacher_number": "T3001"},
    )
    assert invalid_admin_teacher.status_code == 422
