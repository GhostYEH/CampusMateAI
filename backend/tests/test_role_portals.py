from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _client() -> TestClient:
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        auto_import_demo=False,
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    return TestClient(create_app())


def _headers(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Demo123456"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_teacher_can_publish_assignment_and_view_dashboard() -> None:
    client = _client()
    teacher = _headers(client, "teacher_demo")
    dashboard = client.get("/api/v1/dashboard/teacher", headers=teacher)
    assert dashboard.status_code == 200
    assert dashboard.json()["class_count"] > 0

    classes = client.get(
        "/api/v1/classes?page_size=100",
        headers=teacher,
    ).json()["items"]
    created = client.post(
        f"/api/v1/classes/{classes[0]['id']}/assignments",
        headers=teacher,
        json={
            "title": "教师端接口验收任务",
            "description": "验证任务发布数据链路。",
            "submission_types": ["text", "file"],
            "max_score": 100,
            "status": "draft",
        },
    )
    assert created.status_code == 201
    published = client.post(
        f"/api/v1/assignments/{created.json()['id']}/publish",
        headers=teacher,
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"


def test_admin_activity_and_user_management_permissions() -> None:
    client = _client()
    admin = _headers(client, "admin_demo")
    student = _headers(client, "student_demo")

    users = client.get(
        "/api/v1/auth/admin/users?page_size=100",
        headers=admin,
    )
    assert users.status_code == 200
    assert users.json()["total"] >= 4
    assert client.get(
        "/api/v1/auth/admin/users",
        headers=student,
    ).status_code == 403

    created = client.post(
        "/api/v1/admin/activities",
        headers=admin,
        json={
            "title": "管理员端接口验收活动",
            "content": "验证全校活动发布与学生可见性。",
            "category": "campus",
            "status": "published",
        },
    )
    assert created.status_code == 201

    visible = client.get("/api/v1/activities", headers=student)
    assert visible.status_code == 200
    assert any(
        item["id"] == created.json()["id"]
        for item in visible.json()["items"]
    )
    assert all(item["status"] == "published" for item in visible.json()["items"])
