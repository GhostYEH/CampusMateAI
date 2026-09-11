from datetime import datetime, timezone

from app.core.config import Settings
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data
from app.services.learner_state_service import LearnerStateProjectionService


AS_OF = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


def _container():
    container = reset_container_for_tests(
        Settings(
            app_env="test", database_url="sqlite:///:memory:",
            auto_seed_demo_users=True, auto_import_demo=False, llm_provider="none",
        )
    )
    seed_demo_data(container, force=True)
    return container


def test_input_truncation_is_explicitly_digested_and_downgrades_affected_state():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    for index in range(3):
        container.personal_task_repository.create_task(user_id=user_id, title=f"bounded-{index}")
    inputs = container.learner_state_repository.collect_inputs(user_id=user_id, limit=2)
    assert inputs["input_metadata"]["truncated"] is True
    assert "tasks" in inputs["input_metadata"]["truncated_sources"]
    service = LearnerStateProjectionService(container.learner_state_repository, input_limit=2)
    result = service.project_user(user_id, as_of=AS_OF, trigger="test")
    assert "input_truncated" in result.warnings
    workload = next(item for item in result.snapshots if item.state_type == "task_workload")
    assert workload.data_quality == "partial"
    assert workload.confidence <= 0.6
    assert "truncated" in inputs["input_metadata"]


def test_projection_failure_log_contains_only_safe_dimensions(monkeypatch):
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    calls = []
    monkeypatch.setattr(
        "app.services.learner_state_service.logger.warning",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        container.learner_state_repository,
        "collect_inputs",
        lambda **_: (_ for _ in ()).throw(RuntimeError("private task title and payload")),
    )
    result = container.learner_state_service.project_user(user_id, as_of=AS_OF, trigger="safe_test")
    assert result.warnings == ["projection_failed"]
    rendered = repr(calls)
    assert "private task title" not in rendered
    assert "payload" not in rendered
    assert "RuntimeError" in rendered
    assert "safe_test" in rendered


def test_input_limit_exactly_at_boundary_is_not_marked_truncated():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    with container.db.query() as conn:
        task_count = conn.execute(
            "SELECT COUNT(*) AS n FROM personal_tasks WHERE user_id=?", (user_id,)
        ).fetchone()["n"]
    inputs = container.learner_state_repository.collect_inputs(
        user_id=user_id, limit=max(1, task_count)
    )
    assert inputs["input_metadata"]["truncated"] is False
