from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import Settings
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data
from app.services.learner_state_service import LearnerStateProjectionService


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


def test_projection_reuses_current_run_for_later_as_of_while_snapshots_are_valid():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    first = container.learner_state_service.project_user(user_id, as_of=AS_OF, trigger="test")
    later = container.learner_state_service.project_user(
        user_id, as_of=AS_OF + timedelta(seconds=1), trigger="test"
    )
    assert later.run_id == first.run_id


def test_projection_recomputes_after_valid_until_and_does_not_reuse_future_run():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    task = container.personal_task_repository.create_task(
        user_id=user_id, title="deadline", deadline="2026-09-10T18:00:00+00:00"
    )
    first = container.learner_state_service.project_user(user_id, as_of=AS_OF, trigger="test")
    expired = container.learner_state_service.project_user(
        user_id, as_of=datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc), trigger="test"
    )
    assert expired.run_id != first.run_id
    future = container.learner_state_service.project_user(
        user_id, as_of=AS_OF + timedelta(days=1), trigger="test"
    )
    historical = container.learner_state_service.project_user(
        user_id, as_of=AS_OF, trigger="test"
    )
    assert future.run_id != historical.run_id
    assert task.id


def test_task_workload_keeps_later_out_of_unknown_deadline():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    container.personal_task_repository.create_task(
        user_id=user_id, title="later", deadline="2026-09-20T12:00:00+00:00"
    )
    container.personal_task_repository.create_task(
        user_id=user_id, title="invalid", deadline="not-a-date"
    )
    result = container.learner_state_service.project_user(user_id, as_of=AS_OF, trigger="test")
    workload = next(item for item in result.snapshots if item.state_type == "task_workload")
    value = workload.value
    assert value["known_later"] >= 1
    assert value["unknown_deadline"] >= 1
    assert value["known_pending"] == sum(
        value[key]
        for key in (
            "known_overdue",
            "known_due_24h",
            "known_due_7d",
            "known_later",
            "known_without_deadline",
            "unknown_deadline",
        )
    )


@pytest.mark.parametrize(
    ("bucket", "deadline", "latest"),
    [
        ("DUE_24H", AS_OF + timedelta(hours=24), AS_OF + timedelta(hours=24)),
        ("DUE_7D", AS_OF + timedelta(days=7), AS_OF + timedelta(days=6)),
        ("LATER", AS_OF + timedelta(days=10), AS_OF + timedelta(days=3)),
    ],
)
def test_deadline_valid_until_is_capped_by_the_next_semantic_boundary(bucket, deadline, latest):
    actual = LearnerStateProjectionService._deadline_valid_until(bucket, AS_OF, deadline)
    assert actual <= latest
