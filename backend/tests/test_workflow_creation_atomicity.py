import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.api.deps import student_only
from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests


@pytest.fixture
def context():
    container = reset_container_for_tests(Settings(
        _env_file=None, app_env="test", auto_seed_demo_users=False,
        auto_import_demo=False, llm_provider="none", agent_runtime_mode="disabled",
    ))
    user = container.user_repository.create_user(username="atomic_workflow", password_hash="test", role="student")
    app = create_app()
    app.dependency_overrides[student_only] = lambda: user
    yield container, user, TestClient(app)


@pytest.mark.parametrize("workflow", ["research", "notice", "review"])
def test_initial_event_failure_rolls_back_job_run_and_idempotency_claim(context, monkeypatch, workflow):
    container, user, client = context
    if workflow == "research":
        path, body = "/api/v1/course-research/runs", {"question": "解释事务隔离级别"}
    elif workflow == "notice":
        notice = container.notice_repository.create_or_update_notice(user.id, "manual", "notice", "通知", "请提交申请表")
        path, body = f"/api/v1/notices/{notice.id}/workflow", {}
    else:
        campaign = container.final_review_repository.create_campaign(
            user_id=user.id, exam_ids=[], daily_capacity_minutes=120,
            preferred_periods=[], rest_days=[], intensity="medium",
        )
        path, body = f"/api/v1/final-review/campaigns/{campaign.campaign_id}/plans/generate", {}

    def fail_event(*args, **kwargs):
        raise sqlite3.OperationalError("injected event failure")

    monkeypatch.setattr(container.agent_runtime_repository, "_insert_event", fail_event)
    response = client.post(path, json=body, headers={"Idempotency-Key": "atomic-workflow"})
    assert response.status_code == 500
    with container.db.query() as conn:
        for table in ("agent_jobs", "agent_runs", "agent_events", "agent_idempotency_claims"):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_notice_key_cannot_be_reused_for_another_notice(context):
    container, user, client = context
    notices = [container.notice_repository.create_or_update_notice(
        user.id, "manual", str(index), "通知", f"请提交申请表 {index}",
    ) for index in range(2)]
    headers = {"Idempotency-Key": "notice-key"}
    first = client.post(f"/api/v1/notices/{notices[0].id}/workflow", json={}, headers=headers)
    assert first.status_code == 200, first.text
    replay = client.post(f"/api/v1/notices/{notices[0].id}/workflow", json={}, headers=headers)
    assert replay.status_code == 200
    assert replay.json()["workflow_id"] == first.json()["workflow_id"]
    conflict = client.post(f"/api/v1/notices/{notices[1].id}/workflow", json={}, headers=headers)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "AGENT_IDEMPOTENCY_CONFLICT"


def test_research_key_cannot_hide_changed_question(context, monkeypatch):
    container, user, client = context

    async def no_external_pipeline(**kwargs):
        return None

    monkeypatch.setattr(container.course_research_pipeline, "execute", no_external_pipeline)
    body = {"question": "解释事务隔离级别"}
    headers = {"Idempotency-Key": "research-key"}
    first = client.post("/api/v1/course-research/runs", json=body, headers=headers)
    assert first.status_code == 200, first.text
    replay = client.post("/api/v1/course-research/runs", json=body, headers=headers)
    assert replay.status_code == 200
    assert replay.json()["run_id"] == first.json()["run_id"]
    conflict = client.post("/api/v1/course-research/runs", json={"question": "解释锁"}, headers=headers)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "AGENT_IDEMPOTENCY_CONFLICT"
