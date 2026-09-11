from __future__ import annotations

from datetime import datetime, timedelta, timezone

from test_phase4_learning_plans import _request, _setup


def test_semantic_task_change_marks_plan_stale_before_execute() -> None:
    client, container, headers, _ = _setup()
    user_id = container.user_repository.get_user_by_username("phase4_student").id
    task = container.personal_task_repository.create_task(user_id=user_id, title="deadline", deadline="2099-01-01T00:00:00+00:00")
    generated = client.post("/api/v1/learning-plans/generate", json=_request(60), headers=headers).json()
    container.personal_task_repository.complete(task.id, user_id=user_id)
    assert client.post(f"/api/v1/learning-plans/{generated['plan_id']}/decision", json={"decision": "ACCEPT"}, headers=headers).status_code == 200
    response = client.post(f"/api/v1/learning-plans/{generated['plan_id']}/execute", headers=headers)
    assert response.status_code == 409
    assert response.json()["code"] == "LEARNING_PLAN_STALE"
    assert container.learning_plan_repository.get_plan(generated["plan_id"], user_id=user_id).status == "STALE"


def test_updated_at_only_change_does_not_mark_plan_stale() -> None:
    client, container, headers, _ = _setup()
    user_id = container.user_repository.get_user_by_username("phase4_student").id
    task = container.personal_task_repository.create_task(user_id=user_id, title="same")
    generated = client.post("/api/v1/learning-plans/generate", json=_request(30), headers=headers).json()
    container.personal_task_repository.update_task(task.id, user_id=user_id, fields={"title": "same"})
    assert client.post(f"/api/v1/learning-plans/{generated['plan_id']}/decision", json={"decision": "ACCEPT"}, headers=headers).status_code == 200
    assert client.post(f"/api/v1/learning-plans/{generated['plan_id']}/execute", headers=headers).status_code == 200


def test_expired_plan_returns_stable_expired_error() -> None:
    client, container, headers, _ = _setup()
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    plan = container.learning_planner_service.generate(user_id=container.user_repository.get_user_by_username("phase4_student").id, available_minutes=30, as_of=old)
    assert client.post(f"/api/v1/learning-plans/{plan.plan_id}/decision", json={"decision": "ACCEPT"}, headers=headers).status_code == 200
    response = client.post(f"/api/v1/learning-plans/{plan.plan_id}/execute", headers=headers)
    assert response.status_code == 409
    assert response.json()["code"] == "LEARNING_PLAN_EXPIRED"


def test_replan_creates_a_linked_unaccepted_plan() -> None:
    client, _, headers, _ = _setup()
    generated = client.post("/api/v1/learning-plans/generate", json=_request(), headers=headers).json()
    response = client.post(f"/api/v1/learning-plans/{generated['plan_id']}/replan", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "PROPOSED"
    assert response.json()["supersedes_plan_id"] == generated["plan_id"]
