"""Regression coverage for the governed final-review runtime closure.

覆盖:审批后的高风险写操作必须经 `ToolInvocationGateway` 执行、
拒绝与过期一律不执行、以及"批准后进程重启"可从 checkpoint 恢复且只生效一次。
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.exceptions import AgentToolRejected
from app.database.sqlite_db import reset_db_for_tests
from app.main import create_app
from app.repositories.agent_runtime_repository import AgentRuntimeRepository
from app.repositories.final_review_repository import FinalReviewRepository
from app.services.agent_runtime.event_store import AgentEventStore
from app.services.agent_runtime.handlers.final_review import PLAN_ACTIVATE_TOOL
from app.services.agent_runtime.run_manager import RunManager
from app.services.agent_runtime.tool_gateway import (
    ToolInvocationGateway,
    ToolInvocationRequest,
)
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data

from final_review_helpers import drain_worker

ADJUST_APPLY_TOOL = "final_review.adjust.apply"


def _setup():
    container = reset_container_for_tests(
        Settings(
            app_env="test",
            database_url="sqlite:///:memory:",
            auto_seed_demo_users=True,
            auto_import_demo=False,
            llm_provider="none",
            agent_allow_mock_providers=True,
        )
    )
    seed_demo_data(container, force=True)
    container.agent_provider_registry.add_fake("fake")
    return container, TestClient(create_app())


def _login(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "student_demo", "password": "Demo123456"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_exam(client, headers, course_name="高等数学"):
    exam = client.post(
        "/api/v1/student/exams",
        json={"course_name": course_name, "exam_date": "2026-12-30"},
        headers=headers,
    )
    assert exam.status_code == 201, exam.text
    return exam.json()["id"]


def _create_campaign(client, headers, exam_ids):
    campaign = client.post(
        "/api/v1/final-review/campaigns",
        json={"exam_ids": exam_ids, "daily_capacity_minutes": 120},
        headers=headers,
    )
    assert campaign.status_code == 200, campaign.text
    return campaign.json()["campaign_id"]


def _approve_plan_and_activate(container, client, headers, campaign_id, version=1):
    """生成计划 → 审批 → 激活命令 → 由 Worker 完成激活。"""
    plan = client.post(
        f"/api/v1/final-review/campaigns/{campaign_id}/plans/generate",
        json={}, headers=headers,
    )
    assert plan.status_code == 200, plan.text
    approved = client.post(
        f"/api/v1/agent-approvals/{plan.json()['approval_id']}/decision",
        json={"decision": "APPROVED"}, headers=headers,
    )
    assert approved.status_code == 200, approved.text
    activated = client.post(
        f"/api/v1/final-review/campaigns/{campaign_id}/activate",
        json={"version": version}, headers=headers,
    )
    assert activated.status_code == 200, activated.text
    drain_worker(container)
    return plan.json()


def _active_campaign(container, client, headers):
    campaign_id = _create_campaign(client, headers, [_create_exam(client, headers)])
    _approve_plan_and_activate(container, client, headers, campaign_id)
    return campaign_id


def _analyze(container, client, headers, campaign_id):
    """产生一条调整建议(不产生写副作用),返回 proposal。"""
    client.get(
        f"/api/v1/final-review/campaigns/{campaign_id}/agendas/today", headers=headers
    )
    response = client.post(
        f"/api/v1/final-review/campaigns/{campaign_id}/adjustments/analyze",
        json={}, headers=headers,
    )
    assert response.status_code == 200, response.text
    proposals = client.get(
        f"/api/v1/final-review/campaigns/{campaign_id}/adjustment-proposals",
        headers=headers,
    ).json()
    return next(p for p in proposals if p["proposal_id"] == response.json()["proposal_id"])


def _version_numbers(client, headers, campaign_id):
    return sorted(
        v["version"]
        for v in client.get(
            f"/api/v1/final-review/campaigns/{campaign_id}/plan-versions", headers=headers
        ).json()
    )


def _tool_call_count(container, run_id, tool_name):
    calls = container.agent_runtime_repository.list_tool_calls_by_run(run_id)
    return len([c for c in calls if c["tool_name"] == tool_name])


def _expire_approval(container, approval_id):
    conn = container.db._connect()
    try:
        past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        conn.execute(
            "UPDATE agent_approvals SET expires_at = ? WHERE approval_id = ?",
            (past, approval_id),
        )
        conn.commit()
    finally:
        container.db._release(conn)


def _force_requeue(container, run_id, *, clear_checkpoint=False):
    """模拟"批准后进程重启":把已完成的 Run 放回队列,可选清掉 checkpoint。"""
    conn = container.db._connect()
    try:
        conn.execute(
            "UPDATE agent_runs SET status = 'QUEUED', phase = 'IDLE', lease_owner = NULL, "
            "lease_expires_at = NULL, next_attempt_at = NULL"
            + (", checkpoint_json = NULL" if clear_checkpoint else "")
            + " WHERE run_id = ?",
            (run_id,),
        )
        conn.commit()
    finally:
        container.db._release(conn)


def test_legacy_recovery_hook_leaves_interrupted_runs_for_worker():
    db = reset_db_for_tests()
    conn = db._connect()
    try:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
            "VALUES ('u1', 'u1', 'x', 'student', 't', 't')"
        )
        conn.commit()
    finally:
        db._release(conn)
    repo = AgentRuntimeRepository(db)
    manager = RunManager(repo, AgentEventStore(repo))
    job_id = repo.create_job(user_id="u1", job_kind="final_review")
    run_id = repo.create_run(job_id=job_id, user_id="u1")
    manager.transition(run_id, "RUNNING", phase="WAITING_FOR_MODEL")

    recovered = manager.recover_incomplete_runs()

    assert recovered == []
    assert repo.get_run(run_id)["status"] == "RUNNING"


def test_rejecting_a_plan_ends_its_waiting_run():
    _, client = _setup()
    headers = _login(client)
    exam = client.post(
        "/api/v1/student/exams",
        json={"course_name": "线性代数", "exam_date": "2026-12-30"},
        headers=headers,
    ).json()
    campaign = client.post(
        "/api/v1/final-review/campaigns",
        json={"exam_ids": [exam["id"]], "daily_capacity_minutes": 120}, headers=headers,
    ).json()
    plan = client.post(
        f"/api/v1/final-review/campaigns/{campaign['campaign_id']}/plans/generate",
        json={}, headers=headers,
    ).json()

    rejected = client.post(
        f"/api/v1/agent-approvals/{plan['approval_id']}/decision",
        json={"decision": "REJECTED"}, headers=headers,
    )
    assert rejected.status_code == 200, rejected.text
    run = client.get(f"/api/v1/agent-runs/{plan['run_id']}", headers=headers)
    assert run.status_code == 200, run.text
    assert run.json()["status"] == "CANCELLED"


def test_adjustment_analysis_reuses_its_idempotency_result():
    container, client = _setup()
    headers = _login(client)
    campaign_id = _active_campaign(container, client, headers)
    client.get(f"/api/v1/final-review/campaigns/{campaign_id}/agendas/today", headers=headers)
    headers = {**headers, "Idempotency-Key": "adjustment-retry-1"}

    first = client.post(
        f"/api/v1/final-review/campaigns/{campaign_id}/adjustments/analyze",
        json={}, headers=headers,
    )
    second = client.post(
        f"/api/v1/final-review/campaigns/{campaign_id}/adjustments/analyze",
        json={}, headers=headers,
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["run_id"] == first.json()["run_id"]
    assert second.json()["proposal_id"] == first.json()["proposal_id"]


def test_daily_checkin_persists_feedback_for_later_adjustment():
    container, client = _setup()
    headers = _login(client)
    campaign_id = _active_campaign(container, client, headers)
    report_date = datetime.now(timezone.utc).date().isoformat()

    response = client.post(
        f"/api/v1/final-review/campaigns/{campaign_id}/daily-checkins",
        json={
            "report_date": report_date,
            "completed_item_ids": [],
            "insufficient_time": True,
            "difficulty_notes": "本周实验太多，无法按计划完成。",
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text

    student = container.user_repository.get_user_by_username("student_demo")
    evidence = FinalReviewRepository(container.db).list_checkin_evidence(
        campaign_id, user_id=student.id
    )
    assert evidence[0]["insufficient_time"] is True
    assert evidence[0]["difficulty_notes"] == "本周实验太多，无法按计划完成。"


# ===== Task 7:审批后的写操作经 Gateway 执行 =====


def test_generating_a_proposal_has_no_write_side_effects():
    """生成建议只落 proposal:不建版本、不改 active plan、不开写命令。"""
    container, client = _setup()
    headers = _login(client)
    campaign_id = _active_campaign(container, client, headers)
    before_versions = _version_numbers(client, headers, campaign_id)

    proposal = _analyze(container, client, headers, campaign_id)

    assert proposal["status"] == "pending"
    assert _version_numbers(client, headers, campaign_id) == before_versions
    campaign = client.get(
        f"/api/v1/final-review/campaigns/{campaign_id}", headers=headers
    ).json()
    assert campaign["active_version"] == 1

    # 分析阶段不得产生任何调整写命令。
    assert container.agent_runtime_repository.find_job_by_idempotency(
        container.user_repository.get_user_by_username("student_demo").id,
        f"final_review_adjust_apply:{proposal['proposal_id']}",
    ) is None


def test_approved_adjustment_is_applied_by_worker_through_gateway():
    """批准只创建命令;新版本由 Worker 经 Gateway 创建并激活。"""
    container, client = _setup()
    headers = _login(client)
    campaign_id = _active_campaign(container, client, headers)
    proposal = _analyze(container, client, headers, campaign_id)

    decision = client.post(
        f"/api/v1/final-review/adjustment-proposals/{proposal['proposal_id']}/decision",
        json={"decision": "APPROVED"}, headers=headers,
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["pending"] is True
    run_id = decision.json()["run_id"]

    # 命令已受理但 Worker 还没跑:计划未被改动。
    assert _version_numbers(client, headers, campaign_id) == [1]

    drain_worker(container)

    assert _version_numbers(client, headers, campaign_id) == [1, 2]
    campaign = client.get(
        f"/api/v1/final-review/campaigns/{campaign_id}", headers=headers
    ).json()
    assert campaign["active_version"] == 2
    run = client.get(f"/api/v1/agent-runs/{run_id}", headers=headers).json()
    assert run["status"] == "SUCCEEDED"

    # 副作用确实经 Gateway 的工具调用落库,并且只调用了一次。
    calls = container.agent_runtime_repository.list_tool_calls_by_run(run_id)
    assert [c["tool_name"] for c in calls] == [ADJUST_APPLY_TOOL]
    assert calls[0]["status"] == "completed"


def test_rejected_and_expired_decisions_never_execute():
    """拒绝与过期都不执行:计划不变,也不产生任何写命令。"""
    container, client = _setup()
    headers = _login(client)
    campaign_id = _active_campaign(container, client, headers)
    student_id = container.user_repository.get_user_by_username("student_demo").id

    rejected_proposal = _analyze(container, client, headers, campaign_id)
    rejected = client.post(
        f"/api/v1/final-review/adjustment-proposals/{rejected_proposal['proposal_id']}/decision",
        json={"decision": "REJECTED"}, headers=headers,
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert _version_numbers(client, headers, campaign_id) == [1]
    assert container.agent_runtime_repository.find_job_by_idempotency(
        student_id, f"final_review_adjust_apply:{rejected_proposal['proposal_id']}"
    ) is None

    expired_proposal = _analyze(container, client, headers, campaign_id)
    _expire_approval(container, expired_proposal["approval_id"])
    expired = client.post(
        f"/api/v1/final-review/adjustment-proposals/{expired_proposal['proposal_id']}/decision",
        json={"decision": "APPROVED"}, headers=headers,
    )
    assert expired.status_code == 410, expired.text
    assert _version_numbers(client, headers, campaign_id) == [1]
    assert container.agent_runtime_repository.find_job_by_idempotency(
        student_id, f"final_review_adjust_apply:{expired_proposal['proposal_id']}"
    ) is None


def test_gateway_refuses_execution_when_approval_is_rejected_or_expired():
    """Gateway 自身也必须拒绝:过期绝不等于批准。"""
    container, client = _setup()
    headers = _login(client)
    campaign_id = _active_campaign(container, client, headers)
    proposal = _analyze(container, client, headers, campaign_id)

    repo = container.agent_runtime_repository
    handler = container.agent_handler_registry.require("final_review_adjust_apply")
    created = repo.create_job_with_run_and_event(
        user_id=container.user_repository.get_user_by_username("student_demo").id,
        job_kind=handler.job_kind,
        input_ref={"proposal_id": proposal["proposal_id"], "approved": True},
        handler_code=handler.code,
        handler_version=handler.version,
    )
    run_id = created["run_id"]
    repo.claim_next_run(
        owner="test-worker",
        now=datetime.now(timezone.utc).isoformat(),
        lease_expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
    )

    arguments = {
        "proposal_id": proposal["proposal_id"],
        "approved": True,
        "user_id": repo.get_run(run_id)["user_id"],
    }
    gateway = container.agent_tool_gateway

    async def _invoke(approval_id):
        return await gateway.invoke(
            ToolInvocationRequest(
                run_id=run_id,
                role_code="analyzer",
                tool_name=ADJUST_APPLY_TOOL,
                arguments=arguments,
                idempotency_key=f"run:{run_id}",
                approval_id=approval_id,
            )
        )

    container.agent_approval_gate.resolve(
        proposal["approval_id"], decision="REJECTED", user_id=arguments["user_id"]
    )
    with pytest.raises(AgentToolRejected):
        asyncio.run(_invoke(proposal["approval_id"]))
    assert _version_numbers(client, headers, campaign_id) == [1]

    _expire_approval(container, proposal["approval_id"])
    with pytest.raises(AgentToolRejected):
        asyncio.run(_invoke(proposal["approval_id"]))
    assert _version_numbers(client, headers, campaign_id) == [1]


def test_approved_activation_resumes_from_checkpoint_and_applies_once():
    """批准后进程重启:可从 checkpoint 恢复,且激活只发生一次。"""
    container, client = _setup()
    headers = _login(client)
    campaign_id = _create_campaign(client, headers, [_create_exam(client, headers)])
    plan = _approve_plan_and_activate(container, client, headers, campaign_id)

    activate_run = container.agent_runtime_repository.find_job_by_idempotency(
        container.user_repository.get_user_by_username("student_demo").id,
        f"final_review_plan_activate:{campaign_id}:1",
    )
    run_id = container.agent_runtime_repository.get_run_by_job(activate_run["job_id"])["run_id"]
    assert _tool_call_count(container, run_id, PLAN_ACTIVATE_TOOL) == 1

    # 第一次"重启":checkpoint 仍在 → Handler 直接返回既有结果。
    _force_requeue(container, run_id)
    drain_worker(container)
    assert _tool_call_count(container, run_id, PLAN_ACTIVATE_TOOL) == 1

    # 第二次"重启":checkpoint 丢失 → 仍由 Gateway 幂等声明兜底,不重复执行。
    _force_requeue(container, run_id, clear_checkpoint=True)
    drain_worker(container)
    assert _tool_call_count(container, run_id, PLAN_ACTIVATE_TOOL) == 1

    run = client.get(f"/api/v1/agent-runs/{run_id}", headers=headers).json()
    assert run["status"] == "SUCCEEDED"
    campaign = client.get(
        f"/api/v1/final-review/campaigns/{campaign_id}", headers=headers
    ).json()
    assert campaign["active_version"] == 1
    assert _version_numbers(client, headers, campaign_id) == [1]
    assert plan["version"] == 1


def test_restarted_approval_apply_does_not_create_a_second_version():
    """调整写操作在进程重启后同样只生效一次。"""
    container, client = _setup()
    headers = _login(client)
    campaign_id = _active_campaign(container, client, headers)
    proposal = _analyze(container, client, headers, campaign_id)
    decision = client.post(
        f"/api/v1/final-review/adjustment-proposals/{proposal['proposal_id']}/decision",
        json={"decision": "APPROVED"}, headers=headers,
    ).json()
    drain_worker(container)
    assert _version_numbers(client, headers, campaign_id) == [1, 2]

    run_id = decision["run_id"]
    _force_requeue(container, run_id)
    drain_worker(container)
    _force_requeue(container, run_id, clear_checkpoint=True)
    drain_worker(container)

    assert _version_numbers(client, headers, campaign_id) == [1, 2]
    assert _tool_call_count(container, run_id, ADJUST_APPLY_TOOL) == 1
    assert json.loads(
        container.agent_runtime_repository.get_run(run_id)["checkpoint_json"] or "{}"
    ).get("stage") == "APPLIED"
