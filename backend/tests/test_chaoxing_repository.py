"""Sync read models must filter by user, source, course and active task status."""
from types import SimpleNamespace

import pytest

from app.database.sqlite_db import Database
from app.repositories.chaoxing_repository import ChaoxingRepository
from app.repositories.course_repository import CourseRepository
from app.repositories.notice_repository import NoticeRepository
from app.repositories.personal_task_repository import PersonalTaskRepository
from app.services.chaoxing.sync_service import is_assignment_duplicate


@pytest.fixture
def sync_repositories():
    database = Database(None)
    try:
        with database.transaction() as conn:
            for user in ("u", "other"):
                conn.execute(
                    "INSERT INTO users (id, username, password_hash, created_at, updated_at) "
                    "VALUES (?, ?, 'hash', 'now', 'now')", (user, user),
                )
        yield SimpleNamespace(
            sync=ChaoxingRepository(database), courses=CourseRepository(database),
            tasks=PersonalTaskRepository(database), notices=NoticeRepository(database),
        )
    finally:
        database.dispose()


def test_synced_counts_filter_user_source_and_pending_status(sync_repositories):
    repos = sync_repositories
    for user in ("u", "other"):
        for provider, teacher in (("chaoxing", "同一老师"), ("chaoxing", "同一老师"),
                                  ("chaoxing", None), (None, "其他老师")):
            repos.courses.create_course(name="课程", owner_user_id=user, provider=provider,
                                        remote_teacher_name=teacher)
        repos.tasks.create_task(user_id=user, title="未交", source="chaoxing")
        completed = repos.tasks.create_task(user_id=user, title="已交", source="chaoxing")
        deleted = repos.tasks.create_task(user_id=user, title="删除", source="chaoxing")
        repos.tasks.complete(completed.id, user_id=user)
        repos.tasks.soft_delete(deleted.id, user_id=user)
        repos.tasks.create_task(user_id=user, title="手动任务")
        repos.notices.create_or_update_notice(user, "chaoxing", "remote", "通知")
        repos.notices.create_or_update_notice(user, "manual", "other", "手动通知")
    assert {kind: repos.sync.count_synced_items(user_id="u", kind=kind) for kind in (
        "courses", "teachers", "pending_assignments", "notices",
    )} == {"courses": 3, "teachers": 1, "pending_assignments": 1, "notices": 1}
    with pytest.raises(ValueError, match="Unsupported"):
        repos.sync.count_synced_items(user_id="u", kind="unknown")


@pytest.mark.parametrize("owner, source, deleted, unrelated_course, expected", [
    ("u", "chaoxing", False, False, True),
    ("other", "chaoxing", False, False, False),
    ("u", "manual", False, False, False),
    ("u", "chaoxing", True, False, False),
    ("u", "chaoxing", False, True, False),
])
def test_assignment_duplicate_candidates_respect_scope(
    sync_repositories, owner, source, deleted, unrelated_course, expected,
):
    repos = sync_repositories
    selected = repos.courses.create_course(name="当前课程", owner_user_id="u")
    unrelated = repos.courses.create_course(name="其他课程", owner_user_id=owner)
    task = repos.tasks.create_task(user_id=owner, title="提交实验报告", source=source,
                                  course_id=unrelated.id if unrelated_course else selected.id)
    if deleted:
        repos.tasks.soft_delete(task.id, user_id=owner)
    extraction = SimpleNamespace(task="提交实验报告", deadline=None)
    assert is_assignment_duplicate(
        repos.sync, None, user_id="u", course_name="当前课程", course_id=selected.id,
        remote_course_id="remote", notice={"title": "提交实验报告"}, extracted=extraction,
    ) is expected


def test_external_assignment_id_and_notice_snapshot_do_not_cross_users(sync_repositories):
    repos = sync_repositories
    repos.tasks.create_task(user_id="other", title="其他人的作业", source="chaoxing", external_id="work")
    repos.notices.create_or_update_notice("other", "chaoxing", "notice", "私有通知", content="private")
    repos.tasks.create_task(user_id="other", title="私有待办", source="chaoxing_notice",
                            source_notice_id="notice")
    assert not repos.sync.assignment_exists(user_id="u", external_id="work")
    assert repos.sync.get_assignment_snapshot(user_id="u", external_id="work") is None
    assert repos.sync.get_notice_sync_snapshot(user_id="u", external_id="notice") == (None, None)
    task = repos.tasks.create_task(user_id="u", title="不同标题", source="chaoxing", external_id="work")
    repos.tasks.update_task(task.id, user_id="u", fields={"score": 90})
    assert repos.sync.scored_assignment_ids(user_id="u") == {"work"}
    assert repos.sync.scored_assignment_ids(user_id="other") == set()
    assert is_assignment_duplicate(
        repos.sync, None, user_id="u", course_name="课程", course_id=None, remote_course_id=None,
        notice={"link": "https://example.invalid/work?workId=work"},
        extracted=SimpleNamespace(task="完全不同的抽取标题"),
    )
