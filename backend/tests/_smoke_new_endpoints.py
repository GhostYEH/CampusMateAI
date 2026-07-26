"""冒烟测试: 验证本次新增接口的端到端流程。

仅做手动验证用,不参与 pytest 套件。
覆盖:
1. POST /api/v1/auth/admin/users — admin 创建用户 → 立即登录
2. GET /api/v1/submissions/{id}/attachments/{id} — 上传 → 下载
3. SSE 流式 AI 上下文权限 (草稿任务 → 学生 404)
"""
from __future__ import annotations


def main() -> None:
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.services.container import get_container, reset_container_for_tests
    from app.services.demo_seeder import seed_demo_data

    get_settings.cache_clear()
    settings = get_settings()
    reset_container_for_tests(settings)
    seed_demo_data(get_container(), force=True)

    from app.main import create_app

    app = create_app()
    c = TestClient(app)

    # ===== 1. admin 创建用户 =====
    admin_token = c.post(
        "/api/v1/auth/login",
        json={"username": "admin_demo", "password": "Demo123456"},
    ).json()["access_token"]
    h_admin = {"Authorization": f"Bearer {admin_token}"}

    create = c.post(
        "/api/v1/auth/admin/users",
        json={
            "username": "smoke_user",
            "password": "SmokePass1234",
            "role": "teacher",
            "teacher_number": "T_SMOKE_001",
            "display_name": "冒烟测试教师",
        },
        headers=h_admin,
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert "password_hash" not in body
    print(f"[PASS] POST /auth/admin/users -> 201, username={body['username']}")

    login = c.post(
        "/api/v1/auth/login",
        json={"username": "smoke_user", "password": "SmokePass1234"},
    )
    assert login.status_code == 200, login.text
    print("[PASS] New user can login immediately")

    # ===== 2. 附件上传与下载 =====
    teacher_token = c.post(
        "/api/v1/auth/login",
        json={"username": "teacher_demo", "password": "Demo123456"},
    ).json()["access_token"]
    student_token = c.post(
        "/api/v1/auth/login",
        json={"username": "student_demo", "password": "Demo123456"},
    ).json()["access_token"]
    h_t = {"Authorization": f"Bearer {teacher_token}"}
    h_s = {"Authorization": f"Bearer {student_token}"}

    container = get_container()
    teacher = container.user_repository.get_user_by_username("teacher_demo")
    courses, _ = container.course_repository.list_courses(
        teacher_id=teacher.id, page=1, page_size=10
    )
    classes, _ = container.class_group_repository.list_classes(
        course_id=courses[0].id, page=1, page_size=10
    )
    cls_id = classes[0].id

    asg = c.post(
        f"/api/v1/classes/{cls_id}/assignments",
        json={"title": "冒烟附件测试", "status": "published"},
        headers=h_t,
    ).json()
    asg_id = asg["id"]

    sub = c.post(
        f"/api/v1/assignments/{asg_id}/submissions",
        json={"text_content": "见附件", "submit": False},
        headers=h_s,
    ).json()
    sub_id = sub["id"]

    file_content = b"hello smoke"
    up = c.post(
        f"/api/v1/submissions/{sub_id}/attachments",
        files={"file": ("a.txt", file_content, "text/plain")},
        headers=h_s,
    ).json()
    att_id = up["id"]
    print(f"[PASS] Upload attachment: {up['original_filename']} ({up['size_bytes']}B)")

    # 学生下载自己的附件
    dl = c.get(
        f"/api/v1/submissions/{sub_id}/attachments/{att_id}",
        headers=h_s,
    )
    assert dl.status_code == 200, dl.text
    assert dl.content == file_content
    assert "a.txt" in dl.headers.get("content-disposition", "")
    print(f"[PASS] GET download by owner -> 200, content={dl.content!r}")

    # 教师下载
    dl_t = c.get(
        f"/api/v1/submissions/{sub_id}/attachments/{att_id}",
        headers=h_t,
    )
    assert dl_t.status_code == 200
    print(f"[PASS] GET download by teacher -> 200")

    # ===== 3. SSE 流式 AI 上下文权限 =====
    # 创建草稿任务
    draft = c.post(
        f"/api/v1/classes/{cls_id}/assignments",
        json={"title": "SSE 草稿冒烟", "status": "draft"},
        headers=h_t,
    ).json()
    draft_id = draft["id"]

    # 学生通过 SSE 提问草稿任务 -> 404 ASSIGNMENT_NOT_FOUND
    with c.stream(
        "POST",
        "/api/v1/counselor/chat",
        json={
            "message": "这个任务?",
            "stream": True,
            "assignment_id": draft_id,
        },
        headers=h_s,
    ) as resp:
        assert resp.status_code == 404, resp.status_code
        body = b""
        for chunk in resp.iter_bytes():
            body += chunk
        import json

        err = json.loads(body.decode("utf-8"))
        assert err["code"] == "ASSIGNMENT_NOT_FOUND"
    print("[PASS] SSE stream + draft assignment -> 404 ASSIGNMENT_NOT_FOUND")

    # 学生通过 SSE 提问已发布任务 -> 200 事件流
    with c.stream(
        "POST",
        "/api/v1/counselor/chat",
        json={
            "message": "这个任务要交什么?",
            "stream": True,
            "assignment_id": asg_id,
        },
        headers=h_s,
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        body = b""
        for chunk in resp.iter_bytes():
            body += chunk
        text = body.decode("utf-8")
        assert "event: done" in text
        assert "event: error" not in text
    print("[PASS] SSE stream + published assignment -> 200 with done event")

    print("\nAll smoke tests passed.")


if __name__ == "__main__":
    main()
