from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from app.core.exceptions import AppException
from app.models.model_capability import ModelCapabilityRequest
from app.services.model_capability_registry import ModelCapabilityRegistry
from app.services.model_shadow_runner import ModelShadowRunner
from app.repositories.model_shadow_repository import ShadowIdempotencyConflict
from app.database.sqlite_db import Database
from test_phase4_learning_plans import _setup


def _request(user_id: str, request_id: str = "migration-request") -> ModelCapabilityRequest:
    return ModelCapabilityRequest(
        capability_name="read_only_tool_routing_v1", capability_version="v1", subject_user_id=user_id,
        input_payload={"intent_code": "read_state", "authorized_resource_type": "learner_state",
                       "candidate_read_tools": ["read_core_state"], "parameter_schema": {"projection_kind": "CORE"},
                       "resource_ownership": "current_user"},
        request_id=request_id, id_mode=True,
    )


def test_shadow_schema_is_created_idempotently_and_online_rows_are_user_scoped() -> None:
    client, container, headers, other_headers = _setup()
    user_id = container.user_repository.get_user_by_username("phase4_student").id
    other_id = container.user_repository.get_user_by_username("phase4_other").id
    runner = ModelShadowRunner(registry=ModelCapabilityRegistry(), enabled=False,
                               repository=container.model_shadow_runner.repository)
    first = asyncio.run(runner.run(_request(user_id)))
    second = asyncio.run(runner.run(_request(user_id)))
    assert first.input_digest == second.input_digest
    assert len(container.model_shadow_runner.repository.list_for_user(user_id=user_id)) == 1
    assert container.model_shadow_runner.repository.list_for_user(user_id=other_id) == []
    with container.db.query() as conn:
        names = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"model_shadow_runs", "model_shadow_results", "model_shadow_metric_records", "model_promotion_decisions"}.issubset(names)
    # Rebuilding the same in-memory application schema is the migration's
    # idempotency check; no duplicate table/constraint is introduced.
    assert client.get("/api/v1/learning-plans", headers=headers).status_code == 200


def test_same_shadow_request_with_changed_input_has_stable_conflict() -> None:
    _, container, _, _ = _setup()
    user_id = container.user_repository.get_user_by_username("phase4_student").id
    runner = ModelShadowRunner(registry=ModelCapabilityRegistry(), enabled=False,
                               repository=container.model_shadow_runner.repository)
    original = _request(user_id)
    result = asyncio.run(runner.run(original))
    changed = ModelCapabilityRequest(
        capability_name=original.capability_name, capability_version=original.capability_version,
        subject_user_id=user_id, input_payload={**original.input_payload, "intent_code": "read_tasks"},
        request_id=original.request_id, id_mode=True,
    )
    changed_result = asyncio.run(runner.run(changed))
    assert result.output_payload is not None and changed_result.output_payload is not None
    # The runner isolates persistence failures from its caller; the existing
    # record remains the only online row and is not overwritten.
    assert len(container.model_shadow_runner.repository.list_for_user(user_id=user_id)) == 1
    with pytest.raises(ShadowIdempotencyConflict):
        container.model_shadow_runner.repository.record_result(
            request=changed,
            result=replace(result, input_digest=ModelCapabilityRegistry.digest(changed.input_payload)),
        )


def test_user_shadow_rows_cascade_without_deleting_global_offline_metrics() -> None:
    _, container, _, _ = _setup()
    user_id = container.user_repository.create_user(
        username="shadow_cascade_student", password_hash="test-hash",
    ).id
    runner = ModelShadowRunner(registry=ModelCapabilityRegistry(), enabled=False,
                               repository=container.model_shadow_runner.repository)
    asyncio.run(runner.run(_request(user_id, request_id="cascade-request")))
    digest = container.model_shadow_runner.repository.record_offline_metrics(
        capability_name="read_only_tool_routing_v1", capability_version="v1",
        dataset_version="campusmate-lm-shadow-v1", evaluator_version="test", metrics={"safe": 1.0},
    )
    with container.db.transaction() as conn:
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        assert conn.execute("SELECT COUNT(*) FROM model_shadow_runs WHERE user_id=?", (user_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM model_shadow_metric_records WHERE metrics_digest=?", (digest,)).fetchone()[0] == 1


def test_database_without_phase5_tables_is_upgraded_idempotently(tmp_path) -> None:
    path = tmp_path / "legacy.db"
    legacy = Database(path)
    with legacy.transaction() as conn:
        conn.executescript("""
            DROP TABLE model_shadow_metric_records;
            DROP TABLE model_shadow_results;
            DROP TABLE model_shadow_runs;
            DROP TABLE model_promotion_decisions;
        """)
    legacy.dispose()
    upgraded = Database(path)
    with upgraded.query() as conn:
        names = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    upgraded.dispose()
    assert {"model_shadow_runs", "model_shadow_results", "model_shadow_metric_records", "model_promotion_decisions"}.issubset(names)
