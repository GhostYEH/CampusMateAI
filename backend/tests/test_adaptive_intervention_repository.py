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
    WRITABLE_INTERVENTION_STATUSES,
)
from app.repositories.adaptive_intervention_repository import AdaptiveInterventionRepository
from app.repositories.learner_control_repository import LearnerControlRepository
from app.schemas.adaptive_intervention import (
    OUTCOME_EVALUATOR_VERSION,
    InterventionEvaluation,
    StudentStateAssessment,
    StrategyDecision,
)

USER = "user_intv_1"
OTHER = "user_intv_2"


def _evaluation(
    intervention_id: str, *, digest: str, verdict: str = "PARTIALLY_EFFECTIVE",
    observation_status: str = "IN_PROGRESS", execution_signal: str = "IN_PROGRESS",
    plan_fidelity: str = "MATCHED",
) -> InterventionEvaluation:
    """构造一条契约自洽的评估，用于验证仓储的状态推进与幂等。"""
    return InterventionEvaluation(
        evaluation_id=f"inteval_{digest}",
        intervention_id=intervention_id, user_id=USER, goal_id="goal_math_final", plan_id="plan_1",
        as_of="2026-09-18T02:00:00+00:00", window_start=None, window_end=None,
        observation_status=observation_status, execution_signal=execution_signal,
        plan_fidelity=plan_fidelity, verdict=verdict,
        outcome_checks=[{
            "code": "TOTAL_WORKLOAD_REDUCED", "verdict": "REALIZED",
            "reason_code": "allocated_below_available",
            "evidence_refs": [{"kind": "PLAN_RUN", "reference_id": "lprun_1", "detail_code": "d"}],
        }],
        execution_signals={"planned_item_count": 3, "window_elapsed": observation_status == "COMPLETE"},
        confidence=0.8, data_quality="verified",
    )


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
    observing = repository.update_status(user_id=USER, intervention_id=row.intervention_id, status="OBSERVING")
    assert observing is not None and observing.status == "OBSERVING"
    cancelled = repository.update_status(user_id=USER, intervention_id=row.intervention_id, status="CANCELLED")
    assert cancelled is not None and cancelled.status == "CANCELLED"
    # 事务性重规划成功后，旧干预允许收口为 SUPERSEDED。
    superseded = repository.update_status(user_id=USER, intervention_id=row.intervention_id, status="SUPERSEDED")
    assert superseded is not None and superseded.status == "SUPERSEDED"
    with pytest.raises(ValueError):
        repository.update_status(user_id=USER, intervention_id=row.intervention_id, status="NOT_A_STATUS")


def test_status_enum_covers_lifecycle_and_reserved_states_stay_unwritable() -> None:
    """表约束覆盖完整生命周期；保留状态只能出现在约束里，不能出现在写入白名单里。"""
    for status in ("PROPOSED", "PLAN_GENERATED", "ACCEPTED", "EXECUTING", "CANCELLED", "OBSERVING", "EVALUATED"):
        assert status in INTERVENTION_STATUSES
        assert status in WRITABLE_INTERVENTION_STATUSES
    assert set(RESERVED_INTERVENTION_STATUSES) <= set(INTERVENTION_STATUSES)
    for reserved in RESERVED_INTERVENTION_STATUSES:
        assert reserved not in WRITABLE_INTERVENTION_STATUSES


def test_schema_check_rejects_unknown_status(db: Database, repository: AdaptiveInterventionRepository) -> None:
    """写入白名单是应用层防线，表约束是数据库层防线，两层都要在。"""
    _create(repository)
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as conn:
            conn.execute(
                "UPDATE adaptive_interventions SET status='NOT_A_STATUS' WHERE user_id=?", (USER,)
            )


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
        # 结果反馈与评估新增的列。
        "observation_started_at", "evaluated_at", "outcome_verdict", "evaluation_id",
    } <= columns


