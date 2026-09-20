"""普通（非 Agent）学习计划进入自适应闭环的测试。

背景：`/learning-plans/generate` 只产出**草案**；只有 Agent `learning_goal` 工作流
会创建干预。这条用例组钉住补齐后的语义：

- 生成草案 → **不**创建干预（未采纳的计划永远不会被自动重规划）；
- 学生**确认** → 创建一条绑定该计划的干预记录，进入观测/评估/重规划闭环；
- 学生**执行** → 幂等兜底，不产生第二条记录；
- Agent 路径已绑定的计划 → 确认时**不会**产生第二条干预；
- 采纳失败 → 只降级为警告，确认计划本身必须成功。

闭环推进复用真实 Worker 与真实 HTTP 路由，不 mock 决策与血缘逻辑。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.adaptive_agent.replanning_worker import AdaptiveReplanningWorker
from app.services.container import reset_container_for_tests

from test_adaptive_closed_loop_integrity import _add_tasks  # noqa: F401 - 复用任务构造

PASSWORD = "Demo123456"
API = "/api/v1"


def _setup(username: str):
    container = reset_container_for_tests(Settings(app_env="test", database_url="sqlite:///:memory:"))
    student = container.user_repository.create_user(
        username=username, password_hash=hash_password(PASSWORD), role="student"
    )
    client = TestClient(create_app())
    response = client.post(f"{API}/auth/login", json={"username": username, "password": PASSWORD})
    assert response.status_code == 200, response.text
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    return container, student, client, headers


def _generate(client, headers, *, key: str, **body) -> dict:
    payload = {"available_minutes": 60, "idempotency_key": key}
    payload.update(body)
    response = client.post(f"{API}/learning-plans/generate", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _accept(client, headers, plan_id: str):
    return client.post(f"{API}/learning-plans/{plan_id}/decision", json={"decision": "ACCEPT"}, headers=headers)


def _reject(client, headers, plan_id: str):
    return client.post(f"{API}/learning-plans/{plan_id}/decision", json={"decision": "REJECT"}, headers=headers)


def _execute(client, headers, plan_id: str):
    return client.post(f"{API}/learning-plans/{plan_id}/execute", headers=headers)


def _interventions_for_plan(container, user_id: str, plan_id: str) -> list[dict]:
    with container.db.query() as conn:
        return [
            dict(row) for row in conn.execute(
                "SELECT * FROM adaptive_interventions WHERE user_id=? AND plan_id=?",
                (user_id, plan_id),
            ).fetchall()
        ]


def _tick(container, *, clock):
    return AdaptiveReplanningWorker(
        repository=container.adaptive_intervention_repository,
        intervention_service=container.adaptive_intervention_service,
        clock=lambda: clock,
    ).tick(batch_size=10)


# ===== 1. 未采纳的计划永不进入闭环 =====


def test_generating_a_plan_does_not_create_an_intervention():
    container, student, client, headers = _setup("adopt_generate_only")
    _add_tasks(container, student.id, count=2, day_offset=2)

    plan = _generate(client, headers, key="adopt-generate-only")

    assert plan["status"] == "PROPOSED"
    assert _interventions_for_plan(container, student.id, plan["plan_id"]) == []


def test_rejecting_a_plan_never_creates_an_intervention():
    container, student, client, headers = _setup("adopt_reject")
    _add_tasks(container, student.id, count=2, day_offset=2)
    plan = _generate(client, headers, key="adopt-reject")

    response = _reject(client, headers, plan["plan_id"])

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "REJECTED"
    assert _interventions_for_plan(container, student.id, plan["plan_id"]) == []


# ===== 2. 采纳后创建可观测干预 =====


def test_accepting_a_plan_creates_one_observable_intervention():
    container, student, client, headers = _setup("adopt_accept")
    _add_tasks(container, student.id, count=2, day_offset=2)
    plan = _generate(client, headers, key="adopt-accept")

    response = _accept(client, headers, plan["plan_id"])
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ACCEPTED"

    rows = _interventions_for_plan(container, student.id, plan["plan_id"])
    assert len(rows) == 1, f"确认计划应当恰好产生一条干预记录：{rows}"
    row = rows[0]
    assert row["status"] == "PLAN_GENERATED"
    assert row["observation_due_at"], "必须设置观测窗到期时间，否则后台永远不会评估"
    assert row["goal_id"] == f"plan:{plan['plan_id']}", "无目标计划用计划自身的稳定 scope 键"
    assert row["chain_depth"] == 0
    assert row["supersedes_intervention_id"] is None, "采纳不是替换，不得写血缘"

    # 可观测：真实 HTTP 接口能读到它
    listed = client.get(f"{API}/adaptive-interventions?page=1&page_size=10", headers=headers)
    assert listed.status_code == 200, listed.text
    assert any(item["intervention_id"] == row["intervention_id"] for item in listed.json()["items"])


def test_accept_then_execute_is_idempotent():
    container, student, client, headers = _setup("adopt_idempotent")
    _add_tasks(container, student.id, count=2, day_offset=2)
    plan = _generate(client, headers, key="adopt-idempotent")

    _accept(client, headers, plan["plan_id"])
    assert _execute(client, headers, plan["plan_id"]).status_code == 200
    assert _execute(client, headers, plan["plan_id"]).status_code == 200

    assert len(_interventions_for_plan(container, student.id, plan["plan_id"])) == 1


def test_execute_backfills_intervention_for_plan_accepted_before_this_feature():
    """在"确认即建干预"上线前已被接受的计划，会在第一次执行时补上记录。"""
    container, student, client, headers = _setup("adopt_backfill")
    _add_tasks(container, student.id, count=2, day_offset=2)
    plan = _generate(client, headers, key="adopt-backfill")
    # 直接落库成"已接受"，模拟历史数据（绕过路由，因此不会触发采纳）
    container.learning_plan_repository.update_status(
        plan_id=plan["plan_id"], user_id=student.id, status="ACCEPTED"
    )
    assert _interventions_for_plan(container, student.id, plan["plan_id"]) == []

    assert _execute(client, headers, plan["plan_id"]).status_code == 200

    assert len(_interventions_for_plan(container, student.id, plan["plan_id"])) == 1


def test_accepting_an_agent_plan_does_not_double_adopt():
    """Agent `learning_goal` 已建好干预并绑定计划：确认时不得再建第二条。"""
    container, student, client, headers = _setup("adopt_agent_plan")
    _add_tasks(container, student.id, count=2, day_offset=2)
    goal = container.student_goal_repository.create_goal(
        user_id=student.id, name="闭环目标", category="ACADEMIC",
        target_date=(datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat(),
        idempotency_key="adopt-agent-goal",
    )[0]
    planned = container.adaptive_intervention_service.plan_for_goal(
        user_id=student.id, goal_id=goal.goal_id, available_minutes=60,
        idempotency_key="adopt-agent-intervention",
    )
    plan_id = planned.plan.plan_id
    assert len(_interventions_for_plan(container, student.id, plan_id)) == 1

    response = _accept(client, headers, plan_id)

    assert response.status_code == 200, response.text
    rows = _interventions_for_plan(container, student.id, plan_id)
    assert len(rows) == 1, "Agent 路径的计划只能有一条干预记录"
    assert rows[0]["intervention_id"] == planned.intervention.intervention_id


# ===== 3. 采纳不产生副作用 =====


def test_adoption_does_not_create_a_second_plan():
    container, student, client, headers = _setup("adopt_no_new_plan")
    _add_tasks(container, student.id, count=2, day_offset=2)
    plan = _generate(client, headers, key="adopt-no-new-plan")

    _accept(client, headers, plan["plan_id"])

    page = client.get(f"{API}/learning-plans?page=1&page_size=20", headers=headers)
    assert page.status_code == 200, page.text
    assert page.json()["total"] == 1, "采纳既有计划不得生成第二份计划"
    assert page.json()["items"][0]["plan_id"] == plan["plan_id"]


def test_adoption_failure_does_not_break_plan_acceptance(monkeypatch):
    container, student, client, headers = _setup("adopt_failure_tolerated")
    _add_tasks(container, student.id, count=2, day_offset=2)
    plan = _generate(client, headers, key="adopt-failure")

    def _boom(**kwargs):
        raise RuntimeError("闭环是增强项，不能拖垮计划确认")

    monkeypatch.setattr(container.adaptive_intervention_service, "adopt_plan", _boom)

    response = _accept(client, headers, plan["plan_id"])

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ACCEPTED"
    assert _interventions_for_plan(container, student.id, plan["plan_id"]) == []


# ===== 4. 采纳后的计划真的能走完闭环 =====


def _goal(container, student, *, key: str):
    return container.student_goal_repository.create_goal(
        user_id=student.id, name="闭环目标", category="ACADEMIC",
        target_date=(datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat(),
        idempotency_key=f"{key}-goal",
    )[0]


def test_adopted_plan_is_evaluated_and_visible_after_the_observation_window():
    container, student, client, headers = _setup("adopt_closed_loop")
    goal = _goal(container, student, key="adopt-closed-loop")
    _add_tasks(container, student.id, count=1, day_offset=2)
    _add_tasks(container, student.id, count=6, completed=True, day_offset=-3)
    plan = _generate(client, headers, key="adopt-closed-loop", goal_id=goal.goal_id)
    _accept(client, headers, plan["plan_id"])
    rows = _interventions_for_plan(container, student.id, plan["plan_id"])
    assert len(rows) == 1
    assert rows[0]["goal_id"] == goal.goal_id, "计划绑定了目标时必须沿用真实 goal_id"
    intervention_id = rows[0]["intervention_id"]
    due = datetime.fromisoformat(rows[0]["observation_due_at"].replace("Z", "+00:00"))

    # 干预后积压激增：真实投影下降，后台应当自己得出结论
    _add_tasks(container, student.id, count=25, day_offset=3)
    report = _tick(container, clock=due + timedelta(minutes=1))
    assert report.failed == 0, "闭环里不该有基础设施失败"

    outcome = client.get(f"{API}/adaptive-interventions/{intervention_id}/outcome", headers=headers)
    assert outcome.status_code == 200, outcome.text
    payload = outcome.json()

    assert payload["observed_outcome"] == "DECLINED", (
        f"真实投影必须自己得出下降结论：{payload}"
    )
    assert payload["decision"] == "REPLAN"
    assert payload["decision_status"] == "APPLIED", "只有 APPLIED 才代表计划真的切换完成"
    assert payload["decision_reason_codes"]

    # 血缘：旧计划被替代，且任何时刻只有一份正式计划
    with container.db.query() as conn:
        lineage = {
            row["plan_id"]: dict(row) for row in conn.execute(
                "SELECT plan_id, supersedes_plan_id, superseded_by_plan_id FROM learning_plans WHERE user_id=?",
                (student.id,),
            ).fetchall()
        }
    assert lineage[plan["plan_id"]]["superseded_by_plan_id"] is not None
    official = [pid for pid, row in lineage.items() if row["superseded_by_plan_id"] is None]
    assert len(official) == 1 and official[0] != plan["plan_id"]

    # 采纳链路沿用同一套防抖语义：链深只加一层
    successor = container.adaptive_intervention_repository.find_by_plan(
        user_id=student.id, plan_id=official[0]
    )
    assert successor is not None and successor.chain_depth == 1
    assert successor.supersedes_intervention_id == intervention_id


def test_adopted_plan_without_goal_stays_conservative_and_never_churns_the_plan():
    """无学生目标的普通计划：证据不足以归因时只 WAIT_FOR_EVIDENCE，绝不乱换计划。"""
    container, student, client, headers = _setup("adopt_no_goal_conservative")
    _add_tasks(container, student.id, count=1, day_offset=2)
    _add_tasks(container, student.id, count=6, completed=True, day_offset=-3)
    plan = _generate(client, headers, key="adopt-no-goal")
    _accept(client, headers, plan["plan_id"])
    rows = _interventions_for_plan(container, student.id, plan["plan_id"])
    assert len(rows) == 1
    due = datetime.fromisoformat(rows[0]["observation_due_at"].replace("Z", "+00:00"))

    _add_tasks(container, student.id, count=25, day_offset=3)
    report = _tick(container, clock=due + timedelta(minutes=1))
    assert report.failed == 0

    outcome = client.get(
        f"{API}/adaptive-interventions/{rows[0]['intervention_id']}/outcome", headers=headers
    )
    assert outcome.status_code == 200, outcome.text
    payload = outcome.json()
    # 观测与决策都真实落库（闭环完整），但结论保守：不动计划。
    assert payload["decision"] in {"CONTINUE", "WAIT_FOR_EVIDENCE", "SUSPEND"}
    assert payload["decision_status"] == "APPLIED"
    with container.db.query() as conn:
        official = conn.execute(
            "SELECT plan_id FROM learning_plans WHERE user_id=? AND superseded_by_plan_id IS NULL",
            (student.id,),
        ).fetchall()
    assert [row["plan_id"] for row in official] == [plan["plan_id"]], "保守结论不得替换计划"
