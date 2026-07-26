"""多角色协同平台 — 认证与 RBAC 测试。

覆盖要求:
- 登录成功和失败
- access token 与 refresh token
- 学生 / 教师 / 管理员权限
- 教师不能管理其他教师课程
- 学生不能查看其他学生提交
- 学生不能加入不存在的班级
- 教师无法跨课程读取学生数据(权限边界)
"""
from __future__ import annotations

import pytest


# ===== 通用夹具 =====


@pytest.fixture
def app_client_with_demo(app_client):
    """开启多角色演示数据 seeding 的 app_client。

    conftest.app_client 默认 AUTO_IMPORT_DEMO=false, 不会 seed 多角色数据。
    此处通过 force=True 显式 seed, 演示 RBAC 与多角色场景。
    """
    from app.services.container import get_container
    from app.services.demo_seeder import seed_demo_data

    container = get_container()
    seed_demo_data(container, force=True)
    return app_client


@pytest.fixture
def teacher_tokens(app_client_with_demo):
    """登录演示教师账号,返回 (access_token, refresh_token, user_id)。"""
    resp = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "teacher_demo", "password": "Demo123456"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return body["access_token"], body["refresh_token"], body["token_type"]


@pytest.fixture
def teacher2_tokens(app_client_with_demo):
    resp = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "teacher_demo2", "password": "Demo123456"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return body["access_token"], body["refresh_token"]


@pytest.fixture
def student_tokens(app_client_with_demo):
    resp = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "student_demo", "password": "Demo123456"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return body["access_token"], body["refresh_token"]


@pytest.fixture
def admin_tokens(app_client_with_demo):
    resp = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "admin_demo", "password": "Demo123456"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return body["access_token"], body["refresh_token"]


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ===== 登录与登出 =====


def test_login_success_returns_token_pair(app_client_with_demo):
    """登录成功应返回 access_token 与 refresh_token。"""
    resp = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "teacher_demo", "password": "Demo123456"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] > 0


def test_login_wrong_password_returns_401(app_client_with_demo):
    """密码错误返回 401,且不暴露用户名是否存在。"""
    resp = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "teacher_demo", "password": "wrong_password"},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["code"] == "INVALID_CREDENTIALS"
    assert "用户名或密码错误" in body["message"]


def test_login_nonexistent_user_returns_same_error(app_client_with_demo):
    """不存在的用户与密码错误返回相同错误,避免用户名枚举。"""
    resp = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "nonexistent_user_xyz", "password": "whatever"},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["code"] == "INVALID_CREDENTIALS"


def test_login_inactive_user_rejected(app_client_with_demo):
    """停用账号不可登录。"""
    # 用管理员创建一个停用账号(直接走 repo 更快)
    from app.services.container import get_container
    from app.core.security import hash_password

    container = get_container()
    user = container.user_repository.create_user(
        username="inactive_user",
        password_hash=hash_password("Test123456"),
        role="student",
        display_name="停用测试",
    )
    container.user_repository.update_user(user.id, fields={"is_active": False})

    resp = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "inactive_user", "password": "Test123456"},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "INVALID_CREDENTIALS"


def test_me_endpoint_returns_user_info(app_client_with_demo, teacher_tokens):
    """GET /auth/me 应返回当前登录用户信息(不含 password_hash)。"""
    access_token, _, _ = teacher_tokens
    resp = app_client_with_demo.get("/api/v1/auth/me", headers=_auth_header(access_token))
    assert resp.status_code == 200
    body = resp.json()
    assert "user" in body
    user = body["user"]
    assert user["username"] == "teacher_demo"
    assert user["role"] == "teacher"
    # 绝不能返回 password_hash
    assert "password_hash" not in user


def test_me_endpoint_rejects_missing_token(app_client_with_demo):
    """无 token 访问 /auth/me 应返回 401。"""
    resp = app_client_with_demo.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


