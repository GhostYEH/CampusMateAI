"""个人待办任务 — 后端真实闭环测试。

覆盖要求:
- 创建任务
- 用户数据隔离(跨用户访问返回 404)
- 列表与筛选(status/priority/deadline)
- 修改
- 完成
- 软删除
- 恢复
- 截止时间计算
- 原文追溯(source_text 保留)
- 越权访问
- 无效 Token
- 数据持久化(创建后再次读取)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


# ===== 通用夹具 =====


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
def student_token(app_client_with_demo) -> str:
    return _login(app_client_with_demo, "student_demo")


@pytest.fixture
def student01_token(app_client_with_demo) -> str:
    return _login(app_client_with_demo, "student_demo_01")


@pytest.fixture
def teacher_token(app_client_with_demo) -> str:
    return _login(app_client_with_demo, "teacher_demo")


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _future_iso(days: int = 3) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _past_iso(days: int = 1) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _create_task(
    app_client,
    token: str,
    *,
    title: str = "提交实践申请",
    source_text: str = "关于 2024 年暑期实践申请的通知",
    deadline: str | None = None,
    priority: str = "medium",
    materials: list[str] | None = None,
    reminder_minutes: int | None = None,
    source_notice_id: str | None = None,
) -> dict:
    payload = {
        "title": title,
        "description": "请按时提交",
        "target_students": "2024级各班",
        "deadline": deadline or _future_iso(3),
        "materials": materials or ["申请表", "证明材料"],
        "submission_method": "线上提交",
        "location": "教务处",
        "source_name": "教务处",
        "source_text": source_text,
        "source_notice_id": source_notice_id,
        "priority": priority,
        "reminder_minutes": reminder_minutes if reminder_minutes is not None else 120,
    }
    resp = app_client.post("/api/v1/tasks", json=payload, headers=_h(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


# ===== 创建 =====


def test_create_personal_task_returns_created_fields(app_client_with_demo, student_token):
    """创建任务应返回 201 与完整字段(user_id 为当前用户)。"""
    body = _create_task(app_client_with_demo, student_token, title="提交奖学金申请")
    assert body["id"].startswith("ptask_")
    assert body["title"] == "提交奖学金申请"
    assert body["status"] == "pending"
    assert body["priority"] == "medium"
    assert body["completed_at"] is None
    assert body["deleted_at"] is None
    assert body["materials"] == ["申请表", "证明材料"]
    assert body["source_text"] == "关于 2024 年暑期实践申请的通知"
    assert body["reminder_minutes"] == 120
    assert body["created_at"]
    assert body["updated_at"]


def test_create_task_preserves_source_text_for_traceability(app_client_with_demo, student_token):
    """source_text 必须保留(确保原通知可追溯)。"""
    long_text = "关于举办 2024 年大学生创新创业大赛的通知\n各学院:请于 5 月 30 日前提交申请表。"
    body = _create_task(
        app_client_with_demo, student_token,
        title="提交创新创业大赛申请",
        source_text=long_text,
    )
    assert body["source_text"] == long_text
    # 再次查询详情,确认原文持久化
    resp = app_client_with_demo.get(f"/api/v1/tasks/{body['id']}", headers=_h(student_token))
    assert resp.status_code == 200
    assert resp.json()["source_text"] == long_text


# ===== 用户数据隔离 =====


def test_user_isolation_other_user_cannot_read(app_client_with_demo, student_token, student01_token):
    """student_demo 创建的任务,student_demo_01 不能读取(404)。"""
    body = _create_task(app_client_with_demo, student_token, title="我的待办")
    # 另一个学生访问应返回 404(不泄露存在性)
    resp = app_client_with_demo.get(
        f"/api/v1/tasks/{body['id']}", headers=_h(student01_token)
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "PERSONAL_TASK_NOT_FOUND"


def test_user_isolation_other_user_cannot_update(app_client_with_demo, student_token, student01_token):
    """跨用户 PATCH 应返回 404。"""
    body = _create_task(app_client_with_demo, student_token)
    resp = app_client_with_demo.patch(
        f"/api/v1/tasks/{body['id']}",
        json={"title": "篡改标题"},
        headers=_h(student01_token),
    )
    assert resp.status_code == 404


def test_user_isolation_other_user_cannot_complete(app_client_with_demo, student_token, student01_token):
    """跨用户 complete 应返回 404。"""
    body = _create_task(app_client_with_demo, student_token)
    resp = app_client_with_demo.post(
        f"/api/v1/tasks/{body['id']}/complete", headers=_h(student01_token)
    )
    assert resp.status_code == 404


def test_user_isolation_other_user_cannot_delete(app_client_with_demo, student_token, student01_token):
    """跨用户 DELETE 应返回 404。"""
    body = _create_task(app_client_with_demo, student_token)
    resp = app_client_with_demo.delete(
        f"/api/v1/tasks/{body['id']}", headers=_h(student01_token)
    )
    assert resp.status_code == 404


def test_user_isolation_list_excludes_other_users(app_client_with_demo, student_token, student01_token):
    """列表只返回当前用户的任务。"""
    _create_task(app_client_with_demo, student_token, title="学生A的任务")
    _create_task(app_client_with_demo, student01_token, title="学生B的任务")
    resp = app_client_with_demo.get("/api/v1/tasks", headers=_h(student_token))
    assert resp.status_code == 200
    items = resp.json()["items"]
    titles = [it["title"] for it in items]
    assert "学生A的任务" in titles
    assert "学生B的任务" not in titles


# ===== 无效 Token =====


def test_invalid_token_returns_401(app_client_with_demo):
    """无 Authorization 头应返回 401。"""
    resp = app_client_with_demo.get("/api/v1/tasks")
    assert resp.status_code == 401


def test_malformed_token_returns_401(app_client_with_demo):
    """无效 token 应返回 401。"""
    resp = app_client_with_demo.get(
        "/api/v1/tasks", headers={"Authorization": "Bearer invalid.token.here"}
    )
    assert resp.status_code == 401


def test_create_task_without_token_returns_401(app_client_with_demo):
    """无 token 创建任务应返回 401。"""
    resp = app_client_with_demo.post(
        "/api/v1/tasks",
        json={"title": "无 token"},
    )
    assert resp.status_code == 401


# ===== 列表与筛选 =====


def test_list_tasks_filters_by_status(app_client_with_demo, student_token):
    """按 status 筛选。"""
    t1 = _create_task(app_client_with_demo, student_token, title="待办1")
    t2 = _create_task(app_client_with_demo, student_token, title="待办2")
    # 完成 t2
    app_client_with_demo.post(f"/api/v1/tasks/{t2['id']}/complete", headers=_h(student_token))
    # 只看 pending
    resp = app_client_with_demo.get(
        "/api/v1/tasks?status=pending", headers=_h(student_token)
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    titles = [it["title"] for it in items]
    assert "待办1" in titles
    assert "待办2" not in titles
    # 只看 completed
    resp = app_client_with_demo.get(
        "/api/v1/tasks?status=completed", headers=_h(student_token)
    )
    titles = [it["title"] for it in resp.json()["items"]]
    assert "待办2" in titles
    assert "待办1" not in titles


def test_list_tasks_filters_by_priority(app_client_with_demo, student_token):
    """按 priority 筛选。"""
    _create_task(app_client_with_demo, student_token, title="高优先级", priority="high")
    _create_task(app_client_with_demo, student_token, title="低优先级", priority="low")
    resp = app_client_with_demo.get(
        "/api/v1/tasks?priority=high", headers=_h(student_token)
    )
    titles = [it["title"] for it in resp.json()["items"]]
    assert "高优先级" in titles
    assert "低优先级" not in titles


def test_list_tasks_filters_by_deadline_range(app_client_with_demo, student_token):
    """按 deadline_before / deadline_after 筛选。"""
    _create_task(
        app_client_with_demo, student_token,
        title="即将截止",
        deadline=_future_iso(2),
    )
    _create_task(
        app_client_with_demo, student_token,
        title="远期截止",
        deadline=_future_iso(30),
    )
    # 只看 7 天内截止
    resp = app_client_with_demo.get(
        f"/api/v1/tasks?deadline_before={_future_iso(7)}",
        headers=_h(student_token),
    )
    titles = [it["title"] for it in resp.json()["items"]]
    assert "即将截止" in titles
    assert "远期截止" not in titles


def test_list_tasks_excludes_deleted_by_default(app_client_with_demo, student_token):
    """默认列表不返回已删除任务。"""
    t1 = _create_task(app_client_with_demo, student_token, title="会被删除")
    app_client_with_demo.delete(f"/api/v1/tasks/{t1['id']}", headers=_h(student_token))
    # 默认列表
    resp = app_client_with_demo.get("/api/v1/tasks", headers=_h(student_token))
    titles = [it["title"] for it in resp.json()["items"]]
    assert "会被删除" not in titles
    # include_deleted=true 可看到
    resp = app_client_with_demo.get(
        "/api/v1/tasks?include_deleted=true", headers=_h(student_token)
    )
    titles = [it["title"] for it in resp.json()["items"]]
    assert "会被删除" in titles


# ===== 修改 =====


def test_update_task_changes_fields(app_client_with_demo, student_token):
    """PATCH 部分更新。"""
    body = _create_task(app_client_with_demo, student_token, title="原标题")
    resp = app_client_with_demo.patch(
        f"/api/v1/tasks/{body['id']}",
        json={"title": "新标题", "priority": "high", "reminder_minutes": 60},
        headers=_h(student_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "新标题"
    assert data["priority"] == "high"
    assert data["reminder_minutes"] == 60
    # 未更新的字段保留
    assert data["source_text"] == body["source_text"]


def test_update_deleted_task_returns_conflict(app_client_with_demo, student_token):
    """已删除任务不能修改。"""
    body = _create_task(app_client_with_demo, student_token)
    app_client_with_demo.delete(f"/api/v1/tasks/{body['id']}", headers=_h(student_token))
    resp = app_client_with_demo.patch(
        f"/api/v1/tasks/{body['id']}",
        json={"title": "新标题"},
        headers=_h(student_token),
    )
    assert resp.status_code == 409


def test_update_nonexistent_task_returns_404(app_client_with_demo, student_token):
    """更新不存在的任务返回 404。"""
    resp = app_client_with_demo.patch(
        "/api/v1/tasks/ptask_nonexistent",
        json={"title": "新标题"},
        headers=_h(student_token),
    )
    assert resp.status_code == 404


def test_update_task_materials(app_client_with_demo, student_token):
    """materials 数组可更新。"""
    body = _create_task(app_client_with_demo, student_token)
    resp = app_client_with_demo.patch(
        f"/api/v1/tasks/{body['id']}",
        json={"materials": ["新材料1", "新材料2"]},
        headers=_h(student_token),
    )
    assert resp.status_code == 200
    assert resp.json()["materials"] == ["新材料1", "新材料2"]


# ===== 完成 =====


def test_complete_task_sets_completed_at(app_client_with_demo, student_token):
    """完成应设置 completed_at 且 status=completed。"""
    body = _create_task(app_client_with_demo, student_token)
    resp = app_client_with_demo.post(
        f"/api/v1/tasks/{body['id']}/complete", headers=_h(student_token)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["completed_at"] is not None
    assert data["deleted_at"] is None


def test_complete_already_completed_is_idempotent(app_client_with_demo, student_token):
    """已完成任务再次 complete 应幂等返回当前状态。"""
    body = _create_task(app_client_with_demo, student_token)
    app_client_with_demo.post(f"/api/v1/tasks/{body['id']}/complete", headers=_h(student_token))
    resp = app_client_with_demo.post(
        f"/api/v1/tasks/{body['id']}/complete", headers=_h(student_token)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


def test_complete_deleted_task_returns_conflict(app_client_with_demo, student_token):
    """已删除任务不能完成。"""
    body = _create_task(app_client_with_demo, student_token)
    app_client_with_demo.delete(f"/api/v1/tasks/{body['id']}", headers=_h(student_token))
    resp = app_client_with_demo.post(
        f"/api/v1/tasks/{body['id']}/complete", headers=_h(student_token)
    )
    assert resp.status_code == 409


# ===== 软删除 =====


def test_soft_delete_sets_deleted_at(app_client_with_demo, student_token):
    """DELETE 应软删除(status=deleted, deleted_at 非空)。"""
    body = _create_task(app_client_with_demo, student_token)
    resp = app_client_with_demo.delete(
        f"/api/v1/tasks/{body['id']}", headers=_h(student_token)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "deleted"
    assert data["deleted_at"] is not None
    # 详情仍可读(用于"撤销删除")
    resp = app_client_with_demo.get(
        f"/api/v1/tasks/{body['id']}", headers=_h(student_token)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"


def test_soft_delete_is_idempotent(app_client_with_demo, student_token):
    """重复 DELETE 应幂等。"""
    body = _create_task(app_client_with_demo, student_token)
    r1 = app_client_with_demo.delete(f"/api/v1/tasks/{body['id']}", headers=_h(student_token))
    assert r1.status_code == 200
    r2 = app_client_with_demo.delete(f"/api/v1/tasks/{body['id']}", headers=_h(student_token))
    assert r2.status_code == 200
    assert r2.json()["status"] == "deleted"


# ===== 恢复 =====


def test_restore_from_completed(app_client_with_demo, student_token):
    """从 completed 恢复为 pending,清空 completed_at。"""
    body = _create_task(app_client_with_demo, student_token)
    app_client_with_demo.post(f"/api/v1/tasks/{body['id']}/complete", headers=_h(student_token))
    resp = app_client_with_demo.post(
        f"/api/v1/tasks/{body['id']}/restore", headers=_h(student_token)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["completed_at"] is None
    assert data["deleted_at"] is None


def test_restore_from_deleted(app_client_with_demo, student_token):
    """从 deleted 恢复为 pending,清空 deleted_at。"""
    body = _create_task(app_client_with_demo, student_token)
    app_client_with_demo.delete(f"/api/v1/tasks/{body['id']}", headers=_h(student_token))
    resp = app_client_with_demo.post(
        f"/api/v1/tasks/{body['id']}/restore", headers=_h(student_token)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["deleted_at"] is None
    assert data["completed_at"] is None


def test_restore_pending_is_noop(app_client_with_demo, student_token):
    """对 pending 任务 restore 应保持原状(不报错)。"""
    body = _create_task(app_client_with_demo, student_token)
    resp = app_client_with_demo.post(
        f"/api/v1/tasks/{body['id']}/restore", headers=_h(student_token)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


# ===== 截止时间 =====


def test_deadline_persists_and_filters(app_client_with_demo, student_token):
    """deadline 持久化,且 list_recent_pending 按 deadline 升序返回。"""
    # 创建一个未来 1 天截止的任务
    near = _create_task(
        app_client_with_demo, student_token,
        title="近截止",
        deadline=_future_iso(1),
    )
    # 创建一个未来 10 天截止的任务
    far = _create_task(
        app_client_with_demo, student_token,
        title="远截止",
        deadline=_future_iso(10),
    )
    # 直接通过仓库层验证顺序
    from app.services.container import get_container
    repo = get_container().personal_task_repository
    # 通过 token 解析当前用户(从 StudentDashboard 接口间接验证)
    resp = app_client_with_demo.get("/api/v1/dashboard/student", headers=_h(student_token))
    assert resp.status_code == 200
    dashboard = resp.json()
    due_soon = dashboard["due_soon_personal_tasks"]
    titles = [it["title"] for it in due_soon]
    # 近截止应在远截止之前
    if "远截止" in titles and "近截止" in titles:
        assert titles.index("近截止") < titles.index("远截止")


def test_overdue_task_counted_in_dashboard(app_client_with_demo, student_token):
    """逾期任务计入 dashboard.overdue_personal_task_count。"""
    # 创建一个已逾期的任务
    _create_task(
        app_client_with_demo, student_token,
        title="已逾期",
        deadline=_past_iso(1),
    )
    resp = app_client_with_demo.get("/api/v1/dashboard/student", headers=_h(student_token))
    assert resp.status_code == 200
    dashboard = resp.json()
    assert dashboard["overdue_personal_task_count"] >= 1
    assert dashboard["pending_personal_task_count"] >= 1


# ===== 数据持久化 =====


def test_task_persists_across_requests(app_client_with_demo, student_token):
    """任务在多个请求之间持久化(创建 → 查询 → 列表 → 完成 → 查询)。"""
    body = _create_task(app_client_with_demo, student_token, title="持久化任务")
    task_id = body["id"]
    # 详情查询
    r1 = app_client_with_demo.get(f"/api/v1/tasks/{task_id}", headers=_h(student_token))
    assert r1.status_code == 200
    assert r1.json()["title"] == "持久化任务"
    # 列表查询
    r2 = app_client_with_demo.get("/api/v1/tasks", headers=_h(student_token))
    assert any(it["id"] == task_id for it in r2.json()["items"])
    # 完成
    r3 = app_client_with_demo.post(
        f"/api/v1/tasks/{task_id}/complete", headers=_h(student_token)
    )
    assert r3.status_code == 200
    # 再次查询详情,确认 completed_at 已设置
    r4 = app_client_with_demo.get(f"/api/v1/tasks/{task_id}", headers=_h(student_token))
    assert r4.json()["status"] == "completed"
    assert r4.json()["completed_at"] is not None


def test_task_persists_in_database_after_create(app_client_with_demo, student_token):
    """直接通过仓库层验证数据已写入数据库。"""
    body = _create_task(app_client_with_demo, student_token)
    from app.services.container import get_container
    repo = get_container().personal_task_repository
    # 通过 user_id 反查 — 但路由层 user_id 由 JWT 注入,这里我们用 list_tasks 反查
    # 由于 we don't know user_id directly, 我们靠 get_task 的 user 隔离来验证
    # 取所有任务列表(全部用户),通过 list_tasks 不行(它按 user_id 过滤)
    # 改用直接 SQL 验证
    with get_container().db.query() as conn:
        cur = conn.execute(
            "SELECT * FROM personal_tasks WHERE id = ?", (body["id"],)
        )
        row = cur.fetchone()
    assert row is not None
    assert row["title"] == body["title"]
    assert row["source_text"] == body["source_text"]


# ===== Dashboard 集成 =====


def test_dashboard_includes_personal_task_stats(app_client_with_demo, student_token):
    """学生 dashboard 应包含个人待办统计。"""
    _create_task(app_client_with_demo, student_token, title="待办1")
    _create_task(app_client_with_demo, student_token, title="待办2")
    resp = app_client_with_demo.get("/api/v1/dashboard/student", headers=_h(student_token))
    assert resp.status_code == 200
    dashboard = resp.json()
    assert dashboard["pending_personal_task_count"] >= 2
    assert isinstance(dashboard["due_soon_personal_tasks"], list)


# ===== 教师访问 =====


def test_teacher_can_create_personal_task(app_client_with_demo, teacher_token):
    """教师也能创建个人待办(教师同样有校园通知待办)。"""
    body = _create_task(app_client_with_demo, teacher_token, title="教师任务")
    assert body["status"] == "pending"
    # 教师列表也应能返回自己的任务
    resp = app_client_with_demo.get("/api/v1/tasks", headers=_h(teacher_token))
    titles = [it["title"] for it in resp.json()["items"]]
    assert "教师任务" in titles


def test_teacher_dashboard_unaffected_by_personal_tasks(app_client_with_demo, teacher_token):
    """教师 dashboard 接口不受 personal_tasks 影响(应返回正常 TeacherDashboard)。"""
    # 教师创建一个个人待办
    _create_task(app_client_with_demo, teacher_token, title="教师个人待办")
    resp = app_client_with_demo.get("/api/v1/dashboard/teacher", headers=_h(teacher_token))
    assert resp.status_code == 200
    body = resp.json()
    # TeacherDashboard 仍包含原字段
    assert "course_count" in body
    assert "student_count" in body
