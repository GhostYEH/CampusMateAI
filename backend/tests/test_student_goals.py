from datetime import datetime, timezone

import pytest

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


def _make_user(container, username: str = "student_demo"):
    return container.user_repository.get_user_by_username(username).id


def _make_second_user(container, username: str = "student_b"):
    existing = container.user_repository.get_user_by_username(username)
    if existing:
        return existing.id
    row = container.user_repository.create_user(
        username=username, password_hash="x", role="student",
    )
    return row.id


def test_create_goal_and_idempotency():
    container = _container()
    user_id = _make_user(container)
    repo = container.student_goal_repository
    row, created = repo.create_goal(
        user_id=user_id, name="考研复习", category="academic",
        target_date="2026-12-20", idempotency_key="key-1",
        initial_progress_percent=10.0, milestone_count=3,
    )
    assert created is True
    assert row.category == "academic"
    assert row.status == "active"
    assert row.progress_percent == 10.0
    assert row.milestone_count == 3
    row2, created2 = repo.create_goal(
        user_id=user_id, name="考研复习", category="academic",
        idempotency_key="key-1",
    )
    assert created2 is False
    assert row2.goal_id == row.goal_id


def test_list_goals_and_user_isolation():
    container = _container()
    user_a = _make_user(container, "student_demo")
    user_b = _make_second_user(container, "student_b")
    repo = container.student_goal_repository
    repo.create_goal(user_id=user_a, name="目标A", category="academic")
    repo.create_goal(user_id=user_b, name="目标B", category="job_search")
    rows_a, total_a = repo.list_goals(user_id=user_a)
    rows_b, total_b = repo.list_goals(user_id=user_b)
    assert total_a == 1 and rows_a[0].category == "academic"
    assert total_b == 1 and rows_b[0].category == "job_search"


def test_update_goal():
    container = _container()
    user_id = _make_user(container)
    repo = container.student_goal_repository
    row, _ = repo.create_goal(user_id=user_id, name="考证", category="certificate")
    updated = repo.update_goal(
        user_id=user_id, goal_id=row.goal_id,
        name="考证(更新)", category="academic", milestone_count=5,
    )
    assert updated is not None
    assert updated.milestone_count == 5


def test_add_progress_and_idempotency():
    container = _container()
    user_id = _make_user(container)
    repo = container.student_goal_repository
    goal, _ = repo.create_goal(user_id=user_id, name="实习", category="internship")
    now = datetime.now(timezone.utc).isoformat()
    progress, created = repo.add_progress(
        user_id=user_id, goal_id=goal.goal_id,
        progress_percent=40.0, milestone_reached="m1",
        idempotency_key="pkey-1", occurred_at=now,
    )
    assert created is True
    assert progress.progress_percent == 40.0
    progress2, created2 = repo.add_progress(
        user_id=user_id, goal_id=goal.goal_id,
        progress_percent=80.0, idempotency_key="pkey-1", occurred_at=now,
    )
    assert created2 is False
    assert progress2.progress_percent == 40.0
    goal_after = repo.get_goal(user_id=user_id, goal_id=goal.goal_id)
    assert goal_after.progress_percent == 40.0


def test_archive_goal():
    container = _container()
    user_id = _make_user(container)
    repo = container.student_goal_repository
    goal, _ = repo.create_goal(user_id=user_id, name="竞赛", category="competition")
    archived = repo.archive_goal(user_id=user_id, goal_id=goal.goal_id)
    assert archived is not None
    assert archived.status == "archived"
    assert archived.archived_at is not None


def test_get_goal_isolation_returns_none_for_other_user():
    container = _container()
    user_a = _make_user(container, "student_demo")
    user_b = _make_second_user(container, "student_b")
    repo = container.student_goal_repository
    goal, _ = repo.create_goal(user_id=user_a, name="私有目标", category="personal_growth")
    assert repo.get_goal(user_id=user_b, goal_id=goal.goal_id) is None


def test_delete_for_user_cascade():
    container = _container()
    user_id = _make_user(container)
    repo = container.student_goal_repository
    repo.create_goal(user_id=user_id, name="目标1", category="academic")
    repo.create_goal(user_id=user_id, name="目标2", category="academic")
    deleted = repo.delete_for_user(user_id=user_id)
    assert deleted == 2
    rows, total = repo.list_goals(user_id=user_id)
    assert total == 0