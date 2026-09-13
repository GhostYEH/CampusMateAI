from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.exceptions import AppException
from app.core.security import hash_password
from app.main import create_app
from app.services.container import reset_container_for_tests

NOW = datetime.now(timezone.utc).replace(microsecond=0)


def _setup():
    container = reset_container_for_tests(Settings(
        app_env="test", database_url="sqlite:///:memory:", llm_provider="none",
        agent_artifact_path="./data/test-agent-artifacts",
    ))
    users = []
    for name in ("runtime_student", "runtime_other"):
        users.append(container.user_repository.create_user(
            username=name, password_hash=hash_password("Demo123456"), role="student", display_name=name,
        ))
    client = TestClient(create_app())
    headers = []
    for user in users:
        login = client.post("/api/v1/auth/login", json={"username": user.username, "password": "Demo123456"})
        headers.append({"Authorization": f"Bearer {login.json()['access_token']}"})
    exam = client.post("/api/v1/student/exams", headers=headers[0],
                       json={"course_name": "程序设计课程", "exam_date": "2026-12-20"})
    assert exam.status_code == 201
    campaign = client.post("/api/v1/final-review/campaigns", headers=headers[0],
                           json={"exam_id": exam.json()["id"], "daily_capacity_minutes": 90})
    assert campaign.status_code == 200
    return container, client, headers, users, campaign.json()["campaign_id"]


def _titles(client, headers):
    payload = client.get("/api/v1/tasks", headers=headers[0]).json()
    items = payload.get("items", payload)
    return [item["title"] for item in items]


def _versions(client, headers, campaign_id):
    return client.get(f"/api/v1/final-review/campaigns/{campaign_id}/plan-versions", headers=headers[0]).json()


def test_runtime_pauses_at_approval_before_any_task_is_written():
    container, client, headers, users, campaign_id = _setup()
    workflow = container.final_review_runtime_workflow

    view = workflow.start(user_id=users[0].id, campaign_id=campaign_id, idempotency_key="k1")

    assert view["run"].status == "AWAITING_APPROVAL"
    assert view["run"].phase == "WAITING_FOR_APPROVAL"
    assert view["approval"].status == "PENDING"
    assert view["campaign_id"] == campaign_id
    assert [step.status for step in view["steps"]] == [
        "DONE", "DONE", "DONE", "DONE", "PENDING", "PENDING", "PENDING",
    ]
    assert _titles(client, headers) == []
    assert _versions(client, headers, campaign_id)[0]["version"] == 1


def test_approval_activates_plan_and_materializes_today_tasks():
    container, client, headers, users, campaign_id = _setup()
    workflow = container.final_review_runtime_workflow
    view = workflow.start(user_id=users[0].id, campaign_id=campaign_id, idempotency_key="k1")

    result = workflow.decide(
        user_id=users[0].id, approval_id=view["approval"].id, decision="APPROVED", now=NOW,
    )

    assert result["run"].status == "SUCCEEDED"
    assert [step.status for step in result["steps"]] == ["DONE"] * 7
    assert sorted(_titles(client, headers)) == ["复习核心知识点", "完成诊断练习"]
    campaign = client.get(f"/api/v1/final-review/campaigns/{campaign_id}", headers=headers[0]).json()
    assert campaign["active_version"] == 1
    artifact = container.agent_artifact_repository.find(
        run_id=view["run"].id, artifact_type="FINAL_REVIEW_PLAN", version=1,
    )
    assert artifact is not None and artifact.content_hash


def test_rejected_approval_cancels_run_without_tasks():
    container, client, headers, users, campaign_id = _setup()
    workflow = container.final_review_runtime_workflow
    view = workflow.start(user_id=users[0].id, campaign_id=campaign_id, idempotency_key="k1")

    result = workflow.decide(
        user_id=users[0].id, approval_id=view["approval"].id, decision="REJECTED", now=NOW,
    )

    assert result["run"].status == "CANCELLED"
    assert "PENDING" not in [step.status for step in result["steps"]]
    assert _titles(client, headers) == []
    campaign = client.get(f"/api/v1/final-review/campaigns/{campaign_id}", headers=headers[0]).json()
    assert campaign["active_version"] is None


def test_repeated_start_approval_and_resume_never_duplicate_plan_or_tasks():
    container, client, headers, users, campaign_id = _setup()
    workflow = container.final_review_runtime_workflow
    first = workflow.start(user_id=users[0].id, campaign_id=campaign_id, idempotency_key="k1")
    repeated = workflow.start(user_id=users[0].id, campaign_id=campaign_id, idempotency_key="k1")

    assert repeated["run"].id == first["run"].id
    assert repeated["approval"].id == first["approval"].id

    workflow.decide(user_id=users[0].id, approval_id=first["approval"].id, decision="APPROVED", now=NOW)
    workflow.resume(user_id=users[0].id, run_id=first["run"].id)
    workflow.resume(user_id=users[0].id, run_id=first["run"].id)

    assert [version["version"] for version in _versions(client, headers, campaign_id)] == [1]
    assert sorted(_titles(client, headers)) == ["复习核心知识点", "完成诊断练习"]
    with pytest.raises(AppException) as exc:
        workflow.decide(user_id=users[0].id, approval_id=first["approval"].id, decision="APPROVED", now=NOW)
    assert exc.value.code == "AGENT_INVALID_STATE"


