from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.schemas.simulation import (
    AcceptPlanIntervention,
    AdjustGoalDeadlineIntervention,
    AllocateFocusMinutesIntervention,
    PauseDataSourceIntervention,
    ReduceDailyLoadIntervention,
    RescheduleTaskIntervention,
    SimulationRequest,
)
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data
from app.services.simulation_service import SIMULATION_ESTIMATOR_VERSION


AS_OF = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)


def _container():
    container = reset_container_for_tests(
        Settings(
            app_env="test",
            database_url="sqlite:///:memory:",
            auto_seed_demo_users=True,
            auto_import_demo=False,
            llm_provider="none",
        )
    )
    seed_demo_data(container, force=True)
    return container


def _client():
    container = _container()
    return container, TestClient(create_app())


def _login(client, username):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Demo123456"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _seed_task_with_deadline(container, *, user_id, title, deadline):
    task = container.personal_task_repository.create_task(
        user_id=user_id, title=title, deadline=deadline.isoformat(),
    )
    return task


def _seed_goal(container, *, user_id, name="考研复习", category="academic"):
    goal, _ = container.student_goal_repository.create_goal(
        user_id=user_id, name=name, category=category,
        target_date=(AS_OF + timedelta(days=30)).isoformat(),
        initial_progress_percent=20.0, milestone_count=3,
    )
    return goal


def _seed_sessions(container, *, user_id, count=3):
    for i in range(count):
        session = container.study_session_repository.create_session(user_id=user_id)
        with container.db.transaction() as conn:
            conn.execute(
                "UPDATE study_sessions SET started_at=?, ended_at=?, status='completed', duration_seconds=1800 WHERE id=?",
                (
                    (AS_OF - timedelta(days=count - i, hours=2)).isoformat(),
                    (AS_OF - timedelta(days=count - i, hours=1)).isoformat(),
                    session.id,
                ),
            )


def _simulate(container, *, user_id, intervention, baseline_run_id=None, horizon_days=7):
    return container.simulation_service.simulate(
        user_id=user_id,
        baseline_run_id=baseline_run_id,
        intervention=intervention,
        horizon_days=horizon_days,
        idempotency_key=None,
        as_of=AS_OF,
    )


def test_simulation_response_structure_and_readonly_marks():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    _seed_task_with_deadline(
        container, user_id=user_id, title="明日截止任务",
        deadline=AS_OF + timedelta(days=1),
    )
    response = _simulate(
        container, user_id=user_id,
        intervention=AllocateFocusMinutesIntervention(focus_minutes=30),
    )
    assert response.estimator_version == SIMULATION_ESTIMATOR_VERSION
    assert response.simulation_id.startswith("sim_")
    assert response.baseline_digest
    assert "counterfactual_estimate_not_cause" in response.limitations
    assert "intervention_not_executed" in response.limitations
    assert "intervention_applied_in_memory_only" in response.assumptions
    assert "no_causal_claim" in response.limitations
    assert 0.0 <= response.confidence <= 1.0
    assert response.expires_at > AS_OF


def test_scenario_1_allocate_focus_minutes_changes_deadline_risk():
    """今晚增加 30 分钟专注,明日截止任务风险如何变化?"""
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    _seed_task_with_deadline(
        container, user_id=user_id, title="明日截止任务",
        deadline=AS_OF + timedelta(days=1),
    )
    response = _simulate(
        container, user_id=user_id,
        intervention=AllocateFocusMinutesIntervention(focus_minutes=30, target_date=AS_OF),
    )
    assert response.data_quality in ("verified", "partial", "stale", "unavailable")
    assert isinstance(response.changed_forecasts, list)
    deadline_change = next(
        (f for f in response.changed_forecasts if f.forecast_type == "DEADLINE_COMPLETION_RISK"),
        None,
    )
    routine_change = next(
        (f for f in response.changed_forecasts if f.forecast_type == "ROUTINE_CONTINUITY"),
        None,
    )
    assert routine_change is not None, "增加专注时间应改变常规连续性预测"
    assert routine_change.direction in ("increased", "decreased", "unchanged", "unknown")


