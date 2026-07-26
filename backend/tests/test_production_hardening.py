"""正式 Release 强约束测试 — 证明 production 配置无法启用 Mock 业务服务。

验收要点(对应本轮纠正要求):
1. production 环境禁止启用 AUTO_SEED_DEMO_USERS
2. production 环境禁止启用 AUTO_IMPORT_DEMO
3. 不存在 DEMO_MODE / USE_MOCK_BACKEND / MOCK_BACKEND 等开关
4. /knowledge/restore-demo 接口已下线
5. /knowledge/manage/restore_demo action 已下线
6. 工作台数字来自真实 SQL 聚合,而非写死(空数据库下应返回 0)
7. 后端不可用时返回真实错误,不返回 Mock 数据
8. demo_seeder 只能在 dev/test 调用;production 启动不会自动 seed
"""
from __future__ import annotations

import importlib
import os
import sys

import pytest


# ===== 通用夹具 =====


@pytest.fixture
def app_client_with_demo(app_client):
    """显式 seed 验收账号后的 app_client(沿用其它多角色测试同款 fixture)。"""
    from app.services.container import get_container
    from app.services.demo_seeder import seed_demo_data

    container = get_container()
    seed_demo_data(container, force=True)
    return app_client


# ===== 1. production 环境禁止启用 AUTO_SEED_DEMO_USERS / AUTO_IMPORT_DEMO =====


def test_production_env_rejects_auto_seed_demo_users():
    """production + AUTO_SEED_DEMO_USERS=True 必须在 Settings 构造时抛错。"""
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError) as exc:
        Settings(
            _env_file=None,  # 不读取 .env,确保 kwargs 生效
            app_env="production",
            auto_seed_demo_users=True,
            jwt_secret="production_secret_for_test_only",
        )
    assert "production" in str(exc.value).lower()


def test_production_env_rejects_auto_import_demo():
    """production + AUTO_IMPORT_DEMO=True 必须在 Settings 构造时抛错。"""
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError) as exc:
        Settings(
            _env_file=None,
            app_env="production",
            auto_import_demo=True,
            jwt_secret="production_secret_for_test_only",
        )
    assert "production" in str(exc.value).lower()


def test_production_env_defaults_safe():
    """production 环境下未显式启用测试开关时,Settings 应可正常构造且均为 False。"""
    from app.core.config import Settings

    s = Settings(
        _env_file=None,
        app_env="production",
        jwt_secret="production_secret_for_test_only",
    )
    assert s.auto_seed_demo_users is False
    assert s.auto_import_demo is False


# ===== 2. 生产代码不得存在 DEMO_MODE / USE_MOCK_BACKEND / MOCK_BACKEND 开关 =====


def test_no_demo_mode_or_mock_backend_flags_in_app():
    """扫描 app/ 下源码,不应出现 DEMO_MODE / USE_MOCK_BACKEND / MOCK_BACKEND 业务开关。"""
    import re
    from pathlib import Path

    backend_root = Path(__file__).resolve().parents[1]
    app_dir = backend_root / "app"
    forbidden = re.compile(
        r"\b(DEMO_MODE|USE_MOCK_BACKEND|MOCK_BACKEND|demo_mode|use_mock_backend|mock_backend)\b"
    )
    hits = []
    for py in app_dir.rglob("*.py"):
        rel = py.relative_to(backend_root)
        try:
            text = py.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if forbidden.search(line):
                # 允许在注释中作为"禁止"说明出现,但禁止作为真实分支判断
                stripped = line.lstrip()
                if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'"):
                    continue
                hits.append(f"{rel}:{lineno}: {line.strip()}")
    assert not hits, f"发现禁止的 Mock 业务开关: {hits}"


# ===== 3. /knowledge/restore-demo 接口已下线 =====


def test_restore_demo_endpoint_removed(app_client):
    """POST /api/v1/knowledge/restore-demo 应返回 404(接口已删除)。"""
    resp = app_client.post("/api/v1/knowledge/restore-demo")
    assert resp.status_code == 404, f"接口应已下线,实际返回 {resp.status_code}: {resp.text}"


def test_restore_demo_action_removed(app_client):
    """POST /api/v1/knowledge/manage/restore_demo 应返回 400 INVALID_ACTION。"""
    resp = app_client.post("/api/v1/knowledge/manage/restore_demo")
    assert resp.status_code == 400, f"实际 {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body.get("code") == "INVALID_ACTION"


def test_data_management_actions_still_available(app_client):
    """合法的数据管理 action 仍可用:delete_user_documents / delete_all_documents。"""
    # delete_user_documents — 空库也返回 200
    resp = app_client.post("/api/v1/knowledge/manage/delete_user_documents")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["action"] == "delete_user_documents"
    # delete_all_documents — 空库也返回 200
    resp = app_client.post("/api/v1/knowledge/manage/delete_all_documents")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["action"] == "delete_all_documents"


