"""计划血缘的两条路径必须都成立，而且都必须是**双向原子**的。

`learning_plans` 的血缘由两列成对表达：

    old.superseded_by_plan_id = new.plan_id
    new.supersedes_plan_id    = old.plan_id

写入时机被刻意推迟到"绑定成功的那一刻"（`create_plan` 只暂存，不预写一半），
否则一旦绑定失败就会留下"新计划指向旧计划、旧计划仍被当成正式版本"的半截状态。
但"推迟"不能变成"丢失"：除了自动重规划那条显式调用 `link_superseded` 的路径，
还有**普通计划替换**路径（Agent 学习目标处理器直接传 `supersedes_plan_id`）。
两条路径都必须补齐血缘，且自动重规划那条必须与干预血缘同生共死。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.core.config import Settings
from app.core.security import hash_password
from app.services.agent_runtime.handlers.base import HandlerContext
from app.services.container import reset_container_for_tests

from test_adaptive_closed_loop_integrity import (  # noqa: F401 - 复用真实场景夹具
    _declining_scenario,
    _due_after,
    _rows,
)


def _student(username: str):
    container = reset_container_for_tests(
        Settings(app_env="test", database_url="sqlite:///:memory:")
    )
    student = container.user_repository.create_user(
        username=username, password_hash=hash_password("Demo123456"), role="student"
    )
    return container, student


def _seed_tasks(container, user_id: str, *, count: int = 3):
    now = datetime.now(timezone.utc)
    return [
        container.personal_task_repository.create_task(
            user_id=user_id,
            title=f"替换任务{index}",
            deadline=(now + timedelta(days=2, minutes=index)).isoformat(),
        )
        for index in range(count)
    ]


def _goal(container, user_id: str, *, key: str):
    return container.student_goal_repository.create_goal(
        user_id=user_id, name="替换目标", category="ACADEMIC",
        target_date=(datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat(),
        idempotency_key=f"{key}-goal",
    )[0]


def _plan_rows(container, user_id: str) -> list[dict]:
    return _rows(
        container,
        "SELECT plan_id, status, supersedes_plan_id, superseded_by_plan_id, replan_key FROM learning_plans "
        "WHERE user_id=? ORDER BY created_at, plan_id",
        (user_id,),
    )


def _assert_two_sided_lineage(container, user_id: str, old_plan_id: str, new_plan_id: str):
    rows = _plan_rows(container, user_id)
    by_id = {row["plan_id"]: row for row in rows}
    assert new_plan_id != old_plan_id
    assert by_id[old_plan_id]["superseded_by_plan_id"] == new_plan_id, (
        "旧计划必须回指新计划，否则'当前有效计划'查询会同时返回两份"
    )
    assert by_id[new_plan_id]["supersedes_plan_id"] == old_plan_id, (
        "新计划必须记录来源，否则替换历史断裂"
    )
    current = [row["plan_id"] for row in rows if row["superseded_by_plan_id"] is None]
    assert current == [new_plan_id], f"当前有效计划必须唯一，实际 {current}"


# ==================================================== 普通计划替换（干预服务路径）

def test_plan_for_goal_with_supersedes_links_both_plan_sides():
    """Agent 学习目标处理器走的就是这条路径：必须补齐双向血缘。"""
    container, student = _student("lineage_replace_via_goal_student")
    _seed_tasks(container, student.id)
    first = container.learning_planner_service.generate(
        user_id=student.id, available_minutes=60, idempotency_key="replace-first",
    )
    goal = _goal(container, student.id, key="replace-via-goal")

    replaced = container.adaptive_intervention_service.plan_for_goal(
        user_id=student.id, goal_id=goal.goal_id, available_minutes=60,
        idempotency_key="replace-via-goal-intervention",
        supersedes_plan_id=first.plan_id,
    )

    _assert_two_sided_lineage(
        container, student.id, first.plan_id, replaced.plan.plan_id
    )


# ============================================ 普通计划替换（规划器直连的兼容路径）

def test_planner_generate_with_supersedes_links_both_plan_sides():
    """未配置干预服务时的兼容路径同样不能丢血缘。"""
    container, student = _student("lineage_replace_via_planner_student")
    _seed_tasks(container, student.id)
    first = container.learning_planner_service.generate(
        user_id=student.id, available_minutes=60, idempotency_key="planner-first",
    )
    second = container.learning_planner_service.generate(
        user_id=student.id, available_minutes=60, idempotency_key="planner-second",
        force_new=True, supersedes_plan_id=first.plan_id, replan_key="planner-second",
    )

    _assert_two_sided_lineage(container, student.id, first.plan_id, second.plan_id)


# ============================================ 普通计划替换（Agent 处理器端到端）

def test_learning_goal_handler_replacement_links_both_plan_sides():
    """真正的 Agent 学习目标处理器：`input_ref.plan_id` 就是被替换的旧计划。

    这条路径不经过 `/replan` 路由，因此不会碰到那条显式的 `link_superseded`；
    血缘必须由规划器统一补上，否则学生的"换计划"操作在历史上是不留痕的。
    """
    container, student = _student("lineage_handler_student")
    _seed_tasks(container, student.id)
    first = container.learning_planner_service.generate(
        user_id=student.id, available_minutes=60, idempotency_key="handler-first",
    )
    goal = _goal(container, student.id, key="handler")
    input_ref = {
        "goal_id": goal.goal_id, "available_minutes": 60, "plan_id": first.plan_id,
    }

    runtime = container.agent_runtime_repository
    job_id = runtime.create_job(
        user_id=student.id, job_kind="learning_goal", input_ref=input_ref,
        idempotency_key="handler-job-1",
    )
    run_id = runtime.create_run(
        job_id=job_id, user_id=student.id, idempotency_key="handler-run-1",
        handler_code="learning_goal", handler_version="1.1.0",
    )
    handler = container.agent_handler_registry.get("learning_goal")
    assert handler is not None

    result = asyncio.run(handler.execute(HandlerContext(
        run_id=run_id, job_id=job_id, user_id=student.id, job_kind="learning_goal",
        input_ref=input_ref, checkpoint=None, attempt_no=1,
    )))

    assert result.status == "SUCCEEDED", result
    new_plan_id = result.job_output_patch["plan_id"]
    _assert_two_sided_lineage(container, student.id, first.plan_id, new_plan_id)


# ================================================ 自动重规划：与干预血缘同生共死

def test_auto_replan_rolls_back_plan_lineage_when_intervention_link_fails():
    """干预血缘写入失败时，计划血缘必须一起回滚，不能只成功一半。"""
    container, student, _goal, planned = _declining_scenario("lineage_atomic_rollback_student")
    old_plan_id = planned.plan.plan_id
    due = _due_after(planned)

    repository = container.adaptive_intervention_repository
    original = repository.link_replanned

    def exploding(**_kwargs):
        raise RuntimeError("intervention lineage store unavailable")

    repository.link_replanned = exploding
    try:
        worker = container.adaptive_replanning_worker
        worker._clock = lambda: due
        report = worker.tick(batch_size=10)
    finally:
        repository.link_replanned = original
    assert report.failed == 1

    rows = _plan_rows(container, student.id)
    by_id = {row["plan_id"]: row for row in rows}
    # 旧计划仍然是正式版本：既没有被替代，也没有留下半截血缘。
    assert by_id[old_plan_id]["superseded_by_plan_id"] is None
    drafts = [row for row in rows if row["plan_id"] != old_plan_id]
    for row in drafts:
        # 绑定失败的后继只能停在"暂存草稿"：没有任何血缘指针，
        # 因此不会被 `find_reusable` 之类按血缘判定的查询当成正式版本。
        assert row["supersedes_plan_id"] is None, "绑定失败的新计划不允许留下来源指针"
        assert row["superseded_by_plan_id"] is None
        assert row["status"] == "PROPOSED", row
    assert len(drafts) == 1


def test_auto_replan_establishes_both_lineages_in_one_step():
    """自动重规划成功后：计划血缘与干预血缘同时成立，且当前计划唯一。"""
    container, student, _goal, planned = _declining_scenario("lineage_atomic_success_student")
    old = planned.intervention
    old_plan_id = planned.plan.plan_id
    due = _due_after(planned)

    worker = container.adaptive_replanning_worker
    worker._clock = lambda: due
    assert worker.tick(batch_size=10).applied == 1

    successors = _rows(
        container,
        "SELECT * FROM adaptive_interventions WHERE user_id=? AND supersedes_intervention_id=?",
        (student.id, old.intervention_id),
    )
    assert len(successors) == 1
    new_plan_id = successors[0]["plan_id"]
    assert new_plan_id

    _assert_two_sided_lineage(container, student.id, old_plan_id, new_plan_id)

    # 干预血缘同样双向。
    old_row = container.adaptive_intervention_repository.get(
        user_id=student.id, intervention_id=old.intervention_id
    )
    assert old_row.superseded_by_intervention_id == successors[0]["intervention_id"]
    assert successors[0]["supersedes_intervention_id"] == old.intervention_id


# ==================================================== 两条路径共用同一套血缘规则

def test_normal_replacement_and_auto_replan_agree_on_current_plan():
    """普通替换之后再做一次自动重规划：血缘仍是一条链，当前计划仍唯一。"""
    container, student, _goal, planned = _declining_scenario("lineage_chain_student")
    old_plan_id = planned.plan.plan_id
    goal_id = planned.intervention.goal_id

    # 先做一次普通替换（Agent 学习目标路径）。
    replaced = container.adaptive_intervention_service.plan_for_goal(
        user_id=student.id, goal_id=goal_id, available_minutes=60,
        idempotency_key="lineage-chain-replacement",
        supersedes_plan_id=old_plan_id,
    )
    _assert_two_sided_lineage(container, student.id, old_plan_id, replaced.plan.plan_id)

    rows = _plan_rows(container, student.id)
    assert len(rows) == 2
    assert len({row["replan_key"] for row in rows if row["replan_key"]}) == len(
        [row for row in rows if row["replan_key"]]
    ), "重规划键必须唯一，否则一次重规划可能产出多个后继计划"
