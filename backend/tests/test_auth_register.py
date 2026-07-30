"""公开注册接口 POST /api/v1/auth/register 测试。

覆盖:
- 学生 / 教师注册成功
- 注册后可用该账号登录
- 唯一性校验(用户名 / 学号 / 工号冲突)
- 角色一致性校验(student 不应携带 teacher_number 等)
- 不允许注册 admin 角色
- 字段校验(密码长度 / 用户名格式)
- 注册接口不需要鉴权
"""
from __future__ import annotations

import pytest


# ===== 通用夹具(与 test_multi_role_auth.py 对齐,保持独立可运行) =====


@pytest.fixture
def app_client_with_demo(app_client):
    """开启多角色演示数据 seeding 的 app_client。"""
    from app.services.container import get_container
    from app.services.demo_seeder import seed_demo_data

    container = get_container()
    seed_demo_data(container, force=True)
    return app_client


# ===== 注册成功路径 =====


def test_register_student_success(app_client_with_demo):
    """学生注册成功 → 201,返回 UserPublic(不含 password_hash)。"""
    resp = app_client_with_demo.post(
        "/api/v1/auth/register",
        json={
            "username": "new_student_reg_001",
            "password": "TestRegister123",
            "role": "student",
            "display_name": "注册测试学生",
            "student_number": "S_REG_001",
            "college": "信息工程学院",
            "major": "计算机科学与技术",
            "grade": "2024",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["username"] == "new_student_reg_001"
    assert body["role"] == "student"
    assert body["display_name"] == "注册测试学生"
    assert body["student_number"] == "S_REG_001"
    # 绝不能返回 password_hash
    assert "password_hash" not in body
    # 默认应激活
    assert body["is_active"] is True


def test_register_teacher_success(app_client_with_demo):
    """教师注册成功 → 201。"""
    resp = app_client_with_demo.post(
        "/api/v1/auth/register",
        json={
            "username": "new_teacher_reg_001",
            "password": "TestRegister123",
            "role": "teacher",
            "display_name": "注册测试教师",
            "teacher_number": "T_REG_001",
            "department": "计算机系",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["role"] == "teacher"
    assert body["teacher_number"] == "T_REG_001"


def test_register_default_role_is_student(app_client_with_demo):
    """不传 role 时默认为 student。"""
    resp = app_client_with_demo.post(
        "/api/v1/auth/register",
        json={
            "username": "default_role_user_001",
            "password": "TestRegister123",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["role"] == "student"


def test_register_then_login_works(app_client_with_demo):
    """注册成功后,应能用相同凭证登录获取 token。"""
    # 注册
    resp = app_client_with_demo.post(
        "/api/v1/auth/register",
        json={
            "username": "login_after_reg_user",
            "password": "TestRegister123",
            "role": "student",
        },
    )
    assert resp.status_code == 201, resp.text
    # 登录
    resp = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "login_after_reg_user", "password": "TestRegister123"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]


def test_register_no_auth_required(app_client_with_demo):
    """注册接口不应要求 Authorization 头(公开接口)。"""
    # 不带任何 Authorization 头,正常注册应成功
    resp = app_client_with_demo.post(
        "/api/v1/auth/register",
        json={
            "username": "no_auth_header_user",
            "password": "TestRegister123",
            "role": "student",
        },
    )
    assert resp.status_code == 201, resp.text


# ===== 唯一性校验 =====


def test_register_duplicate_username_conflict(app_client_with_demo):
    """用户名已存在 → 409 USERNAME_EXISTS。"""
    payload = {
        "username": "dup_user_reg_001",
        "password": "TestRegister123",
        "role": "student",
    }
    resp1 = app_client_with_demo.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201
    resp2 = app_client_with_demo.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 409
    assert resp2.json()["code"] == "USERNAME_EXISTS"


def test_register_duplicate_student_number_conflict(app_client_with_demo):
    """学号已存在 → 409 STUDENT_NUMBER_EXISTS。"""
    payload = {
        "username": "dup_snum_user_a",
        "password": "TestRegister123",
        "role": "student",
        "student_number": "S_DUP_NUM_001",
    }
    resp1 = app_client_with_demo.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    resp2 = app_client_with_demo.post(
        "/api/v1/auth/register",
        json={
            "username": "dup_snum_user_b",
            "password": "TestRegister123",
            "role": "student",
            "student_number": "S_DUP_NUM_001",
        },
    )
    assert resp2.status_code == 409
    assert resp2.json()["code"] == "STUDENT_NUMBER_EXISTS"


def test_register_duplicate_teacher_number_conflict(app_client_with_demo):
    """工号已存在 → 409 TEACHER_NUMBER_EXISTS。"""
    payload = {
        "username": "dup_tnum_user_a",
        "password": "TestRegister123",
        "role": "teacher",
        "teacher_number": "T_DUP_NUM_001",
    }
    resp1 = app_client_with_demo.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    resp2 = app_client_with_demo.post(
        "/api/v1/auth/register",
        json={
            "username": "dup_tnum_user_b",
            "password": "TestRegister123",
            "role": "teacher",
            "teacher_number": "T_DUP_NUM_001",
        },
    )
    assert resp2.status_code == 409
    assert resp2.json()["code"] == "TEACHER_NUMBER_EXISTS"


# ===== 角色一致性校验 =====


def test_register_student_with_teacher_number_rejected(app_client_with_demo):
    """学生角色携带 teacher_number → 422 VALIDATION_FAILED。"""
    resp = app_client_with_demo.post(
        "/api/v1/auth/register",
        json={
            "username": "bad_mix_student",
            "password": "TestRegister123",
            "role": "student",
            "teacher_number": "T_BAD_MIX_001",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_FAILED"


def test_register_teacher_with_student_number_rejected(app_client_with_demo):
    """教师角色携带 student_number → 422 VALIDATION_FAILED。"""
    resp = app_client_with_demo.post(
        "/api/v1/auth/register",
        json={
            "username": "bad_mix_teacher",
            "password": "TestRegister123",
            "role": "teacher",
            "student_number": "S_BAD_MIX_001",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_FAILED"


# ===== 角色限制 =====


def test_register_admin_role_forbidden(app_client_with_demo):
    """注册 admin 角色 → 422(schema 层 pattern 即拦截)。"""
    resp = app_client_with_demo.post(
        "/api/v1/auth/register",
        json={
            "username": "try_admin_self",
            "password": "TestRegister123",
            "role": "admin",
        },
    )
    # schema pattern="^(student|teacher)$" 应直接拒绝
    assert resp.status_code == 422


# ===== 字段校验 =====


def test_register_short_password_rejected(app_client_with_demo):
    """密码 < 8 字符 → 422。"""
    resp = app_client_with_demo.post(
        "/api/v1/auth/register",
        json={
            "username": "short_pwd_user",
            "password": "short1",
            "role": "student",
        },
    )
    assert resp.status_code == 422


def test_register_invalid_username_format_rejected(app_client_with_demo):
    """用户名包含非法字符(非字母/数字/下划线) → 422。"""
    resp = app_client_with_demo.post(
        "/api/v1/auth/register",
        json={
            "username": "invalid user name!",
            "password": "TestRegister123",
            "role": "student",
        },
    )
    assert resp.status_code == 422


def test_register_short_username_rejected(app_client_with_demo):
    """用户名 < 3 字符 → 422。"""
    resp = app_client_with_demo.post(
        "/api/v1/auth/register",
        json={
            "username": "ab",
            "password": "TestRegister123",
            "role": "student",
        },
    )
    assert resp.status_code == 422