# 第一阶段真实上线过的旧约束：只允许 5 个状态，且没有评估相关列。
_LEGACY_INTERVENTION_DDL = """
CREATE TABLE adaptive_interventions (
    intervention_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    goal_id TEXT NOT NULL,
    plan_id TEXT,
    agent_job_id TEXT,
    agent_run_id TEXT,
    status TEXT NOT NULL CHECK(status IN ('PROPOSED','PLAN_GENERATED','ACCEPTED','EXECUTING','CANCELLED')),
    strategy_code TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    assessment_id TEXT NOT NULL,
    assessment_json TEXT NOT NULL DEFAULT '{}',
    strategy_json TEXT NOT NULL DEFAULT '{}',
    rationale_codes_json TEXT NOT NULL DEFAULT '[]',
    expected_outcomes_json TEXT NOT NULL DEFAULT '[]',
    baseline_core_run_id TEXT,
    baseline_academic_run_id TEXT,
    baseline_world_run_id TEXT,
    baseline_state_digest TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0 CHECK(confidence >= 0 AND confidence <= 1),
    warning_codes_json TEXT NOT NULL DEFAULT '[]',
    idempotency_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, idempotency_key)
);
CREATE INDEX idx_adaptive_interventions_user_created
    ON adaptive_interventions(user_id, created_at DESC, intervention_id DESC);
CREATE INDEX idx_adaptive_interventions_plan
    ON adaptive_interventions(user_id, plan_id);
"""


def _make_legacy_intervention_table(path: Path, *, intervention_id: str = "intv_legacy") -> None:
    """在空库里手工建出"第一阶段线上结构"的干预表并写入一行。"""
    connection = sqlite3.connect(path)
    try:
        connection.execute("DROP TABLE IF EXISTS adaptive_interventions")
        connection.executescript(_LEGACY_INTERVENTION_DDL)
        connection.execute(
            """INSERT INTO adaptive_interventions
               (intervention_id,user_id,goal_id,plan_id,status,strategy_code,strategy_version,
                assessment_id,baseline_state_digest,confidence,idempotency_key,created_at,updated_at)
               VALUES (?,'u1','goal_1','plan_1','PLAN_GENERATED','PACE_RECOVERY','v1','a','d',0.5,'k1','t','t')""",
            (intervention_id,),
        )
        connection.commit()
    finally:
        connection.close()


def _intervention_ddl(path: Path) -> str:
    connection = sqlite3.connect(path)
    try:
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='adaptive_interventions'"
        ).fetchone()
    finally:
        connection.close()
    return row[0] if row else ""


def test_legacy_status_check_is_widened_without_losing_rows(tmp_path: Path) -> None:
    """旧库的 status CHECK 不允许 OBSERVING/EVALUATED，必须重建表才能放宽。"""
    path = tmp_path / "legacy_status.db"
    seed = Database(path)
    with seed.transaction() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
            "VALUES ('u1','u1','h','student','t','t')"
        )
    _make_legacy_intervention_table(path)
    assert "'OBSERVING'" not in _intervention_ddl(path)  # 确认旧约束确实存在

    reopened = Database(path)
    ddl = _intervention_ddl(path)
    for status in ("OBSERVING", "EVALUATED", "SUPERSEDED"):
        assert f"'{status}'" in ddl
    with reopened.query() as conn:
        row = dict(conn.execute(
            "SELECT * FROM adaptive_interventions WHERE intervention_id='intv_legacy'"
        ).fetchone())
        # 数据保留，新增列取 DDL 默认值而不是被旧行伪造。
        assert row["plan_id"] == "plan_1" and row["strategy_code"] == "PACE_RECOVERY"
        assert row["evaluated_at"] is None and row["outcome_verdict"] is None
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE name='adaptive_interventions__legacy_status'"
        ).fetchone() is None
        # 重建后索引必须还在：先 DROP 原表就是为了避免旧索引名占位让建索引变成空操作。
        indexes = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_adaptive_interventions%'"
        )}
        assert {"idx_adaptive_interventions_user_created", "idx_adaptive_interventions_plan"} <= indexes
    # 放宽后的约束允许写入新状态。
    with reopened.transaction() as conn:
        conn.execute("UPDATE adaptive_interventions SET status='OBSERVING' WHERE intervention_id='intv_legacy'")
    with reopened.query() as conn:
        assert conn.execute(
            "SELECT status FROM adaptive_interventions WHERE intervention_id='intv_legacy'"
        ).fetchone()["status"] == "OBSERVING"


def test_status_check_migration_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "legacy_status_twice.db"
    seed = Database(path)
    with seed.transaction() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
            "VALUES ('u1','u1','h','student','t','t')"
        )
    _make_legacy_intervention_table(path)
    Database(path)
    Database(path)  # 第二次打开不应重复重建，也不应丢数据
    with Database(path).query() as conn:
        assert conn.execute("SELECT COUNT(*) AS c FROM adaptive_interventions").fetchone()["c"] == 1
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE name='adaptive_interventions__legacy_status'"
        ).fetchone() is None


