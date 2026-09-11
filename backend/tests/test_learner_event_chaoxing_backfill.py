from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.config import Settings
from app.models.multi_role import CourseRow, NoticeRow
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


def _course(container, user_id: str, remote_id: str) -> CourseRow:
    return container.course_repository.create_course(
        name="历史课程标题不可进入事件",
        owner_user_id=user_id,
        provider="chaoxing",
        external_id=remote_id,
        remote_class_id="class_1",
        remote_student_count=10,
        status="active",
        last_synced_at="2026-09-10T10:00:00+00:00",
    )


def _notice(container, user_id: str, external_id: str) -> NoticeRow:
    return container.notice_repository.create_or_update_notice(
        user_id=user_id,
        source="chaoxing",
        external_id=external_id,
        title="历史通知标题不可进入事件",
        content="历史通知正文不可进入事件",
        course_id=None,
        last_synced_at="2026-09-10T10:00:00+00:00",
    )


def test_chaoxing_backfill_is_paginated_idempotent_and_preserves_source_rows():
    container = _container()
    user_id = _user_id(container)
    course = _course(container, user_id, "course_1")
    task = container.personal_task_repository.create_task(
        user_id=user_id,
        title="历史作业标题不可进入事件",
        source="chaoxing",
        external_id="work_1",
        course_id=course.id,
        last_synced_at="2026-09-10T10:00:00+00:00",
    )
    task = container.personal_task_repository.complete(task.id, user_id=user_id)
    notice = _notice(container, user_id, "notice_1")
    chapter = container.course_content_repository.upsert_item(
        user_id=user_id,
        course_id=course.id,
        provider="chaoxing",
        kind="chapter",
        external_id="chapter_1",
        title="历史章节标题不可进入事件",
        status="completed",
        is_stale=False,
        last_synced_at="2026-09-10T10:00:00+00:00",
    )
    container.course_content_repository.upsert_section_status(
        user_id=user_id,
        course_id=course.id,
        section="chapters",
        status="complete",
        item_count=1,
    )
    source_updated = {
        "course": course.updated_at,
        "task": task.updated_at,
        "notice": notice.updated_at,
        "chapter": chapter.updated_at,
    }

    first = container.learner_event_service.backfill_chaoxing_learning_events(
        user_id=user_id, batch_size=1
    )
    second = container.learner_event_service.backfill_chaoxing_learning_events(
        user_id=user_id, batch_size=1
    )
    assert first == {"scanned": 4, "created": 5, "reused": 0, "skipped": 0, "failed": 0}
    assert second == {"scanned": 4, "created": 0, "reused": 5, "skipped": 0, "failed": 0}
    assert container.learner_event_repository.list_for_user(user_id=user_id)[1] == 5
    assert container.course_repository.get_course(course.id).updated_at == source_updated["course"]
    assert container.personal_task_repository.get_task(task.id, user_id=user_id).updated_at == source_updated["task"]
    assert container.notice_repository.list_notices(user_id)[0].updated_at == source_updated["notice"]
    assert container.course_content_repository.get_item(chapter.id, user_id=user_id).updated_at == source_updated["chapter"]


def test_chaoxing_backfill_full_user_mode_isolated_and_core_backfill_does_not_emit_task_completed():
    container = _container()
    user1 = _user_id(container)
    user2 = "usr_chaoxing_backfill_two"
    _add_user(container, user2)
    _course(container, user1, "course_user1")
    _course(container, user2, "course_user2")
    task1 = container.personal_task_repository.create_task(
        user_id=user1, title="task1", source="chaoxing", external_id="work1"
    )
    task2 = container.personal_task_repository.create_task(
        user_id=user2, title="task2", source="chaoxing", external_id="work2"
    )
    container.personal_task_repository.complete(task1.id, user_id=user1)
    container.personal_task_repository.complete(task2.id, user_id=user2)

    core = container.learner_event_service.backfill_core_learning_events(
        user_id=user1, batch_size=1
    )
    assert core["created"] == 0
    assert container.learner_event_repository.list_for_user(user_id=user1, source="personal_task")[1] == 0
    result = container.learner_event_service.backfill_chaoxing_learning_events(batch_size=1)
    assert result["scanned"] == 4
    assert container.learner_event_repository.list_for_user(user_id=user1)[1] == 3
    assert container.learner_event_repository.list_for_user(user_id=user2)[1] == 3


def test_chaoxing_backfill_counts_discovered_and_submitted_failures_independently(caplog):
    container = _container()
    user_id = _user_id(container)
    course = _course(container, user_id, "course_partial")
    task = container.personal_task_repository.create_task(
        user_id=user_id,
        title="partial assignment",
        source="chaoxing",
        external_id="work_partial",
        course_id=course.id,
        last_synced_at="2026-09-10T10:00:00+00:00",
    )
    task = container.personal_task_repository.complete(task.id, user_id=user_id)
    original_discovered = container.learner_event_service.record_chaoxing_assignment_discovered

    def fail_discovered(_task):
        raise RuntimeError("private assignment title must not be logged")

    container.learner_event_service.record_chaoxing_assignment_discovered = fail_discovered
    with caplog.at_level("WARNING"):
        result = container.learner_event_service.backfill_chaoxing_learning_events(
            user_id=user_id, batch_size=1
        )
    container.learner_event_service.record_chaoxing_assignment_discovered = original_discovered
    assert result["failed"] == 1
    assert result["created"] >= 1
    assert "private assignment title" not in caplog.text


@pytest.mark.parametrize("batch_size", [0, 101])
def test_chaoxing_backfill_rejects_batch_size_outside_one_to_one_hundred(batch_size):
    container = _container()
    with pytest.raises(ValueError):
        container.learner_event_service.backfill_chaoxing_learning_events(batch_size=batch_size)
