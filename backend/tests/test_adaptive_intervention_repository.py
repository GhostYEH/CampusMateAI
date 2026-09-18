"""AdaptiveInterventionRepository —— 幂等、隔离、schema 安全与旧库迁移。"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from adaptive_intervention_helpers import sample_assessment, sample_strategy
from app.database.sqlite_db import Database
from app.models.adaptive_intervention import (
    INTERVENTION_STATUSES,
    RESERVED_INTERVENTION_STATUSES,
)
from app.repositories.adaptive_intervention_repository import AdaptiveInterventionRepository
from app.repositories.learner_control_repository import LearnerControlRepository
from app.schemas.adaptive_intervention import StudentStateAssessment, StrategyDecision

USER = "user_intv_1"
OTHER = "user_intv_2"


@pytest.fixture()
def db() -> Database:
    """内存库 + 两个真实用户：`adaptive_interventions.user_id` 有外键，生产环境用户一定存在。"""
    database = Database(None)
    with database.transaction() as conn:
        for index, user_id in enumerate((USER, OTHER), start=1):
            conn.execute(
                "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
                "VALUES (?, ?, 'h', 'student', 't', 't')",
                (user_id, f"user_intv_{index}"),
            )
    return database


@pytest.fixture()
def repository(db: Database) -> AdaptiveInterventionRepository:
    return AdaptiveInterventionRepository(db)


def _create(repository: AdaptiveInterventionRepository, *, user_id: str = USER, key: str = "run:run_1",
            letter: str = "a", **overrides):
    assessment, strategy = sample_strategy(letter)
    payload = dict(
        user_id=user_id, goal_id="goal_math_final", assessment=assessment, strategy=strategy,
        baseline_state_digest="digest_abc", idempotency_key=key,
    )
    payload.update(overrides)
    return repository.create(**payload)


def _table_exists(path: Path, name: str) -> bool:
    connection = sqlite3.connect(path)
    try:
        return connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone() is not None
    finally:
        connection.close()


def test_create_get_and_list(repository: AdaptiveInterventionRepository) -> None:
    row = _create(repository)
    assert row.intervention_id.startswith("intv_")
    assert row.status == "PROPOSED"
    assert row.plan_id is None
    assert row.strategy_code == "WORKLOAD_REDUCTION"
    assert row.baseline_core_run_id == "lrun_a_core"

    fetched = repository.get(user_id=USER, intervention_id=row.intervention_id)
    assert fetched is not None and fetched.intervention_id == row.intervention_id

    for index in range(5):
        _create(repository, key=f"run:run_extra_{index}")
    rows, total = repository.list_interventions(user_id=USER, page=1, page_size=2)
    assert total == 6
    assert len(rows) == 2
    rows2, _ = repository.list_interventions(user_id=USER, page=3, page_size=2)
    assert len(rows2) == 2
    assert {r.intervention_id for r in rows}.isdisjoint({r.intervention_id for r in rows2})


def test_user_isolation(repository: AdaptiveInterventionRepository) -> None:
    row = _create(repository)
    assert repository.get(user_id=OTHER, intervention_id=row.intervention_id) is None
    rows, total = repository.list_interventions(user_id=OTHER, page=1, page_size=20)
    assert rows == [] and total == 0
    # 同一幂等键在另一个用户下是独立记录。
    other_row = _create(repository, user_id=OTHER)
    assert other_row.intervention_id != row.intervention_id


def test_idempotent_create_returns_same_record(repository: AdaptiveInterventionRepository) -> None:
    first = _create(repository)
    second = _create(repository)
    assert second.intervention_id == first.intervention_id
    assert repository.count_for_user(user_id=USER) == 1


def test_idempotency_key_is_unique_in_schema(db: Database, repository: AdaptiveInterventionRepository) -> None:
    _create(repository)
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as conn:
            conn.execute(
                """INSERT INTO adaptive_interventions
                   (intervention_id,user_id,goal_id,status,strategy_code,strategy_version,assessment_id,
                    baseline_state_digest,idempotency_key,created_at,updated_at)
                   VALUES ('intv_dup',?,'g','PROPOSED','PACE_RECOVERY','v1','a','d','run:run_1','t','t')""",
                (USER,),
            )


def test_bind_plan_and_status_transitions(repository: AdaptiveInterventionRepository) -> None:
    row = _create(repository)
    bound = repository.bind_plan(user_id=USER, intervention_id=row.intervention_id, plan_id="plan_1")
    assert bound is not None
    assert bound.plan_id == "plan_1" and bound.status == "PLAN_GENERATED"
    cancelled = repository.update_status(user_id=USER, intervention_id=row.intervention_id, status="CANCELLED")
    assert cancelled is not None and cancelled.status == "CANCELLED"
    with pytest.raises(ValueError):
        repository.update_status(user_id=USER, intervention_id=row.intervention_id, status="OBSERVING")


def test_status_enum_excludes_reserved_second_phase_states() -> None:
    assert "PROPOSED" in INTERVENTION_STATUSES
    assert "PLAN_GENERATED" in INTERVENTION_STATUSES
    for reserved in RESERVED_INTERVENTION_STATUSES:
        assert reserved not in INTERVENTION_STATUSES


def test_json_payloads_are_schema_validated(repository: AdaptiveInterventionRepository) -> None:
    assessment, strategy = sample_strategy("a")
    # 合法模型 + 绕过校验的字段替换：模拟"调用方手里是一个结构正确但取值越界的模型"。
    tampered = assessment.model_copy(update={"overall_confidence": 5.0})
    assert tampered.overall_confidence == 5.0  # 确认确实越界且未被 pydantic 纠正
    with pytest.raises(ValidationError):
        repository.create(
            user_id=USER, goal_id="g", assessment=tampered,
            strategy=strategy, baseline_state_digest="d", idempotency_key="run:bad",
        )
    assert repository.count_for_user(user_id=USER) == 0


def test_stored_json_round_trips_through_schema(repository: AdaptiveInterventionRepository) -> None:
    row = _create(repository)
    assessment = StudentStateAssessment.model_validate(json.loads(row.assessment_json))
    strategy = StrategyDecision.model_validate(json.loads(row.strategy_json))
    assert assessment.assessment_id == sample_assessment("a").assessment_id
    assert strategy.strategy_code == "WORKLOAD_REDUCTION"
    # 落库内容只包含有限字段，不含原始证据正文或聊天内容。
    for forbidden in ("raw_content", "chat", "prompt", "answer_text"):
        assert forbidden not in row.assessment_json


def test_baseline_state_digest_and_run_references_are_persisted(
    repository: AdaptiveInterventionRepository,
) -> None:
    row = _create(repository)
    assert row.baseline_core_run_id == "lrun_a_core"
    assert row.baseline_academic_run_id == "lrun_a_academic"
    assert row.baseline_world_run_id == "lrun_a_world"
    assert row.baseline_state_digest


def test_legacy_database_is_migrated_idempotently(tmp_path: Path) -> None:
    """旧库缺少 adaptive_interventions 表时，启动必须补齐且可重复执行。"""
    path = tmp_path / "legacy_app.db"
    db = Database(path)
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
            "VALUES ('u1','u1','h','student','t','t')"
        )
        conn.execute("DROP TABLE adaptive_interventions")

    # 用裸 sqlite3 检查，避免 `Database(...)` 的构造本身就完成建表而看不出旧库状态。
    assert not _table_exists(path, "adaptive_interventions")  # 模拟旧库：表确实不存在
    reopened = Database(path)
    assert _table_exists(path, "adaptive_interventions")
    with reopened.query() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    assert count == 1  # 迁移是纯增量的，不动既有数据
    assert _table_exists(path, "adaptive_interventions")  # 再开一次仍然幂等


def test_migrated_table_has_the_expected_columns(tmp_path: Path) -> None:
    path = tmp_path / "old_app.db"
    db = Database(path)
    with db.transaction() as conn:
        conn.execute("DROP TABLE adaptive_interventions")
    reopened = Database(path)
    with reopened.query() as conn:
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(adaptive_interventions)")}
    assert {
        "intervention_id", "user_id", "goal_id", "plan_id", "status", "strategy_code",
        "strategy_version", "assessment_json", "strategy_json", "baseline_core_run_id",
        "baseline_state_digest", "idempotency_key", "created_at", "updated_at",
    } <= columns


def test_learner_model_deletion_scopes_remove_interventions(db: Database) -> None:
    repository = AdaptiveInterventionRepository(db)
    control = LearnerControlRepository(db)
    _create(repository)
    assert repository.count_for_user(user_id=USER) == 1
    control.delete_plans_only(user_id=USER)
    assert repository.count_for_user(user_id=USER) == 0

    _create(repository, key="run:run_2")
    control.delete_all_learner_model_data(user_id=USER)
    assert repository.count_for_user(user_id=USER) == 0


def test_state_only_scope_keeps_interventions(db: Database) -> None:
    """STATE_ONLY 只清状态，不应顺带删掉计划域记录。"""
    repository = AdaptiveInterventionRepository(db)
    control = LearnerControlRepository(db)
    _create(repository)
    control.delete_state_only(user_id=USER)
    assert repository.count_for_user(user_id=USER) == 1