def test_me_endpoint_rejects_invalid_token(app_client_with_demo):
    """无效 token 应返回 401。"""
    resp = app_client_with_demo.get(
        "/api/v1/auth/me", headers=_auth_header("invalid.token.here")
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


def test_refresh_token_issues_new_pair(app_client_with_demo, teacher_tokens):
    """refresh token 应能换发新的 access + refresh token。"""
    _, refresh_token, _ = teacher_tokens
    resp = app_client_with_demo.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    # 新 token 应与旧的不同
    assert body["refresh_token"] != refresh_token


def test_refresh_token_revoked_after_use(app_client_with_demo, teacher_tokens):
    """refresh token 换发后,旧 refresh token 不可再用(防重放)。"""
    _, refresh_token, _ = teacher_tokens
    # 第一次换发
    resp1 = app_client_with_demo.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp1.status_code == 200
    # 第二次用同一个旧 refresh token 应失败
    resp2 = app_client_with_demo.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp2.status_code == 401
    assert resp2.json()["code"] == "UNAUTHORIZED"


def test_refresh_token_rejects_access_token(app_client_with_demo, teacher_tokens):
    """用 access token 充当 refresh token 应失败。"""
    access_token, _, _ = teacher_tokens
    resp = app_client_with_demo.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token},
    )
    assert resp.status_code == 401


def test_logout_revokes_refresh_token(app_client_with_demo, teacher_tokens):
    """logout 后 refresh token 不可再用。"""
    access_token, refresh_token, _ = teacher_tokens
    resp = app_client_with_demo.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers=_auth_header(access_token),
    )
    assert resp.status_code == 200
    # 再用旧 refresh 换发应失败
    resp2 = app_client_with_demo.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp2.status_code == 401


def test_logout_works_without_refresh_token(app_client_with_demo, teacher_tokens):
    """logout 不带 refresh_token 也应正常返回。"""
    access_token, _, _ = teacher_tokens
    resp = app_client_with_demo.post(
        "/api/v1/auth/logout",
        json={},
        headers=_auth_header(access_token),
    )
    assert resp.status_code == 200


# ===== RBAC: 角色权限 =====


