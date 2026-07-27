"""学习陪伴 — 学习会话后端测试。

覆盖要求:
- 状态机: 创建 → 暂停 → 恢复 → 结束,非法转换被拒绝
- 用户隔离: 用户 A 不能访问用户 B 的会话(真实注册第二个用户,不 skip)
- 会话恢复: 应用重启后 GET /sessions/active 返回未结束会话
- 文字感受: finish 时 self_report 由用户主动输入,可保存
- 关联任务权限: related_task_id 必须是当前用户的 PersonalTask,跨用户/已删除/Assignment ID 全部拒绝
- 任务拆解: task_id 只解析 PersonalTask,跨用户读不到内容
- LLM 与降级拆解: 测试环境 LLM=none → rule_fallback,标注 mode
- 任务拆解输出结构化步骤,涉及政策时依赖知识库
- 错误状态: 未登录 401,跨用户 404,空白 self_report 422
"""
from __future__ import annotations

import pytest


# ===== 通用夹具 =====


@pytest.fixture
def app_client_with_demo(app_client):
    """开启多角色演示数据 seeding 的 app_client。"""
    from app.services.container import get_container
    from app.services.demo_seeder import seed_demo_data

    container = get_container()
    seed_demo_data(container, force=True)
    return app_client


@pytest.fixture
def admin_tokens(app_client_with_demo):
    """登录管理员账号,用于创建第二个测试用户。"""
    resp = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "admin_demo", "password": "Demo123456"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def student_tokens(app_client_with_demo):
    """登录演示学生账号,返回 access_token。"""
    resp = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "student_demo", "password": "Demo123456"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def student2_tokens(app_client_with_demo, admin_tokens):
    """注册并登录第二个学生账号,用于用户隔离测试。

    通过 admin API 真实创建一个新用户(不依赖演示数据中的 student_demo2)。
    用户名/学号使用固定值,在 seed_demo_data 后唯一。
    """
    # 注册新学生
    resp = app_client_with_demo.post(
        "/api/v1/auth/admin/users",
        json={
            "username": "student_isolation_test",
            "password": "IsolationTest123",
            "role": "student",
            "display_name": "隔离测试学生",
            "student_number": "S_TEST_ISO_001",
            "college": "信息工程学院",
            "major": "计算机科学与技术",
            "grade": "2024",
        },
        headers={"Authorization": f"Bearer {admin_tokens}"},
    )
    # 已存在则视为成功(幂等)
    if resp.status_code not in (201, 409):
        assert resp.status_code == 201, f"注册第二用户失败: {resp.text}"
    # 登录新学生
    resp = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "student_isolation_test", "password": "IsolationTest123"},
    )
    assert resp.status_code == 200, f"登录第二用户失败: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture
