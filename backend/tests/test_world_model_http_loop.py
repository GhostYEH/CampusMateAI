"""World-model acceptance driven only by public HTTP reads and writes.

The container is reset solely to select a clean test database. All users,
facts, plan decisions, execution results and feedback are created/read via API.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests


API = "/api/v1"
TASK_CREATING_TYPES = {
    "TASK_FOCUS", "EXAM_PREPARATION", "CAMPUS_AFFAIRS", "GOAL_PROGRESS",
    "RESEARCH_OR_COMPETITION", "CAREER_PREPARATION",
}


@pytest.fixture
def client():
    reset_container_for_tests(Settings(
        app_env="test", database_url="sqlite:///:memory:",
        auto_seed_demo_users=False, auto_import_demo=False, llm_provider="none",
    ))
    return TestClient(create_app())


def _auth(client, username="http_loop_student"):
    credentials = {"username": username, "password": "HttpLoop123456"}
    registered = client.post(f"{API}/auth/register", json=credentials)
    assert registered.status_code == 201, registered.text
    login = client.post(f"{API}/auth/login", json=credentials)
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _request(client, headers, method, path, *, expected=200, **kwargs):
    response = client.request(method, f"{API}{path}", headers=headers, **kwargs)
    assert response.status_code == expected, response.text
    return response.json()


@pytest.mark.parametrize("with_existing_task", [True, False])
def test_http_facts_plan_execution_feedback_and_replan_form_a_closed_loop(client, with_existing_task):
    headers = _auth(client)
    goal = _request(client, headers, "POST", "/student-goals", json={
        "name": "Prepare scholarship materials", "category": "campus_affair",
        "idempotency_key": "http-goal-1",
    })["goal"]
    original_task_id = None
    if with_existing_task:
        original_task_id = _request(client, headers, "POST", "/tasks", expected=201, json={
            "title": "Collect documents",
            "deadline": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        })["id"]

    before = {}
    for family in ("CORE", "ACADEMIC", "WORLD"):
        page = _request(client, headers, "GET", "/learner-state/snapshots", params={"projection_kind": family})
        assert page["items"]
        before[family] = page
    original_world_run = before["WORLD"]["items"][0]["run_id"]
    forecasts = _request(client, headers, "GET", "/learner-state/forecasts")
    assert len(forecasts["items"]) == 5
    before_tasks = _request(client, headers, "GET", "/tasks")
    simulation = _request(client, headers, "POST", "/learner-state/simulations", json={
        "intervention": {"intervention_type": "ALLOCATE_FOCUS_MINUTES", "focus_minutes": 30},
    })
    assert simulation["causal_claim"] is False
    assert _request(client, headers, "GET", "/tasks") == before_tasks

    plan = _request(client, headers, "POST", "/learning-plans/generate", json={
        "available_minutes": 60, "goal_id": goal["goal_id"], "idempotency_key": "http-plan-1",
    })
    assert plan["status"] == "PROPOSED"
    assert all(item["execution_task_id"] is None for item in plan["items"])
    plan_id = plan["plan_id"]
    _request(client, headers, "POST", f"/learning-plans/{plan_id}/decision", json={"decision": "ACCEPT"})
    executed = _request(client, headers, "POST", f"/learning-plans/{plan_id}/execute")
    assert executed["status"] == "EXECUTED"
    artifacts = [item for item in executed["items"] if item["item_type"] in TASK_CREATING_TYPES]
    assert artifacts
    execution_ids = {item["execution_task_id"] for item in artifacts}
    assert None not in execution_ids
    assert len(execution_ids) == len(artifacts)
    assert original_task_id not in execution_ids
    if original_task_id:
        assert any(item["task_id"] == original_task_id for item in artifacts)

    retry = _request(client, headers, "POST", f"/learning-plans/{plan_id}/execute")
    assert {item["execution_task_id"] for item in retry["items"]
            if item["item_type"] in TASK_CREATING_TYPES} == execution_ids
    listed_plan = next(item for item in _request(client, headers, "GET", "/learning-plans")["items"]
                       if item["plan_id"] == plan_id)
    assert listed_plan["items"] == executed["items"]
    assert _request(client, headers, "GET", f"/learning-plans/{plan_id}")["items"] == executed["items"]
    tasks = _request(client, headers, "GET", "/tasks")["items"]
    for item in artifacts:
        task = next(task for task in tasks if task["id"] == item["execution_task_id"])
        assert task["source"] == "learning_plan"
        assert task["external_id"] == f"{plan_id}:{item['item_id']}"
        assert _request(client, headers, "GET", f"/tasks/{task['id']}")["source"] == "learning_plan"

    session = _request(client, headers, "POST", "/study/sessions", expected=201, json={
        "related_task_id": artifacts[0]["execution_task_id"], "goal": "Collect documents",
    })
    finished = _request(client, headers, "POST", f"/study/sessions/{session['id']}/finish", json={
        "self_report": "Finished one preparation step",
    })
    assert finished["status"] == "completed"
    for task_id in execution_ids:
        assert _request(client, headers, "POST", f"/tasks/{task_id}/complete")["status"] == "completed"
    progress = _request(client, headers, "POST", f"/student-goals/{goal['goal_id']}/progress", json={
        "progress_percent": 50, "milestone_reached": "Documents ready", "idempotency_key": "http-progress-1",
    })
    assert progress["goal"]["progress_percent"] == 50
    _request(client, headers, "POST", f"/learning-plans/{plan_id}/feedback", json={"feedback": "HELPFUL"})
    evaluation = _request(client, headers, "GET", f"/learning-plans/{plan_id}/evaluation")
    assert evaluation["completed_plan_task_count"] == len(execution_ids)

    world = _request(client, headers, "GET", "/learner-state/snapshots", params={"projection_kind": "WORLD"})
    values = {item["state_type"]: item["value"] for item in world["items"]}
    assert values["goal_progress"]["average_progress_percent"] == 50
    assert values["focus_rhythm"]["observed_session_count"] == 1
    assert values["execution_consistency"]["executed_task_count"] >= len(execution_ids)
    assert world["items"][0]["run_id"] != original_world_run
    changes = _request(client, headers, "GET", "/learner-state/changes", params={
        "projection_kind": "WORLD", "from_run_id": original_world_run,
    })
    assert any(item["state_type"] == "goal_progress" and item["change_type"] == "UPDATED"
               for item in changes["changes"])
    core = _request(client, headers, "GET", "/learner-state/snapshots")
    activity = next(item for item in core["items"] if item["state_type"] == "observed_learning_activity")
    assert activity["value"]["observed_completed_tasks_7d"] == len(execution_ids)
    evidence = _request(client, headers, "GET", f"/learner-state/snapshots/{activity['snapshot_id']}/evidence")
    assert any(item["event_type"] == "task_completed" for item in evidence["items"])

    refreshed_forecasts = _request(client, headers, "GET", "/learner-state/forecasts")
    goal_outlook = next(item for item in refreshed_forecasts["items"]
                        if item["forecast_type"] == "GOAL_PROGRESS_OUTLOOK")
    assert goal_outlook["value"]["average_progress_percent"] == 50
    before_outlook = next(item for item in forecasts["items"]
                         if item["forecast_type"] == "GOAL_PROGRESS_OUTLOOK")
    assert goal_outlook["input_digest"] != before_outlook["input_digest"]

    summary = _request(client, headers, "GET", f"/learning-plans/{plan_id}/summary")
    assert summary["plan_id"] == plan_id
    successor = _request(
        client, {**headers, "Idempotency-Key": "http-replan-1"}, "POST", f"/learning-plans/{plan_id}/replan",
    )
    assert successor["status"] == "PROPOSED"
    assert successor["supersedes_plan_id"] == plan_id
    assert successor["goal_id"] == goal["goal_id"]
    assert successor["input_digest"] != plan["input_digest"]
    assert _request(client, headers, "GET", f"/learning-plans/{plan_id}")["superseded_by_plan_id"] == successor["plan_id"]

    outsider = _auth(client, "http_loop_outsider")
    _request(client, outsider, "GET", f"/learning-plans/{plan_id}", expected=404)
    for task_id in execution_ids:
        _request(client, outsider, "GET", f"/tasks/{task_id}", expected=404)


def test_http_undo_keeps_execution_task_mapping_without_touching_original_task(client):
    headers = _auth(client)
    original = _request(client, headers, "POST", "/tasks", expected=201, json={"title": "Original task"})
    plan = _request(client, headers, "POST", "/learning-plans/generate", json={"available_minutes": 30})
    plan_id = plan["plan_id"]
    _request(client, headers, "POST", f"/learning-plans/{plan_id}/decision", json={"decision": "ACCEPT"})
    executed = _request(client, headers, "POST", f"/learning-plans/{plan_id}/execute")
    artifact_id = executed["items"][0]["execution_task_id"]
    assert artifact_id and artifact_id != original["id"]
    undone = _request(client, headers, "POST", f"/learning-plans/{plan_id}/undo")
    assert undone["status"] == "UNDONE"
    assert undone["items"][0]["execution_task_id"] == artifact_id
    assert undone["items"][0]["execution_status"] == "UNDONE"
    assert _request(client, headers, "GET", f"/tasks/{original['id']}")["status"] == "pending"
    deleted = _request(client, headers, "GET", "/tasks", params={"status": "deleted"})["items"]
    assert any(task["id"] == artifact_id and task["source"] == "learning_plan" for task in deleted)


def test_http_world_read_includes_a_session_finished_in_the_same_second(client, monkeypatch):
    from app.api.routes import forecasts as forecast_routes
    from app.api.routes import learner_state as state_routes
    from app.api.routes import simulations as simulation_routes
    from app.repositories import study_session_repository as sessions
    from app.services.adaptive_agent import intervention_service as interventions
    from app.services import learning_planner_service as planner

    fixed_now = datetime.now(timezone.utc).replace(microsecond=250000)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now.astimezone(tz) if tz else fixed_now.replace(tzinfo=None)

    monkeypatch.setattr(sessions, "datetime", Clock)
    headers = _auth(client)
    goal = _request(client, headers, "POST", "/student-goals", json={
        "name": "Prepare documents", "category": "campus_affair",
    })["goal"]
    session = _request(client, headers, "POST", "/study/sessions", expected=201, json={})
    _request(client, headers, "POST", f"/study/sessions/{session['id']}/finish", json={})
    fixed_now += timedelta(microseconds=250000)
    monkeypatch.setattr(state_routes, "datetime", Clock)
    snapshots = _request(client, headers, "GET", "/learner-state/snapshots", params={"projection_kind": "WORLD"})
    rhythm = next(item for item in snapshots["items"] if item["state_type"] == "focus_rhythm")
    assert rhythm["value"]["observed_session_count"] == 1
    assert datetime.fromisoformat(rhythm["as_of"]) == fixed_now

    monkeypatch.setattr(forecast_routes, "datetime", Clock)
    forecasts = _request(client, headers, "GET", "/learner-state/forecasts")
    routine = next(item for item in forecasts["items"] if item["forecast_type"] == "ROUTINE_CONTINUITY")
    assert routine["value"]["observed_session_count"] == 1

    monkeypatch.setattr(simulation_routes, "datetime", Clock)
    simulation = _request(client, headers, "POST", "/learner-state/simulations", json={
        "intervention": {"intervention_type": "PAUSE_DATA_SOURCE", "source_category": "study_session"},
    })
    routine_change = next(item for item in simulation["changed_forecasts"]
                          if item["forecast_type"] == "ROUTINE_CONTINUITY")
    assert routine_change["baseline_value"]["observed_session_count"] == 1
    assert routine_change["intervention_value"]["observed_session_count"] == 0

    monkeypatch.setattr(planner, "datetime", Clock)
    request = {"available_minutes": 30, "goal_id": goal["goal_id"], "idempotency_key": "same-second-plan"}
    plan = _request(client, headers, "POST", "/learning-plans/generate", json=request)
    fixed_now += timedelta(microseconds=100000)
    retry = _request(client, headers, "POST", "/learning-plans/generate", json=request)
    assert retry["plan_id"] == plan["plan_id"]

    fixed_now += timedelta(microseconds=100000)
    monkeypatch.setattr(interventions, "datetime", Clock)
    _request(client, headers, "POST", f"/learning-plans/{plan['plan_id']}/decision", json={"decision": "ACCEPT"})
    adopted = next(item for item in _request(client, headers, "GET", "/adaptive-interventions")["items"]
                   if item["plan_id"] == plan["plan_id"])
    for family in ("CORE", "ACADEMIC", "WORLD"):
        runs = _request(client, headers, "GET", "/learner-state/runs", params={"projection_kind": family})
        assert adopted[f"baseline_{family.lower()}_run_id"] in {item["run_id"] for item in runs["items"]}