def test_interrupted_status_migration_restores_from_stash(tmp_path: Path) -> None:
    """重建分多步落盘：若进程在"删了原表、还没回填"之间退出，暂存表是唯一数据副本。

    此时主表已经是新约束，重建分支不会再执行，所以必须显式回填暂存表。
    """
    path = tmp_path / "interrupted.db"
    db = Database(path)
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
            "VALUES ('u2','u2','h','student','t','t')"
        )
        conn.execute(
            """INSERT INTO adaptive_interventions
               (intervention_id,user_id,goal_id,plan_id,status,strategy_code,strategy_version,
                assessment_id,baseline_state_digest,confidence,idempotency_key,created_at,updated_at)
               VALUES ('intv_x','u2','g','p','PLAN_GENERATED','PACE_RECOVERY','v1','a','d',0.5,'kx','t','t')"""
        )
        # 造出中断现场：数据搬到暂存表，主表被清空。
        conn.execute("CREATE TABLE adaptive_interventions__legacy_status AS SELECT * FROM adaptive_interventions")
        conn.execute("DELETE FROM adaptive_interventions")

    reopened = Database(path)
    with reopened.query() as conn:
        row = conn.execute("SELECT * FROM adaptive_interventions").fetchone()
        assert row is not None and row["intervention_id"] == "intv_x"
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE name='adaptive_interventions__legacy_status'"
        ).fetchone() is None


