"""状态驱动干预在 Agent Runtime 里的编排。

覆盖：同 Run 重放不产生第二条干预/计划、checkpoint 恢复不重复副作用、
阶段事件可观测且不含敏感内容、失败时状态收口明确，以及端到端 Job 链路。
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.exceptions import AgentRuntimeError
from app.core.security import hash_password
from app.main import create_app
from app.services.agent_runtime.handlers.base import HandlerContext
from app.services.container import reset_container_for_tests

STAGE_EVENT_TYPES = ("STATE_ANALYZED", "STRATEGY_SELECTED", "INTERVENTION_RECORDED", "PLAN_GENERATED")


def _setup(*, with_task: bool = True):
    container = reset_container_for_tests(Settings(app_env="test", database_url="sqlite:///:memory:"))
    student = container.user_repository.create_user(
        username="adaptive_job_student", password_hash=hash_password("Demo123456"), role="student"
    )
    goal = container.student_goal_repository.create_goal(
        user_id=student.id, name="完成高等数学期末复习", category="ACADEMIC",
        target_date=(datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat(),
        idempotency_key="adaptive-goal-1",
    )[0]
    if with_task:
        container.personal_task_repository.create_task(
            user_id=student.id, title="复习极限与连续",
            deadline=(datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(),
        )
    return container, student, goal


def _context(container, student, goal, *, run_id: str, job_id: str, checkpoint=None) -> HandlerContext:
    return HandlerContext(
        run_id=run_id, job_id=job_id, user_id=student.id, job_kind="learning_goal",
        input_ref={"goal_id": goal.goal_id, "available_minutes": 60},
        checkpoint=checkpoint, attempt_no=1,
    )


def _handler(container):
    handler = container.agent_handler_registry.get("learning_goal")
    assert handler is not None
    return handler


def _run_and_job(container, student, goal):
    repository = container.agent_runtime_repository
    job_id = repository.create_job(
        user_id=student.id, job_kind="learning_goal",
        input_ref={"goal_id": goal.goal_id, "available_minutes": 60},
        idempotency_key="adaptive-job-1",
    )
    run_id = repository.create_run(
        job_id=job_id, user_id=student.id, idempotency_key="adaptive-run-1",
        handler_code="learning_goal", handler_version="1.1.0",
    )
    return job_id, run_id


def test_same_run_replay_reuses_intervention_and_plan() -> None:
    container, student, goal = _setup()
    job_id, run_id = _run_and_job(container, student, goal)
    handler = _handler(container)
    context = _context(container, student, goal, run_id=run_id, job_id=job_id)

    first = asyncio.run(handler.execute(context))
    second = asyncio.run(handler.execute(context))

    assert first.job_output_patch["plan_id"] == second.job_output_patch["plan_id"]
    assert first.job_output_patch["intervention_id"] == second.job_output_patch["intervention_id"]
    assert container.adaptive_intervention_repository.count_for_user(user_id=student.id) == 1
    _plans, total = container.learning_plan_repository.list_plans(
        user_id=student.id, page=1, page_size=20
    )
    assert total == 1


def test_checkpoint_resume_does_not_repeat_side_effects() -> None:
    container, student, goal = _setup()
    job_id, run_id = _run_and_job(container, student, goal)
    handler = _handler(container)
    context = _context(container, student, goal, run_id=run_id, job_id=job_id)

    first = asyncio.run(handler.execute(context))
    assert first.checkpoint and first.checkpoint["stage"] == "PLAN_GENERATED"
    resumed = asyncio.run(handler.execute(replace(context, checkpoint=first.checkpoint)))

    assert resumed.status == "SUCCEEDED"
    assert resumed.job_output_patch == {
        "plan_id": first.job_output_patch["plan_id"],
        "intervention_id": first.job_output_patch["intervention_id"],
    }
    assert container.adaptive_intervention_repository.count_for_user(user_id=student.id) == 1
    _plans, total = container.learning_plan_repository.list_plans(
        user_id=student.id, page=1, page_size=20
    )
    assert total == 1


def test_stage_events_are_emitted_and_carry_no_sensitive_content() -> None:
    container, student, goal = _setup()
    job_id, run_id = _run_and_job(container, student, goal)
    handler = _handler(container)
    asyncio.run(handler.execute(_context(container, student, goal, run_id=run_id, job_id=job_id)))

    events = container.agent_event_store.list_events(run_id)
    types = [event["type"] for event in events]
    for stage in STAGE_EVENT_TYPES:
        assert stage in types, types
    # 事件顺序必须与真实执行顺序一致，否则前端进度会跳步。
    assert types.index("STATE_ANALYZED") < types.index("STRATEGY_SELECTED")
    assert types.index("STRATEGY_SELECTED") < types.index("INTERVENTION_RECORDED")
    assert types.index("INTERVENTION_RECORDED") < types.index("PLAN_GENERATED")

    serialized = str([event.get("summary") for event in events])
    for forbidden in (student.id, goal.name, "复习极限与连续", "assessment_json", "strategy_json"):
        assert forbidden not in serialized


def test_intervention_records_agent_job_and_run_references() -> None:
    container, student, goal = _setup()
    job_id, run_id = _run_and_job(container, student, goal)
    handler = _handler(container)
    result = asyncio.run(
        handler.execute(_context(container, student, goal, run_id=run_id, job_id=job_id))
    )
    row = container.adaptive_intervention_repository.get(
        user_id=student.id, intervention_id=result.job_output_patch["intervention_id"]
    )
    assert row is not None
    assert row.agent_job_id == job_id and row.agent_run_id == run_id
    assert row.plan_id == result.job_output_patch["plan_id"]
    assert row.status == "PLAN_GENERATED"


def test_plan_generation_failure_cancels_intervention_and_raises(monkeypatch) -> None:
    """计划生成失败时：干预记录收口为 CANCELLED，异常上抛由 Worker 落 FAILED。"""
    container, student, goal = _setup()
    job_id, run_id = _run_and_job(container, student, goal)
    handler = _handler(container)

    def _boom(**_kwargs):
        raise RuntimeError("planner unavailable")

    monkeypatch.setattr(container.learning_planner_service, "generate", _boom)

    with pytest.raises(AgentRuntimeError) as exc:
        asyncio.run(handler.execute(_context(container, student, goal, run_id=run_id, job_id=job_id)))
    assert exc.value.code == "AGENT_INVALID_STATE"

    rows, total = container.adaptive_intervention_repository.list_interventions(
        user_id=student.id, page=1, page_size=10
    )
    assert total == 1
    assert rows[0].status == "CANCELLED"
    assert rows[0].plan_id is None
    _plans, plan_total = container.learning_plan_repository.list_plans(
        user_id=student.id, page=1, page_size=20
    )
    assert plan_total == 0  # 不留"无归属"的计划


def test_learning_goal_job_end_to_end_exposes_intervention() -> None:
    container, student, goal = _setup()
    client = TestClient(create_app())
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "adaptive_job_student", "password": "Demo123456"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.post(
        "/api/v1/agent-jobs",
        json={"job_kind": "learning_goal", "input_ref": {"goal_id": goal.goal_id, "available_minutes": 60}},
        headers=headers,
    )
    assert response.status_code == 202, response.text
    job = response.json()
    asyncio.run(container.agent_worker.run_once())

    job = client.get(f"/api/v1/agent-jobs/{job['job_id']}", headers=headers).json()
    assert job["status"] == "SUCCEEDED"
    assert job["input_ref"]["plan_id"]
    assert job["input_ref"]["intervention_id"]

    listed = client.get("/api/v1/adaptive-interventions", headers=headers)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["intervention_id"] == job["input_ref"]["intervention_id"]
    assert item["plan_id"] == job["input_ref"]["plan_id"]
    assert item["status"] == "PLAN_GENERATED"
    assert item["strategy_code"]
    assert item["rationale_codes"]

    events = client.get(f"/api/v1/agent-runs/{job['latest_run_id']}/events", headers=headers).json()
    types = [event["type"] for event in events]
    assert "RUN_COMPLETED" in types
    for stage in STAGE_EVENT_TYPES:
        assert stage in types, types
