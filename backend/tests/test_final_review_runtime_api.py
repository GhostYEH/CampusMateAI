from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.database import sqlite_db
from app.main import create_app
from app.services.container import build_container, reset_container_for_tests


def _settings(**overrides) -> Settings:
    base = dict(
        app_env="test", llm_provider="none", database_url="sqlite:///:memory:",
        agent_artifact_path="./data/test-agent-artifacts",
    )
    base.update(overrides)
    return Settings(**base)


def _bootstrap(container, names=("api_runtime_student", "api_runtime_other")):
    users = []
    for name in names:
        users.append(container.user_repository.create_user(
            username=name, password_hash=hash_password("Demo123456"), role="student", display_name=name,
        ))
    client = TestClient(create_app())
    headers = []
    for user in users:
        login = client.post("/api/v1/auth/login", json={"username": user.username, "password": "Demo123456"})
        headers.append({"Authorization": f"Bearer {login.json()['access_token']}"})
    exam = client.post("/api/v1/student/exams", headers=headers[0],
                       json={"course_name": "数据结构课程", "exam_date": "2026-12-20"})
    assert exam.status_code == 201
    campaign = client.post("/api/v1/final-review/campaigns", headers=headers[0],
                           json={"exam_id": exam.json()["id"], "daily_capacity_minutes": 90})
    assert campaign.status_code == 200
    return users, client, headers, campaign.json()["campaign_id"]


