import pytest

from app.database.sqlite_db import Database
from app.repositories.personal_task_repository import PersonalTaskRepository


@pytest.fixture
def repo():
    db = Database(None)
    with db.transaction() as conn:
        conn.executemany(
            "INSERT INTO users (id, username, password_hash, created_at, updated_at) "
            "VALUES (?, ?, 'test-hash', 't', 't')",
            [("first-user", "first-user"), ("second-user", "second-user")],
        )
    try:
        yield PersonalTaskRepository(db)
    finally:
        db.dispose()


@pytest.mark.parametrize(
    "method_name",
    ["list_completed_for_event_backfill", "list_chaoxing_for_event_backfill"],
)
def test_backfill_eligibility_user_isolation_and_stable_pagination(repo, method_name):
    expected = []
    for user_id in ("second-user", "first-user"):
        for source, status in (
            (None, "completed"), ("chaoxing", "completed"),
            ("chaoxing", "pending"), ("chaoxing", "deleted"),
            ("chaoxing", "completed-without-time"),
        ):
            task = repo.create_task(user_id=user_id, title=f"{source}:{status}", source=source)
            if status in {"completed", "deleted"}:
                task = repo.complete(task.id, user_id=user_id)
            elif status == "completed-without-time":
                task = repo.update_task(task.id, user_id=user_id, fields={"status": "completed"})
            if status == "deleted":
                repo.soft_delete(task.id, user_id=user_id)
            elif method_name == "list_completed_for_event_backfill":
                if status == "completed" and source is None:
                    expected.append(task)
            elif source == "chaoxing":
                expected.append(task)

    method = getattr(repo, method_name)
    filters = {"exclude_source": "chaoxing"} if method_name == "list_completed_for_event_backfill" else {}
    expected.sort(key=lambda task: (task.user_id, task.id))
    actual = []
    for page in range(1, len(expected) + 2):
        tasks, total = method(page=page, page_size=1, **filters)
        assert total == len(expected)
        actual.extend(task.id for task in tasks)
    assert actual == [task.id for task in expected]

    tasks, total = method(user_id="first-user", **filters)
    first_user_tasks = [task.id for task in expected if task.user_id == "first-user"]
    assert total == len(first_user_tasks)
    assert [task.id for task in tasks] == first_user_tasks
    assert method(user_id="missing-user", **filters) == ([], 0)


@pytest.mark.parametrize(
    "method_name",
    ["list_completed_for_event_backfill", "list_chaoxing_for_event_backfill"],
)
@pytest.mark.parametrize(
    "pagination,message",
    [
        ({"page": 0}, "page must be >= 1"),
        ({"page": -1}, "page must be >= 1"),
        ({"page_size": 0}, "page_size must stay within 1..100"),
        ({"page_size": 101}, "page_size must stay within 1..100"),
        ({"page": 0, "page_size": 0}, "page must be >= 1"),
    ],
)
def test_backfill_pagination_rejects_invalid_bounds(repo, method_name, pagination, message):
    with pytest.raises(ValueError, match=message):
        getattr(repo, method_name)(**pagination)


def test_noop_updates_preserve_existing_task_visibility(repo):
    task = repo.create_task(user_id="first-user", title="deleted task")
    repo.soft_delete(task.id, user_id="first-user")
    deleted = repo.get_task(task.id, user_id="first-user")
    for fields in ({}, {"user_id": "second-user"}):
        assert repo.update_task(task.id, user_id="first-user", fields=fields) == deleted
        assert repo.update_task(task.id, user_id="second-user", fields=fields) is None
        assert repo.update_task("missing-task", user_id="first-user", fields=fields) is None
