from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from ..database.sqlite_db import Database
from ..core.exceptions import PracticeAttemptConflict
from ..models.c_knowledge import (
    ExerciseMappingRow,
    KnowledgeComponentRow,
    MisconceptionHypothesisRow,
    PracticeAttemptRow,
)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _semantic_occurred_at(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).astimezone(timezone.utc).isoformat()
    except ValueError:
        return text


def _component(row) -> KnowledgeComponentRow:
    return KnowledgeComponentRow(
        knowledge_component_id=row["id"], code=row["code"], name=row["name"],
        category=row["category"], description=row["description"], domain=row["domain"],
        taxonomy_version=row["taxonomy_version"], sort_order=row["sort_order"],
        active=bool(row["active"]), parent_code=row["parent_code"],
        prerequisite_codes=json.loads(row["prerequisite_codes_json"] or "[]"),
    )


def _mapping(row) -> ExerciseMappingRow:
    return ExerciseMappingRow(
        exercise_id=row["exercise_id"], course_id=row["course_id"],
        knowledge_component_code=row["knowledge_component_code"],
        mapping_method=row["mapping_method"], mapping_confidence=float(row["mapping_confidence"]),
        mapping_version=row["mapping_version"], subject_type=row["subject_type"], subject_id=row["subject_id"],
    )


def _attempt(row) -> PracticeAttemptRow:
    return PracticeAttemptRow(
        attempt_id=row["id"], user_id=row["user_id"], client_attempt_id=row["client_attempt_id"],
        course_id=row["course_id"], exercise_id=row["exercise_id"], occurred_at=row["occurred_at"],
        attempt_no=int(row["attempt_no"]), result_type=row["result_type"], score=float(row["score"]),
        max_score=float(row["max_score"]), test_count=int(row["test_count"]),
        passed_test_count=int(row["passed_test_count"]), compiler_outcome=row["compiler_outcome"],
        error_codes=json.loads(row["error_codes_json"] or "[]"), duration_seconds=row["duration_seconds"],
        evidence_quality=row["evidence_quality"], evidence_origin=row["evidence_origin"],
    )


def _hypothesis(row) -> MisconceptionHypothesisRow:
    return MisconceptionHypothesisRow(
        hypothesis_id=row["id"], user_id=row["user_id"], course_id=row["course_id"],
        knowledge_component_code=row["knowledge_component_code"], misconception_code=row["misconception_code"],
        confidence=float(row["confidence"]), supporting_attempt_count=int(row["supporting_attempt_count"]),
        supporting_error_count=int(row["supporting_error_count"]), supporting_evidence_count=int(row["supporting_evidence_count"]), status=row["status"],
        generated_at=row["generated_at"], valid_until=row["valid_until"],
        estimator_version=row["estimator_version"], evidence_digest=row["evidence_digest"],
        decided_at=row["decided_at"],
    )


class KnowledgeRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def seed_components(self, definitions: list[dict[str, Any]]) -> list[KnowledgeComponentRow]:
        now = _now()
        with self._db.transaction() as conn:
            for item in definitions:
                conn.execute(
                    """INSERT INTO knowledge_components
                       (id,code,name,category,description,domain,taxonomy_version,sort_order,active,parent_code,prerequisite_codes_json,created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(code) DO UPDATE SET name=excluded.name, category=excluded.category,
                       description=excluded.description, domain=excluded.domain, active=excluded.active, parent_code=excluded.parent_code,
                       taxonomy_version=excluded.taxonomy_version, sort_order=excluded.sort_order,
                       prerequisite_codes_json=excluded.prerequisite_codes_json, updated_at=excluded.updated_at""",
                    (item["id"], item["code"], item["name"], item["category"], item["description"], item["domain"],
                     item["taxonomy_version"], item["sort_order"], int(item.get("active", True)), item.get("parent_code"),
                     json.dumps(item.get("prerequisite_codes", [])), now, now),
                )
        return self.list_components()

    def list_components(self) -> list[KnowledgeComponentRow]:
        with self._db.query() as conn:
            rows = conn.execute("SELECT * FROM knowledge_components ORDER BY sort_order, code").fetchall()
        return [_component(row) for row in rows]

    def get_component(self, code: str) -> KnowledgeComponentRow | None:
        with self._db.query() as conn:
            row = conn.execute("SELECT * FROM knowledge_components WHERE code=?", (code,)).fetchone()
        return _component(row) if row else None

    def upsert_mapping(
        self, *, course_id: str, exercise_id: str, knowledge_component_code: str,
        mapping_method: str = "CURATED", mapping_confidence: float = 1.0,
        mapping_version: str = "c-language-v1",
    ) -> ExerciseMappingRow:
        if mapping_method not in {"CURATED", "COURSE_AUTHOR", "STRUCTURED_IMPORT"}:
            raise ValueError("mapping_method is unsupported")
        if not 0 <= mapping_confidence <= 1:
            raise ValueError("mapping_confidence must be between zero and one")
        now = _now()
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO exercise_kc_mappings
                   (id,course_id,exercise_id,subject_type,subject_id,knowledge_component_code,mapping_method,mapping_confidence,mapping_version,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(course_id,subject_type,subject_id,knowledge_component_code,mapping_version)
                   DO UPDATE SET mapping_method=excluded.mapping_method, mapping_confidence=excluded.mapping_confidence,
                   active=1, updated_at=excluded.updated_at""",
                (_id("kmap"), course_id, exercise_id, "exercise", exercise_id, knowledge_component_code,
                 mapping_method, mapping_confidence, mapping_version, now, now),
            )
            row = conn.execute(
                "SELECT * FROM exercise_kc_mappings WHERE course_id=? AND subject_type='exercise' AND subject_id=? AND knowledge_component_code=? AND mapping_version=?",
                (course_id, exercise_id, knowledge_component_code, mapping_version),
            ).fetchone()
        return _mapping(row)  # type: ignore[arg-type]

    def list_mappings(self, *, course_id: str, exercise_id: str | None = None) -> list[ExerciseMappingRow]:
        args: list[Any] = [course_id]
        where = "course_id=? AND active=1 AND subject_type='exercise'"
        if exercise_id is not None:
            where += " AND subject_id=?"
            args.append(exercise_id)
        with self._db.query() as conn:
            rows = conn.execute(f"SELECT * FROM exercise_kc_mappings WHERE {where} ORDER BY exercise_id, knowledge_component_code", args).fetchall()
        return [_mapping(row) for row in rows]

    def get_attempt_by_client_id(self, *, user_id: str, client_attempt_id: str) -> PracticeAttemptRow | None:
        with self._db.query() as conn:
            row = conn.execute("SELECT * FROM practice_attempts WHERE user_id=? AND client_attempt_id=?", (user_id, client_attempt_id)).fetchone()
        return _attempt(row) if row else None

    def insert_attempt(self, *, user_id: str, data: dict[str, Any]) -> PracticeAttemptRow:
        attempt_id = _id("pat")
        with self._db.transaction() as conn:
            try:
                conn.execute(
                    """INSERT INTO practice_attempts
                       (id,user_id,client_attempt_id,course_id,exercise_id,occurred_at,attempt_no,result_type,score,max_score,
                        test_count,passed_test_count,compiler_outcome,error_codes_json,duration_seconds,evidence_quality,evidence_origin,created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (attempt_id, user_id, data["client_attempt_id"], data["course_id"], data["exercise_id"],
                     data["occurred_at"], data["attempt_no"], data["result_type"], data["score"], data["max_score"],
                     data["test_count"], data["passed_test_count"], data["compiler_outcome"],
                     json.dumps(data["error_codes"], separators=(",", ":")), data.get("duration_seconds"),
                     data["evidence_quality"], data.get("evidence_origin", "CLIENT"), _now()),
                )
            except sqlite3.IntegrityError:
                existing = conn.execute("SELECT * FROM practice_attempts WHERE user_id=? AND client_attempt_id=?", (user_id, data["client_attempt_id"])).fetchone()
                if existing is None:
                    raise
                row = _attempt(existing)
                semantic_fields = (
                    "course_id", "exercise_id", "occurred_at", "attempt_no", "result_type",
                    "score", "max_score", "test_count", "passed_test_count", "compiler_outcome",
                    "error_codes", "duration_seconds", "evidence_quality", "evidence_origin",
                )
                existing_values = {
                    key: getattr(row, key) for key in semantic_fields
                }
                incoming_values = {key: data.get(key) for key in semantic_fields}
                existing_values["occurred_at"] = _semantic_occurred_at(existing_values["occurred_at"])
                incoming_values["occurred_at"] = _semantic_occurred_at(incoming_values["occurred_at"])
                if existing_values != incoming_values:
                    raise PracticeAttemptConflict()
                return row
            row = conn.execute("SELECT * FROM practice_attempts WHERE id=?", (attempt_id,)).fetchone()
        return _attempt(row)  # type: ignore[arg-type]

    def list_attempts(self, *, user_id: str, course_id: str, limit: int = 5000) -> list[PracticeAttemptRow]:
        rows, _ = self.list_attempts_bounded(user_id=user_id, course_id=course_id, limit=limit)
        return rows

    def list_attempts_bounded(
        self, *, user_id: str, course_id: str, limit: int = 5000
    ) -> tuple[list[PracticeAttemptRow], bool]:
        if limit < 1 or limit > 10000:
            raise ValueError("limit must stay within 1..10000")
        with self._db.query() as conn:
            rows = conn.execute(
                "SELECT * FROM practice_attempts WHERE user_id=? AND course_id=? "
                "ORDER BY occurred_at DESC, id DESC LIMIT ?",
                (user_id, course_id, limit + 1),
            ).fetchall()
        return [_attempt(row) for row in rows[:limit]][::-1], len(rows) > limit

    def upsert_hypothesis(self, *, data: dict[str, Any]) -> MisconceptionHypothesisRow:
        now = _now()
        with self._db.transaction() as conn:
            current = conn.execute(
                "SELECT * FROM misconception_hypotheses WHERE user_id=? AND course_id=? AND knowledge_component_code=? AND misconception_code=?",
                (data["user_id"], data["course_id"], data["knowledge_component_code"], data["misconception_code"]),
            ).fetchone()
            if current is None:
                hid = _id("mhyp")
                conn.execute(
                    """INSERT INTO misconception_hypotheses
                       (id,user_id,course_id,knowledge_component_code,misconception_code,confidence,supporting_attempt_count,
                       supporting_error_count,supporting_evidence_count,status,generated_at,valid_until,estimator_version,evidence_digest,decided_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)""",
                    (hid, data["user_id"], data["course_id"], data["knowledge_component_code"], data["misconception_code"],
                     data["confidence"], data["supporting_attempt_count"], data["supporting_error_count"],
                     data.get("supporting_evidence_count", data["supporting_attempt_count"]),
                     data.get("status", "OPEN"), data["generated_at"], data["valid_until"], data["estimator_version"], data["evidence_digest"]),
                )
                conn.execute("INSERT INTO misconception_hypothesis_history (id,hypothesis_id,status,evidence_digest,decision_source,changed_at) VALUES (?,?,?,?,?,?)", (_id("mhh"), hid, data.get("status", "OPEN"), data["evidence_digest"], "rule", now))
            else:
                hid = current["id"]
                status = current["status"]
                if status not in {"CONFIRMED", "REJECTED", "RESOLVED"} or current["evidence_digest"] != data["evidence_digest"]:
                    status = data.get("status", "OPEN")
                conn.execute(
                    """UPDATE misconception_hypotheses SET confidence=?, supporting_attempt_count=?, supporting_error_count=?, supporting_evidence_count=?,
                       status=?, generated_at=?, valid_until=?, estimator_version=?, evidence_digest=? WHERE id=?""",
                    (data["confidence"], data["supporting_attempt_count"], data["supporting_error_count"], data.get("supporting_evidence_count", data["supporting_attempt_count"]), status,
                     data["generated_at"], data["valid_until"], data["estimator_version"], data["evidence_digest"], hid),
                )
            row = conn.execute("SELECT * FROM misconception_hypotheses WHERE id=?", (hid,)).fetchone()
        return _hypothesis(row)  # type: ignore[arg-type]

    def list_hypotheses(self, *, user_id: str, course_id: str) -> list[MisconceptionHypothesisRow]:
        with self._db.query() as conn:
            rows = conn.execute("SELECT * FROM misconception_hypotheses WHERE user_id=? AND course_id=? ORDER BY knowledge_component_code, misconception_code", (user_id, course_id)).fetchall()
        return [_hypothesis(row) for row in rows]

    def get_hypothesis(self, *, user_id: str, course_id: str, knowledge_component_code: str, misconception_code: str) -> MisconceptionHypothesisRow | None:
        with self._db.query() as conn:
            row = conn.execute(
                """SELECT * FROM misconception_hypotheses WHERE user_id=? AND course_id=?
                   AND knowledge_component_code=? AND misconception_code=?""",
                (user_id, course_id, knowledge_component_code, misconception_code),
            ).fetchone()
        return _hypothesis(row) if row else None

    def expire_hypothesis(self, *, hypothesis_id: str, evidence_digest: str, changed_at: str) -> None:
        with self._db.transaction() as conn:
            row = conn.execute("SELECT status FROM misconception_hypotheses WHERE id=?", (hypothesis_id,)).fetchone()
            if row is None or row["status"] != "OPEN":
                return
            conn.execute("UPDATE misconception_hypotheses SET status='RESOLVED', evidence_digest=?, decided_at=NULL WHERE id=?", (evidence_digest, hypothesis_id))
            conn.execute("INSERT INTO misconception_hypothesis_history (id,hypothesis_id,status,evidence_digest,decision_source,changed_at) VALUES (?,?,?,?,?,?)", (_id("mhh"), hypothesis_id, "RESOLVED", evidence_digest, "contrary_practice", changed_at))

    def resolve_hypothesis(self, *, hypothesis_id: str, evidence_digest: str, changed_at: str) -> None:
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT status FROM misconception_hypotheses WHERE id=?", (hypothesis_id,)
            ).fetchone()
            if row is None or row["status"] not in {"OPEN", "CONFIRMED"}:
                return
            conn.execute(
                "UPDATE misconception_hypotheses SET status='RESOLVED', evidence_digest=?, decided_at=NULL WHERE id=?",
                (evidence_digest, hypothesis_id),
            )
            conn.execute(
                "INSERT INTO misconception_hypothesis_history "
                "(id,hypothesis_id,status,evidence_digest,decision_source,changed_at) "
                "VALUES (?,?,?,?,?,?)",
                (_id("mhh"), hypothesis_id, "RESOLVED", evidence_digest, "contrary_practice", changed_at),
            )

    def decide_hypothesis(self, *, user_id: str, hypothesis_id: str, status: str) -> MisconceptionHypothesisRow | None:
        now = _now()
        with self._db.transaction() as conn:
            row = conn.execute("SELECT * FROM misconception_hypotheses WHERE id=? AND user_id=?", (hypothesis_id, user_id)).fetchone()
            if row is None:
                return None
            normalized = {"CONFIRM": "CONFIRMED", "REJECT": "REJECTED", "CONFIRMED": "CONFIRMED", "REJECTED": "REJECTED"}[status]
            conn.execute("UPDATE misconception_hypotheses SET status=?, decided_at=? WHERE id=?", (normalized, now, hypothesis_id))
            conn.execute("INSERT INTO misconception_hypothesis_history (id,hypothesis_id,status,evidence_digest,decision_source,changed_at) VALUES (?,?,?,?,?,?)", (_id("mhh"), hypothesis_id, normalized, row["evidence_digest"], "student", now))
            row = conn.execute("SELECT * FROM misconception_hypotheses WHERE id=?", (hypothesis_id,)).fetchone()
        return _hypothesis(row)

    def count_hypothesis_history(self, hypothesis_id: str) -> int:
        with self._db.query() as conn:
            return int(conn.execute("SELECT COUNT(*) AS n FROM misconception_hypothesis_history WHERE hypothesis_id=?", (hypothesis_id,)).fetchone()["n"])

    def user_can_access_course(self, *, user_id: str, course_id: str) -> bool:
        with self._db.query() as conn:
            row = conn.execute(
                """SELECT 1 FROM courses c WHERE c.id=? AND (c.owner_user_id=? OR EXISTS (
                   SELECT 1 FROM class_groups cg JOIN enrollments e ON e.class_group_id=cg.id
                   WHERE cg.course_id=c.id AND e.user_id=? AND e.status='active' AND e.member_role='student'))""",
                (course_id, user_id, user_id),
            ).fetchone()
        return row is not None


__all__ = ["KnowledgeRepository"]