# ===== 4. 工作台数字必须来自真实 SQL 聚合(空库返回 0) =====


def test_student_dashboard_returns_real_aggregate_zero_for_empty_user(app_client_with_demo):
    """登录一个未加入任何班级的演示学生 → dashboard 应返回 0,而非写死的非零数字。

    备注:演示数据中存在 31 名演示学生,此处通过 admin 调用真实接口
    POST /api/v1/auth/admin/users 创建一个全新真实学生账号,
    走完整真实业务流程登录,验证空数据下数字为 0。
    """
    # 用 admin 登录获取 token
    admin_resp = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "admin_demo", "password": "Demo123456"},
    )
    assert admin_resp.status_code == 200, admin_resp.text
    admin_token = admin_resp.json()["access_token"]
    h = {"Authorization": f"Bearer {admin_token}"}

    # 通过真实接口 POST /api/v1/auth/admin/users 创建一个全新真实学生账号
    # (走完整真实业务流程,无任何特殊权限或绕过认证的通道)
    new_username = "fresh_student_for_dash_test"
    # 若已存在(重复运行),先尝试创建,失败则复用
    create_resp = app_client_with_demo.post(
        "/api/v1/auth/admin/users",
        json={
            "username": new_username,
            "password": "Fresh123456",
            "role": "student",
            "display_name": "全新真实学生(验收)",
            "student_number": "S_FRESH_001",
            "college": "信息工程学院",
            "major": "计算机科学与技术",
            "grade": "2024",
        },
        headers=h,
    )
    # 若已存在则返回 409,允许通过(重复运行场景)
    assert create_resp.status_code in (201, 409), create_resp.text

    # 登录该新学生(走真实业务流程)
    login = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": new_username, "password": "Fresh123456"},
    )
    assert login.status_code == 200, login.text
    student_token = login.json()["access_token"]
    h_student = {"Authorization": f"Bearer {student_token}"}

    # 学生工作台 — 全部应为 0(因为该学生未加入任何班级/课程)
    resp = app_client_with_demo.get("/api/v1/dashboard/student", headers=h_student)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["enrolled_course_count"] == 0
    assert body["unread_announcement_count"] == 0
    assert body["pending_assignment_count"] == 0
    assert body["overdue_assignment_count"] == 0
    assert body["due_soon_assignments"] == []
    assert body["recent_announcements"] == []


def test_teacher_dashboard_returns_real_aggregate_for_real_teacher(app_client_with_demo):
    """teacher_demo 的 dashboard 数字必须与数据库真实状态一致。

    验收:登录 teacher_demo → 调 dashboard → 数字应等于 SQL 聚合结果,
    而非任何写死值。
    """
    # 登录演示教师
    login = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "teacher_demo", "password": "Demo123456"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    resp = app_client_with_demo.get("/api/v1/dashboard/teacher", headers=h)
    assert resp.status_code == 200, resp.text
    dash = resp.json()

    # 直接查数据库做交叉验证
    from app.services.container import get_container

    container = get_container()
    teacher = container.user_repository.get_user_by_username("teacher_demo")
    assert teacher is not None

    expected_courses = container.course_repository.count_courses(teacher_id=teacher.id)
    expected_classes = container.class_group_repository.count_classes(teacher_id=teacher.id)
    expected_active = container.assignment_repository.count_active_assignments(teacher_id=teacher.id)

    assert dash["course_count"] == expected_courses
    assert dash["class_count"] == expected_classes
    assert dash["active_assignment_count"] == expected_active
    # 数字必须 >= 1(teacher_demo 已 seed 至少 2 门课程 / 2 个班级 / 多个任务)
    assert dash["course_count"] >= 1, "teacher_demo 应至少有 1 门课程"
    assert dash["class_count"] >= 1
    assert dash["active_assignment_count"] >= 1


# ===== 5. 后端不可用时返回真实错误,不返回 Mock 数据 =====


def test_unauthenticated_dashboard_returns_real_401(app_client_with_demo):
    """未带 token 访问 dashboard → 真实 401,不返回任何 Mock 数据。"""
    resp = app_client_with_demo.get("/api/v1/dashboard/teacher")
    assert resp.status_code == 401, resp.text
    body = resp.json()
    # 真实错误结构,而非 Mock 业务数据
    assert "code" in body
    assert body["code"] in {"UNAUTHORIZED", "INVALID_CREDENTIALS"}


def test_invalid_token_returns_real_401(app_client_with_demo):
    """带无效 token → 真实 401。"""
    h = {"Authorization": "Bearer invalid.token.here"}
    resp = app_client_with_demo.get("/api/v1/dashboard/teacher", headers=h)
    assert resp.status_code == 401