def test_landed_writes_without_bookkeeping_are_reconciled_instead_of_replayed():
    container, client, headers, users, campaign_id = _setup()
    workflow = container.final_review_runtime_workflow
    view = workflow.start(user_id=users[0].id, campaign_id=campaign_id, idempotency_key="k1")
    run_id = view["run"].id

    # 模拟：审批通过后进程在写入落库、步骤记账落库之前死亡。
    container.agent_runtime_repository.decide_approval(
        approval_id=view["approval"].id, user_id=users[0].id, status="APPROVED", decided_at=NOW.isoformat(),
    )
    container.final_review_service.activate_version(users[0].id, campaign_id, 1)
    container.final_review_service.materialize_today(users[0].id, campaign_id)
    assert len(_titles(client, headers)) == 2

    result = workflow.resume(user_id=users[0].id, run_id=run_id)

    assert result["run"].status == "SUCCEEDED"
    assert sorted(_titles(client, headers)) == ["复习核心知识点", "完成诊断练习"]
    assert [version["version"] for version in _versions(client, headers, campaign_id)] == [1]
    assert [step.status for step in result["steps"]] == ["DONE"] * 7


def test_activation_is_refused_when_plan_version_changed_after_approval():
    container, client, headers, users, campaign_id = _setup()
    workflow = container.final_review_runtime_workflow
    view = workflow.start(user_id=users[0].id, campaign_id=campaign_id, idempotency_key="k1")

    # 审批对应的版本被后续写入改写：此时无法再证明「批准的」与「要激活的」是同一份计划。
    container.final_review_repository.create_version(campaign_id, {"days": []}, "MANUAL_ADJUST")
    container.agent_runtime_repository.decide_approval(
        approval_id=view["approval"].id, user_id=users[0].id, status="APPROVED", decided_at=NOW.isoformat(),
    )

    result = workflow.resume(user_id=users[0].id, run_id=view["run"].id)

    assert result["run"].status == "FAILED"
    assert _titles(client, headers) == []
    campaign = client.get(f"/api/v1/final-review/campaigns/{campaign_id}", headers=headers[0]).json()
    assert campaign["active_version"] is None


def test_can_resume_and_startup_classification_require_provable_campaign():
    container, client, headers, users, campaign_id = _setup()
    workflow = container.final_review_runtime_workflow
    repository = container.agent_runtime_repository
    run_manager = container.agent_run_manager

    view = workflow.start(user_id=users[0].id, campaign_id=campaign_id, idempotency_key="k1")
    assert workflow.can_resume(repository.get_run(run_id=view["run"].id)) is True

    orphan_job = repository.create_job(user_id=users[0].id, domain="final_review", objective_summary="孤儿运行")
    orphan = repository.create_run(job_id=orphan_job.id, user_id=users[0].id, domain="final_review", total_steps=7)
    foreign_job = repository.create_job(user_id=users[1].id, domain="course_research", objective_summary="其它域")
    foreign = repository.create_run(job_id=foreign_job.id, user_id=users[1].id, domain="course_research", total_steps=1)
    assert workflow.can_resume(orphan) is False
    assert workflow.can_resume(foreign) is False

    classification = run_manager.classify_incomplete_runs(workflow.can_resume)

    assert [run.id for run in classification["pending"]] == [view["run"].id]
    assert sorted(run.id for run in classification["failed"]) == sorted([orphan.id, foreign.id])
    # 待接管的运行在真正被调度前保持原状态，不伪造「恢复中」。
    assert repository.get_run(run_id=view["run"].id).status == "AWAITING_APPROVAL"
    assert repository.get_run(run_id=orphan.id).status == "FAILED"
    assert repository.get_run(run_id=foreign.id).status == "FAILED"


def test_resume_is_owner_scoped_and_marks_recovery_only_when_dispatched():
    container, client, headers, users, campaign_id = _setup()
    workflow = container.final_review_runtime_workflow
    repository = container.agent_runtime_repository
    view = workflow.start(user_id=users[0].id, campaign_id=campaign_id, idempotency_key="k1")

    with pytest.raises(AppException) as exc:
        workflow.resume(user_id=users[1].id, run_id=view["run"].id)
    assert exc.value.code == "AGENT_RUN_NOT_FOUND"

    resumable = repository.get_run(run_id=view["run"].id)
    repository.update_run(run_id=resumable.id, status="RUNNING", phase="VALIDATING_OUTPUT")
    workflow.resume(user_id=users[0].id, run_id=resumable.id)

    event_types = [event.type for event in repository.list_events(run_id=resumable.id)]
    assert "RUN_RECOVERY_STARTED" in event_types
    assert repository.get_run(run_id=resumable.id).status == "AWAITING_APPROVAL"
