from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import Settings
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


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


def _user_id(container, username: str = "student_demo") -> str:
    return container.user_repository.get_user_by_username(username).id


def _add_user(container, user_id: str) -> None:
    with container.db.transaction() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
            "VALUES (?, ?, ?, 'student', ?, ?)",
            (user_id, user_id, "hash", "now", "now"),
        )


def _completed_session(container, user_id: str):
    session = container.study_session_repository.create_session(user_id=user_id)
    return container.study_session_repository.finish(session.id, user_id=user_id)


def _completed_task(container, user_id: str, title: str = "task"):
    task = container.personal_task_repository.create_task(user_id=user_id, title=title)
    return container.personal_task_repository.complete(task.id, user_id=user_id)


def _event_count(container, user_id: str) -> int:
    return container.learner_event_repository.list_for_user(user_id=user_id)[1]


def test_backfill_projects_existing_completed_rows_and_is_idempotent():
    container = _container()
    user_id = _user_id(container)
    session = _completed_session(container, user_id)
    task = _completed_task(container, user_id)
    session_updated_at = session.updated_at
    task_updated_at = task.updated_at

    first = container.learner_event_service.backfill_core_learning_events(
        user_id=user_id, batch_size=1
    )
    second = container.learner_event_service.backfill_core_learning_events(
        user_id=user_id, batch_size=1
    )

    assert first == {"scanned": 2, "created": 2, "reused": 0, "skipped": 0, "failed": 0}
    assert second == {"scanned": 2, "created": 0, "reused": 2, "skipped": 0, "failed": 0}
    assert _event_count(container, user_id) == 2
    assert container.study_session_repository.get_session(session.id, user_id=user_id).updated_at == session_updated_at
    assert container.personal_task_repository.get_task(task.id, user_id=user_id).updated_at == task_updated_at


def test_backfill_can_process_all_users_in_batches_without_cross_user_events():
    container = _container()
    user1 = _user_id(container)
    user2 = "usr_backfill_two"
    _add_user(container, user2)
    _completed_session(container, user1)
    _completed_task(container, user2)

    result = container.learner_event_service.backfill_core_learning_events(batch_size=1)

    assert result == {"scanned": 2, "created": 2, "reused": 0, "skipped": 0, "failed": 0}
    assert _event_count(container, user1) == 1
    assert _event_count(container, user2) == 1


def test_backfill_skips_ineligible_and_malformed_rows_without_stopping():
    container = _container()
    user_id = _user_id(container)
    valid = _completed_session(container, user_id)
    malformed = _completed_session(container, user_id)
    pending = container.study_session_repository.create_session(user_id=user_id)
    deleted = _completed_task(container, user_id, title="deleted")
    with container.db.transaction() as conn:
        conn.execute(
            "UPDATE study_sessions SET ended_at=? WHERE id=?",
            ("not-an-iso-time", malformed.id),
        )
        conn.execute(
            "UPDATE personal_tasks SET status='deleted', deleted_at=? WHERE id=?",
            (datetime.now(timezone.utc).isoformat(), deleted.id),
        )

    result = container.learner_event_service.backfill_core_learning_events(user_id=user_id)

    assert result == {"scanned": 2, "created": 1, "reused": 0, "skipped": 1, "failed": 0}
    assert _event_count(container, user_id) == 1
    assert container.learner_event_repository.get_by_dedupe(
        user_id=user_id,
        dedupe_key=f"study:study_session_finished:{valid.id}",
    ) is not None
    assert container.learner_event_repository.get_by_dedupe(
        user_id=user_id,
        dedupe_key=f"study:study_session_finished:{pending.id}",
    ) is None


def test_backfill_counts_one_bad_record_as_failed_and_keeps_safe_aggregate_result():
    container = _container()
    user_id = _user_id(container)
    _completed_task(container, user_id, title="good")
    bad = _completed_task(container, user_id, title="bad")
    original = container.learner_event_service.record_personal_task_completed

    def fail_for_bad(task):
        if task.id == bad.id:
            raise RuntimeError("private task details must not be returned")
        return original(task)

    container.learner_event_service.record_personal_task_completed = fail_for_bad
    try:
        result = container.learner_event_service.backfill_core_learning_events(user_id=user_id)
    finally:
        container.learner_event_service.record_personal_task_completed = original

    assert result == {"scanned": 2, "created": 1, "reused": 0, "skipped": 0, "failed": 1}
    assert set(result) == {"scanned", "created", "reused", "skipped", "failed"}
    assert "private task details" not in str(result)
