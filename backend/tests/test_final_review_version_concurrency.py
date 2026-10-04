"""Version allocation and approval binding must survive concurrent generation."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

import pytest

from app.api.routes.final_review import _persist_generated_plan
from app.database.sqlite_db import Database
from app.repositories.agent_runtime_repository import AgentRuntimeRepository
from app.repositories.final_review_repository import FinalReviewRepository
from app.services.agent_runtime.approval_gate import ApprovalGate
from app.services.agent_runtime.handlers.final_review import PLAN_ACTIVATE_TOOL
from app.services.agent_runtime.tool_gateway import build_request_hash


def _container(db):
    runtime = AgentRuntimeRepository(db)
    return SimpleNamespace(
        db=db,
        final_review_repository=FinalReviewRepository(db),
        agent_runtime_repository=runtime,
        agent_approval_gate=ApprovalGate(runtime),
    )


def _generate(container, campaign_id, key):
    run = container.agent_runtime_repository.create_job_with_run_and_event(
        user_id="student-1", job_kind="final_review_plan_generate",
        idempotency_key=key, input_ref={"campaign_id": campaign_id},
    )
    return _persist_generated_plan(
        container, campaign_id=campaign_id, user_id="student-1",
        run_id=run["run_id"], plan={"days": []},
        source_snapshot_id="snapshot-1", model_provider="deterministic",
        route_policy="reasoning_primary",
    )


def _campaign(container):
    with container.db.transaction() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
            "VALUES ('student-1', 'student-test', 'test-hash', 'student', ?, ?)",
            ("2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
        )
    return container.final_review_repository.create_campaign(
        user_id="student-1", exam_ids=["exam-1"], daily_capacity_minutes=60,
    ).campaign_id


def test_concurrent_generation_across_database_instances(tmp_path, monkeypatch):
    path = tmp_path / "plans.sqlite3"
    first = _container(Database(path))
    second = _container(Database(path))
    campaign_id = _campaign(first)
    entered = Event()
    release = Event()
    second_started = Event()
    original_require = first.agent_approval_gate.require

    def blocked_require(**kwargs):
        entered.set()
        assert release.wait(10)
        return original_require(**kwargs)

    monkeypatch.setattr(first.agent_approval_gate, "require", blocked_require)

    # Create both jobs before the write lock is held: the second caller must
    # contend specifically on allocation, not on its preliminary job insert.
    runs = [c.agent_runtime_repository.create_job_with_run_and_event(
        user_id="student-1", job_kind="final_review_plan_generate",
        idempotency_key=f"generate-{i}", input_ref={"campaign_id": campaign_id},
    ) for i, c in enumerate((first, second))]

    def generate(container, run_id, started=None):
        if started:
            started.set()
        return _persist_generated_plan(
            container, campaign_id=campaign_id, user_id="student-1", run_id=run_id,
            plan={"days": []}, source_snapshot_id="snapshot-1",
            model_provider="deterministic", route_policy="reasoning_primary",
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(generate, first, runs[0]["run_id"])
            try:
                assert entered.wait(10)
                b = pool.submit(generate, second, runs[1]["run_id"], second_started)
                assert second_started.wait(10)
                assert not b.done()
            finally:
                release.set()
            plans = [a.result(timeout=10), b.result(timeout=10)]
        assert [p.version for p in plans] == [1, 2]
        assert len(first.final_review_repository.list_plan_versions(
            campaign_id, user_id="student-1",
        )) == 2
        assert plans[0].approval_id != plans[1].approval_id
        for plan, run in zip(plans, runs):
            approval = first.agent_runtime_repository.get_approval(plan.approval_id)
            assert approval.run_id == run["run_id"]
            assert approval.tool_name == PLAN_ACTIVATE_TOOL
            assert approval.request_hash == build_request_hash(
                PLAN_ACTIVATE_TOOL,
                {"campaign_id": campaign_id, "version": plan.version,
                 "user_id": "student-1"},
            )
    finally:
        first.db.dispose()
        second.db.dispose()


@pytest.mark.parametrize("memory", [False, True])
def test_failed_plan_insert_rolls_back_approval_and_version(tmp_path, monkeypatch, memory):
    container = _container(Database(None if memory else tmp_path / "plans.sqlite3"))
    campaign_id = _campaign(container)
    repo = container.final_review_repository
    original_create = repo.create_plan_version

    def fail_after_insert(**kwargs):
        original_create(**kwargs)
        raise RuntimeError("failed after plan insert")

    try:
        with monkeypatch.context() as patch:
            patch.setattr(repo, "create_plan_version", fail_after_insert)
            with pytest.raises(RuntimeError, match="failed after plan insert"):
                _generate(container, campaign_id, "failed-generate")
        assert repo.list_plan_versions(campaign_id, user_id="student-1") == []
        with container.db.query() as conn:
            assert conn.execute("SELECT COUNT(*) FROM agent_approvals").fetchone()[0] == 0
        plan = _generate(container, campaign_id, "retry-generate")
        assert plan.version == 1
        assert container.agent_runtime_repository.get_approval(plan.approval_id)
    finally:
        container.db.dispose()