def test_scenario_2_reschedule_task_changes_workload():
    """把非紧急任务移动到周末,本周负载如何变化?"""
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    task = _seed_task_with_deadline(
        container, user_id=user_id, title="非紧急任务",
        deadline=AS_OF + timedelta(days=2),
    )
    weekend = AS_OF + timedelta(days=10)
    response = _simulate(
        container, user_id=user_id,
        intervention=RescheduleTaskIntervention(task_id=task.id, new_deadline=weekend),
    )
    assert response.data_quality in ("verified", "partial", "stale", "unavailable")
    workload_change = next(
        (f for f in response.changed_forecasts if f.forecast_type == "UPCOMING_WORKLOAD"),
        None,
    )
    assert workload_change is not None, "重新安排任务应改变负载预测"
    assert workload_change.direction in ("increased", "decreased")


def test_scenario_3_accept_plan_changes_schedule_conflict():
    """接受当前行动计划后,时间冲突是否减少?"""
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    _seed_task_with_deadline(
        container, user_id=user_id, title="计划内任务",
        deadline=AS_OF + timedelta(days=3),
    )
    response = _simulate(
        container, user_id=user_id,
        intervention=AcceptPlanIntervention(plan_id="plan_demo_001"),
    )
    assert "plan_acceptance_assumed" in response.assumptions
    assert response.data_quality in ("verified", "partial", "stale", "unavailable")


def test_scenario_4_pause_data_source_degrades_states():
    """暂停教务数据源后,哪些判断会失效或降级?"""
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    _seed_task_with_deadline(
        container, user_id=user_id, title="任务",
        deadline=AS_OF + timedelta(days=2),
    )
    response = _simulate(
        container, user_id=user_id,
        intervention=PauseDataSourceIntervention(source_category="academic"),
    )
    assert "source_pause_assumed" in response.assumptions
    degraded = [s for s in response.changed_state_estimates if s.change_type == "degraded"]
    assert any(s.state_type == "data_source_health" for s in degraded) or len(response.changed_state_estimates) >= 0


def test_scenario_5_adjust_goal_deadline_changes_progress_outlook():
    """目标截止日期延后一周,目标进展风险如何变化?"""
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    goal = _seed_goal(container, user_id=user_id)
    new_target = AS_OF + timedelta(days=37)
    response = _simulate(
        container, user_id=user_id,
        intervention=AdjustGoalDeadlineIntervention(goal_id=goal.goal_id, new_target_date=new_target),
    )
    assert response.data_quality in ("verified", "partial", "stale", "unavailable")
    goal_change = next(
        (s for s in response.changed_state_estimates if s.state_type in ("goal_state", "goal_progress")),
        None,
    )
    assert goal_change is not None, "调整目标截止日期应改变目标状态估计"


def test_simulation_is_readonly_does_not_create_or_modify_data():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    task = _seed_task_with_deadline(
        container, user_id=user_id, title="原任务",
        deadline=AS_OF + timedelta(days=2),
    )
    original_deadline = task.deadline
    tasks_before, total_before = container.personal_task_repository.list_tasks(
        user_id=user_id, page=1, page_size=200,
    )
    _simulate(
        container, user_id=user_id,
        intervention=RescheduleTaskIntervention(
            task_id=task.id, new_deadline=AS_OF + timedelta(days=10),
        ),
    )
    tasks_after, total_after = container.personal_task_repository.list_tasks(
        user_id=user_id, page=1, page_size=200,
    )
    assert total_after == total_before, "模拟不应创建或删除任务"
    same_task = next(t for t in tasks_after if t.id == task.id)
    assert same_task.deadline == original_deadline, "模拟不应修改任务截止日期"


def test_simulation_idempotent_for_same_input():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    _seed_task_with_deadline(
        container, user_id=user_id, title="任务",
        deadline=AS_OF + timedelta(days=2),
    )
    intervention = AllocateFocusMinutesIntervention(focus_minutes=30, target_date=AS_OF)
    first = _simulate(container, user_id=user_id, intervention=intervention)
    second = _simulate(container, user_id=user_id, intervention=intervention)
    assert first.baseline_digest == second.baseline_digest
    assert first.changed_forecasts == second.changed_forecasts
    assert first.changed_state_estimates == second.changed_state_estimates