def _auth(client, username):
    login = client.post("/api/v1/auth/login", json={"username": username, "password": "Demo123456"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _titles(client, headers):
    payload = client.get("/api/v1/tasks", headers=headers).json()
    return sorted(item["title"] for item in payload.get("items", payload))


def test_generate_with_idempotency_key_exposes_run_and_requires_approval():
    container = reset_container_for_tests(_settings())
    _users, client, headers, campaign_id = _bootstrap(container)

    generated = client.post(f"/api/v1/final-review/campaigns/{campaign_id}/plans/generate",
                            headers={**headers[0], "Idempotency-Key": "gen-1"})
    assert generated.status_code == 200
    body = generated.json()
    assert body["version"] == 1
    assert body["job_id"] and body["run_id"] and body["approval_id"]

    assert _titles(client, headers[0]) == []
    blocked = client.post(f"/api/v1/final-review/campaigns/{campaign_id}/activate", headers=headers[0])
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "AGENT_APPROVAL_REQUIRED"

    repeated = client.post(f"/api/v1/final-review/campaigns/{campaign_id}/plans/generate",
                           headers={**headers[0], "Idempotency-Key": "gen-1"}).json()
    assert repeated["run_id"] == body["run_id"]

    steps = client.get(f"/api/v1/agent-runs/{body['run_id']}/steps", headers=headers[0]).json()
    assert [item["status"] for item in steps["items"]] == [
        "DONE", "DONE", "DONE", "DONE", "PENDING", "PENDING", "PENDING",
    ]
    run = client.get(f"/api/v1/final-review/campaigns/{campaign_id}/run", headers=headers[0]).json()
    assert run["status"] == "AWAITING_APPROVAL"
    assert run["approval_id"] == body["approval_id"]
    assert run["approval_status"] == "PENDING"
    listed = client.get("/api/v1/final-review/campaigns", headers=headers[0]).json()
    assert listed[0]["run_id"] == body["run_id"]
    assert listed[0]["pending_approval_id"] == body["approval_id"]


def test_approval_decision_resumes_run_and_materializes_today_tasks():
    container = reset_container_for_tests(_settings())
    _users, client, headers, campaign_id = _bootstrap(container)
    generated = client.post(f"/api/v1/final-review/campaigns/{campaign_id}/plans/generate",
                            headers={**headers[0], "Idempotency-Key": "gen-1"}).json()

    decided = client.post(f"/api/v1/agent-approvals/{generated['approval_id']}/decision",
                          headers=headers[0], json={"decision": "APPROVED"})
    assert decided.status_code == 200
    assert decided.json()["status"] == "APPROVED"

    run = client.get(f"/api/v1/final-review/campaigns/{campaign_id}/run", headers=headers[0]).json()
    assert run["status"] == "SUCCEEDED"
    assert run["progress_current"] == 7
    assert [item["status"] for item in run["steps"]] == ["DONE"] * 7
    assert _titles(client, headers[0]) == ["复习核心知识点", "完成诊断练习"]
    types = [event["type"] for event in
             client.get(f"/api/v1/agent-runs/{run['run_id']}/events", headers=headers[0]).json()["items"]]
    assert "APPROVAL_REQUIRED" in types and "RUN_SUCCEEDED" in types


def test_foreign_user_cannot_read_or_approve_another_users_run():
    container = reset_container_for_tests(_settings())
    _users, client, headers, campaign_id = _bootstrap(container)
    generated = client.post(f"/api/v1/final-review/campaigns/{campaign_id}/plans/generate",
                            headers={**headers[0], "Idempotency-Key": "gen-1"}).json()

    assert client.get(f"/api/v1/agent-runs/{generated['run_id']}/steps", headers=headers[1]).status_code == 404
    assert client.post(f"/api/v1/agent-runs/{generated['run_id']}/resume", headers=headers[1]).status_code == 404
    assert client.post(f"/api/v1/agent-approvals/{generated['approval_id']}/decision",
                       headers=headers[1], json={"decision": "APPROVED"}).status_code == 404
    assert client.get(f"/api/v1/final-review/campaigns/{campaign_id}/run", headers=headers[1]).status_code == 404
    assert _titles(client, headers[1]) == []

    resumed = client.post(f"/api/v1/agent-runs/{generated['run_id']}/resume", headers=headers[0])
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "AWAITING_APPROVAL"


def test_restart_resumes_from_last_completed_step(tmp_path):
    db_path = tmp_path / "runtime-restart.db"
    settings = _settings(database_url=f"sqlite:///{db_path.as_posix()}",
                         agent_artifact_path=str(tmp_path / "artifacts"))
    sqlite_db._db_instance = None
    first = build_container(settings)
    users, client, headers, campaign_id = _bootstrap(first)
    generated = client.post(f"/api/v1/final-review/campaigns/{campaign_id}/plans/generate",
                            headers={**headers[0], "Idempotency-Key": "gen-1"}).json()
    run_id = generated["run_id"]
    first.db.dispose()
    sqlite_db._db_instance = None

    second = build_container(settings)
    # main.py 启动流程中的同一行：只有能证明可恢复的运行才保留下来，等执行器接管。
    classification = second.agent_run_manager.classify_incomplete_runs(
        second.final_review_runtime_workflow.can_resume
    )
    assert [run.id for run in classification["pending"]] == [run_id]
    assert second.agent_runtime_repository.get_run(run_id=run_id, user_id=users[0].id).status == "AWAITING_APPROVAL"

    restarted = TestClient(create_app())
    headers2 = _auth(restarted, "api_runtime_student")
    resumed = restarted.post(f"/api/v1/agent-runs/{run_id}/resume", headers=headers2)
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "AWAITING_APPROVAL"
    types = [event["type"] for event in
             restarted.get(f"/api/v1/agent-runs/{run_id}/events", headers=headers2).json()["items"]]
    assert "RUN_RECOVERY_STARTED" in types

    decided = restarted.post(f"/api/v1/agent-approvals/{generated['approval_id']}/decision",
                             headers=headers2, json={"decision": "APPROVED"})
    assert decided.status_code == 200
    run = restarted.get(f"/api/v1/final-review/campaigns/{campaign_id}/run", headers=headers2).json()
    assert run["status"] == "SUCCEEDED"
    assert run["progress_current"] == 7
    assert _titles(restarted, headers2) == ["复习核心知识点", "完成诊断练习"]
    second.db.dispose()


def test_startup_lifespan_fails_runs_that_cannot_be_proven_resumable(tmp_path, monkeypatch):
    db_path = tmp_path / "runtime-startup.db"
    settings = _settings(database_url=f"sqlite:///{db_path.as_posix()}",
                         agent_artifact_path=str(tmp_path / "artifacts"))
    sqlite_db._db_instance = None
    container = build_container(settings)
    users, _client, _headers, _campaign_id = _bootstrap(container)
    repository = container.agent_runtime_repository
    orphan_job = repository.create_job(user_id=users[0].id, domain="final_review", objective_summary="孤儿运行")
    orphan = repository.create_run(job_id=orphan_job.id, user_id=users[0].id,
                                   domain="final_review", total_steps=7)
    assert repository.get_run(run_id=orphan.id).status == "QUEUED"

    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr("app.main.build_container", lambda settings=None: container)
    with TestClient(create_app()):
        pass

    assert repository.get_run(run_id=orphan.id).status == "FAILED"
    assert "RUN_FAILED" in [event.type for event in repository.list_events(run_id=orphan.id)]
    container.db.dispose()
