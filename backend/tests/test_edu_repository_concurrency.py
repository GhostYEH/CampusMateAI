from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.database.sqlite_db import Database
from app.repositories.edu_repository import EduRepository


def _seed_school(database):
    with database.transaction() as conn:
        conn.execute("INSERT INTO users (id, username, password_hash, created_at, updated_at) VALUES ('user', 'user', 'hash', 'now', 'now')")
        conn.execute("INSERT INTO universities (id, name, created_at, updated_at) VALUES ('school', 'School', 'now', 'now')")


@pytest.mark.parametrize("kind", ["system", "config"])
def test_partial_edu_updates_use_one_locked_snapshot_across_database_instances(tmp_path, monkeypatch, kind):
    path = tmp_path / "edu-updates.db"
    first_db = Database(path)
    second_db = Database(path)
    _seed_school(first_db)
    first_repo = EduRepository(first_db)
    second_repo = EduRepository(second_db)
    if kind == "system":
        first_repo.upsert_system(university_id="school", system_key="main")
        lookup = "get_system_by_key"

        def update(repository, **changes):
            return repository.upsert_system(university_id="school", system_key="main", **changes)

        second_changes = {"auth_type": "form"}
    else:
        first_repo.upsert_config("school")
        lookup = "get_config_by_university"

        def update(repository, **changes):
            return repository.upsert_config("school", **changes)

        second_changes = {"login_method": "form"}
    first_read = threading.Event()
    resume_first = threading.Event()
    second_started = threading.Event()
    second_done = threading.Event()
    original_lookup = getattr(first_repo, lookup)

    def pause_after_lookup(*args):
        row = original_lookup(*args)
        first_read.set()
        if not resume_first.wait(timeout=5):
            raise TimeoutError("first writer release was not signaled")
        return row

    monkeypatch.setattr(first_repo, lookup, pause_after_lookup)

    def second_writer():
        second_started.set()
        result = update(second_repo, **second_changes)
        second_done.set()
        return result

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(update, first_repo, provider="zhengfang")
            assert first_read.wait(timeout=3)
            second = pool.submit(second_writer)
            assert second_started.wait(timeout=3)
            try:
                assert not second_done.wait(timeout=0.15), "second writer bypassed the read/merge write lock"
            finally:
                resume_first.set()
            first.result(timeout=5)
            stored = second.result(timeout=5)
        assert stored.provider == "zhengfang"
        assert getattr(stored, next(iter(second_changes))) == "form"
    finally:
        resume_first.set()
        first_db.dispose()
        second_db.dispose()


@pytest.mark.parametrize("memory", [True, False])
def test_nullable_system_binding_can_be_updated_without_overwriting_another_system(tmp_path, memory):
    database = Database(None if memory else tmp_path / "nullable-binding.db")
    try:
        _seed_school(database)
        repository = EduRepository(database)
        system = repository.upsert_system(university_id="school", system_key="main")
        scoped = repository.upsert_binding(
            user_id="user", university_id="school", provider="provider", edu_system_id=system.id,
            external_student_id="scoped-student",
        )
        legacy = repository.upsert_binding(user_id="user", university_id="school", provider="provider")
        updated = repository.upsert_binding(
            user_id="user", university_id="school", provider="provider", external_student_id="legacy-student",
        )
        assert updated.id == legacy.id
        assert updated.id != scoped.id
        assert updated.edu_system_id is None
        assert updated.external_student_id == "legacy-student"
        assert repository.get_binding_by_user("user", system.id).external_student_id == "scoped-student"
        assert len(repository.list_bindings_by_user("user")) == 2
    finally:
        database.dispose()