def test_intervention_evaluations_table_exists_with_unique_digest(tmp_path: Path) -> None:
    """同一份观测只落一行：UNIQUE(intervention_id, evaluator_version, input_digest) 是约束而非约定。"""
    path = tmp_path / "eval_table.db"
    db = Database(path)
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
            "VALUES ('u3','u3','h','student','t','t')"
        )
        conn.execute(
            """INSERT INTO adaptive_interventions
               (intervention_id,user_id,goal_id,status,strategy_code,strategy_version,
                assessment_id,baseline_state_digest,confidence,idempotency_key,created_at,updated_at)
               VALUES ('intv_y','u3','g','PLAN_GENERATED','PACE_RECOVERY','v1','a','d',0.5,'ky','t','t')"""
        )
        values = (
            "inteval_1", "intv_y", "u3", "g", None, "adaptive-intervention-outcome-v1", "dig",
            "IN_PROGRESS", "IN_PROGRESS", "MATCHED", "PARTIALLY_EFFECTIVE", "{}", "[]", "t", "t",
        )
        insert = (
            """INSERT INTO intervention_evaluations
               (evaluation_id,intervention_id,user_id,goal_id,plan_id,evaluator_version,input_digest,
                observation_status,execution_signal,plan_fidelity,verdict,evaluation_json,
                warning_codes_json,as_of,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
        )
        conn.execute(insert, values)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(insert, ("inteval_2", *values[1:]))


def test_evaluated_status_is_not_downgraded_by_a_later_observation(
    repository: AdaptiveInterventionRepository,
) -> None:
    """已经评估完成的记录不会因为一次更早的观测而回退到 OBSERVING。"""
    row = _create(repository)
    repository.bind_plan(user_id=USER, intervention_id=row.intervention_id, plan_id="plan_1")

    final = _evaluation(row.intervention_id, digest="d_final", verdict="EFFECTIVE",
                        observation_status="COMPLETE", execution_signal="COMPLETED")
    saved, created = repository.save_evaluation(
        user_id=USER, intervention_id=row.intervention_id, evaluation=final,
        input_digest="d_final", status="EVALUATED",
    )
    assert created is True
    current = repository.get(user_id=USER, intervention_id=row.intervention_id)
    assert current is not None and current.status == "EVALUATED"
    assert current.evaluated_at is not None and current.outcome_verdict == "EFFECTIVE"
    assert current.evaluation_id == saved.evaluation_id

    earlier = _evaluation(row.intervention_id, digest="d_earlier")
    repository.save_evaluation(
        user_id=USER, intervention_id=row.intervention_id, evaluation=earlier,
        input_digest="d_earlier", status="OBSERVING",
    )
    current = repository.get(user_id=USER, intervention_id=row.intervention_id)
    assert current is not None
    assert current.status == "EVALUATED"  # 不回退
    assert current.outcome_verdict == "EFFECTIVE"  # 弱 OBSERVING 不能覆盖最终结论
    assert current.evaluated_at is not None
    assert len(repository.list_evaluations(user_id=USER, intervention_id=row.intervention_id)) == 2
    # 同一份观测重复落库：复用既有行，不产生第三条。
    _, created_again = repository.save_evaluation(
        user_id=USER, intervention_id=row.intervention_id, evaluation=earlier,
        input_digest="d_earlier", status="OBSERVING",
    )
    assert created_again is False
    assert len(repository.list_evaluations(user_id=USER, intervention_id=row.intervention_id)) == 2


def test_cancelled_intervention_is_never_advanced_by_save_evaluation(
    repository: AdaptiveInterventionRepository,
) -> None:
    row = _create(repository)
    repository.update_status(user_id=USER, intervention_id=row.intervention_id, status="CANCELLED")
    repository.save_evaluation(
        user_id=USER, intervention_id=row.intervention_id,
        evaluation=_evaluation(row.intervention_id, digest="d_cancelled"),
        input_digest="d_cancelled", status="OBSERVING",
    )
    current = repository.get(user_id=USER, intervention_id=row.intervention_id)
    assert current is not None and current.status == "CANCELLED"
    assert current.outcome_verdict is None and current.observation_started_at is None


def test_save_evaluation_rejects_unknown_target_status(
    repository: AdaptiveInterventionRepository,
) -> None:
    row = _create(repository)
    with pytest.raises(ValueError):
        repository.save_evaluation(
            user_id=USER, intervention_id=row.intervention_id,
            evaluation=_evaluation(row.intervention_id, digest="d_bad"),
            input_digest="d_bad", status="SUPERSEDED",
        )


def test_evaluations_are_user_scoped(repository: AdaptiveInterventionRepository) -> None:
    row = _create(repository)
    repository.save_evaluation(
        user_id=USER, intervention_id=row.intervention_id,
        evaluation=_evaluation(row.intervention_id, digest="d_scope"),
        input_digest="d_scope", status="OBSERVING",
    )
    assert repository.get_evaluation(user_id=OTHER, intervention_id=row.intervention_id) is None
    assert repository.find_evaluation_by_digest(
        user_id=OTHER, intervention_id=row.intervention_id,
        evaluator_version=OUTCOME_EVALUATOR_VERSION, input_digest="d_scope",
    ) is None
    assert repository.list_evaluations(user_id=OTHER, intervention_id=row.intervention_id) == []


def test_deletion_scopes_also_remove_evaluations(db: Database) -> None:
    """删除范围不能留下指向已删干预记录的评估行。"""
    repository = AdaptiveInterventionRepository(db)
    control = LearnerControlRepository(db)
    row = _create(repository)
    repository.save_evaluation(
        user_id=USER, intervention_id=row.intervention_id,
        evaluation=_evaluation(row.intervention_id, digest="d_delete"),
        input_digest="d_delete", status="OBSERVING",
    )
    assert len(repository.list_evaluations(user_id=USER, intervention_id=row.intervention_id)) == 1
    control.delete_plans_only(user_id=USER)
    assert repository.list_evaluations(user_id=USER, intervention_id=row.intervention_id) == []
    with db.query() as conn:
        assert conn.execute("SELECT COUNT(*) AS c FROM intervention_evaluations").fetchone()["c"] == 0

    again = _create(repository, key="run:run_3")
    repository.save_evaluation(
        user_id=USER, intervention_id=again.intervention_id,
        evaluation=_evaluation(again.intervention_id, digest="d_delete_2"),
        input_digest="d_delete_2", status="OBSERVING",
    )
    control.delete_all_learner_model_data(user_id=USER)
    with db.query() as conn:
        assert conn.execute("SELECT COUNT(*) AS c FROM intervention_evaluations").fetchone()["c"] == 0


def test_state_only_scope_keeps_evaluations(db: Database) -> None:
    repository = AdaptiveInterventionRepository(db)
    control = LearnerControlRepository(db)
    row = _create(repository)
    repository.save_evaluation(
        user_id=USER, intervention_id=row.intervention_id,
        evaluation=_evaluation(row.intervention_id, digest="d_state_only"),
        input_digest="d_state_only", status="OBSERVING",
    )
    control.delete_state_only(user_id=USER)
    assert len(repository.list_evaluations(user_id=USER, intervention_id=row.intervention_id)) == 1


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
