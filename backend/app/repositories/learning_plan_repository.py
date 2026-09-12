from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from ..database.sqlite_db import Database
from ..models.learning_plan import (
    LearningPlanActionRow,
    LearningPlanItemRow,
    LearningPlanRow,
    LearningPlanRunRow,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _run(row) -> LearningPlanRunRow:
    return LearningPlanRunRow(
        run_id=row["run_id"], user_id=row["user_id"], planner_version=row["planner_version"],
        input_digest=row["input_digest"], as_of=row["as_of"], valid_until=row["valid_until"],
        available_minutes=int(row["available_minutes"]), allocated_minutes=int(row["allocated_minutes"]),
        course_scope=row["course_scope"], window_start=row["window_start"], window_end=row["window_end"],
        warning_codes=json.loads(row["warning_codes_json"] or "[]"),
        idempotency_key=row["idempotency_key"], created_at=row["created_at"],
        core_run_id=row["core_run_id"] if "core_run_id" in row.keys() else None,
        core_input_digest=row["core_input_digest"] if "core_input_digest" in row.keys() else None,
        knowledge_bindings=json.loads(row["knowledge_bindings_json"] or "{}") if "knowledge_bindings_json" in row.keys() else {},
        task_binding_digest=row["task_binding_digest"] if "task_binding_digest" in row.keys() else None,
        task_bindings=json.loads(row["task_bindings_json"] or "{}") if "task_bindings_json" in row.keys() else {},
        input_truncated=bool(row["input_truncated"]) if "input_truncated" in row.keys() else False,
        core_quality=row["core_quality"] if "core_quality" in row.keys() else "verified",
    )


def _item(row, evidence: list[dict[str, Any]] | None = None) -> LearningPlanItemRow:
    return LearningPlanItemRow(
        item_id=row["item_id"], plan_id=row["plan_id"], item_type=row["item_type"],
        course_id=row["course_id"], task_id=row["task_id"],
        knowledge_component_code=row["knowledge_component_code"],
        estimated_minutes=int(row["estimated_minutes"]), priority_score=float(row["priority_score"]),
        priority_components=json.loads(row["priority_components_json"]),
        explanation_codes=json.loads(row["explanation_codes_json"]),
        execution_status=row["execution_status"], evidence=evidence or [],
    )


class LearningPlanRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create_plan(self, *, user_id: str, run: dict[str, Any], items: list[dict[str, Any]]) -> LearningPlanRow:
        now = _now()
        plan_id = _id("plan")
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO learning_plan_runs
                   (run_id,user_id,planner_version,input_digest,as_of,valid_until,available_minutes,
                    allocated_minutes,course_scope,window_start,window_end,warning_codes_json,idempotency_key,
                    core_run_id,core_input_digest,knowledge_bindings_json,task_binding_digest,task_bindings_json,input_truncated,core_quality,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (run["run_id"], user_id, run["planner_version"], run["input_digest"], run["as_of"],
                 run["valid_until"], run["available_minutes"], run["allocated_minutes"],
                 run.get("course_scope"), run.get("window_start"), run.get("window_end"),
                 json.dumps(run.get("warning_codes", []), ensure_ascii=False), run.get("idempotency_key"),
                 run.get("core_run_id"), run.get("core_input_digest"),
                 json.dumps(run.get("knowledge_bindings", {}), sort_keys=True), run.get("task_binding_digest"),
                 json.dumps(run.get("task_bindings", {}), sort_keys=True), int(bool(run.get("input_truncated"))),
                 run.get("core_quality", "verified"), now),
            )
            conn.execute(
                """INSERT INTO learning_plans(plan_id,run_id,user_id,status,llm_summary,
                   supersedes_plan_id,superseded_by_plan_id,stale_reason,replan_key,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (plan_id, run["run_id"], user_id, "PROPOSED", None, run.get("supersedes_plan_id"),
                 None, None, run.get("replan_key"), now),
            )
            for item in items:
                item_id = item["item_id"]
                conn.execute(
                    """INSERT INTO learning_plan_items
                       (item_id,plan_id,item_type,course_id,task_id,knowledge_component_code,estimated_minutes,
                        priority_score,priority_components_json,explanation_codes_json,execution_status,created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (item_id, plan_id, item["item_type"], item.get("course_id"), item.get("task_id"),
                     item.get("knowledge_component_code"), item["estimated_minutes"], item["priority_score"],
                     json.dumps(item["priority_components"], sort_keys=True),
                     json.dumps(item["explanation_codes"], ensure_ascii=False), "PENDING", now),
                )
                for evidence in item.get("evidence", []):
                    conn.execute(
                        """INSERT INTO learning_plan_evidence
                           (evidence_id,plan_id,item_id,evidence_type,reference_id,relevance_score,metadata_json)
                           VALUES (?,?,?,?,?,?,?)""",
                        (_id("plev"), plan_id, item_id, evidence["evidence_type"], evidence["reference_id"],
                         evidence.get("relevance_score"), json.dumps(evidence.get("metadata", {}), sort_keys=True)),
                    )
        return self.get_plan(plan_id, user_id=user_id)  # type: ignore[return-value]

    def get_plan(self, plan_id: str, *, user_id: str) -> LearningPlanRow | None:
        with self._db.query() as conn:
            row = conn.execute(
                """SELECT p.*, r.* FROM learning_plans p
                   JOIN learning_plan_runs r ON r.run_id=p.run_id
                   WHERE p.plan_id=? AND p.user_id=?""", (plan_id, user_id)
            ).fetchone()
            if row is None:
                return None
            run = _run(row)
            item_rows = conn.execute(
                "SELECT * FROM learning_plan_items WHERE plan_id=? ORDER BY priority_score DESC,item_id ASC", (plan_id,)
            ).fetchall()
            items = []
            for item_row in item_rows:
                evidence_rows = conn.execute(
                    "SELECT evidence_type,reference_id,relevance_score,metadata_json FROM learning_plan_evidence WHERE item_id=? ORDER BY evidence_id",
                    (item_row["item_id"],),
                ).fetchall()
                evidence = [{
                    "evidence_type": e["evidence_type"], "reference_id": e["reference_id"],
                    "relevance_score": e["relevance_score"], "metadata": json.loads(e["metadata_json"] or "{}"),
                } for e in evidence_rows]
                items.append(_item(item_row, evidence))
        status = "STALE" if row["stale_reason"] else ("SUPERSEDED" if row["superseded_by_plan_id"] else row["status"])
        return LearningPlanRow(
            plan_id=plan_id, run=run, user_id=row["user_id"], status=status,
            llm_summary=row["llm_summary"], created_at=row["created_at"], items=items,
            supersedes_plan_id=row["supersedes_plan_id"], superseded_by_plan_id=row["superseded_by_plan_id"],
        )

    def find_by_idempotency_key(self, *, user_id: str, idempotency_key: str) -> LearningPlanRow | None:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT plan_id FROM learning_plans p JOIN learning_plan_runs r ON r.run_id=p.run_id WHERE p.user_id=? AND r.idempotency_key=?",
                (user_id, idempotency_key),
            ).fetchone()
        return self.get_plan(row["plan_id"], user_id=user_id) if row else None

    def find_reusable(self, *, user_id: str, planner_version: str, input_digest: str, as_of: str) -> LearningPlanRow | None:
        with self._db.query() as conn:
            row = conn.execute(
                """SELECT p.plan_id FROM learning_plans p JOIN learning_plan_runs r ON r.run_id=p.run_id
                   WHERE p.user_id=? AND r.planner_version=? AND r.input_digest=?
                     AND r.valid_until>? AND p.status NOT IN ('REJECTED','EXPIRED')
                     AND p.stale_reason IS NULL AND p.superseded_by_plan_id IS NULL
                   ORDER BY r.created_at DESC LIMIT 1""",
                (user_id, planner_version, input_digest, as_of),
            ).fetchone()
        return self.get_plan(row["plan_id"], user_id=user_id) if row else None

    def has_recent_rejection(self, *, user_id: str, input_digest: str, since: str) -> bool:
        with self._db.query() as conn:
            return conn.execute(
                """SELECT 1 FROM learning_plan_decisions d JOIN learning_plans p ON p.plan_id=d.plan_id
                   JOIN learning_plan_runs r ON r.run_id=p.run_id
                   WHERE d.user_id=? AND d.decision='REJECT' AND r.input_digest=? AND d.created_at>=? LIMIT 1""",
                (user_id, input_digest, since),
            ).fetchone() is not None

    def update_status(self, *, plan_id: str, user_id: str, status: str, conn=None) -> LearningPlanRow | None:
        if conn is not None:
            conn.execute("UPDATE learning_plans SET status=? WHERE plan_id=? AND user_id=?", (status, plan_id, user_id))
            return None
        with self._db.transaction() as conn:
            conn.execute("UPDATE learning_plans SET status=? WHERE plan_id=? AND user_id=?", (status, plan_id, user_id))
        return self.get_plan(plan_id, user_id=user_id)

    def set_llm_summary(self, *, plan_id: str, user_id: str, summary: str) -> LearningPlanRow | None:
        with self._db.transaction() as conn:
            conn.execute("UPDATE learning_plans SET llm_summary=? WHERE plan_id=? AND user_id=?", (summary, plan_id, user_id))
        return self.get_plan(plan_id, user_id=user_id)

    def add_decision(self, *, plan_id: str, user_id: str, decision: str) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                "INSERT INTO learning_plan_decisions(decision_id,plan_id,user_id,decision,created_at) VALUES (?,?,?,?,?)",
                (_id("pdec"), plan_id, user_id, decision, _now()),
            )

    def get_action(self, *, plan_id: str, item_id: str, action_type: str, user_id: str) -> LearningPlanActionRow | None:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM learning_plan_execution_actions WHERE plan_id=? AND item_id=? AND action_type=? AND user_id=?",
                (plan_id, item_id, action_type, user_id),
            ).fetchone()
        return LearningPlanActionRow(**dict(row)) if row else None

    def create_action(self, *, plan_id: str, item_id: str, user_id: str, action_type: str, conn=None) -> LearningPlanActionRow:
        def _insert(current_conn):
            now = _now()
            current_conn.execute(
                """INSERT OR IGNORE INTO learning_plan_execution_actions
                   (action_id,plan_id,item_id,user_id,action_type,status,created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (_id("pact"), plan_id, item_id, user_id, action_type, "PENDING", now),
            )
            row = current_conn.execute(
                "SELECT * FROM learning_plan_execution_actions WHERE plan_id=? AND item_id=? AND action_type=? AND user_id=?",
                (plan_id, item_id, action_type, user_id),
            ).fetchone()
            return LearningPlanActionRow(**dict(row))
        if conn is not None:
            return _insert(conn)
        with self._db.transaction() as current_conn:
            return _insert(current_conn)

    def finish_action(self, *, action_id: str, status: str, target_task_id: str | None = None,
                      error_code: str | None = None, target_task_digest: str | None = None, conn=None) -> None:
        def _finish(current_conn):
            current_conn.execute(
                "UPDATE learning_plan_execution_actions SET status=?,target_task_id=?,target_task_digest=?,error_code=?,completed_at=? WHERE action_id=?",
                (status, target_task_id, target_task_digest, error_code, _now(), action_id),
            )
        if conn is not None:
            _finish(conn)
            return
        with self._db.transaction() as current_conn:
            _finish(current_conn)

    def mark_item(self, *, item_id: str, status: str, conn=None) -> None:
        if conn is not None:
            conn.execute("UPDATE learning_plan_items SET execution_status=? WHERE item_id=?", (status, item_id))
            return
        with self._db.transaction() as current_conn:
            current_conn.execute("UPDATE learning_plan_items SET execution_status=? WHERE item_id=?", (status, item_id))

    def mark_stale(self, *, plan_id: str, user_id: str, reason: str) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE learning_plans SET stale_reason=? WHERE plan_id=? AND user_id=?",
                (reason[:64], plan_id, user_id),
            )

    def link_superseded(self, *, old_plan_id: str, new_plan_id: str, user_id: str, replan_key: str | None = None) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE learning_plans SET superseded_by_plan_id=? WHERE plan_id=? AND user_id=?",
                (new_plan_id, old_plan_id, user_id),
            )
            conn.execute(
                "UPDATE learning_plans SET supersedes_plan_id=?, replan_key=? WHERE plan_id=? AND user_id=?",
                (old_plan_id, replan_key, new_plan_id, user_id),
            )

    def execute_atomic(self, *, plan_id: str, user_id: str, task_repository) -> None:
        """Execute all stored items on one database connection/transaction."""
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT status FROM learning_plans WHERE plan_id=? AND user_id=?",
                (plan_id, user_id),
            ).fetchone()
            if row is None:
                return
            if row["status"] == "EXECUTED":
                return
            items = conn.execute(
                "SELECT * FROM learning_plan_items WHERE plan_id=? ORDER BY priority_score DESC,item_id ASC",
                (plan_id,),
            ).fetchall()
            for item in items:
                action_type = "CREATE_PERSONAL_TASK" if item["item_type"] == "CREATE_PERSONAL_TASK" else "REVIEW_PLAN_ITEM"
                action = self.create_action(plan_id=plan_id, item_id=item["item_id"], user_id=user_id,
                                            action_type=action_type, conn=conn)
                if action.status in {"SUCCEEDED", "UNDONE"}:
                    continue
                target = None
                if action_type == "CREATE_PERSONAL_TASK":
                    target = task_repository.create_task(
                        user_id=user_id,
                        title=f"学习诊断：{item['knowledge_component_code'] or '课程复习'}",
                        source="learning_plan", external_id=f"{plan_id}:{item['item_id']}",
                        course_id=item["course_id"], conn=conn,
                    )
                self.finish_action(action_id=action.action_id, status="SUCCEEDED",
                                   target_task_id=target.id if target else None,
                                   target_task_digest=task_repository.semantic_digest(target) if target else None,
                                   conn=conn)
                self.mark_item(item_id=item["item_id"], status="SUCCEEDED", conn=conn)
            self.update_status(plan_id=plan_id, user_id=user_id, status="EXECUTED", conn=conn)

    def undo_atomic(self, *, plan_id: str, user_id: str, task_repository) -> bool:
        """Undo only untouched tasks created by this plan; return conflict state."""
        with self._db.transaction() as conn:
            actions = [LearningPlanActionRow(**dict(row)) for row in conn.execute(
                "SELECT * FROM learning_plan_execution_actions WHERE plan_id=? AND user_id=? ORDER BY created_at,action_id",
                (plan_id, user_id),
            ).fetchall()]
            conflicts = []
            for action in actions:
                if action.status == "FAILED" and action.error_code == "undo_conflict":
                    conflicts.append(action)
                    continue
                if action.status != "SUCCEEDED" or action.action_type != "CREATE_PERSONAL_TASK" or not action.target_task_id:
                    continue
                task = task_repository.get_task_in_connection(conn, action.target_task_id, user_id=user_id)
                if (task is None or task.source != "learning_plan" or
                        task.external_id != f"{plan_id}:{action.item_id}" or
                        task.status != "pending" or
                        not action.target_task_digest or
                        task_repository.semantic_digest(task) != action.target_task_digest):
                    conflicts.append(action)
            if conflicts:
                for action in conflicts:
                    self.finish_action(action_id=action.action_id, status="FAILED",
                                       target_task_id=action.target_task_id, error_code="undo_conflict", conn=conn)
                self.update_status(plan_id=plan_id, user_id=user_id, status="PARTIALLY_EXECUTED", conn=conn)
                return True
            for action in actions:
                if action.status != "SUCCEEDED" or action.action_type != "CREATE_PERSONAL_TASK" or not action.target_task_id:
                    continue
                task = task_repository.get_task_in_connection(conn, action.target_task_id, user_id=user_id)
                task_repository.soft_delete_in_connection(conn, task.id, user_id=user_id)
                self.finish_action(action_id=action.action_id, status="UNDONE",
                                   target_task_id=action.target_task_id, conn=conn)
                self.mark_item(item_id=action.item_id, status="UNDONE", conn=conn)
            self.update_status(plan_id=plan_id, user_id=user_id, status="UNDONE", conn=conn)
        return False

    def add_feedback(self, *, plan_id: str, user_id: str, feedback: str) -> str:
        feedback_id = _id("plfb")
        with self._db.transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO learning_plan_feedback(feedback_id,plan_id,user_id,feedback,created_at) VALUES (?,?,?,?,?)",
                (feedback_id, plan_id, user_id, feedback, _now()),
            )
            row = conn.execute(
                "SELECT feedback_id FROM learning_plan_feedback WHERE plan_id=? AND user_id=? AND feedback=?",
                (plan_id, user_id, feedback),
            ).fetchone()
        return row["feedback_id"]

    def get_latest_evaluation(self, *, plan_id: str, user_id: str, evaluator_version: str, input_digest: str):
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM learning_plan_evaluation_runs WHERE plan_id=? AND user_id=? AND evaluator_version=? AND input_digest=?",
                (plan_id, user_id, evaluator_version, input_digest),
            ).fetchone()
        return dict(row) if row else None

    def add_evaluation(self, *, plan_id: str, user_id: str, evaluator_version: str, input_digest: str,
                       baseline_as_of: str, evaluated_as_of: str, metrics: dict, warning_codes: list[str]) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO learning_plan_evaluation_runs
                   (evaluation_id,plan_id,user_id,evaluator_version,input_digest,baseline_as_of,evaluated_as_of,metrics_json,warning_codes_json,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (_id("pleval"), plan_id, user_id, evaluator_version, input_digest, baseline_as_of, evaluated_as_of,
                 json.dumps(metrics, sort_keys=True), json.dumps(sorted(set(warning_codes))), _now()),
            )

    def list_actions(self, *, plan_id: str, user_id: str) -> list[LearningPlanActionRow]:
        with self._db.query() as conn:
            rows = conn.execute(
                "SELECT * FROM learning_plan_execution_actions WHERE plan_id=? AND user_id=? ORDER BY created_at,action_id",
                (plan_id, user_id),
            ).fetchall()
        return [LearningPlanActionRow(**dict(row)) for row in rows]

    def list_plans(self, *, user_id: str, page: int, page_size: int) -> tuple[list[LearningPlanRow], int]:
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            total = int(conn.execute("SELECT COUNT(*) n FROM learning_plans WHERE user_id=?", (user_id,)).fetchone()["n"])
            rows = conn.execute(
                "SELECT plan_id FROM learning_plans WHERE user_id=? ORDER BY created_at DESC,plan_id DESC LIMIT ? OFFSET ?",
                (user_id, page_size, offset),
            ).fetchall()
        result = []
        for row in rows:
            plan = self.get_plan(row["plan_id"], user_id=user_id)
            if plan is not None:
                result.append(plan)
        return result, total


__all__ = ["LearningPlanRepository"]
