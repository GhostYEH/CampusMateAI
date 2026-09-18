"""AdaptiveInterventionRepository —— 状态驱动干预记录与结果评估的持久化。

- 与仓库其它 repository 一致：直接用 `Database` + SQLite，不引入新 ORM。
- 幂等：`UNIQUE(user_id, idempotency_key)`，重复创建返回既有记录而不是第二条；
  评估用 `UNIQUE(intervention_id, evaluator_version, input_digest)`，同一份观测只落一行。
- 隔离：所有读写都带 `user_id`，跨用户查询返回 None（由路由映射成 404）。
- 安全：assessment/strategy/evaluation 写入前必须通过 Pydantic schema 校验；
  只落结构化有限字段，不落原始聊天、答案或证据正文。
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from ..database.sqlite_db import Database
from ..models.adaptive_intervention import (
    WRITABLE_INTERVENTION_STATUSES,
    AdaptiveInterventionRow,
    InterventionEvaluationRow,
    AdaptiveReplanDecisionRow,
)
from ..schemas.adaptive_intervention import (
    InterventionEvaluation,
    StudentStateAssessment,
    StrategyDecision,
)


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
        if status not in WRITABLE_INTERVENTION_STATUSES:
            raise ValueError(f"未知或本轮不可写入的干预状态: {status}")
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
        self, *, user_id: str, intervention_id: str, plan_id: str,
        observation_due_at: str | None = None, status: str = "PLAN_GENERATED"
    ) -> AdaptiveInterventionRow | None:
        if status not in WRITABLE_INTERVENTION_STATUSES:
            raise ValueError(f"未知或本轮不可写入的干预状态: {status}")
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE adaptive_interventions SET plan_id=?, status=?, observation_due_at=?, updated_at=? "
                "WHERE intervention_id=? AND user_id=?",
                (plan_id, status, observation_due_at, _now(), intervention_id, user_id),
            )
        return self.get(user_id=user_id, intervention_id=intervention_id)

    def update_status(self, *, user_id: str, intervention_id: str, status: str) -> AdaptiveInterventionRow | None:
        if status not in WRITABLE_INTERVENTION_STATUSES:
            raise ValueError(f"未知或本轮不可写入的干预状态: {status}")
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE adaptive_interventions SET status=?, updated_at=? WHERE intervention_id=? AND user_id=?",
                (status, _now(), intervention_id, user_id),
            )
        return self.get(user_id=user_id, intervention_id=intervention_id)

    def update_strategy(self, *, user_id: str, intervention_id: str, strategy: StrategyDecision) -> AdaptiveInterventionRow | None:
        strategy = StrategyDecision.model_validate(strategy.model_dump(mode="json"))
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE adaptive_interventions SET strategy_code=?, strategy_version=?, strategy_json=?, rationale_codes_json=?, expected_outcomes_json=?, confidence=?, updated_at=? WHERE intervention_id=? AND user_id=?",
                (strategy.strategy_code, strategy.strategy_version,
                 json.dumps(strategy.model_dump(mode="json"), ensure_ascii=False, sort_keys=True),
                 json.dumps(list(strategy.rationale_codes)), json.dumps(list(strategy.expected_outcomes)),
                 strategy.confidence, _now(), intervention_id, user_id),
            )
            if cursor.rowcount != 1:
                return None
        return self.get(user_id=user_id, intervention_id=intervention_id)

    def link_replanned(
        self, *, user_id: str, old_intervention_id: str, new_intervention_id: str,
        evaluation_id: str, decision_id: str, reason_codes: list[str],
    ) -> None:
        """Only call after successor plan binding succeeds; the old record stays usable on failure."""
        with self._db.transaction() as conn:
            old_cursor = conn.execute(
                "UPDATE adaptive_interventions SET status='SUPERSEDED', superseded_by_intervention_id=?, "
                "updated_at=? WHERE intervention_id=? AND user_id=? AND status IN ('EVALUATED','OBSERVING','PLAN_GENERATED','ACCEPTED','EXECUTING')",
                (new_intervention_id, _now(), old_intervention_id, user_id),
            )
            if old_cursor.rowcount != 1:
                raise sqlite3.IntegrityError("old intervention state changed before successor link")
            new_cursor = conn.execute(
                "UPDATE adaptive_interventions SET status='PLAN_GENERATED', supersedes_intervention_id=?, source_evaluation_id=?, "
                "replan_decision_id=?, replan_reason_codes_json=?, chain_depth=(SELECT chain_depth+1 FROM adaptive_interventions "
                "WHERE intervention_id=? AND user_id=?), updated_at=? WHERE intervention_id=? AND user_id=?",
                (old_intervention_id, evaluation_id, decision_id, json.dumps(sorted(set(reason_codes))),
                 old_intervention_id, user_id, _now(), new_intervention_id, user_id),
            )
            if new_cursor.rowcount != 1:
                raise sqlite3.IntegrityError("successor intervention missing during link")

    def has_replan_guard_violation(self, *, user_id: str, goal_id: str, old_intervention_id: str,
                                   since: str, day_start: str, daily_limit: int) -> bool:
        with self._db.query() as conn:
            active = conn.execute(
                "SELECT COUNT(*) FROM adaptive_interventions WHERE user_id=? AND goal_id=? "
                "AND intervention_id!=? AND status IN ('PLAN_GENERATED','ACCEPTED','EXECUTING','OBSERVING')",
                (user_id, goal_id, old_intervention_id),
            ).fetchone()[0]
            recent = conn.execute(
                "SELECT COUNT(*) FROM adaptive_interventions WHERE user_id=? AND goal_id=? "
                "AND supersedes_intervention_id IS NOT NULL AND created_at>=?",
                (user_id, goal_id, since),
            ).fetchone()[0]
            daily = conn.execute(
                "SELECT COUNT(*) FROM adaptive_interventions WHERE user_id=? AND goal_id=? "
                "AND supersedes_intervention_id IS NOT NULL AND created_at>=?",
                (user_id, goal_id, day_start),
            ).fetchone()[0]
        return bool(active or recent or daily >= daily_limit)

    def save_evaluation(
        self,
        *,
        user_id: str,
        intervention_id: str,
        evaluation: InterventionEvaluation,
        input_digest: str,
        status: str,
    ) -> tuple[InterventionEvaluationRow, bool]:
        """落库一次评估，并把干预记录推进到 `status`（OBSERVING 或 EVALUATED）。

        返回 `(评估行, 是否新建)`。同一 `(intervention_id, evaluator_version, input_digest)`
        只存在一行；重复调用复用既有行，但仍然把干预记录的收口字段对齐到该行，
        避免"评估已存在但状态还停在旧值"的半截状态。

        状态推进刻意做成单条 SQL 里的条件更新，而不是"先 mark_observing 再置 EVALUATED"：
        - `status != 'CANCELLED'`：已取消的干预不能被评估复活。
        - `CASE WHEN status='EVALUATED'`：已经评估完成的记录不会因为一次较早的观测而回退。
        - `observation_started_at` 用 COALESCE 只在第一次观测时写入，保留最早观测时点。
        """
        if status not in ("OBSERVING", "EVALUATED"):
            raise ValueError(f"结果评估只能推进到 OBSERVING 或 EVALUATED，收到: {status}")
        evaluation = InterventionEvaluation.model_validate(evaluation.model_dump(mode="json"))
        now = _now()
        with self._db.transaction() as conn:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO intervention_evaluations
                   (evaluation_id,intervention_id,user_id,goal_id,plan_id,evaluator_version,
                    input_digest,observation_status,execution_signal,plan_fidelity,verdict,
                    evaluation_json,warning_codes_json,as_of,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    evaluation.evaluation_id, evaluation.intervention_id, user_id, evaluation.goal_id,
                    evaluation.plan_id, evaluation.evaluator_version, input_digest,
                    evaluation.observation_status, evaluation.execution_signal,
                    evaluation.plan_fidelity, evaluation.verdict,
                    json.dumps(evaluation.model_dump(mode="json"), ensure_ascii=False, sort_keys=True),
                    json.dumps(sorted(set(evaluation.warning_codes)), ensure_ascii=False),
                    evaluation.as_of, now,
                ),
            )
            created = cursor.rowcount > 0
            stored = conn.execute(
                "SELECT * FROM intervention_evaluations "
                "WHERE intervention_id=? AND evaluator_version=? AND input_digest=?",
                (intervention_id, evaluation.evaluator_version, input_digest),
            ).fetchone()
            current = conn.execute(
                "SELECT * FROM adaptive_interventions WHERE intervention_id=? AND user_id=?",
                (intervention_id, user_id),
            ).fetchone()
            if current is not None and current["status"] not in {"CANCELLED", "SUPERSEDED"}:
                previous = None
                if current["evaluation_id"]:
                    previous = conn.execute(
                        "SELECT * FROM intervention_evaluations WHERE evaluation_id=?",
                        (current["evaluation_id"],),
                    ).fetchone()
                if self._is_better_current(candidate=stored, current=previous, candidate_status=status):
                    conn.execute(
                        "UPDATE adaptive_interventions SET status=?, observation_started_at=COALESCE(observation_started_at, ?), "
                        "observation_completed_at=CASE WHEN ?='EVALUATED' THEN ? ELSE observation_completed_at END, "
                        "evaluated_at=CASE WHEN ?='EVALUATED' THEN ? ELSE evaluated_at END, "
                        "evaluation_version=?, outcome_verdict=?, evaluation_id=?, updated_at=? "
                        "WHERE intervention_id=? AND user_id=?",
                        (status, now, status, evaluation.as_of, status, evaluation.as_of,
                         evaluation.evaluator_version, evaluation.verdict, stored["evaluation_id"], now,
                         intervention_id, user_id),
                    )
        return InterventionEvaluationRow.from_row(stored), created

    @staticmethod
    def _is_better_current(*, candidate, current, candidate_status: str) -> bool:
        """选择 current evaluation 的单调规则，永不让弱观察覆盖最终评估。"""
        if current is None:
            return True
        current_payload = json.loads(current["evaluation_json"] or "{}")
        candidate_payload = json.loads(candidate["evaluation_json"] or "{}")
        current_final = current["observation_status"] == "COMPLETE"
        candidate_final = candidate_status == "EVALUATED" and candidate["observation_status"] == "COMPLETE"
        if current_final and not candidate_final:
            return False
        def rank(row, payload, final):
            evidence = 1 if payload.get("observed_outcome") not in (None, "INSUFFICIENT_EVIDENCE") else 0
            confidence = float(payload.get("confidence") or 0.0)
            return (int(final), evidence, confidence, row["as_of"], row["created_at"], row["evaluation_id"])
        return rank(candidate, candidate_payload, candidate_final) > rank(current, current_payload, current_final)

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

    def find_by_plan(self, *, user_id: str, plan_id: str) -> AdaptiveInterventionRow | None:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM adaptive_interventions WHERE user_id=? AND plan_id=? ORDER BY created_at DESC LIMIT 1",
                (user_id, plan_id),
            ).fetchone()
        return AdaptiveInterventionRow.from_row(row) if row else None

    def get_evaluation(
        self, *, user_id: str, intervention_id: str
    ) -> InterventionEvaluationRow | None:
        """最近一次结果评估。跨用户返回 None，与其它读取入口一致。"""
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT e.* FROM intervention_evaluations e JOIN adaptive_interventions i "
                "ON i.evaluation_id=e.evaluation_id WHERE i.intervention_id=? AND i.user_id=?",
                (intervention_id, user_id),
            ).fetchone()
        return InterventionEvaluationRow.from_row(row) if row is not None else None

    def find_evaluation_by_digest(
        self, *, user_id: str, intervention_id: str, evaluator_version: str, input_digest: str
    ) -> InterventionEvaluationRow | None:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM intervention_evaluations WHERE intervention_id=? AND user_id=? "
                "AND evaluator_version=? AND input_digest=?",
                (intervention_id, user_id, evaluator_version, input_digest),
            ).fetchone()
        return InterventionEvaluationRow.from_row(row) if row is not None else None

    def list_evaluations(
        self, *, user_id: str, intervention_id: str, limit: int = 20
    ) -> list[InterventionEvaluationRow]:
        with self._db.query() as conn:
            rows = conn.execute(
                "SELECT * FROM intervention_evaluations WHERE intervention_id=? AND user_id=? "
                "ORDER BY created_at DESC, evaluation_id DESC LIMIT ?",
                (intervention_id, user_id, max(1, limit)),
            ).fetchall()
        return [InterventionEvaluationRow.from_row(row) for row in rows]

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

    def list_due_for_evaluation(self, *, as_of: str, limit: int = 50) -> list[AdaptiveInterventionRow]:
        """Bounded background-work query; never used by HTTP reads."""
        with self._db.query() as conn:
            rows = conn.execute(
                "SELECT * FROM adaptive_interventions WHERE status IN ('PLAN_GENERATED','ACCEPTED','OBSERVING','EXECUTING') "
                "AND observation_due_at IS NOT NULL AND observation_due_at<=? "
                "ORDER BY observation_due_at, intervention_id LIMIT ?",
                (as_of, max(1, min(limit, 100))),
            ).fetchall()
        return [AdaptiveInterventionRow.from_row(row) for row in rows]

    def save_decision(self, *, user_id: str, goal_id: str, intervention_id: str,
                      evaluation_id: str, decision: str, decision_digest: str,
                      reason_codes: list[str], suggested_adjustments: list[str],
                      confidence: float, evidence_refs: list[str], status: str = "PENDING") -> AdaptiveReplanDecisionRow:
        now = _now()
        decision_id = f"rdec_{decision_digest[:16]}"
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO adaptive_replan_decisions
                   (decision_id,decision_digest,user_id,goal_id,intervention_id,evaluation_id,decision,
                    reason_codes_json,suggested_adjustments_json,confidence,evidence_refs_json,status,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(evaluation_id) DO NOTHING""",
                (decision_id, decision_digest, user_id, goal_id, intervention_id, evaluation_id, decision,
                 json.dumps(sorted(set(reason_codes))), json.dumps(sorted(set(suggested_adjustments))), confidence,
                 json.dumps(sorted(set(evidence_refs))), status, now),
            )
        row = self.get_decision(user_id=user_id, evaluation_id=evaluation_id)
        if row is None:
            raise RuntimeError("decision disappeared after commit")
        return row

    def get_decision(self, *, user_id: str, evaluation_id: str) -> AdaptiveReplanDecisionRow | None:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM adaptive_replan_decisions WHERE user_id=? AND evaluation_id=?",
                (user_id, evaluation_id),
            ).fetchone()
        return AdaptiveReplanDecisionRow.from_row(row) if row else None

    def list_pending_decisions(self, *, as_of: str, limit: int = 50) -> list[tuple[AdaptiveInterventionRow, AdaptiveReplanDecisionRow | None]]:
        with self._db.query() as conn:
            rows = conn.execute(
                """SELECT i.*, d.decision_id AS d_decision_id FROM adaptive_interventions i
                   JOIN intervention_evaluations e ON e.evaluation_id=i.evaluation_id
                   LEFT JOIN adaptive_replan_decisions d ON d.evaluation_id=e.evaluation_id
                   WHERE e.observation_status='COMPLETE'
                     AND (d.decision_id IS NULL OR d.status IN ('PENDING','APPLYING'))
                   ORDER BY e.as_of, i.intervention_id LIMIT ?""",
                (max(1, min(limit, 100)),),
            ).fetchall()
        out = []
        for row in rows:
            intervention = AdaptiveInterventionRow.from_row(row)
            out.append((intervention, self.get_decision(user_id=intervention.user_id, evaluation_id=intervention.evaluation_id)))
        return out

    def update_decision_status(self, *, user_id: str, decision_id: str, status: str,
                               failure_code: str | None = None) -> AdaptiveReplanDecisionRow | None:
        if status not in {"PENDING", "APPLYING", "APPLIED", "FAILED"}:
            raise ValueError("invalid decision status")
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE adaptive_replan_decisions SET status=?, applied_at=CASE WHEN ?='APPLIED' THEN ? ELSE applied_at END, failure_code=? WHERE decision_id=? AND user_id=?",
                (status, status, _now(), failure_code, decision_id, user_id),
            )
            if cursor.rowcount != 1:
                return None
        with self._db.query() as conn:
            row = conn.execute("SELECT * FROM adaptive_replan_decisions WHERE decision_id=? AND user_id=?", (decision_id, user_id)).fetchone()
        return AdaptiveReplanDecisionRow.from_row(row) if row else None

    def count_for_user(self, *, user_id: str) -> int:
        with self._db.query() as conn:
            return int(
                conn.execute(
                    "SELECT COUNT(*) AS c FROM adaptive_interventions WHERE user_id=?", (user_id,)
                ).fetchone()["c"]
            )


__all__ = ["AdaptiveInterventionRepository"]