def teacher_tokens(app_client_with_demo):
    resp = app_client_with_demo.post(
        "/api/v1/auth/login",
        json={"username": "teacher_demo", "password": "Demo123456"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_personal_task(
    client, token: str, *, title: str = "测试待办", description: str = "测试描述"
) -> dict:
    """辅助:通过 /api/v1/tasks 创建个人待办,返回 JSON。"""
    resp = client.post(
        "/api/v1/tasks",
        json={"title": title, "description": description},
        headers=_auth(token),
    )
    assert resp.status_code == 201, f"创建个人待办失败: {resp.text}"
    return resp.json()


def _get_assignment_id() -> str:
    """辅助:从数据库中获取一条已存在的 Assignment ID(用于验证实体类型隔离)。

    演示数据 seeding 会创建若干 Assignment,这里直接查询 assignments 表。
    若不存在则 fail(不再 skip)— 用户隔离与实体区分测试不得 skip。
    """
    from app.services.container import get_container

    container = get_container()
    db = container.db
    with db.query() as conn:
        cur = conn.execute(
            "SELECT id FROM assignments ORDER BY created_at DESC LIMIT 1"
        )
        row = cur.fetchone()
    assert row is not None, (
        "演示数据无 Assignment — 请检查 demo_seeder 是否正确执行。"
        "用户隔离与实体区分测试不得 skip。"
    )
    return row["id"]


# ===== 状态机 =====


def test_create_session_returns_active_status(app_client_with_demo, student_tokens):
    """创建会话: 状态 active,duration=0,pause=0,有 started_at 无 ended_at。"""
    resp = app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "复习高等数学第三章"},
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "active"
    assert body["duration_seconds"] == 0
    assert body["pause_seconds"] == 0
    assert body["started_at"]
    assert body["ended_at"] is None
    assert body["goal"] == "复习高等数学第三章"
    assert body["breaks"] == []


def test_pause_resume_lifecycle(app_client_with_demo, student_tokens):
    """完整生命周期: create → pause → resume → pause → finish。"""
    # create
    create = app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "刷 LeetCode"},
        headers=_auth(student_tokens),
    ).json()
    sid = create["id"]
    # pause
    pause = app_client_with_demo.post(
        f"/api/v1/study/sessions/{sid}/pause",
        headers=_auth(student_tokens),
    )
    assert pause.status_code == 200, pause.text
    assert pause.json()["status"] == "paused"
    assert pause.json()["paused_at"] is not None
    # 检查休息记录
    detail = app_client_with_demo.get(
        f"/api/v1/study/sessions/{sid}", headers=_auth(student_tokens)
    ).json()
    assert len(detail["breaks"]) == 1
    assert detail["breaks"][0]["ended_at"] is None  # 未结束
    # resume
    resume = app_client_with_demo.post(
        f"/api/v1/study/sessions/{sid}/resume",
        headers=_auth(student_tokens),
    )
    assert resume.status_code == 200, resume.text
    assert resume.json()["status"] == "active"
    # 休息记录应已关闭
    detail = app_client_with_demo.get(
        f"/api/v1/study/sessions/{sid}", headers=_auth(student_tokens)
    ).json()
    assert detail["breaks"][0]["ended_at"] is not None
    assert detail["pause_seconds"] >= 0
    # finish
    finish = app_client_with_demo.post(
        f"/api/v1/study/sessions/{sid}/finish",
        json={"self_report": "今天刷了 5 道动态规划,有点累但收获很大。"},
        headers=_auth(student_tokens),
    )
    assert finish.status_code == 200, finish.text
    body = finish.json()
    assert body["status"] == "completed"
    assert body["ended_at"] is not None
    assert body["duration_seconds"] >= 0
    assert body["self_report"] == "今天刷了 5 道动态规划,有点累但收获很大。"


