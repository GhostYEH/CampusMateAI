from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier
from types import SimpleNamespace

import pytest

from app.core.exceptions import LearningPlanIdempotencyConflict
from app.database.sqlite_db import Database
from app.repositories.learning_plan_repository import LearningPlanRepository
from app.repositories.personal_task_repository import PersonalTaskRepository
from app.repositories.user_repository import UserRepository
from app.services.learning_planner_service import LearningPlannerService


def _services(tmp_path):
    path = tmp_path / "plans.sqlite3"
    databases = [Database(path), Database(path)]
    user = UserRepository(databases[0]).create_user(
        username="concurrent_planner", password_hash="unused-test-hash",
    )
    PersonalTaskRepository(databases[0]).create_task(user_id=user.id, title="Study")
    projection = SimpleNamespace(
        run_id="fixed-state", input_digest="fixed-digest", snapshots=[], warnings=[],
    )
    state = SimpleNamespace(
        project_user=lambda *args, **kwargs: projection,
        project_academic=lambda *args, **kwargs: projection,
        project_world=lambda *args, **kwargs: projection,
    )
    services = [LearningPlannerService(
        repository=LearningPlanRepository(db), state_service=state,
        state_repository=None, task_repository=PersonalTaskRepository(db),
        content_repository=None,
    ) for db in databases]
    return services, user.id


@pytest.mark.parametrize("minutes", [(60, 60), (60, 90)])
def test_concurrent_generation_rechecks_key_across_database_instances(tmp_path, monkeypatch, minutes):
    services, user_id = _services(tmp_path)
    barrier = Barrier(2)
    for service in services:
        original = service.repository.find_by_idempotency_key

        def find_after_both_read(*, _original=original, **kwargs):
            result = _original(**kwargs)
            assert result is None
            barrier.wait(timeout=10)
            return result

        monkeypatch.setattr(service.repository, "find_by_idempotency_key", find_after_both_read)

    def generate(index):
        try:
            return services[index].generate(
                user_id=user_id, available_minutes=minutes[index],
                idempotency_key="shared-key", force_new=True,
                as_of=datetime(2026, 10, 4, 12, tzinfo=timezone.utc),
            )
        except LearningPlanIdempotencyConflict as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(generate, range(2)))

    conflicts = [result for result in results if isinstance(result, LearningPlanIdempotencyConflict)]
    if minutes[0] == minutes[1]:
        assert not conflicts
        assert results[0] == results[1]
        assert results[0].items and results[0].items[0].evidence
    else:
        assert len(conflicts) == 1
        assert conflicts[0].code == "LEARNING_PLAN_IDEMPOTENCY_CONFLICT"
    with services[0].repository._db.query() as conn:
        assert conn.execute("SELECT COUNT(*) FROM learning_plans").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM learning_plan_runs").fetchone()[0] == 1


def test_repository_replay_preserves_executed_items_and_targets(tmp_path):
    services, user_id = _services(tmp_path)
    first = services[0].generate(
        user_id=user_id, available_minutes=60, idempotency_key="executed-key",
        as_of=datetime(2026, 10, 4, 12, tzinfo=timezone.utc),
    )
    repository = services[0].repository
    repository.execute_atomic(
        plan_id=first.plan_id, user_id=user_id, task_repository=services[0].task_repository,
    )
    with repository._db.query() as conn:
        stored = conn.execute(
            "SELECT * FROM learning_plan_runs WHERE run_id=?", (first.run.run_id,),
        ).fetchone()
    replay = services[1].repository.create_plan(
        user_id=user_id,
        run={"idempotency_key": stored["idempotency_key"], "input_digest": stored["input_digest"]},
        items=[],
    )
    expected = repository.get_plan(first.plan_id, user_id=user_id)
    assert replay == expected
    assert replay.status == "EXECUTED"
    assert replay.items[0].execution_status == "SUCCEEDED"
    assert replay.items[0].execution_task_id
    assert services[1].task_repository.get_task(replay.items[0].execution_task_id, user_id=user_id)


def test_generation_replay_does_not_repeat_supersession(tmp_path, monkeypatch):
    services, user_id = _services(tmp_path)
    arguments = {
        "user_id": user_id, "available_minutes": 60,
        "as_of": datetime(2026, 10, 4, 12, tzinfo=timezone.utc), "force_new": True,
    }
    original = services[0].generate(**arguments)
    successor = services[0].generate(
        **arguments, idempotency_key="successor-key", supersedes_plan_id=original.plan_id,
    )
    # Emulate the early read that completed before the concurrent writer committed.
    monkeypatch.setattr(services[1].repository, "find_by_idempotency_key", lambda **kwargs: None)
    replay = services[1].generate(
        **arguments, idempotency_key="successor-key", supersedes_plan_id=original.plan_id,
    )
    assert replay == successor
    assert replay.supersedes_plan_id == original.plan_id
    assert services[0].repository.get_plan(original.plan_id, user_id=user_id).superseded_by_plan_id == replay.plan_id
