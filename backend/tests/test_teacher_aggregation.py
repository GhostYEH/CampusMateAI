"""教师视角聚合接口验收测试。

覆盖:
- GET /teacher/assignments /announcements /submissions /analytics /today
- DELETE /announcements/{id}(草稿可删,已发布需先归档)
- RBAC: 学生禁止访问 /teacher/*;教师只能看自己课程下的数据。
"""
from __future__ import annotations

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


def test_teacher_aggregation_endpoints_return_real_data() -> None:
    client = _client()
    teacher = _headers(client, "teacher_demo")

    assignments = client.get("/api/v1/teacher/assignments", headers=teacher)
    assert assignments.status_code == 200
    items = assignments.json()["items"]
    assert len(items) > 0
    first = items[0]
    # 关键字段必须来自真实数据,非空且结构完整
    assert first["course_name"]
    assert first["class_name"]
    assert "student_count" in first
    assert "submitted_count" in first
    assert "graded_count" in first

    announcements = client.get("/api/v1/teacher/announcements", headers=teacher)
    assert announcements.status_code == 200
    ann_items = announcements.json()["items"]
    assert len(ann_items) > 0
    assert "read_count" in ann_items[0]
    assert "unread_count" in ann_items[0]

    submissions = client.get("/api/v1/teacher/submissions", headers=teacher)
    assert submissions.status_code == 200
    sub_items = submissions.json()["items"]
    # demo seeder 已创建至少 2 条提交
    assert len(sub_items) >= 1
    assert "assignment_title" in sub_items[0]
    assert "is_late" in sub_items[0]

    analytics = client.get("/api/v1/teacher/analytics", headers=teacher)
    assert analytics.status_code == 200
    body = analytics.json()
    assert body["total_assignments"] > 0
    assert "score_distribution" in body
    assert isinstance(body["assignments"], list)
    assert isinstance(body["students"], list)

    today = client.get("/api/v1/teacher/today", headers=teacher)
    assert today.status_code == 200
    today_body = today.json()
    assert "pending_grading_count" in today_body
    assert "due_soon_assignments" in today_body


def test_teacher_status_and_class_filters() -> None:
    client = _client()
    teacher = _headers(client, "teacher_demo")

    drafts = client.get(
        "/api/v1/teacher/assignments?status=draft", headers=teacher
    )
    assert drafts.status_code == 200
    assert all(item["status"] == "draft" for item in drafts.json()["items"])

    published = client.get(
        "/api/v1/teacher/announcements?status=published", headers=teacher
    )
    assert published.status_code == 200
    assert all(item["status"] == "published" for item in published.json()["items"])

    # 按班级筛选
    classes = client.get(
        "/api/v1/classes?page_size=100", headers=teacher
    ).json()["items"]
    if classes:
        filtered = client.get(
            f"/api/v1/teacher/assignments?class_id={classes[0]['id']}",
            headers=teacher,
        )
        assert filtered.status_code == 200
        assert all(
            item["class_group_id"] == classes[0]["id"]
            for item in filtered.json()["items"]
        )


def test_student_forbidden_to_teacher_aggregation() -> None:
    client = _client()
    student = _headers(client, "student_demo")
    for path in (
        "/api/v1/teacher/assignments",
        "/api/v1/teacher/announcements",
        "/api/v1/teacher/submissions",
        "/api/v1/teacher/analytics",
        "/api/v1/teacher/today",
    ):
        resp = client.get(path, headers=student)
        assert resp.status_code == 403, f"{path} 应拒绝学生访问"


def test_teacher_cannot_see_other_teacher_data() -> None:
    """teacher_demo2 不应看到 teacher_demo 的课程数据。"""
    client = _client()
    teacher2 = _headers(client, "teacher_demo2")
    assignments = client.get(
        "/api/v1/teacher/assignments", headers=teacher2
    )
    assert assignments.status_code == 200
    # teacher_demo2 负责英语课程,不应出现 teacher_demo 的高数/程设课程
    course_names = {item["course_name"] for item in assignments.json()["items"]}
    assert all("高等数学" not in name and "程序设计" not in name for name in course_names)


def test_delete_announcement_draft_and_published_guard() -> None:
    client = _client()
    teacher = _headers(client, "teacher_demo")
    classes = client.get(
        "/api/v1/classes?page_size=100", headers=teacher
    ).json()["items"]
    assert classes

    # 创建草稿通知
    created = client.post(
        f"/api/v1/classes/{classes[0]['id']}/announcements",
        headers=teacher,
        json={"title": "待删除草稿", "content": "测试删除", "status": "draft"},
    )
    assert created.status_code == 201
    ann_id = created.json()["id"]

    # 草稿可直接删除
    deleted = client.delete(f"/api/v1/announcements/{ann_id}", headers=teacher)
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True

    # 已发布通知不能直接删除
    published = client.post(
        f"/api/v1/classes/{classes[0]['id']}/announcements",
        headers=teacher,
        json={"title": "已发布通知", "content": "不可直接删", "status": "published"},
    )
    assert published.status_code == 201
    pub_id = published.json()["id"]
    direct_delete = client.delete(
        f"/api/v1/announcements/{pub_id}", headers=teacher
    )
    assert direct_delete.status_code == 409

    # 先归档再删除
    archived = client.patch(
        f"/api/v1/announcements/{pub_id}",
        headers=teacher,
        json={"status": "archived"},
    )
    assert archived.status_code == 200
    delete_after_archive = client.delete(
        f"/api/v1/announcements/{pub_id}", headers=teacher
    )
    assert delete_after_archive.status_code == 200


def test_student_cannot_delete_announcement() -> None:
    client = _client()
    student = _headers(client, "student_demo")
    teacher = _headers(client, "teacher_demo")
    classes = client.get(
        "/api/v1/classes?page_size=100", headers=teacher
    ).json()["items"]
    created = client.post(
        f"/api/v1/classes/{classes[0]['id']}/announcements",
        headers=teacher,
        json={"title": "学生不可删", "content": "RBAC", "status": "draft"},
    )
    ann_id = created.json()["id"]
    resp = client.delete(f"/api/v1/announcements/{ann_id}", headers=student)
    assert resp.status_code == 403