def test_student_cannot_access_teacher_dashboard_real_forbidden(app_client_with_demo):
    """学生访问教师工作台 → 真实 403,不返回 Mock 教师数据。"""
    login = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "student_demo", "password": "Demo123456"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    resp = app_client_with_demo.get("/api/v1/dashboard/teacher", headers=h)
    assert resp.status_code == 403, resp.text
    body = resp.json()
    assert body["code"] == "FORBIDDEN"


# ===== 6. POST /auth/admin/users RBAC 与一致性校验 =====


def test_admin_create_user_endpoint_rbac(app_client_with_demo):
    """POST /auth/admin/users 必须 RBAC: 仅 admin 可调用,其他角色均 403。"""
    # 学生调用 → 403
    s_login = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "student_demo", "password": "Demo123456"},
    ).json()
    resp = app_client_with_demo.post(
        "/api/v1/auth/admin/users",
        json={
            "username": "new_student_x",
            "password": "NewPass1234",
            "role": "student",
        },
        headers={"Authorization": f"Bearer {s_login['access_token']}"},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN"

    # 教师调用 → 403
    t_login = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "teacher_demo", "password": "Demo123456"},
    ).json()
    resp = app_client_with_demo.post(
        "/api/v1/auth/admin/users",
        json={
            "username": "new_student_y",
            "password": "NewPass1234",
            "role": "student",
        },
        headers={"Authorization": f"Bearer {t_login['access_token']}"},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN"

    # 未认证 → 401
    resp = app_client_with_demo.post(
        "/api/v1/auth/admin/users",
        json={
            "username": "new_student_z",
            "password": "NewPass1234",
            "role": "student",
        },
    )
    assert resp.status_code == 401


def test_admin_create_user_unauthenticated_rejected(app_client_with_demo):
    """未认证调用 POST /auth/admin/users → 真实 401,不创建任何账号。"""
    resp = app_client_with_demo.post(
        "/api/v1/auth/admin/users",
        json={
            "username": "should_not_be_created",
            "password": "NewPass1234",
            "role": "student",
        },
    )
    assert resp.status_code == 401
    # 验证账号确实未被创建
    from app.services.container import get_container

    container = get_container()
    assert container.user_repository.get_user_by_username("should_not_be_created") is None


def test_admin_create_user_role_field_consistency_validation(app_client_with_demo):
    """管理员创建用户时,role 与 student_number / teacher_number 必须一致。"""
    admin_login = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "admin_demo", "password": "Demo123456"},
    ).json()
    h = {"Authorization": f"Bearer {admin_login['access_token']}"}

    # 学生角色携带 teacher_number → 422
    resp = app_client_with_demo.post(
        "/api/v1/auth/admin/users",
        json={
            "username": "bad_student_role_mix",
            "password": "NewPass1234",
            "role": "student",
            "teacher_number": "T_BAD_001",
        },
        headers=h,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_FAILED"

    # 教师角色携带 student_number → 422
    resp = app_client_with_demo.post(
        "/api/v1/auth/admin/users",
        json={
            "username": "bad_teacher_role_mix",
            "password": "NewPass1234",
            "role": "teacher",
            "student_number": "S_BAD_001",
        },
        headers=h,
    )
    assert resp.status_code == 422

    # 管理员角色携带学号或工号 → 422
    resp = app_client_with_demo.post(
        "/api/v1/auth/admin/users",
        json={
            "username": "bad_admin_role_mix",
            "password": "NewPass1234",
            "role": "admin",
            "student_number": "S_BAD_002",
        },
        headers=h,
    )
    assert resp.status_code == 422


def test_admin_create_user_password_too_short_rejected(app_client_with_demo):
    """密码不足 8 位应被拒绝(防止弱密码)。"""
    admin_login = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "admin_demo", "password": "Demo123456"},
    ).json()
    h = {"Authorization": f"Bearer {admin_login['access_token']}"}

    resp = app_client_with_demo.post(
        "/api/v1/auth/admin/users",
        json={
            "username": "weak_pass_user",
            "password": "short",  # 不足 8 位
            "role": "student",
        },
        headers=h,
    )
    assert resp.status_code == 422


