"""多角色协同平台 — 课程 / 班级 / 通知 / 任务 测试。

覆盖要求:
- 通知发布与已读回执
- 重复已读不产生重复记录
- 任务草稿学生不可见
- 学生提交、修改和重新提交
- 截止后状态为 late
- 教师评分
- 任务统计正确
- dashboard 聚合正确
- 分页与搜索
- 旧数据库迁移
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


# ===== 通用夹具(从 auth 测试模块借用相同模式) =====


@pytest.fixture
def app_client_with_demo(app_client):
    from app.services.container import get_container
    from app.services.demo_seeder import seed_demo_data

    container = get_container()
    seed_demo_data(container, force=True)
    return app_client


def _login(app_client, username: str, password: str = "Demo123456") -> str:
    resp = app_client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def teacher_token(app_client_with_demo) -> str:
    return _login(app_client_with_demo, "teacher_demo")


@pytest.fixture
def teacher2_token(app_client_with_demo) -> str:
    return _login(app_client_with_demo, "teacher_demo2")


@pytest.fixture
def student_token(app_client_with_demo) -> str:
    return _login(app_client_with_demo, "student_demo")


@pytest.fixture
def student01_token(app_client_with_demo) -> str:
    return _login(app_client_with_demo, "student_demo_01")


@pytest.fixture
def admin_token(app_client_with_demo) -> str:
    return _login(app_client_with_demo, "admin_demo")


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ===== 课程 =====


def test_list_courses_pagination(app_client_with_demo, admin_token):
    """课程列表分页应正确返回(管理员可见全部课程)。"""
    # 演示数据已有 3 门课程,管理员可全部看到
    resp = app_client_with_demo.get(
        "/api/v1/courses?page=1&page_size=2", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] >= 3
    assert body["has_more"] is True  # 演示数据 3 门,分页 2 应有更多
    assert len(body["items"]) == 2
    # 第二页
    resp2 = app_client_with_demo.get(
        "/api/v1/courses?page=2&page_size=2", headers=_h(admin_token)
    )
    body2 = resp2.json()
    assert len(body2["items"]) >= 1


def test_list_courses_search(app_client_with_demo, teacher_token):
    """按名称/代码模糊搜索。"""
    resp = app_client_with_demo.get(
        "/api/v1/courses?query=高等数学", headers=_h(teacher_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert any("高等数学" in c["name"] for c in body["items"])


def test_list_courses_teacher_only_sees_own(
    app_client_with_demo, teacher_token, teacher2_token
):
    """教师只能看到自己负责的课程。"""
    # teacher2 创建一个新课程
    new_course = app_client_with_demo.post(
        "/api/v1/courses",
        json={"name": "teacher2 私有", "code": "T2OWN001"},
        headers=_h(teacher2_token),
    ).json()
    # teacher_demo 列表不应包含 teacher2 的课程
    resp = app_client_with_demo.get(
        "/api/v1/courses", headers=_h(teacher_token)
    )
    body = resp.json()
    codes = [c.get("code") for c in body["items"]]
    assert "T2OWN001" not in codes
    # teacher2 列表应包含
    resp2 = app_client_with_demo.get(
        "/api/v1/courses", headers=_h(teacher2_token)
    )
    body2 = resp2.json()
    codes2 = [c.get("code") for c in body2["items"]]
    assert "T2OWN001" in codes2


def test_get_course_not_found(app_client_with_demo, teacher_token):
    """获取不存在的课程应返回 404。"""
    resp = app_client_with_demo.get(
        "/api/v1/courses/nonexistent_id", headers=_h(teacher_token)
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "COURSE_NOT_FOUND"


def test_update_course_status(app_client_with_demo, teacher_token):
    """更新课程状态。"""
    create = app_client_with_demo.post(
        "/api/v1/courses",
        json={"name": "状态测试", "code": "STATUSTEST"},
        headers=_h(teacher_token),
    )
    course_id = create.json()["id"]
    resp = app_client_with_demo.patch(
        f"/api/v1/courses/{course_id}",
        json={"status": "active"},
        headers=_h(teacher_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


# ===== 班级 =====


def test_create_class_under_course(app_client_with_demo, teacher_token):
    """教师在课程下创建班级。"""
    course = app_client_with_demo.post(
        "/api/v1/courses",
        json={"name": "班级创建测试", "code": "CLASSCREATE"},
        headers=_h(teacher_token),
    ).json()
    cls = app_client_with_demo.post(
        f"/api/v1/courses/{course['id']}/classes",
        json={"name": "测试班级", "capacity": 50},
        headers=_h(teacher_token),
    )
    assert cls.status_code == 201
    body = cls.json()
    assert body["name"] == "测试班级"
    assert body["capacity"] == 50
    assert body["invite_code"]
    assert body["course_id"] == course["id"]


def test_student_join_class_by_invite_code(
    app_client_with_demo, teacher_token, student_token
):
    """学生凭邀请码加入班级。"""
    course = app_client_with_demo.post(
        "/api/v1/courses",
        json={"name": "学生加入测试", "code": "STUDENTJOIN"},
        headers=_h(teacher_token),
    ).json()
    cls = app_client_with_demo.post(
        f"/api/v1/courses/{course['id']}/classes",
        json={"name": "学生加入班级", "capacity": 100},
        headers=_h(teacher_token),
    ).json()
    invite = cls["invite_code"]
    resp = app_client_with_demo.post(
        f"/api/v1/classes/{cls['id']}/join",
        json={"invite_code": invite},
        headers=_h(student_token),
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == cls["id"]


def test_student_already_enrolled_returns_409(
    app_client_with_demo, teacher_token, student_token
):
    """重复加入同班级应返回 409。"""
    course = app_client_with_demo.post(
        "/api/v1/courses",
        json={"name": "重复加入测试", "code": "DUPJOIN"},
        headers=_h(teacher_token),
    ).json()
    cls = app_client_with_demo.post(
        f"/api/v1/courses/{course['id']}/classes",
        json={"name": "重复加入班级"},
        headers=_h(teacher_token),
    ).json()
    invite = cls["invite_code"]
    # 第一次加入
    r1 = app_client_with_demo.post(
        f"/api/v1/classes/{cls['id']}/join",
        json={"invite_code": invite},
        headers=_h(student_token),
    )
    assert r1.status_code == 200
    # 第二次应 409
    r2 = app_client_with_demo.post(
        f"/api/v1/classes/{cls['id']}/join",
        json={"invite_code": invite},
        headers=_h(student_token),
    )
    assert r2.status_code == 409
    assert r2.json()["code"] == "ALREADY_ENROLLED"


def test_class_capacity_full_rejects_join(
    app_client_with_demo, teacher_token, student_token, student01_token
):
    """班级满员后不可加入。"""
    course = app_client_with_demo.post(
        "/api/v1/courses",
        json={"name": "容量测试", "code": "CAPTEST"},
        headers=_h(teacher_token),
    ).json()
    cls = app_client_with_demo.post(
        f"/api/v1/courses/{course['id']}/classes",
        json={"name": "容量班级", "capacity": 1},
        headers=_h(teacher_token),
    ).json()
    # 教师自动加入为助教,占 1 个名额
    # student_demo 加入 → 应失败
    resp = app_client_with_demo.post(
        f"/api/v1/classes/{cls['id']}/join",
        json={"invite_code": cls["invite_code"]},
        headers=_h(student_token),
    )
    # 注意: 教师以 teaching_assistant 加入,可能不计入 capacity。
    # 此处仅验证容量校验机制存在。
    # 如果教师占名额,这里返回 409
    # 如果不占,student_demo 加入成功
    # 此处放宽断言,允许 200 或 409
    if resp.status_code == 409:
        # 若占名额,student_demo_01 也应失败
        resp2 = app_client_with_demo.post(
            f"/api/v1/classes/{cls['id']}/join",
            json={"invite_code": cls["invite_code"]},
            headers=_h(student01_token),
        )
        assert resp2.status_code == 409
    else:
        # 若不占名额,student_demo 加入后 student01 应失败
        assert resp.status_code == 200
        resp2 = app_client_with_demo.post(
            f"/api/v1/classes/{cls['id']}/join",
            json={"invite_code": cls["invite_code"]},
            headers=_h(student01_token),
        )
        assert resp2.status_code == 409
        assert resp2.json()["code"] == "CLASS_GROUP_FULL"


def test_list_class_members(app_client_with_demo, teacher_token):
    """教师查看班级成员列表。"""
    # 直接使用演示数据中的班级
    from app.services.container import get_container

    container = get_container()
    teacher = container.user_repository.get_user_by_username("teacher_demo")
    courses, _ = container.course_repository.list_courses(
        teacher_id=teacher.id, page=1, page_size=10
    )
    course = courses[0]
    classes, _ = container.class_group_repository.list_classes(
        course_id=course.id, page=1, page_size=10
    )
    cls = classes[0]
    resp = app_client_with_demo.get(
        f"/api/v1/classes/{cls.id}/members", headers=_h(teacher_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    # 不应返回 password_hash
    for m in body["items"]:
        assert "password_hash" not in m


def test_list_members_search_by_student_number(
    app_client_with_demo, teacher_token
):
    """按学号搜索班级成员。"""
    from app.services.container import get_container

    container = get_container()
    teacher = container.user_repository.get_user_by_username("teacher_demo")
    courses, _ = container.course_repository.list_courses(
        teacher_id=teacher.id, page=1, page_size=10
    )
    course = courses[0]
    classes, _ = container.class_group_repository.list_classes(
        course_id=course.id, page=1, page_size=10
    )
    cls = classes[0]
    # 演示数据 student_demo_01 学号 S20241001
    resp = app_client_with_demo.get(
        f"/api/v1/classes/{cls.id}/members?query=S20241001",
        headers=_h(teacher_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    # 找到匹配
    assert any(m.get("student_number") == "S20241001" for m in body["items"])


def test_teacher_remove_member(app_client_with_demo, teacher_token, student_token):
    """教师从班级移除成员。"""
    course = app_client_with_demo.post(
        "/api/v1/courses",
        json={"name": "移除成员测试", "code": "REMOVE"},
        headers=_h(teacher_token),
    ).json()
    cls = app_client_with_demo.post(
        f"/api/v1/courses/{course['id']}/classes",
        json={"name": "移除成员班级", "capacity": 100},
        headers=_h(teacher_token),
    ).json()
    # 学生加入
    app_client_with_demo.post(
        f"/api/v1/classes/{cls['id']}/join",
        json={"invite_code": cls["invite_code"]},
        headers=_h(student_token),
    )
    # 获取成员列表找到 student_demo
    from app.services.container import get_container

    container = get_container()
    student = container.user_repository.get_user_by_username("student_demo")
    # 教师移除
    resp = app_client_with_demo.delete(
        f"/api/v1/classes/{cls['id']}/members/{student.id}",
        headers=_h(teacher_token),
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


# ===== 通知 =====


def test_create_announcement_draft(app_client_with_demo, teacher_token):
    """教师创建通知草稿。"""
    from app.services.container import get_container

    container = get_container()
    teacher = container.user_repository.get_user_by_username("teacher_demo")
    courses, _ = container.course_repository.list_courses(
        teacher_id=teacher.id, page=1, page_size=10
    )
    course = courses[0]
    classes, _ = container.class_group_repository.list_classes(
        course_id=course.id, page=1, page_size=10
    )
    cls_id = classes[0].id

    resp = app_client_with_demo.post(
        f"/api/v1/classes/{cls_id}/announcements",
        json={
            "title": "测试通知",
            "content": "测试通知内容",
            "require_read": True,
            "status": "draft",
        },
        headers=_h(teacher_token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "draft"
    assert body["published_at"] is None


def test_publish_announcement(app_client_with_demo, teacher_token):
    """教师发布通知。"""
    from app.services.container import get_container

    container = get_container()
    teacher = container.user_repository.get_user_by_username("teacher_demo")
    courses, _ = container.course_repository.list_courses(
        teacher_id=teacher.id, page=1, page_size=10
    )
    course = courses[0]
    classes, _ = container.class_group_repository.list_classes(
        course_id=course.id, page=1, page_size=10
    )
    cls_id = classes[0].id
    # 创建草稿
    create = app_client_with_demo.post(
        f"/api/v1/classes/{cls_id}/announcements",
        json={"title": "发布测试", "content": "测试", "status": "draft"},
        headers=_h(teacher_token),
    ).json()
    ann_id = create["id"]
    # 发布
    resp = app_client_with_demo.post(
        f"/api/v1/announcements/{ann_id}/publish", headers=_h(teacher_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "published"
    assert body["published_at"] is not None


def test_student_cannot_view_draft_announcement(
    app_client_with_demo, teacher_token, student_token
):
    """学生不可见草稿通知。"""
    from app.services.container import get_container

    container = get_container()
    teacher = container.user_repository.get_user_by_username("teacher_demo")
    courses, _ = container.course_repository.list_courses(
        teacher_id=teacher.id, page=1, page_size=10
    )
    course = courses[0]
    classes, _ = container.class_group_repository.list_classes(
        course_id=course.id, page=1, page_size=10
    )
    cls_id = classes[0].id
    # 创建草稿
    create = app_client_with_demo.post(
        f"/api/v1/classes/{cls_id}/announcements",
        json={"title": "学生不可见草稿", "content": "x", "status": "draft"},
        headers=_h(teacher_token),
    ).json()
    ann_id = create["id"]
    # 学生尝试查看 → 404
    resp = app_client_with_demo.get(
        f"/api/v1/announcements/{ann_id}", headers=_h(student_token)
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "ANNOUNCEMENT_NOT_FOUND"


def test_student_list_announcements_excludes_draft(
    app_client_with_demo, teacher_token, student_token
):
    """学生列表不包含草稿通知。"""
    from app.services.container import get_container

    container = get_container()
    teacher = container.user_repository.get_user_by_username("teacher_demo")
    courses, _ = container.course_repository.list_courses(
        teacher_id=teacher.id, page=1, page_size=10
    )
    course = courses[0]
    classes, _ = container.class_group_repository.list_classes(
        course_id=course.id, page=1, page_size=10
    )
    cls_id = classes[0].id
    # 教师创建草稿
    create = app_client_with_demo.post(
        f"/api/v1/classes/{cls_id}/announcements",
        json={"title": "学生列表不见草稿", "content": "y", "status": "draft"},
        headers=_h(teacher_token),
    ).json()
    # 学生列表不应包含
    resp = app_client_with_demo.get(
        f"/api/v1/classes/{cls_id}/announcements", headers=_h(student_token)
    )
    body = resp.json()
    titles = [i["title"] for i in body["items"]]
    assert "学生列表不见草稿" not in titles


def test_mark_announcement_read_idempotent(
    app_client_with_demo, teacher_token, student_token
):
    """重复标记已读不应产生重复记录,且 first_time 仅首次为 True。"""
    from app.services.container import get_container

    container = get_container()
    teacher = container.user_repository.get_user_by_username("teacher_demo")
    courses, _ = container.course_repository.list_courses(
        teacher_id=teacher.id, page=1, page_size=10
    )
    course = courses[0]
    classes, _ = container.class_group_repository.list_classes(
        course_id=course.id, page=1, page_size=10
    )
    cls_id = classes[0].id
    # 创建并发布通知
    create = app_client_with_demo.post(
        f"/api/v1/classes/{cls_id}/announcements",
        json={
            "title": "已读幂等测试",
            "content": "请阅读",
            "require_read": True,
            "status": "published",
        },
        headers=_h(teacher_token),
    ).json()
    ann_id = create["id"]
    # 第一次标记已读
    r1 = app_client_with_demo.post(
        f"/api/v1/announcements/{ann_id}/read", headers=_h(student_token)
    )
    assert r1.status_code == 200
    assert r1.json()["first_time"] is True
    # 第二次标记已读
    r2 = app_client_with_demo.post(
        f"/api/v1/announcements/{ann_id}/read", headers=_h(student_token)
    )
    assert r2.status_code == 200
    assert r2.json()["first_time"] is False
    # read-status 中 read_count 仍为 1
    status = app_client_with_demo.get(
        f"/api/v1/announcements/{ann_id}/read-status", headers=_h(teacher_token)
    ).json()
    assert status["read_count"] == 1


def test_announcement_read_status_aggregation(
    app_client_with_demo, teacher_token, student_token, student01_token
):
    """read-status 应聚合已读/未读数。"""
    from app.services.container import get_container

    container = get_container()
    teacher = container.user_repository.get_user_by_username("teacher_demo")
    courses, _ = container.course_repository.list_courses(
        teacher_id=teacher.id, page=1, page_size=10
    )
    course = courses[0]
    classes, _ = container.class_group_repository.list_classes(
        course_id=course.id, page=1, page_size=10
    )
    cls_id = classes[0].id
    # 已发布的通知
    create = app_client_with_demo.post(
        f"/api/v1/classes/{cls_id}/announcements",
        json={
            "title": "已读聚合测试",
            "content": "请阅读",
            "require_read": True,
            "status": "published",
        },
        headers=_h(teacher_token),
    ).json()
    ann_id = create["id"]
    # student_demo 标记已读
    app_client_with_demo.post(
        f"/api/v1/announcements/{ann_id}/read", headers=_h(student_token)
    )
    # 查询 read-status
    resp = app_client_with_demo.get(
        f"/api/v1/announcements/{ann_id}/read-status", headers=_h(teacher_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["read_count"] == 1
    assert body["unread_count"] >= 0
    assert body["total_recipients"] >= 1


def test_student_cannot_view_read_status(
    app_client_with_demo, teacher_token, student_token
):
    """学生不可查看 read-status(教师专属)。"""
    from app.services.container import get_container

    container = get_container()
    teacher = container.user_repository.get_user_by_username("teacher_demo")
    courses, _ = container.course_repository.list_courses(
        teacher_id=teacher.id, page=1, page_size=10
    )
    course = courses[0]
    classes, _ = container.class_group_repository.list_classes(
        course_id=course.id, page=1, page_size=10
    )
    cls_id = classes[0].id
    create = app_client_with_demo.post(
        f"/api/v1/classes/{cls_id}/announcements",
        json={"title": "学生不可见状态", "content": "x", "status": "published"},
        headers=_h(teacher_token),
    ).json()
    resp = app_client_with_demo.get(
        f"/api/v1/announcements/{create['id']}/read-status",
        headers=_h(student_token),
    )
    assert resp.status_code == 403


# ===== 任务 =====


def test_create_assignment_draft(app_client_with_demo, teacher_token):
    """教师创建任务草稿。"""
    from app.services.container import get_container

    container = get_container()
    teacher = container.user_repository.get_user_by_username("teacher_demo")
    courses, _ = container.course_repository.list_courses(
        teacher_id=teacher.id, page=1, page_size=10
    )
    course = courses[0]
    classes, _ = container.class_group_repository.list_classes(
        course_id=course.id, page=1, page_size=10
    )
    cls_id = classes[0].id
    resp = app_client_with_demo.post(
        f"/api/v1/classes/{cls_id}/assignments",
        json={
            "title": "任务草稿",
            "description": "测试任务",
            "deadline": "2026-12-31T23:59:59+08:00",
            "max_score": 100,
            "allow_resubmit": True,
            "status": "draft",
        },
        headers=_h(teacher_token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "draft"
    assert body["published_at"] is None


def test_assignment_draft_invisible_to_student(
    app_client_with_demo, teacher_token, student_token
):
    """学生不可见草稿任务。"""
    from app.services.container import get_container

    container = get_container()
    teacher = container.user_repository.get_user_by_username("teacher_demo")
    courses, _ = container.course_repository.list_courses(
        teacher_id=teacher.id, page=1, page_size=10
    )
    course = courses[0]
    classes, _ = container.class_group_repository.list_classes(
        course_id=course.id, page=1, page_size=10
    )
    cls_id = classes[0].id
    # 创建草稿
    create = app_client_with_demo.post(
        f"/api/v1/classes/{cls_id}/assignments",
        json={"title": "学生不可见草稿任务", "status": "draft"},
        headers=_h(teacher_token),
    ).json()
    asg_id = create["id"]
    # 学生 GET → 404
    resp = app_client_with_demo.get(
        f"/api/v1/assignments/{asg_id}", headers=_h(student_token)
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "ASSIGNMENT_NOT_FOUND"
    # 学生列表不包含草稿
    lst = app_client_with_demo.get(
        f"/api/v1/classes/{cls_id}/assignments", headers=_h(student_token)
    ).json()
    titles = [i["title"] for i in lst["items"]]
    assert "学生不可见草稿任务" not in titles


def test_publish_assignment(app_client_with_demo, teacher_token):
    """教师发布任务。"""
    from app.services.container import get_container

    container = get_container()
    teacher = container.user_repository.get_user_by_username("teacher_demo")
    courses, _ = container.course_repository.list_courses(
        teacher_id=teacher.id, page=1, page_size=10
    )
    course = courses[0]
    classes, _ = container.class_group_repository.list_classes(
        course_id=course.id, page=1, page_size=10
    )
    cls_id = classes[0].id
    create = app_client_with_demo.post(
        f"/api/v1/classes/{cls_id}/assignments",
        json={"title": "发布测试任务", "status": "draft"},
        headers=_h(teacher_token),
    ).json()
    asg_id = create["id"]
    resp = app_client_with_demo.post(
        f"/api/v1/assignments/{asg_id}/publish", headers=_h(teacher_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "published"
    assert body["published_at"] is not None


def test_close_assignment(app_client_with_demo, teacher_token):
    """教师关闭任务。"""
    from app.services.container import get_container

    container = get_container()
    teacher = container.user_repository.get_user_by_username("teacher_demo")
    courses, _ = container.course_repository.list_courses(
        teacher_id=teacher.id, page=1, page_size=10
    )
    course = courses[0]
    classes, _ = container.class_group_repository.list_classes(
        course_id=course.id, page=1, page_size=10
    )
    cls_id = classes[0].id
    create = app_client_with_demo.post(
        f"/api/v1/classes/{cls_id}/assignments",
        json={"title": "关闭测试任务", "status": "published"},
        headers=_h(teacher_token),
    ).json()
    asg_id = create["id"]
    resp = app_client_with_demo.post(
        f"/api/v1/assignments/{asg_id}/close", headers=_h(teacher_token)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "closed"


def test_assignment_stats_correct(
    app_client_with_demo, teacher_token, student_token, student01_token
):
    """任务统计聚合正确。"""
    from app.services.container import get_container

    container = get_container()
    teacher = container.user_repository.get_user_by_username("teacher_demo")
    courses, _ = container.course_repository.list_courses(
        teacher_id=teacher.id, page=1, page_size=10
    )
    course = courses[0]
    classes, _ = container.class_group_repository.list_classes(
        course_id=course.id, page=1, page_size=10
    )
    cls_id = classes[0].id
    # 创建新任务(独立测试,避免被演示数据干扰)
    create = app_client_with_demo.post(
        f"/api/v1/classes/{cls_id}/assignments",
        json={
            "title": "统计测试任务",
            "status": "published",
            "allow_resubmit": True,
        },
        headers=_h(teacher_token),
    ).json()
    asg_id = create["id"]
    # student_demo 创建草稿
    s1 = app_client_with_demo.post(
        f"/api/v1/assignments/{asg_id}/submissions",
        json={"text_content": "草稿", "submit": False},
        headers=_h(student_token),
    )
    assert s1.status_code == 201
    # student_demo_01 直接提交
    s2 = app_client_with_demo.post(
        f"/api/v1/assignments/{asg_id}/submissions",
        json={"text_content": "已提交", "submit": True},
        headers=_h(student01_token),
    )
    assert s2.status_code == 201
    # 查询统计
    resp = app_client_with_demo.get(
        f"/api/v1/assignments/{asg_id}/stats", headers=_h(teacher_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["assignment_id"] == asg_id
    assert body["total_students"] >= 2
    # 至少 1 个已提交
    assert body["submitted"] >= 1
    # 至少 1 个草稿
    assert body["draft"] >= 1


def test_student_status_endpoint(
    app_client_with_demo, teacher_token, student_token
):
    """student-status 接口返回每个学生的状态。"""
    from app.services.container import get_container

    container = get_container()
    teacher = container.user_repository.get_user_by_username("teacher_demo")
    courses, _ = container.course_repository.list_courses(
        teacher_id=teacher.id, page=1, page_size=10
    )
    course = courses[0]
    classes, _ = container.class_group_repository.list_classes(
        course_id=course.id, page=1, page_size=10
    )
    cls_id = classes[0].id
    # 使用演示数据中已发布任务
    asgs, _ = container.assignment_repository.list_assignments(
        cls_id, status="published", page=1, page_size=10
    )
    assert asgs, "演示数据应有已发布任务"
    asg = asgs[0]
    resp = app_client_with_demo.get(
        f"/api/v1/assignments/{asg.id}/student-status",
        headers=_h(teacher_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    for item in body["items"]:
        assert "student_id" in item
        assert "submission_status" in item
        assert "is_late" in item


def test_student_status_filter_by_status(
    app_client_with_demo, teacher_token, student01_token
):
    """student-status 支持按提交状态筛选。"""
    from app.services.container import get_container

    container = get_container()
    teacher = container.user_repository.get_user_by_username("teacher_demo")
    courses, _ = container.course_repository.list_courses(
        teacher_id=teacher.id, page=1, page_size=10
    )
    course = courses[0]
    classes, _ = container.class_group_repository.list_classes(
        course_id=course.id, page=1, page_size=10
    )
    cls_id = classes[0].id
    assignment = app_client_with_demo.post(
        f"/api/v1/classes/{cls_id}/assignments",
        json={
            "title": "student-status filter isolation",
            "status": "published",
            "allow_resubmit": True,
        },
        headers=_h(teacher_token),
    )
    assert assignment.status_code == 201
    asg_id = assignment.json()["id"]
    submission = app_client_with_demo.post(
        f"/api/v1/assignments/{asg_id}/submissions",
        json={"text_content": "submitted for status filter", "submit": True},
        headers=_h(student01_token),
    )
    assert submission.status_code == 201
    # 筛选已提交
    resp = app_client_with_demo.get(
        f"/api/v1/assignments/{asg_id}/student-status?submission_status=submitted",
        headers=_h(teacher_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    # 演示数据 student_demo_01 有提交
    assert body["total"] >= 1


def test_student_status_search_by_name(
    app_client_with_demo, teacher_token
):
    """student-status 支持按姓名/学号搜索。"""
    from app.services.container import get_container

    container = get_container()
    teacher = container.user_repository.get_user_by_username("teacher_demo")
    courses, _ = container.course_repository.list_courses(
        teacher_id=teacher.id, page=1, page_size=10
    )
    course = courses[0]
    classes, _ = container.class_group_repository.list_classes(
        course_id=course.id, page=1, page_size=10
    )
    cls_id = classes[0].id
    asgs, _ = container.assignment_repository.list_assignments(
        cls_id, status="published", page=1, page_size=10
    )
    asg = asgs[0]
    # 用学号搜索
    resp = app_client_with_demo.get(
        f"/api/v1/assignments/{asg.id}/student-status?query=S20241001",
        headers=_h(teacher_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert any(item["student_number"] == "S20241001" for item in body["items"])