def test_student_cannot_create_course(app_client_with_demo, student_tokens):
    """学生不能创建课程。"""
    access_token, _ = student_tokens
    resp = app_client_with_demo.post(
        "/api/v1/courses",
        json={"name": "学生尝试创建", "code": "FORBID"},
        headers=_auth_header(access_token),
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN"


def test_teacher_can_create_course(app_client_with_demo, teacher_tokens):
    """教师可以创建课程。"""
    access_token, _, _ = teacher_tokens
    resp = app_client_with_demo.post(
        "/api/v1/courses",
        json={"name": "新课程测试", "code": "NEW101", "status": "draft"},
        headers=_auth_header(access_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "新课程测试"
    assert body["code"] == "NEW101"
    assert body["status"] == "draft"


def test_admin_can_create_course(app_client_with_demo, admin_tokens):
    """管理员可以创建课程。"""
    access_token, _ = admin_tokens
    resp = app_client_with_demo.post(
        "/api/v1/courses",
        json={"name": "管理员课程", "code": "ADMIN101"},
        headers=_auth_header(access_token),
    )
    assert resp.status_code == 201


def test_teacher_cannot_update_other_teacher_course(
    app_client_with_demo, teacher_tokens, teacher2_tokens
):
    """教师不能修改其他教师的课程。"""
    t1_access, _, _ = teacher_tokens
    t2_access, _ = teacher2_tokens
    # teacher1 创建课程
    create = app_client_with_demo.post(
        "/api/v1/courses",
        json={"name": "T1 私有课程", "code": "T1PRIV"},
        headers=_auth_header(t1_access),
    )
    assert create.status_code == 201
    course_id = create.json()["id"]
    # teacher2 尝试修改
    resp = app_client_with_demo.patch(
        f"/api/v1/courses/{course_id}",
        json={"name": "T2 篡改"},
        headers=_auth_header(t2_access),
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN"


def test_teacher_cannot_manage_other_teacher_class(
    app_client_with_demo, teacher_tokens, teacher2_tokens
):
    """教师不能在另一个教师的课程下创建班级。"""
    t1_access, _, _ = teacher_tokens
    t2_access, _ = teacher2_tokens
    # teacher1 创建课程
    create = app_client_with_demo.post(
        "/api/v1/courses",
        json={"name": "T1 课程", "code": "T1CLSCOURSE"},
        headers=_auth_header(t1_access),
    )
    course_id = create.json()["id"]
    # teacher2 尝试在该课程下创建班级
    resp = app_client_with_demo.post(
        f"/api/v1/courses/{course_id}/classes",
        json={"name": "T2 班级"},
        headers=_auth_header(t2_access),
    )
    assert resp.status_code == 403


def test_student_cannot_view_other_student_submission(
    app_client_with_demo, student_tokens
):
    """学生不能查看其他学生的提交。"""
    s1_access, _ = student_tokens
    # 通过演示数据已有 student_demo 的提交(在 DEMO-MATH101-CLS1 第一章习题)
    # 此处需要找另一个学生的提交。先用教师列出所有提交。
    from app.services.container import get_container

    container = get_container()
    # 取 teacher_demo
    teacher = container.user_repository.get_user_by_username("teacher_demo")
    # 列出 teacher 的课程
    courses, _ = container.course_repository.list_courses(
        teacher_id=teacher.id, page=1, page_size=10
    )
    assert courses, "演示数据应有课程"
    course = courses[0]
    # 列出班级
    classes, _ = container.class_group_repository.list_classes(
        course_id=course.id, page=1, page_size=10
    )
    assert classes
    cls = classes[0]
    # 列出任务
    asgs, _ = container.assignment_repository.list_assignments(
        cls.id, status=None, page=1, page_size=10
    )
    assert asgs
    asg = asgs[0]
    # 列出所有提交
    subs, _ = container.submission_repository.list_submissions(asg.id, page=1, page_size=20)
    if not subs:
        pytest.skip("演示数据未生成提交")
    other_sub = subs[0]
    # student_demo 尝试访问这条提交(可能不是自己的)
    if other_sub["student_id"] == container.user_repository.get_user_by_username(
        "student_demo"
    ).id:
        if len(subs) < 2:
            pytest.skip("需要至少两条提交来测试跨学生访问")
        other_sub = subs[1]
    resp = app_client_with_demo.get(
        f"/api/v1/submissions/{other_sub['id']}",
        headers=_auth_header(s1_access),
    )
    assert resp.status_code == 403


def test_student_cannot_join_nonexistent_class(app_client_with_demo, student_tokens):
    """学生尝试加入不存在的班级应失败。"""
    access_token, _ = student_tokens
    # 班级不存在 → 404
    resp = app_client_with_demo.post(
        "/api/v1/classes/nonexistent_class_id/join",
        json={"invite_code": "ABCD1234"},
        headers=_auth_header(access_token),
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "CLASS_GROUP_NOT_FOUND"


def test_student_cannot_join_class_with_wrong_invite_code(
    app_client_with_demo, student_tokens, teacher_tokens
):
    """邀请码错误不可加入。"""
    s_access, _ = student_tokens
    t_access, _, _ = teacher_tokens
    # 教师创建课程+班级
    course = app_client_with_demo.post(
        "/api/v1/courses",
        json={"name": "邀请码测试课程", "code": "INVITE_TEST"},
        headers=_auth_header(t_access),
    ).json()
    cls = app_client_with_demo.post(
        f"/api/v1/courses/{course['id']}/classes",
        json={"name": "邀请码测试班"},
        headers=_auth_header(t_access),
    ).json()
    # 错误邀请码
    resp = app_client_with_demo.post(
        f"/api/v1/classes/{cls['id']}/join",
        json={"invite_code": "WRONG_CODE"},
        headers=_auth_header(s_access),
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "INVALID_INVITE_CODE"


def test_teacher_cannot_access_student_dashboard(
    app_client_with_demo, teacher_tokens
):
    """教师不可访问学生工作台。"""
    access_token, _, _ = teacher_tokens
    resp = app_client_with_demo.get(
        "/api/v1/dashboard/student", headers=_auth_header(access_token)
    )
    assert resp.status_code == 403


def test_student_cannot_access_teacher_dashboard(
    app_client_with_demo, student_tokens
):
    """学生不可访问教师工作台。"""
    access_token, _ = student_tokens
    resp = app_client_with_demo.get(
        "/api/v1/dashboard/teacher", headers=_auth_header(access_token)
    )
    assert resp.status_code == 403


def test_teacher_cross_course_student_data_forbidden(
    app_client_with_demo, teacher_tokens, teacher2_tokens
):
    """教师 A 不能读取教师 B 课程下的学生数据(跨课程权限边界)。"""
    t1_access, _, _ = teacher_tokens
    t2_access, _ = teacher2_tokens
    # teacher2 创建课程与班级
    course2 = app_client_with_demo.post(
        "/api/v1/courses",
        json={"name": "T2 课程", "code": "T2ONLY"},
        headers=_auth_header(t2_access),
    ).json()
    cls2 = app_client_with_demo.post(
        f"/api/v1/courses/{course2['id']}/classes",
        json={"name": "T2 班级"},
        headers=_auth_header(t2_access),
    ).json()
    # teacher1 尝试查看 teacher2 的班级详情
    resp = app_client_with_demo.get(
        f"/api/v1/classes/{cls2['id']}",
        headers=_auth_header(t1_access),
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN"


# ===== 邀请码 =====


def test_invite_code_unique_per_class(
    app_client_with_demo, teacher_tokens
):
    """每个班级的邀请码应唯一。"""
    access_token, _, _ = teacher_tokens
    course = app_client_with_demo.post(
        "/api/v1/courses",
        json={"name": "邀请码唯一性测试", "code": "INVUNIQUE"},
        headers=_auth_header(access_token),
    ).json()
    codes = set()
    for i in range(3):
        cls = app_client_with_demo.post(
            f"/api/v1/courses/{course['id']}/classes",
            json={"name": f"班级{i}"},
            headers=_auth_header(access_token),
        ).json()
        assert cls["invite_code"]
        assert cls["invite_code"] not in codes
        codes.add(cls["invite_code"])


def test_reset_invite_code_changes_code(
    app_client_with_demo, teacher_tokens
):
    """重置邀请码应生成新邀请码。"""
    access_token, _, _ = teacher_tokens
    course = app_client_with_demo.post(
        "/api/v1/courses",
        json={"name": "重置邀请码测试", "code": "RESETTEST"},
        headers=_auth_header(access_token),
    ).json()
    cls = app_client_with_demo.post(
        f"/api/v1/courses/{course['id']}/classes",
        json={"name": "重置邀请码班级"},
        headers=_auth_header(access_token),
    ).json()
    old_code = cls["invite_code"]
    resp = app_client_with_demo.post(
        f"/api/v1/classes/{cls['id']}/reset-invite-code",
        headers=_auth_header(access_token),
    )
    assert resp.status_code == 200
    new_code = resp.json()["invite_code"]
    assert new_code != old_code


def test_student_cannot_reset_invite_code(
    app_client_with_demo, student_tokens, teacher_tokens
):
    """学生不可重置邀请码。"""
    s_access, _ = student_tokens
    t_access, _, _ = teacher_tokens
    course = app_client_with_demo.post(
        "/api/v1/courses",
        json={"name": "学生不可重置", "code": "STDNORESET"},
        headers=_auth_header(t_access),
    ).json()
    cls = app_client_with_demo.post(
        f"/api/v1/courses/{course['id']}/classes",
        json={"name": "测试班级"},
        headers=_auth_header(t_access),
    ).json()
    resp = app_client_with_demo.post(
        f"/api/v1/classes/{cls['id']}/reset-invite-code",
        headers=_auth_header(s_access),
    )
    assert resp.status_code == 403
