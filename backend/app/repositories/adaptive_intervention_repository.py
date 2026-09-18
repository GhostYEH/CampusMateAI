"""AdaptiveInterventionRepository —— 状态驱动干预记录的持久化。

- 与仓库其它 repository 一致：直接用 `Database` + SQLite，不引入新 ORM。
- 幂等：`UNIQUE(user_id, idempotency_key)`，重复创建返回既有记录而不是第二条。
- 隔离：所有读写都带 `user_id`，跨用户查询返回 None（由路由映射成 404）。
- 安全：assessment/strategy 写入前必须通过 Pydantic schema 校验；
  只落结构化有限字段，不落原始聊天、答案或证据正文。
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from ..database.sqlite_db import Database
from ..models.adaptive_intervention import INTERVENTION_STATUSES, AdaptiveInterventionRow
from ..schemas.adaptive_intervention import StudentStateAssessment, StrategyDecision


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id() -> str:
    return f"intv_{uuid.uuid4().hex[:16]}"


class AdaptiveInterventionRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    # ---------------------------------------------------------------- 写入

    def create(
        self,
        *,
        user_id: str,
        goal_id: str,
        assessment: StudentStateAssessment,
        strategy: StrategyDecision,
        baseline_state_digest: str,
        idempotency_key: str,
        status: str = "PROPOSED",
        agent_job_id: str | None = None,
        agent_run_id: str | None = None,
        plan_id: str | None = None,
    ) -> AdaptiveInterventionRow:
        """创建干预记录。同一 (user_id, idempotency_key) 只会存在一条。"""
        if status not in INTERVENTION_STATUSES:
            raise ValueError(f"未知的干预状态: {status}")
        # 写库前再校验一次：调用方即使绕过 service，也不可能写入不合规 JSON。
        assessment = StudentStateAssessment.model_validate(assessment.model_dump(mode="json"))
        strategy = StrategyDecision.model_validate(strategy.model_dump(mode="json"))

        existing = self.find_by_idempotency_key(user_id=user_id, idempotency_key=idempotency_key)
        if existing is not None:
            return existing

        now = _now()
        intervention_id = _id()
        values = (
            intervention_id, user_id, goal_id, plan_id, agent_job_id, agent_run_id, status,
            strategy.strategy_code, strategy.strategy_version, assessment.assessment_id,
            json.dumps(assessment.model_dump(mode="json"), ensure_ascii=False, sort_keys=True),
            json.dumps(strategy.model_dump(mode="json"), ensure_ascii=False, sort_keys=True),
            json.dumps(list(strategy.rationale_codes), ensure_ascii=False),
            json.dumps(list(strategy.expected_outcomes), ensure_ascii=False),
            assessment.core_run_id, assessment.academic_run_id, assessment.world_run_id,
            baseline_state_digest, float(strategy.confidence),
            json.dumps(sorted(set([*assessment.warning_codes, *strategy.warning_codes])), ensure_ascii=False),
            idempotency_key, now, now,
        )
        try:
            with self._db.transaction() as conn:
                conn.execute(
                    """INSERT INTO adaptive_interventions
                       (intervention_id,user_id,goal_id,plan_id,agent_job_id,agent_run_id,status,
                        strategy_code,strategy_version,assessment_id,assessment_json,strategy_json,
                        rationale_codes_json,expected_outcomes_json,
                        baseline_core_run_id,baseline_academic_run_id,baseline_world_run_id,
                        baseline_state_digest,confidence,warning_codes_json,idempotency_key,
                        created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    values,
                )
        except sqlite3.IntegrityError:
            # 并发下另一个请求已经写入同一幂等键：返回既有记录，不产生第二条。
            existing = self.find_by_idempotency_key(user_id=user_id, idempotency_key=idempotency_key)
            if existing is not None:
                return existing
            raise
        return self.get(user_id=user_id, intervention_id=intervention_id)  # type: ignore[return-value]

    def bind_plan(
        self, *, user_id: str, intervention_id: str, plan_id: str, status: str = "PLAN_GENERATED"
    ) -> AdaptiveInterventionRow | None:
        if status not in INTERVENTION_STATUSES:
            raise ValueError(f"未知的干预状态: {status}")
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE adaptive_interventions SET plan_id=?, status=?, updated_at=? "
                "WHERE intervention_id=? AND user_id=?",
                (plan_id, status, _now(), intervention_id, user_id),
            )
        return self.get(user_id=user_id, intervention_id=intervention_id)

    def update_status(self, *, user_id: str, intervention_id: str, status: str) -> AdaptiveInterventionRow | None:
        if status not in INTERVENTION_STATUSES:
            raise ValueError(f"未知的干预状态: {status}")
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE adaptive_interventions SET status=?, updated_at=? WHERE intervention_id=? AND user_id=?",
                (status, _now(), intervention_id, user_id),
            )
        return self.get(user_id=user_id, intervention_id=intervention_id)

    # ---------------------------------------------------------------- 读取

    def get(self, *, user_id: str, intervention_id: str) -> AdaptiveInterventionRow | None:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM adaptive_interventions WHERE intervention_id=? AND user_id=?",
                (intervention_id, user_id),
            ).fetchone()
        return AdaptiveInterventionRow.from_row(row) if row is not None else None

    def find_by_idempotency_key(self, *, user_id: str, idempotency_key: str) -> AdaptiveInterventionRow | None:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM adaptive_interventions WHERE user_id=? AND idempotency_key=?",
                (user_id, idempotency_key),
            ).fetchone()
        return AdaptiveInterventionRow.from_row(row) if row is not None else None

    def list_interventions(
        self, *, user_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[AdaptiveInterventionRow], int]:
        offset = (max(1, page) - 1) * max(1, page_size)
        with self._db.query() as conn:
            total = int(
                conn.execute(
                    "SELECT COUNT(*) AS c FROM adaptive_interventions WHERE user_id=?", (user_id,)
                ).fetchone()["c"]
            )
            rows = conn.execute(
                "SELECT * FROM adaptive_interventions WHERE user_id=? "
                "ORDER BY created_at DESC, intervention_id DESC LIMIT ? OFFSET ?",
                (user_id, max(1, page_size), offset),
            ).fetchall()
        return [AdaptiveInterventionRow.from_row(row) for row in rows], total

    def count_for_user(self, *, user_id: str) -> int:
        with self._db.query() as conn:
            return int(
                conn.execute(
                    "SELECT COUNT(*) AS c FROM adaptive_interventions WHERE user_id=?", (user_id,)
                ).fetchone()["c"]
            )


__all__ = ["AdaptiveInterventionRepository"]