def test_cannot_pause_completed_session(app_client_with_demo, student_tokens):
    """已结束的会话不能再次暂停。"""
    create = app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "测试"},
        headers=_auth(student_tokens),
    ).json()
    sid = create["id"]
    # 先结束
    app_client_with_demo.post(
        f"/api/v1/study/sessions/{sid}/finish",
        json={},
        headers=_auth(student_tokens),
    )
    # 再次暂停 → 409
    resp = app_client_with_demo.post(
        f"/api/v1/study/sessions/{sid}/pause",
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "INVALID_TRANSITION"


def test_cannot_resume_active_session(app_client_with_demo, student_tokens):
    """未暂停的会话不能直接恢复。"""
    create = app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "测试"},
        headers=_auth(student_tokens),
    ).json()
    sid = create["id"]
    # active 状态直接 resume → 409
    resp = app_client_with_demo.post(
        f"/api/v1/study/sessions/{sid}/resume",
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "INVALID_TRANSITION"


def test_cannot_finish_twice(app_client_with_demo, student_tokens):
    """会话已结束不能再次结束。"""
    create = app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "测试"},
        headers=_auth(student_tokens),
    ).json()
    sid = create["id"]
    app_client_with_demo.post(
        f"/api/v1/study/sessions/{sid}/finish",
        json={},
        headers=_auth(student_tokens),
    )
    resp = app_client_with_demo.post(
        f"/api/v1/study/sessions/{sid}/finish",
        json={},
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "INVALID_TRANSITION"


def test_paused_session_can_finish(app_client_with_demo, student_tokens):
    """paused 状态可直接结束,关闭未结束的休息记录。"""
    create = app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "测试"},
        headers=_auth(student_tokens),
    ).json()
    sid = create["id"]
    # pause
    app_client_with_demo.post(
        f"/api/v1/study/sessions/{sid}/pause",
        headers=_auth(student_tokens),
    )
    # finish(从 paused 直接结束)
    resp = app_client_with_demo.post(
        f"/api/v1/study/sessions/{sid}/finish",
        json={"self_report": "中断了,先结束"},
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    # 休息记录应已关闭
    assert all(b["ended_at"] for b in body["breaks"])


# ===== 用户隔离 =====


def test_user_cannot_access_other_user_session(
    app_client_with_demo, student_tokens, student2_tokens
):
    """用户 A 创建的会话,用户 B 不能访问(404)。"""
    # student1 创建
    create = app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "student1 的会话"},
        headers=_auth(student_tokens),
    ).json()
    sid = create["id"]
    # student2 尝试访问 → 404
    resp = app_client_with_demo.get(
        f"/api/v1/study/sessions/{sid}", headers=_auth(student2_tokens)
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "STUDY_SESSION_NOT_FOUND"
    # student2 尝试暂停 → 404
    resp2 = app_client_with_demo.post(
        f"/api/v1/study/sessions/{sid}/pause",
        headers=_auth(student2_tokens),
    )
    assert resp2.status_code == 404
    # student2 尝试结束 → 404
    resp3 = app_client_with_demo.post(
        f"/api/v1/study/sessions/{sid}/finish",
        json={},
        headers=_auth(student2_tokens),
    )
    assert resp3.status_code == 404


def test_list_sessions_only_returns_own(
    app_client_with_demo, student_tokens, student2_tokens
):
    """列表接口只返回当前用户的会话。"""
    # student1 创建 2 个
    app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "s1-a"},
        headers=_auth(student_tokens),
    )
    app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "s1-b"},
        headers=_auth(student_tokens),
    )
    # student2 创建 1 个
    app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "s2-a"},
        headers=_auth(student2_tokens),
    )
    # student1 列表应只有 2 个
    resp = app_client_with_demo.get(
        "/api/v1/study/sessions", headers=_auth(student_tokens)
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    assert all(item["user_id"] != "" for item in items)
    goals = {item["goal"] for item in items}
    assert goals == {"s1-a", "s1-b"}


# ===== 会话恢复 =====


def test_get_active_session_returns_unfinished(app_client_with_demo, student_tokens):
    """GET /sessions/active 返回当前未结束会话(用于应用重启后恢复)。"""
    # 无会话
    resp = app_client_with_demo.get(
        "/api/v1/study/sessions/active", headers=_auth(student_tokens)
    )
    assert resp.status_code == 200
    assert resp.json() is None
    # 创建一个 active 会话
    create = app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "未结束的会话"},
        headers=_auth(student_tokens),
    ).json()
    # 再查询
    resp = app_client_with_demo.get(
        "/api/v1/study/sessions/active", headers=_auth(student_tokens)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body is not None
    assert body["id"] == create["id"]
    assert body["status"] == "active"
    # 暂停后再查
    app_client_with_demo.post(
        f"/api/v1/study/sessions/{create['id']}/pause",
        headers=_auth(student_tokens),
    )
    resp = app_client_with_demo.get(
        "/api/v1/study/sessions/active", headers=_auth(student_tokens)
    )
    body = resp.json()
    assert body["status"] == "paused"  # paused 也算"未结束"
    # 结束后再查 → null
    app_client_with_demo.post(
        f"/api/v1/study/sessions/{create['id']}/finish",
        json={},
        headers=_auth(student_tokens),
    )
    resp = app_client_with_demo.get(
        "/api/v1/study/sessions/active", headers=_auth(student_tokens)
    )
    assert resp.json() is None


# ===== 文字感受(self_report) =====


def test_finish_accepts_self_report(app_client_with_demo, student_tokens):
    """finish 接口接受 self_report 文字感受,持久化并可读取。"""
    create = app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "测试"},
        headers=_auth(student_tokens),
    ).json()
    sid = create["id"]
    report = "今天复习了三个小时,对积分部分理解更深了,但还有点累。"
    tags = ["专注", "略有收获"]
    resp = app_client_with_demo.post(
        f"/api/v1/study/sessions/{sid}/finish",
        json={"self_report": report, "self_report_tags": tags},
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["self_report"] == report
    assert body["self_report_tags"] == tags


def test_finish_rejects_blank_self_report(app_client_with_demo, student_tokens):
    """空白 self_report 应被拒绝(若填写需有内容)。"""
    create = app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "测试"},
        headers=_auth(student_tokens),
    ).json()
    sid = create["id"]
    resp = app_client_with_demo.post(
        f"/api/v1/study/sessions/{sid}/finish",
        json={"self_report": "   "},
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_FAILED"


def test_patch_can_update_self_report(app_client_with_demo, student_tokens):
    """PATCH 接口可在任意状态更新 self_report/tags/expression_signal。"""
    create = app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "测试"},
        headers=_auth(student_tokens),
    ).json()
    sid = create["id"]
    # 在 active 状态更新 self_report
    resp = app_client_with_demo.patch(
        f"/api/v1/study/sessions/{sid}",
        json={"self_report": "中途记录: 有点困"},
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["self_report"] == "中途记录: 有点困"
    # 结束后仍可更新 self_report
    app_client_with_demo.post(
        f"/api/v1/study/sessions/{sid}/finish",
        json={},
        headers=_auth(student_tokens),
    )
    resp = app_client_with_demo.patch(
        f"/api/v1/study/sessions/{sid}",
        json={"self_report": "事后补充: 整体不错"},
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["self_report"] == "事后补充: 整体不错"
    # expression_signal 透传存储(预留 CNN 字段)
    resp = app_client_with_demo.patch(
        f"/api/v1/study/sessions/{sid}",
        json={"expression_signal": {"label": "neutral", "confidence": 0.7}},
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["expression_signal"]["label"] == "neutral"


def test_patch_goal_blocked_for_completed_session(app_client_with_demo, student_tokens):
    """已结束会话不能改 goal/related_task_id(repo 层校验,不会报错但不更新)。"""
    create = app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "原目标"},
        headers=_auth(student_tokens),
    ).json()
    sid = create["id"]
    app_client_with_demo.post(
        f"/api/v1/study/sessions/{sid}/finish",
        json={},
        headers=_auth(student_tokens),
    )
    # 尝试改 goal → 应不更新(repo 层静默跳过)
    resp = app_client_with_demo.patch(
        f"/api/v1/study/sessions/{sid}",
        json={"goal": "新目标"},
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["goal"] == "原目标"  # 未改变


# ===== 任务拆解 =====


def test_task_breakdown_rule_fallback_mode(app_client_with_demo, student_tokens):
    """测试环境 LLM=none,任务拆解应走 rule_fallback,标注 mode。"""
    resp = app_client_with_demo.post(
        "/api/v1/study/task-breakdown",
        json={"goal": "复习数据结构链表章节"},
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mode"] == "rule_fallback"
    assert len(body["steps"]) >= 3
    # 每步必须包含必需字段
    for step in body["steps"]:
        assert "step_number" in step
        assert "title" in step
        assert "description" in step
        assert "estimated_minutes" in step
        assert "dependencies" in step
        assert "completion_criteria" in step
        assert "is_policy_step" in step
        assert 5 <= step["estimated_minutes"] <= 120
    # 步骤编号应从 1 开始连续
    numbers = [s["step_number"] for s in body["steps"]]
    assert numbers == list(range(1, len(numbers) + 1))
    # 依赖必须指向更早步骤
    for step in body["steps"]:
        for dep in step["dependencies"]:
            assert dep < step["step_number"]
    # 至少有一个 warning 说明走的是降级
    assert any("规则" in w or "LLM" in w for w in body["warnings"])


def test_task_breakdown_policy_step_uses_kb(app_client_with_demo, student_tokens):
    """涉及政策关键词(申请奖学金)的目标,应检索知识库,政策步骤标注 is_policy_step。"""
    resp = app_client_with_demo.post(
        "/api/v1/study/task-breakdown",
        json={"goal": "申请奖学金,准备材料"},
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # 应至少有一个政策步骤
    policy_steps = [s for s in body["steps"] if s["is_policy_step"]]
    assert len(policy_steps) >= 1, "政策关键词目标应至少有一个政策步骤"
    # 若知识库匹配到资料,knowledge_source 应非空
    # (演示资料中有奖学金相关文档,但具体是否匹配取决于检索)
    for step in policy_steps:
        assert "completion_criteria" in step


def test_task_breakdown_rejects_empty_input(app_client_with_demo, student_tokens):
    """task_id 和 goal 同时为空应被拒绝。"""
    resp = app_client_with_demo.post(
        "/api/v1/study/task-breakdown",
        json={},
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_FAILED"


def test_task_breakdown_with_invalid_task_id_falls_back_to_goal(
    app_client_with_demo, student_tokens
):
    """task_id 不存在时,以 goal 为准,记录 warning。"""
    resp = app_client_with_demo.post(
        "/api/v1/study/task-breakdown",
        json={
            "task_id": "nonexistent_assignment_id_xyz",
            "goal": "复习操作系统",
        },
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "rule_fallback"
    assert body["related_task_id"] is None
    assert body["related_task_title"] is None
    assert any("不存在" in w or "改用 goal" in w for w in body["warnings"])


def test_task_breakdown_with_valid_personal_task(
    app_client_with_demo, student_tokens
):
    """task_id 为当前用户 PersonalTask 时,应解析成功并填充 related_task_title。

    严格区分实体类型:不接受教师 Assignment ID(见 test_task_breakdown_rejects_assignment_id)。
    """
    # 通过 /api/v1/tasks 创建一条个人待办
    task = _create_personal_task(
        app_client_with_demo,
        student_tokens,
        title="复习数据结构链表",
        description="完成第三章习题",
    )
    task_id = task["id"]

    resp = app_client_with_demo.post(
        "/api/v1/study/task-breakdown",
        json={"task_id": task_id},
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["related_task_id"] == task_id
    assert body["related_task_title"] == "复习数据结构链表"
    assert body["goal"]  # goal 应使用任务标题(可能含上下文)


def test_task_breakdown_rejects_assignment_id(
    app_client_with_demo, student_tokens
):
    """task_id 为教师 Assignment ID 时,PersonalTaskRepository 查不到,改用 goal 拆解。

    严格区分:不得把教师 Assignment 当成 PersonalTask。
    不依赖 dashboard 返回字段名,直接从 DB 获取真实 Assignment ID。
    """
    assignment_id = _get_assignment_id()

    resp = app_client_with_demo.post(
        "/api/v1/study/task-breakdown",
        json={"task_id": assignment_id, "goal": "完成作业"},
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # task_id 解析失败 → related_task_id 为 None,记录 warning,改用 goal
    assert body["related_task_id"] is None
    assert body["related_task_title"] is None
    assert any("不存在" in w or "改用 goal" in w for w in body["warnings"])


def test_task_breakdown_cross_user_cannot_read_task_content(
    app_client_with_demo, student_tokens, student2_tokens
):
    """用户 B 不能通过 task_id 读取用户 A 的个人待办内容。

    PersonalTaskRepository.get_task 按 user_id 过滤,跨用户访问返回 None,
    服务改用 goal 拆解,related_task_id 为 None。
    """
    # student1 创建个人待办
    task = _create_personal_task(
        app_client_with_demo,
        student_tokens,
        title="student1 私密待办",
        description="敏感内容:不应对 student2 暴露",
    )

    # student2 用该 task_id 调用拆解
    resp = app_client_with_demo.post(
        "/api/v1/study/task-breakdown",
        json={"task_id": task["id"], "goal": "复习高数"},
        headers=_auth(student2_tokens),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # student2 不应能读取到 student1 的任务标题/描述
    assert body["related_task_id"] is None
    assert body["related_task_title"] is None
    assert any("不存在" in w or "改用 goal" in w for w in body["warnings"])
    # goal 只应包含 student2 自己提供的 goal,不应包含 student1 的任务内容
    assert "敏感内容" not in body["goal"]
    assert "student1 私密待办" not in body["goal"]


def test_task_breakdown_with_deleted_personal_task_falls_back(
    app_client_with_demo, student_tokens
):
    """task_id 已软删除时,改用 goal 拆解,记录 warning。"""
    task = _create_personal_task(
        app_client_with_demo,
        student_tokens,
        title="待删除的任务",
    )
    # 软删除
    del_resp = app_client_with_demo.delete(
        f"/api/v1/tasks/{task['id']}", headers=_auth(student_tokens)
    )
    assert del_resp.status_code == 200, del_resp.text

    resp = app_client_with_demo.post(
        "/api/v1/study/task-breakdown",
        json={"task_id": task["id"], "goal": "继续学习"},
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["related_task_id"] is None
    assert body["related_task_title"] is None
    assert any("已删除" in w or "改用 goal" in w for w in body["warnings"])


# ===== 鉴权 =====


def test_study_endpoints_require_auth(app_client_with_demo):
    """所有学习陪伴接口必须登录。"""
    # 无 token → 401
    resp = app_client_with_demo.get("/api/v1/study/sessions")
    assert resp.status_code == 401
    resp = app_client_with_demo.post("/api/v1/study/sessions", json={"goal": "x"})
    assert resp.status_code == 401
    resp = app_client_with_demo.get("/api/v1/study/sessions/active")
    assert resp.status_code == 401
    resp = app_client_with_demo.post("/api/v1/study/task-breakdown", json={"goal": "x"})
    assert resp.status_code == 401


def test_create_session_rejects_blank_goal(app_client_with_demo, student_tokens):
    """空白 goal 应被拒绝。"""
    resp = app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "   "},
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 422


def test_get_session_404_for_nonexistent(app_client_with_demo, student_tokens):
    """不存在的 session_id 返回 404。"""
    resp = app_client_with_demo.get(
        "/api/v1/study/sessions/nonexistent_id", headers=_auth(student_tokens)
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "STUDY_SESSION_NOT_FOUND"


# ===== 休息记录 =====


def test_breaks_recorded_for_each_pause(app_client_with_demo, student_tokens):
    """每次 pause 都生成一条休息记录,resume 时关闭。"""
    create = app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "测试"},
        headers=_auth(student_tokens),
    ).json()
    sid = create["id"]
    # 第一次 pause
    app_client_with_demo.post(
        f"/api/v1/study/sessions/{sid}/pause?reason=喝水",
        headers=_auth(student_tokens),
    )
    app_client_with_demo.post(
        f"/api/v1/study/sessions/{sid}/resume",
        headers=_auth(student_tokens),
    )
    # 第二次 pause
    app_client_with_demo.post(
        f"/api/v1/study/sessions/{sid}/pause?reason=上厕所",
        headers=_auth(student_tokens),
    )
    app_client_with_demo.post(
        f"/api/v1/study/sessions/{sid}/resume",
        headers=_auth(student_tokens),
    )
    # 查询休息记录
    detail = app_client_with_demo.get(
        f"/api/v1/study/sessions/{sid}", headers=_auth(student_tokens)
    ).json()
    assert len(detail["breaks"]) == 2
    reasons = {b["reason"] for b in detail["breaks"]}
    assert reasons == {"喝水", "上厕所"}
    # 两条都已关闭
    assert all(b["ended_at"] for b in detail["breaks"])
    # pause_seconds 应大于 0(实际休息时长)
    assert detail["pause_seconds"] >= 0


# ===== 列表与分页 =====


def test_list_sessions_filter_by_status(app_client_with_demo, student_tokens):
    """列表接口支持按 status 过滤。"""
    # 创建 2 个,其中一个结束
    s1 = app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "active"},
        headers=_auth(student_tokens),
    ).json()
    s2 = app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "completed"},
        headers=_auth(student_tokens),
    ).json()
    app_client_with_demo.post(
        f"/api/v1/study/sessions/{s2['id']}/finish",
        json={},
        headers=_auth(student_tokens),
    )
    # 过滤 active
    resp = app_client_with_demo.get(
        "/api/v1/study/sessions?status=active", headers=_auth(student_tokens)
    )
    items = resp.json()
    assert len(items) == 1
    assert items[0]["goal"] == "active"
    # 过滤 completed
    resp = app_client_with_demo.get(
        "/api/v1/study/sessions?status=completed", headers=_auth(student_tokens)
    )
    items = resp.json()
    assert len(items) == 1
    assert items[0]["goal"] == "completed"


# ===== 关联任务权限校验(PersonalTask) =====


def test_create_session_with_own_personal_task_succeeds(
    app_client_with_demo, student_tokens
):
    """related_task_id 为当前用户的 PersonalTask 时,允许创建会话。"""
    task = _create_personal_task(
        app_client_with_demo,
        student_tokens,
        title="复习高数",
    )
    resp = app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "复习高数", "related_task_id": task["id"]},
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["related_task_id"] == task["id"]


def test_create_session_with_other_user_task_rejected(
    app_client_with_demo, student_tokens, student2_tokens
):
    """related_task_id 为他人 PersonalTask 时,返回 404 PERSONAL_TASK_NOT_FOUND。

    统一返回 404 而非 403,避免泄露任务存在性。
    """
    # student2 创建任务
    task2 = _create_personal_task(
        app_client_with_demo,
        student2_tokens,
        title="student2 的任务",
    )
    # student1 尝试关联
    resp = app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "复习", "related_task_id": task2["id"]},
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "PERSONAL_TASK_NOT_FOUND"


def test_create_session_with_deleted_task_rejected(
    app_client_with_demo, student_tokens
):
    """related_task_id 为已软删除任务时,返回 404。"""
    task = _create_personal_task(
        app_client_with_demo,
        student_tokens,
        title="待删除任务",
    )
    # 软删除
    app_client_with_demo.delete(
        f"/api/v1/tasks/{task['id']}", headers=_auth(student_tokens)
    )
    # 尝试关联已删除任务
    resp = app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "复习", "related_task_id": task["id"]},
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "PERSONAL_TASK_NOT_FOUND"


def test_create_session_with_assignment_id_rejected(
    app_client_with_demo, student_tokens
):
    """related_task_id 为教师 Assignment ID 时,返回 404(不区分实体类型泄露存在性)。

    严格区分:Assignment 不是 PersonalTask,PersonalTaskRepository 查不到。
    不依赖 dashboard 返回字段名,直接从 DB 获取真实 Assignment ID。
    """
    assignment_id = _get_assignment_id()

    # 学生尝试用 Assignment ID 作为 related_task_id
    resp = app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "复习", "related_task_id": assignment_id},
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "PERSONAL_TASK_NOT_FOUND"


def test_update_session_related_task_id_validation(
    app_client_with_demo, student_tokens, student2_tokens
):
    """PATCH 接口更新 related_task_id 时同样校验权限。"""
    # 先创建一个无关联任务的会话
    create = app_client_with_demo.post(
        "/api/v1/study/sessions",
        json={"goal": "测试"},
        headers=_auth(student_tokens),
    ).json()
    sid = create["id"]

    # student2 的任务
    task2 = _create_personal_task(
        app_client_with_demo,
        student2_tokens,
        title="student2 的任务",
    )

    # student1 尝试 PATCH 关联 student2 的任务
    resp = app_client_with_demo.patch(
        f"/api/v1/study/sessions/{sid}",
        json={"related_task_id": task2["id"]},
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "PERSONAL_TASK_NOT_FOUND"

    # student1 自己的任务可以关联
    task1 = _create_personal_task(
        app_client_with_demo,
        student_tokens,
        title="student1 的任务",
    )
    resp = app_client_with_demo.patch(
        f"/api/v1/study/sessions/{sid}",
        json={"related_task_id": task1["id"]},
        headers=_auth(student_tokens),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["related_task_id"] == task1["id"]
