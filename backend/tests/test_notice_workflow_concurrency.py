"""Separate SQLite connections must preserve independent concurrent updates."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
from threading import Barrier

import pytest

from app.database.sqlite_db import Database
from app.repositories.notice_workflow_repository import NoticeWorkflowRepository
from app.repositories.user_repository import UserRepository


@pytest.fixture
def workflows(tmp_path):
    path = tmp_path / "workflows.sqlite3"
    databases = [Database(path), Database(path)]
    repositories = [NoticeWorkflowRepository(db) for db in databases]
    user = UserRepository(databases[0]).create_user(username="concurrent-user", password_hash="unused")
    yield databases, repositories, user.id
    for db in databases:
        db.dispose()


def _synchronize_transactions(databases, monkeypatch):
    # Both requests reach the write phase together. A read before that phase
    # observes the same old value and exposes the former lost-update window.
    barrier = Barrier(len(databases))
    for db in databases:
        original = db.transaction

        @contextmanager
        def synchronized(original=original, **kwargs):
            # Forward keywords so callers can request an immediate transaction.
            barrier.wait(timeout=10)
            with original(**kwargs) as conn:
                yield conn

        monkeypatch.setattr(db, "transaction", synchronized)


def test_concurrent_step_completion_preserves_both_steps(workflows, monkeypatch):
    databases, repositories, user_id = workflows
    workflow = repositories[0].create_workflow(
        user_id=user_id, notice_id="notice", content_fingerprint="fingerprint",
    )
    repositories[0].update_workflow_interpretation(
        workflow.workflow_id, steps=[{"text": "first"}, {"text": "second"}],
    )
    _synchronize_transactions(databases, monkeypatch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(repo.mark_step_done, workflow.workflow_id, index)
                   for index, repo in enumerate(repositories)]
        for future in futures:
            future.result(timeout=15)
    stored = repositories[0].get_workflow(workflow.workflow_id)
    assert [step["done"] for step in json.loads(stored.steps_json)] == [True, True]


def test_concurrent_partial_source_preferences_do_not_overwrite_other_fields(workflows, monkeypatch):
    databases, repositories, user_id = workflows
    source = repositories[0].create_source(code="manual_input", display_name="Manual", kind="manual")
    _synchronize_transactions(databases, monkeypatch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(repositories[0].update_source_preference, source.source_id, user_id,
                        automation_enabled=True),
            pool.submit(repositories[1].update_source_preference, source.source_id, user_id,
                        display_name="Personal source"),
        ]
        for future in futures:
            future.result(timeout=15)
    stored = repositories[0].get_source_for_user(source.source_id, user_id)
    assert stored.automation_enabled is True
    assert stored.display_name == "Personal source"
    assert repositories[0].get_source(source.source_id).display_name == source.display_name