def test_admin_create_user_duplicate_username_rejected(app_client_with_demo):
    """重复用户名应被拒绝(409 USERNAME_EXISTS)。"""
    admin_login = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "admin_demo", "password": "Demo123456"},
    ).json()
    h = {"Authorization": f"Bearer {admin_login['access_token']}"}

    # admin_demo 已存在 → 409
    resp = app_client_with_demo.post(
        "/api/v1/auth/admin/users",
        json={
            "username": "admin_demo",
            "password": "SomePass1234",
            "role": "admin",
        },
        headers=h,
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "USERNAME_EXISTS"


def test_admin_create_user_returns_no_password_hash(app_client_with_demo):
    """创建用户响应不得包含 password_hash(仅返回 UserPublic 字段)。"""
    admin_login = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "admin_demo", "password": "Demo123456"},
    ).json()
    h = {"Authorization": f"Bearer {admin_login['access_token']}"}

    resp = app_client_with_demo.post(
        "/api/v1/auth/admin/users",
        json={
            "username": "verify_no_hash_user",
            "password": "VerifyPass1234",
            "role": "student",
            "student_number": "S_NO_HASH_001",
        },
        headers=h,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # 不得包含 password_hash 或 password 字段
    assert "password_hash" not in body
    assert "password" not in body
    # 应包含 UserPublic 标准字段
    assert body["username"] == "verify_no_hash_user"
    assert body["role"] == "student"
    assert body["student_number"] == "S_NO_HASH_001"
    assert "id" in body
    assert "is_active" in body


def test_admin_create_user_can_login_immediately(app_client_with_demo):
    """管理员创建的账号应能立即登录,走完整真实业务流程。"""
    admin_login = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "admin_demo", "password": "Demo123456"},
    ).json()
    h = {"Authorization": f"Bearer {admin_login['access_token']}"}

    # 创建教师账号
    create = app_client_with_demo.post(
        "/api/v1/auth/admin/users",
        json={
            "username": "new_teacher_can_login",
            "password": "TeacherPass1234",
            "role": "teacher",
            "teacher_number": "T_NEW_001",
            "display_name": "新教师(验收)",
        },
        headers=h,
    )
    assert create.status_code == 201, create.text

    # 立即用新账号登录
    login = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "new_teacher_can_login", "password": "TeacherPass1234"},
    )
    assert login.status_code == 200
    body = login.json()
    assert "access_token" in body
    assert "refresh_token" in body

    # 调用 /me 验证身份
    me = app_client_with_demo.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    me_body = me.json()
    assert me_body["user"]["username"] == "new_teacher_can_login"
    assert me_body["user"]["role"] == "teacher"


# ===== 7. demo_seeder 在 production 启动路径不会被调用 =====


def test_demo_seeder_not_invoked_in_production_lifespan(monkeypatch):
    """模拟 production 启动,验证 demo_seeder.seed_demo_data 不会被调用。

    通过 lifespan 实际启动一次 app,跟踪 seed_demo_data 是否被调用。
    """
    # 隔离 Settings 缓存
    from app.core.config import get_settings as _get_settings
    _get_settings.cache_clear()

    # 设置 production 环境(不启用任何测试开关)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "production_secret_for_test_only")
    monkeypatch.setenv("AUTO_SEED_DEMO_USERS", "false")
    monkeypatch.setenv("AUTO_IMPORT_DEMO", "false")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./data/test_production_app.db")
    _get_settings.cache_clear()

    # 跟踪 seed_demo_data 是否被调用
    import app.services.demo_seeder as seeder_mod
    import app.services.container as container_mod

    called = {"seed": False, "import_demo": False}

    def fake_seed(*args, **kwargs):
        called["seed"] = True
        return {"skipped": True}

    def fake_import_demo(self, *args, **kwargs):
        called["import_demo"] = True
        return 0

    monkeypatch.setattr(seeder_mod, "seed_demo_data", fake_seed)
    # container_mod 已 import 时持有 demo_seeder 的引用,需要也 patch
    if hasattr(container_mod, "seed_demo_data"):
        monkeypatch.setattr(container_mod, "seed_demo_data", fake_seed)

    # 还需 patch KnowledgeIngestionService.import_demo_documents
    import app.services.knowledge_ingestion_service as kis_mod
    original = kis_mod.KnowledgeIngestionService.import_demo_documents
    monkeypatch.setattr(
        kis_mod.KnowledgeIngestionService, "import_demo_documents", fake_import_demo
    )

    try:
        from app.services.container import reset_container_for_tests
        from app.main import create_app
        from fastapi.testclient import TestClient

        settings = _get_settings()
        assert settings.app_env == "production"
        assert settings.auto_seed_demo_users is False
        reset_container_for_tests(settings)
        app = create_app()
        with TestClient(app) as client:
            # lifespan 已运行,验证 seed 与 import_demo 均未被调用
            assert called["seed"] is False, "production 启动不得调用 demo_seeder"
            assert called["import_demo"] is False, "production 启动不得导入测试环境资料"
            # 健康检查应正常
            r = client.get("/api/v1/health")
            assert r.status_code == 200
    finally:
        # 恢复原始方法
        kis_mod.KnowledgeIngestionService.import_demo_documents = original
        _get_settings.cache_clear()
        # 清理测试数据库
        from pathlib import Path
        test_db = Path("./data/test_production_app.db")
        if test_db.exists():
            try:
                test_db.unlink()
            except OSError:
                pass
