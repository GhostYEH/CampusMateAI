from datetime import datetime, timezone

import pytest

from app.core.config import Settings
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data
from app.services.learner_state_service import WORLD_ESTIMATOR_VERSION


AS_OF = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


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


def _empty_user(container, username: str = "empty_user"):
    existing = container.user_repository.get_user_by_username(username)
    if existing:
        return existing.id
    return container.user_repository.create_user(
        username=username, password_hash="x", role="student",
    ).id


def _state_value(result, state_type):
    for snap in result.snapshots:
        if snap.state_type == state_type:
            return snap.value
    return None


def _state_snapshot(result, state_type):
    for snap in result.snapshots:
        if snap.state_type == state_type:
            return snap
    return None


def test_world_projection_empty_data_returns_unavailable():
    container = _container()
    user_id = _empty_user(container)
    result = container.learner_state_service.project_world(
        user_id=user_id, as_of=AS_OF, trigger="read"
    )
    assert result.estimator_version == WORLD_ESTIMATOR_VERSION
    wp = _state_value(result, "workload_pressure")
    assert wp is not None
    assert wp["data_completeness"] == "unavailable"
    assert wp["pressure_band"] == "LOW"
    gp = _state_value(result, "goal_progress")
    assert gp is not None
    assert gp["data_completeness"] == "unavailable"
    fr = _state_value(result, "focus_rhythm")
    assert fr is not None
    assert fr["rhythm_stability"] == "unknown"


def test_world_projection_with_tasks_computes_workload_pressure():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    container.personal_task_repository.create_task(
        user_id=user_id,
        title="期末复习",
        deadline="2026-09-12T18:00:00+00:00",
    )
    result = container.learner_state_service.project_world(
        user_id=user_id, as_of=AS_OF, trigger="read"
    )
    wp = _state_value(result, "workload_pressure")
    assert wp is not None
    assert wp["window_days"] == 7
    assert wp["task_count"] >= 1
    assert wp["pressure_band"] in {"LOW", "MODERATE", "HIGH", "VERY_HIGH"}
    assert wp["data_completeness"] in {"verified", "partial"}


def test_world_projection_with_goal_computes_goal_progress():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    container.student_goal_repository.create_goal(
        user_id=user_id, name="考研", category="academic",
        initial_progress_percent=30.0, milestone_count=2,
    )
    result = container.learner_state_service.project_world(
        user_id=user_id, as_of=AS_OF, trigger="read"
    )
    gp = _state_value(result, "goal_progress")
    assert gp is not None
    assert gp["active_goal_count"] == 1
    assert gp["goals_with_milestones"] == 1
    assert gp["average_progress_percent"] == 30.0
    gm = _state_value(result, "growth_momentum")
    assert gm is not None
    assert gm["goal_count"] == 1
    assert gm["momentum_band"] in {"rising", "steady", "declining", "insufficient_data"}


def test_world_projection_with_session_computes_focus_rhythm():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    session = container.study_session_repository.create_session(user_id=user_id)
    with container.db.transaction() as conn:
        conn.execute(
            "UPDATE study_sessions SET started_at=?, ended_at=?, status='completed', duration_seconds=1800 WHERE id=?",
            ("2026-09-09T10:00:00+00:00", "2026-09-09T10:30:00+00:00", session.id),
        )
    result = container.learner_state_service.project_world(
        user_id=user_id, as_of=AS_OF, trigger="read"
    )
    fr = _state_value(result, "focus_rhythm")
    assert fr is not None
    assert fr["observed_session_count"] >= 1
    assert fr["rhythm_stability"] in {"stable", "variable", "unknown"}


def test_world_projection_generates_all_state_types():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    result = container.learner_state_service.project_world(
        user_id=user_id, as_of=AS_OF, trigger="read"
    )
    state_types = {snap.state_type for snap in result.snapshots}
    expected = {
        "workload_pressure", "schedule_conflict", "academic_progress",
        "focus_rhythm", "goal_progress", "execution_consistency",
        "growth_momentum", "preference_profile",
    }
    assert expected.issubset(state_types)


def test_world_projection_is_deterministic():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    r1 = container.learner_state_service.project_world(user_id=user_id, as_of=AS_OF, trigger="read")
    r2 = container.learner_state_service.project_world(user_id=user_id, as_of=AS_OF, trigger="read")
    assert r1.estimator_version == r2.estimator_version
    assert r1.input_digest == r2.input_digest
    assert {s.state_type for s in r1.snapshots} == {s.state_type for s in r2.snapshots}


def test_world_projection_execution_consistency_does_not_judge_user():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    result = container.learner_state_service.project_world(
        user_id=user_id, as_of=AS_OF, trigger="read"
    )
    ec = _state_value(result, "execution_consistency")
    assert ec is not None
    assert ec["consistency_band"] in {"none", "low", "moderate", "high", "no_plan"}
    assert 0.0 <= ec["consistency_ratio"] <= 1.0