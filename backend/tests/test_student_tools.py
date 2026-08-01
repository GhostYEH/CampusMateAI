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


def test_student_activity_registration_and_profile_isolated() -> None:
    client = _client()
    admin = _headers(client, "admin_demo")
    student = _headers(client, "student_demo")

    activity = client.post(
        "/api/v1/admin/activities",
        headers=admin,
        json={"title": "学生端报名测试", "content": "报名链路测试", "status": "published"},
    )
    assert activity.status_code == 201
    activity_id = activity.json()["id"]

    before = client.get(f"/api/v1/activities/{activity_id}/registration", headers=student)
    assert before.status_code == 200
    assert before.json()["registered"] is False
    registered = client.post(f"/api/v1/activities/{activity_id}/registration", headers=student)
    assert registered.status_code == 200
    assert registered.json()["registered"] is True
    cancelled = client.delete(f"/api/v1/activities/{activity_id}/registration", headers=student)
    assert cancelled.status_code == 200
    assert cancelled.json()["registered"] is False

    profile = client.patch(
        "/api/v1/admin/profile",
        headers=student,
        json={"display_name": "学生端测试资料"},
    )
    assert profile.status_code == 200
    assert profile.json()["display_name"] == "学生端测试资料"


def test_student_tools_only_return_current_users_records() -> None:
    client = _client()
    student = _headers(client, "student_demo")
    created = client.post(
        "/api/v1/student/exams",
        headers=student,
        json={"course_name": "接口测试课程", "exam_date": "2026-08-20", "location": "测试楼"},
    )
    assert created.status_code == 201
    assert any(item["id"] == created.json()["id"] for item in client.get("/api/v1/student/exams", headers=student).json())

    request = client.post(
        "/api/v1/student/service-requests",
        headers=student,
        json={"kind": "feedback", "title": "接口测试申请", "content": "仅当前学生可见"},
    )
    assert request.status_code == 201
    assert request.json()["user_id"] == client.get("/api/v1/auth/me", headers=student).json()["user"]["id"]

    item = client.post(
        "/api/v1/student/lost-found",
        headers=student,
        json={"kind": "lost", "title": "接口测试物品", "location": "测试地点"},
    )
    assert item.status_code == 201
    listed = client.get("/api/v1/student/lost-found", headers=student)
    assert listed.status_code == 200
    assert any(row["id"] == item.json()["id"] for row in listed.json())

