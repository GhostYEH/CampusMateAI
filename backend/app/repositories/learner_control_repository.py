"""Phase 6A: 学生世界模型控制的数据访问层。

涵盖状态纠正、数据源控制、世界模型删除和安全导出摘要的 SQL 操作。
所有查询都以 user_id 为隔离边界，跨用户资源不可枚举。
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ..database.sqlite_db import Database


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _uuid() -> str:
    return uuid.uuid4().hex


# ===== 行模型 =====


@dataclass(frozen=True)
class CorrectionRow:
    correction_id: str
    user_id: str
    projection_kind: str
    projection_scope: str
    scope_type: str
    scope_id: str
    state_type: str
    target_snapshot_id: str
    correction_type: str
    reason_code: str
    status: str
    created_at: datetime
    revoked_at: Optional[datetime]
    correction_version: int
    idempotency_key: str


@dataclass(frozen=True)
class DataSourceControlRow:
    source_key: str
    user_id: str
    status: str
    updated_at: datetime


@dataclass(frozen=True)
class DeleteRequestRow:
    request_id: str
    user_id: str
    scope: str
    status: str
    before_counts: dict[str, int]
    after_counts: dict[str, int]
    created_at: datetime
    completed_at: Optional[datetime]
    idempotency_key: str


# ===== 默认数据源 =====

DEFAULT_SOURCES = (
    "CORE_STUDY",
    "PERSONAL_TASK",
    "CHAOXING",
    "EDU",
    "MODEL_SHADOW",
    "PROACTIVE_SUGGESTIONS",
)


class LearnerControlRepository:
    """学生世界模型控制的 SQL 边界层。"""

    def __init__(self, db: Database) -> None:
        self._db = db

    # ===== 状态纠正 =====

    def create_correction(
        self,
        *,
        user_id: str,
        projection_kind: str,
        projection_scope: str,
        scope_type: str,
        scope_id: str,
        state_type: str,
        target_snapshot_id: str,
        correction_type: str,
        reason_code: str,
        idempotency_key: str,
    ) -> CorrectionRow:
        """幂等创建纠正记录。

        幂等键冲突时：
        - 若请求完全一致 → 返回已有记录
        - 若请求语义不同 → 抛 Conflict
        """
        correction_id = _uuid()
        now = _utc_now()
        with self._db.transaction() as conn:
            existing = conn.execute(
                "SELECT * FROM learner_state_corrections WHERE user_id=? AND idempotency_key=?",
                (user_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if (
                    existing["projection_kind"] == projection_kind
                    and existing["projection_scope"] == projection_scope
                    and existing["scope_type"] == scope_type
                    and existing["scope_id"] == scope_id
                    and existing["state_type"] == state_type
                    and existing["target_snapshot_id"] == target_snapshot_id
                    and existing["correction_type"] == correction_type
                    and existing["reason_code"] == reason_code
                ):
                    return self._row_to_correction(existing)
                from ..core.exceptions import LearnerCorrectionConflict
                raise LearnerCorrectionConflict()
            version = conn.execute(
                "SELECT COUNT(*) AS c FROM learner_state_corrections WHERE user_id=? AND target_snapshot_id=?",
                (user_id, target_snapshot_id),
            ).fetchone()["c"] + 1
            conn.execute(
                """INSERT INTO learner_state_corrections
                (correction_id, user_id, projection_kind, projection_scope, scope_type, scope_id,
                 state_type, target_snapshot_id, correction_type, reason_code, status,
                 created_at, revoked_at, correction_version, idempotency_key)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    correction_id, user_id, projection_kind, projection_scope, scope_type, scope_id,
                    state_type, target_snapshot_id, correction_type, reason_code, "ACTIVE",
                    now.isoformat(), None, version, idempotency_key,
                ),
            )
            row = conn.execute(
                "SELECT * FROM learner_state_corrections WHERE correction_id=?",
                (correction_id,),
            ).fetchone()
            return self._row_to_correction(row)

    def list_corrections(
        self,
        *,
        user_id: str,
        page: int = 1,
        page_size: int = 50,
        status: Optional[str] = None,
    ) -> tuple[list[CorrectionRow], int]:
        offset = (page - 1) * page_size
        with self._db.transaction() as conn:
            where = "WHERE user_id=?"
            params: list[Any] = [user_id]
            if status is not None:
                where += " AND status=?"
                params.append(status)
            total = conn.execute(
                f"SELECT COUNT(*) AS c FROM learner_state_corrections {where}", params
            ).fetchone()["c"]
            rows = conn.execute(
                f"""SELECT * FROM learner_state_corrections {where}
                ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                [*params, page_size, offset],
            ).fetchall()
            return [self._row_to_correction(r) for r in rows], total

    def get_correction(self, *, user_id: str, correction_id: str) -> Optional[CorrectionRow]:
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM learner_state_corrections WHERE user_id=? AND correction_id=?",
                (user_id, correction_id),
            ).fetchone()
            return self._row_to_correction(row) if row else None

    def revoke_correction(self, *, user_id: str, correction_id: str) -> CorrectionRow:
        """撤销纠正。幂等：已撤销则返回已有记录。"""
        from ..core.exceptions import LearnerCorrectionAlreadyRevoked, LearnerCorrectionNotFound
        now = _utc_now()
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM learner_state_corrections WHERE user_id=? AND correction_id=?",
                (user_id, correction_id),
            ).fetchone()
            if row is None:
                raise LearnerCorrectionNotFound()
            if row["status"] == "REVOKED":
                return self._row_to_correction(row)
            conn.execute(
                "UPDATE learner_state_corrections SET status='REVOKED', revoked_at=? WHERE correction_id=?",
                (now.isoformat(), correction_id),
            )
            row = conn.execute(
                "SELECT * FROM learner_state_corrections WHERE correction_id=?",
                (correction_id,),
            ).fetchone()
            return self._row_to_correction(row)

    def has_active_corrections_for_snapshot(self, *, user_id: str, snapshot_id: str) -> bool:
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT 1 FROM learner_state_corrections WHERE user_id=? AND target_snapshot_id=? AND status='ACTIVE' LIMIT 1",
                (user_id, snapshot_id),
            ).fetchone()
            return row is not None

    def list_active_corrections(self, *, user_id: str) -> list[CorrectionRow]:
        with self._db.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM learner_state_corrections WHERE user_id=? AND status='ACTIVE' ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
            return [self._row_to_correction(r) for r in rows]

    @staticmethod
    def _row_to_correction(row: sqlite3.Row) -> CorrectionRow:
        return CorrectionRow(
            correction_id=row["correction_id"],
            user_id=row["user_id"],
            projection_kind=row["projection_kind"],
            projection_scope=row["projection_scope"],
            scope_type=row["scope_type"],
            scope_id=row["scope_id"],
            state_type=row["state_type"],
            target_snapshot_id=row["target_snapshot_id"],
            correction_type=row["correction_type"],
            reason_code=row["reason_code"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            revoked_at=datetime.fromisoformat(row["revoked_at"]) if row["revoked_at"] else None,
            correction_version=row["correction_version"],
            idempotency_key=row["idempotency_key"],
        )

    # ===== 数据源控制 =====

    def list_source_controls(self, *, user_id: str) -> list[DataSourceControlRow]:
        with self._db.transaction() as conn:
            existing = {
                r["source_key"]: r
                for r in conn.execute(
                    "SELECT * FROM learner_data_source_controls WHERE user_id=?",
                    (user_id,),
                ).fetchall()
            }
            now = _utc_now().isoformat()
            result: list[DataSourceControlRow] = []
            for src in DEFAULT_SOURCES:
                if src in existing:
                    result.append(self._row_to_source_control(existing[src]))
                else:
                    conn.execute(
                        "INSERT INTO learner_data_source_controls (source_key, user_id, status, updated_at) VALUES (?,?,?,?)",
                        (src, user_id, "ENABLED", now),
                    )
                    result.append(DataSourceControlRow(source_key=src, user_id=user_id, status="ENABLED", updated_at=_utc_now()))
            return result

    def get_source_control(self, *, user_id: str, source_key: str) -> Optional[DataSourceControlRow]:
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM learner_data_source_controls WHERE user_id=? AND source_key=?",
                (user_id, source_key),
            ).fetchone()
            if row:
                return self._row_to_source_control(row)
            return None

    def upsert_source_control(
        self,
        *,
        user_id: str,
        source_key: str,
        status: str,
    ) -> DataSourceControlRow:
        now = _utc_now()
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM learner_data_source_controls WHERE user_id=? AND source_key=?",
                (user_id, source_key),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO learner_data_source_controls (source_key, user_id, status, updated_at) VALUES (?,?,?,?)",
                    (source_key, user_id, status, now.isoformat()),
                )
            else:
                conn.execute(
                    "UPDATE learner_data_source_controls SET status=?, updated_at=? WHERE user_id=? AND source_key=?",
                    (status, now.isoformat(), user_id, source_key),
                )
            row = conn.execute(
                "SELECT * FROM learner_data_source_controls WHERE user_id=? AND source_key=?",
                (user_id, source_key),
            ).fetchone()
            return self._row_to_source_control(row)

    def is_source_paused(self, *, user_id: str, source_key: str) -> bool:
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT status FROM learner_data_source_controls WHERE user_id=? AND source_key=?",
                (user_id, source_key),
            ).fetchone()
            return row is not None and row["status"] in ("PAUSED", "DISCONNECTED", "DELETE_REQUESTED")

    @staticmethod
    def _row_to_source_control(row: sqlite3.Row) -> DataSourceControlRow:
        return DataSourceControlRow(
            source_key=row["source_key"],
            user_id=row["user_id"],
            status=row["status"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # ===== 世界模型删除 =====

    def count_learner_model_data(self, *, user_id: str) -> dict[str, int]:
        """统计学生模型派生数据，不返回原文。"""
        with self._db.transaction() as conn:
            counts: dict[str, int] = {}
            counts["projection_runs"] = conn.execute(
                "SELECT COUNT(*) AS c FROM learner_state_projection_runs WHERE user_id=?", (user_id,)
            ).fetchone()["c"]
            counts["snapshots"] = conn.execute(
                "SELECT COUNT(*) AS c FROM learner_state_snapshots WHERE run_id IN (SELECT run_id FROM learner_state_projection_runs WHERE user_id=?)",
                (user_id,),
            ).fetchone()["c"]
            counts["evidence"] = conn.execute(
                "SELECT COUNT(*) AS c FROM learner_state_evidence WHERE snapshot_id IN (SELECT snapshot_id FROM learner_state_snapshots WHERE run_id IN (SELECT run_id FROM learner_state_projection_runs WHERE user_id=?))",
                (user_id,),
            ).fetchone()["c"]
            counts["learner_events"] = conn.execute(
                "SELECT COUNT(*) AS c FROM learner_events WHERE user_id=?", (user_id,)
            ).fetchone()["c"]
            counts["corrections"] = conn.execute(
                "SELECT COUNT(*) AS c FROM learner_state_corrections WHERE user_id=?", (user_id,)
            ).fetchone()["c"]
            counts["learning_plans"] = conn.execute(
                "SELECT COUNT(*) AS c FROM learning_plans WHERE user_id=?", (user_id,)
            ).fetchone()["c"]
            counts["plan_items"] = conn.execute(
                "SELECT COUNT(*) AS c FROM learning_plan_items WHERE plan_id IN (SELECT plan_id FROM learning_plans WHERE user_id=?)",
                (user_id,),
            ).fetchone()["c"]
            counts["plan_feedback"] = conn.execute(
                "SELECT COUNT(*) AS c FROM learning_plan_feedback WHERE user_id=?", (user_id,)
            ).fetchone()["c"]
            counts["plan_evaluations"] = conn.execute(
                "SELECT COUNT(*) AS c FROM learning_plan_evaluation_runs WHERE user_id=?", (user_id,)
            ).fetchone()["c"]
            counts["shadow_runs"] = conn.execute(
                "SELECT COUNT(*) AS c FROM model_shadow_runs WHERE user_id=?", (user_id,)
            ).fetchone()["c"]
            return counts

    # 以下删除入口统一走 `_delete_by_scope_conn`：此前这里与 scope 分发器各有一份
    # 逐表 DELETE 列表，新增表时只改一处就会导致"请求删除"与"直接调用"结果不一致。
    def _delete_scope(self, *, user_id: str, scope: str) -> None:
        with self._db.transaction() as conn:
            self._delete_by_scope_conn(conn, user_id=user_id, scope=scope)

    def delete_state_only(self, *, user_id: str) -> None:
        self._delete_scope(user_id=user_id, scope="STATE_ONLY")

    def delete_events_and_state(self, *, user_id: str) -> None:
        self._delete_scope(user_id=user_id, scope="EVENTS_AND_STATE")

    def delete_knowledge_only(self, *, user_id: str) -> None:
        self._delete_scope(user_id=user_id, scope="KNOWLEDGE_ONLY")

    def delete_plans_only(self, *, user_id: str) -> None:
        self._delete_scope(user_id=user_id, scope="PLANS_ONLY")

    def delete_model_shadow_only(self, *, user_id: str) -> None:
        self._delete_scope(user_id=user_id, scope="MODEL_SHADOW_ONLY")

    def delete_all_learner_model_data(self, *, user_id: str) -> None:
        self._delete_scope(user_id=user_id, scope="ALL_LEARNER_MODEL_DATA")

    def record_delete_request(
        self,
        *,
        user_id: str,
        scope: str,
        before_counts: dict[str, int],
        after_counts: dict[str, int],
        idempotency_key: str,
    ) -> DeleteRequestRow:
        request_id = _uuid()
        now = _utc_now()
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO learner_model_delete_requests
                (request_id, user_id, scope, status, before_counts_json, after_counts_json,
                 created_at, completed_at, idempotency_key)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    request_id, user_id, scope, "COMPLETED",
                    json.dumps(before_counts, sort_keys=True),
                    json.dumps(after_counts, sort_keys=True),
                    now.isoformat(), now.isoformat(), idempotency_key,
                ),
            )
            row = conn.execute(
                "SELECT * FROM learner_model_delete_requests WHERE request_id=?",
                (request_id,),
            ).fetchone()
            return self._row_to_delete_request(row)

    def request_deletion_atomic(
        self,
        *,
        user_id: str,
        scope: str,
        idempotency_key: str,
    ) -> DeleteRequestRow:
        """原子化删除：幂等检查 + before count + delete + after count + record，单事务。"""
        now = _utc_now()
        with self._db.transaction() as conn:
            existing = conn.execute(
                """SELECT * FROM learner_model_delete_requests
                   WHERE user_id=? AND idempotency_key=?""",
                (user_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing["scope"] != scope:
                    from ..core.exceptions import LearnerDeleteIdempotencyConflict
                    raise LearnerDeleteIdempotencyConflict()
                return self._row_to_delete_request(existing)

            before = self._count_learner_model_data_conn(conn, user_id=user_id)
            self._delete_by_scope_conn(conn, user_id=user_id, scope=scope)
            after = self._count_learner_model_data_conn(conn, user_id=user_id)

            request_id = _uuid()
            conn.execute(
                """INSERT INTO learner_model_delete_requests
                (request_id, user_id, scope, status, before_counts_json, after_counts_json,
                 created_at, completed_at, idempotency_key)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    request_id, user_id, scope, "COMPLETED",
                    json.dumps(before, sort_keys=True),
                    json.dumps(after, sort_keys=True),
                    now.isoformat(), now.isoformat(), idempotency_key,
                ),
            )
            row = conn.execute(
                "SELECT * FROM learner_model_delete_requests WHERE request_id=?",
                (request_id,),
            ).fetchone()
            return self._row_to_delete_request(row)

    @staticmethod
    def _count_learner_model_data_conn(conn: sqlite3.Connection, *, user_id: str) -> dict[str, int]:
        """在已有 connection 上统计学生模型数据。"""
        counts: dict[str, int] = {}
        counts["projection_runs"] = conn.execute(
            "SELECT COUNT(*) AS c FROM learner_state_projection_runs WHERE user_id=?", (user_id,)
        ).fetchone()["c"]
        counts["snapshots"] = conn.execute(
            "SELECT COUNT(*) AS c FROM learner_state_snapshots WHERE run_id IN (SELECT run_id FROM learner_state_projection_runs WHERE user_id=?)",
            (user_id,),
        ).fetchone()["c"]
        counts["evidence"] = conn.execute(
            "SELECT COUNT(*) AS c FROM learner_state_evidence WHERE snapshot_id IN (SELECT snapshot_id FROM learner_state_snapshots WHERE run_id IN (SELECT run_id FROM learner_state_projection_runs WHERE user_id=?))",
            (user_id,),
        ).fetchone()["c"]
        counts["learner_events"] = conn.execute(
            "SELECT COUNT(*) AS c FROM learner_events WHERE user_id=?", (user_id,)
        ).fetchone()["c"]
        counts["corrections"] = conn.execute(
            "SELECT COUNT(*) AS c FROM learner_state_corrections WHERE user_id=?", (user_id,)
        ).fetchone()["c"]
        counts["learning_plans"] = conn.execute(
            "SELECT COUNT(*) AS c FROM learning_plans WHERE user_id=?", (user_id,)
        ).fetchone()["c"]
        counts["plan_items"] = conn.execute(
            "SELECT COUNT(*) AS c FROM learning_plan_items WHERE plan_id IN (SELECT plan_id FROM learning_plans WHERE user_id=?)",
            (user_id,),
        ).fetchone()["c"]
        counts["plan_feedback"] = conn.execute(
            "SELECT COUNT(*) AS c FROM learning_plan_feedback WHERE user_id=?", (user_id,)
        ).fetchone()["c"]
        counts["plan_evaluations"] = conn.execute(
            "SELECT COUNT(*) AS c FROM learning_plan_evaluation_runs WHERE user_id=?", (user_id,)
        ).fetchone()["c"]
        counts["shadow_runs"] = conn.execute(
            "SELECT COUNT(*) AS c FROM model_shadow_runs WHERE user_id=?", (user_id,)
        ).fetchone()["c"]
        return counts

    @staticmethod
    def _delete_by_scope_conn(conn: sqlite3.Connection, *, user_id: str, scope: str) -> None:
        """在已有 connection 上按 scope 执行删除。"""
        if scope == "STATE_ONLY":
            snapshot_ids = [
                r["snapshot_id"]
                for r in conn.execute(
                    "SELECT snapshot_id FROM learner_state_snapshots WHERE run_id IN (SELECT run_id FROM learner_state_projection_runs WHERE user_id=?)",
                    (user_id,),
                ).fetchall()
            ]
            if snapshot_ids:
                placeholders = ",".join("?" * len(snapshot_ids))
                conn.execute(f"DELETE FROM learner_state_evidence WHERE snapshot_id IN ({placeholders})", snapshot_ids)
            conn.execute("DELETE FROM learner_state_snapshots WHERE run_id IN (SELECT run_id FROM learner_state_projection_runs WHERE user_id=?)", (user_id,))
            conn.execute("DELETE FROM learner_state_projection_runs WHERE user_id=?", (user_id,))
        elif scope == "EVENTS_AND_STATE":
            snapshot_ids = [
                r["snapshot_id"]
                for r in conn.execute(
                    "SELECT snapshot_id FROM learner_state_snapshots WHERE run_id IN (SELECT run_id FROM learner_state_projection_runs WHERE user_id=?)",
                    (user_id,),
                ).fetchall()
            ]
            if snapshot_ids:
                placeholders = ",".join("?" * len(snapshot_ids))
                conn.execute(f"DELETE FROM learner_state_evidence WHERE snapshot_id IN ({placeholders})", snapshot_ids)
            conn.execute("DELETE FROM learner_state_snapshots WHERE run_id IN (SELECT run_id FROM learner_state_projection_runs WHERE user_id=?)", (user_id,))
            conn.execute("DELETE FROM learner_state_projection_runs WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM learner_events WHERE user_id=?", (user_id,))
        elif scope == "KNOWLEDGE_ONLY":
            snapshot_ids = [
                r["snapshot_id"]
                for r in conn.execute(
                    "SELECT snapshot_id FROM learner_state_snapshots WHERE run_id IN (SELECT run_id FROM learner_state_projection_runs WHERE user_id=?)",
                    (user_id,),
                ).fetchall()
            ]
            if snapshot_ids:
                placeholders = ",".join("?" * len(snapshot_ids))
                conn.execute(f"DELETE FROM learner_state_evidence WHERE snapshot_id IN ({placeholders})", snapshot_ids)
            conn.execute("DELETE FROM learner_state_snapshots WHERE run_id IN (SELECT run_id FROM learner_state_projection_runs WHERE user_id=?)", (user_id,))
            conn.execute("DELETE FROM learner_state_projection_runs WHERE user_id=?", (user_id,))
        elif scope == "PLANS_ONLY":
            plan_ids = [
                r["plan_id"]
                for r in conn.execute("SELECT plan_id FROM learning_plans WHERE user_id=?", (user_id,)).fetchall()
            ]
            if plan_ids:
                placeholders = ",".join("?" * len(plan_ids))
                conn.execute(f"DELETE FROM learning_plan_evidence WHERE plan_id IN ({placeholders})", plan_ids)
                conn.execute(f"DELETE FROM learning_plan_decisions WHERE plan_id IN ({placeholders})", plan_ids)
                conn.execute(f"DELETE FROM learning_plan_execution_actions WHERE plan_id IN ({placeholders})", plan_ids)
                conn.execute(f"DELETE FROM learning_plan_feedback WHERE plan_id IN ({placeholders})", plan_ids)
                conn.execute(f"DELETE FROM learning_plan_evaluation_runs WHERE plan_id IN ({placeholders})", plan_ids)
                conn.execute(f"DELETE FROM learning_plan_items WHERE plan_id IN ({placeholders})", plan_ids)
            conn.execute("DELETE FROM learning_plans WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM learning_plan_runs WHERE user_id=?", (user_id,))
            # 干预记录是"计划 + 生成决策时的状态引用"的派生记录：计划被删除后
            # 继续保留会留下指向已删计划的 plan_id 与已删状态 run 的悬空引用。
            # 结果评估同样指向已删的干预记录，一并删除（不依赖 FK 级联开关）。
            conn.execute("DELETE FROM intervention_evaluations WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM adaptive_interventions WHERE user_id=?", (user_id,))
        elif scope == "MODEL_SHADOW_ONLY":
            conn.execute("DELETE FROM model_shadow_results WHERE shadow_run_id IN (SELECT shadow_run_id FROM model_shadow_runs WHERE user_id=?)", (user_id,))
            conn.execute("DELETE FROM model_shadow_metric_records WHERE shadow_run_id IN (SELECT shadow_run_id FROM model_shadow_runs WHERE user_id=?)", (user_id,))
            conn.execute("DELETE FROM model_shadow_runs WHERE user_id=?", (user_id,))
        elif scope == "ALL_LEARNER_MODEL_DATA":
            snapshot_ids = [
                r["snapshot_id"]
                for r in conn.execute(
                    "SELECT snapshot_id FROM learner_state_snapshots WHERE run_id IN (SELECT run_id FROM learner_state_projection_runs WHERE user_id=?)",
                    (user_id,),
                ).fetchall()
            ]
            if snapshot_ids:
                placeholders = ",".join("?" * len(snapshot_ids))
                conn.execute(f"DELETE FROM learner_state_evidence WHERE snapshot_id IN ({placeholders})", snapshot_ids)
            conn.execute("DELETE FROM learner_state_snapshots WHERE run_id IN (SELECT run_id FROM learner_state_projection_runs WHERE user_id=?)", (user_id,))
            conn.execute("DELETE FROM learner_state_projection_runs WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM learner_events WHERE user_id=?", (user_id,))

            plan_ids = [
                r["plan_id"]
                for r in conn.execute("SELECT plan_id FROM learning_plans WHERE user_id=?", (user_id,)).fetchall()
            ]
            if plan_ids:
                placeholders = ",".join("?" * len(plan_ids))
                conn.execute(f"DELETE FROM learning_plan_evidence WHERE plan_id IN ({placeholders})", plan_ids)
                conn.execute(f"DELETE FROM learning_plan_decisions WHERE plan_id IN ({placeholders})", plan_ids)
                conn.execute(f"DELETE FROM learning_plan_execution_actions WHERE plan_id IN ({placeholders})", plan_ids)
                conn.execute(f"DELETE FROM learning_plan_feedback WHERE plan_id IN ({placeholders})", plan_ids)
                conn.execute(f"DELETE FROM learning_plan_evaluation_runs WHERE plan_id IN ({placeholders})", plan_ids)
                conn.execute(f"DELETE FROM learning_plan_items WHERE plan_id IN ({placeholders})", plan_ids)
            conn.execute("DELETE FROM learning_plans WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM learning_plan_runs WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM intervention_evaluations WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM adaptive_interventions WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM model_shadow_results WHERE shadow_run_id IN (SELECT shadow_run_id FROM model_shadow_runs WHERE user_id=?)", (user_id,))
            conn.execute("DELETE FROM model_shadow_metric_records WHERE shadow_run_id IN (SELECT shadow_run_id FROM model_shadow_runs WHERE user_id=?)", (user_id,))
            conn.execute("DELETE FROM model_shadow_runs WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM learner_state_corrections WHERE user_id=?", (user_id,))


    def list_delete_requests(self, *, user_id: str, limit: int = 10) -> list[DeleteRequestRow]:
        with self._db.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM learner_model_delete_requests WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
            return [self._row_to_delete_request(r) for r in rows]

    @staticmethod
    def _row_to_delete_request(row: sqlite3.Row) -> DeleteRequestRow:
        return DeleteRequestRow(
            request_id=row["request_id"],
            user_id=row["user_id"],
            scope=row["scope"],
            status=row["status"],
            before_counts=json.loads(row["before_counts_json"]),
            after_counts=json.loads(row["after_counts_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            idempotency_key=row["idempotency_key"],
        )

    # ===== 数据摘要 =====

    def get_data_summary(self, *, user_id: str) -> dict[str, Any]:
        counts = self.count_learner_model_data(user_id=user_id)
        with self._db.transaction() as conn:
            oldest = conn.execute(
                "SELECT MIN(occurred_at) AS v FROM learner_events WHERE user_id=?", (user_id,)
            ).fetchone()["v"]
            newest = conn.execute(
                "SELECT MAX(occurred_at) AS v FROM learner_events WHERE user_id=?", (user_id,)
            ).fetchone()["v"]
            estimator_versions = [
                r["v"]
                for r in conn.execute(
                    "SELECT DISTINCT estimator_version AS v FROM learner_state_projection_runs WHERE user_id=?",
                    (user_id,),
                ).fetchall()
            ]
            planner_versions = [
                r["v"]
                for r in conn.execute(
                    "SELECT DISTINCT planner_version AS v FROM learning_plan_runs WHERE user_id=?",
                    (user_id,),
                ).fetchall()
            ]
            evaluator_versions = [
                r["v"]
                for r in conn.execute(
                    "SELECT DISTINCT evaluator_version AS v FROM learning_plan_evaluation_runs WHERE user_id=?",
                    (user_id,),
                ).fetchall()
            ]
        controls = self.list_source_controls(user_id=user_id)
        enabled = [c.source_key for c in controls if c.status == "ENABLED"]
        paused = [c.source_key for c in controls if c.status != "ENABLED"]
        return {
            "event_count": counts["learner_events"],
            "snapshot_count": counts["snapshots"],
            "correction_count": counts["corrections"],
            "learning_plan_count": counts["learning_plans"],
            "plan_feedback_count": counts["plan_feedback"],
            "plan_evaluation_count": counts["plan_evaluations"],
            "shadow_run_count": counts["shadow_runs"],
            "enabled_sources": enabled,
            "paused_sources": paused,
            "oldest_recorded_at": datetime.fromisoformat(oldest) if oldest else None,
            "newest_recorded_at": datetime.fromisoformat(newest) if newest else None,
            "estimator_versions": estimator_versions,
            "planner_versions": planner_versions,
            "evaluator_versions": evaluator_versions,
        }

    # ===== 产品事件 =====

    def record_product_event(
        self,
        *,
        user_id: str,
        event_type: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """记录固定枚举产品事件，不记录正文/标题/源码/凭据。"""
        event_id = _uuid()
        now = _utc_now().isoformat()
        safe_meta = json.dumps(metadata or {}, sort_keys=True, separators=(",", ":"))
        with self._db.transaction() as conn:
            conn.execute(
                "INSERT INTO learner_product_events (event_id, user_id, event_type, metadata_json, created_at) VALUES (?,?,?,?,?)",
                (event_id, user_id, event_type, safe_meta, now),
            )


__all__ = [
    "CorrectionRow",
    "DataSourceControlRow",
    "DeleteRequestRow",
    "LearnerControlRepository",
    "DEFAULT_SOURCES",
]