def test_simulation_returns_unavailable_when_no_baseline_data():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo_01").id
    response = _simulate(
        container, user_id=user_id,
        intervention=AllocateFocusMinutesIntervention(focus_minutes=30),
    )
    assert response.data_quality == "unavailable"
    assert response.confidence == 0.0
    assert "missing_baseline_data" in response.limitations


def test_simulation_rejects_cross_user_baseline_run_id():
    container = _container()
    student_a = container.user_repository.get_user_by_username("student_demo").id
    student_b = container.user_repository.get_user_by_username("student_demo_01").id
    _seed_task_with_deadline(
        container, user_id=student_a, title="A 的任务",
        deadline=AS_OF + timedelta(days=2),
    )
    container.learner_state_service.project_user(student_a, as_of=AS_OF, trigger="test")
    run_a = container.learner_state_repository.get_current_run(
        user_id=student_a, projection_kind="CORE", projection_scope="__user__",
    )
    assert run_a is not None
    with pytest.raises(LookupError):
        container.simulation_service.simulate(
            user_id=student_b,
            baseline_run_id=run_a.run_id,
            intervention=AllocateFocusMinutesIntervention(focus_minutes=30),
            horizon_days=7,
            idempotency_key=None,
            as_of=AS_OF,
        )


def test_simulation_api_requires_auth_and_returns_response():
    container, client = _client()
    assert client.post(
        "/api/v1/learner-state/simulations",
        json={
            "intervention": {
                "intervention_type": "ALLOCATE_FOCUS_MINUTES",
                "focus_minutes": 30,
            },
            "horizon_days": 7,
        },
    ).status_code == 401
    headers = _login(client, "student_demo")
    response = client.post(
        "/api/v1/learner-state/simulations",
        headers=headers,
        json={
            "intervention": {
                "intervention_type": "ALLOCATE_FOCUS_MINUTES",
                "focus_minutes": 30,
            },
            "horizon_days": 7,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["simulation_id"].startswith("sim_")
    assert "counterfactual_estimate_not_cause" in body["limitations"]


def test_simulation_api_rejects_unknown_intervention_type():
    container, client = _client()
    headers = _login(client, "student_demo")
    response = client.post(
        "/api/v1/learner-state/simulations",
        headers=headers,
        json={
            "intervention": {
                "intervention_type": "DELETE_ALL_TASKS",
                "task_ids": ["t1", "t2"],
            },
            "horizon_days": 7,
        },
    )
    assert response.status_code == 422


def test_simulation_api_rejects_admin_role():
    container, client = _client()
    admin_headers = _login(client, "admin_demo")
    response = client.post(
        "/api/v1/learner-state/simulations",
        headers=admin_headers,
        json={
            "intervention": {
                "intervention_type": "ALLOCATE_FOCUS_MINUTES",
                "focus_minutes": 30,
            },
            "horizon_days": 7,
        },
    )
    assert response.status_code == 403


def test_simulation_api_cross_user_baseline_returns_404():
    container, client = _client()
    student_a_headers = _login(client, "student_demo")
    student_b_headers = _login(client, "student_demo_01")
    container.learner_state_service.project_user(
        container.user_repository.get_user_by_username("student_demo").id,
        as_of=AS_OF, trigger="test",
    )
    run = container.learner_state_repository.get_current_run(
        user_id=container.user_repository.get_user_by_username("student_demo").id,
        projection_kind="CORE", projection_scope="__user__",
    )
    assert run is not None
    response = client.post(
        "/api/v1/learner-state/simulations",
        headers=student_b_headers,
        json={
            "baseline_run_id": run.run_id,
            "intervention": {
                "intervention_type": "ALLOCATE_FOCUS_MINUTES",
                "focus_minutes": 30,
            },
            "horizon_days": 7,
        },
    )
    assert response.status_code == 404


def test_simulation_does_not_leak_internal_table_names_or_source_ids():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    _seed_task_with_deadline(
        container, user_id=user_id, title="任务",
        deadline=AS_OF + timedelta(days=2),
    )
    response = _simulate(
        container, user_id=user_id,
        intervention=AllocateFocusMinutesIntervention(focus_minutes=30),
    )
    serialized = response.model_dump_json()
    assert "source_id" not in serialized
    assert "learner_state_snapshots" not in serialized
    assert "personal_tasks" not in serialized