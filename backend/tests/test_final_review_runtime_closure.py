"""Regression coverage for the governed final-review runtime closure."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.database.sqlite_db import reset_db_for_tests
from app.main import create_app
from app.repositories.agent_runtime_repository import AgentRuntimeRepository
from app.repositories.final_review_repository import FinalReviewRepository
from app.services.agent_runtime.event_store import AgentEventStore
from app.services.agent_runtime.run_manager import RunManager
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


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


def _active_campaign(client, headers):
    exam = client.post(
        "/api/v1/student/exams",
        json={"course_name": "高等数学", "exam_date": "2026-12-30"},
        headers=headers,
    )
    assert exam.status_code == 201, exam.text
    campaign = client.post(
        "/api/v1/final-review/campaigns",
        json={"exam_ids": [exam.json()["id"]], "daily_capacity_minutes": 120},
        headers=headers,
    )
    assert campaign.status_code == 200, campaign.text
    campaign_id = campaign.json()["campaign_id"]
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
        json={"version": 1}, headers=headers,
    )
    assert activated.status_code == 200, activated.text
    return campaign_id


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
    _, client = _setup()
    headers = _login(client)
    campaign_id = _active_campaign(client, headers)
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
    campaign_id = _active_campaign(client, headers)
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
