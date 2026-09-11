from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from ..database.sqlite_db import Database
from ..models.learner_state import ProjectionRunRow, StateEvidenceRow, StateSnapshotRow


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _run(row) -> ProjectionRunRow:
    return ProjectionRunRow(
        run_id=row["run_id"],
        user_id=row["user_id"],
        as_of=row["as_of"],
        computed_at=row["computed_at"],
        estimator_version=row["estimator_version"],
        input_digest=row["input_digest"],
        trigger=row["trigger"],
        is_current=bool(row["is_current"]),
        warnings=json.loads(row["warnings_json"] or "[]"),
        snapshot_count=int(row["snapshot_count"]) if "snapshot_count" in row.keys() else 0,
        projection_kind=row["projection_kind"] if "projection_kind" in row.keys() else "CORE",
        projection_scope=row["projection_scope"] if "projection_scope" in row.keys() else "__user__",
    )


def _snapshot(row) -> StateSnapshotRow:
    return StateSnapshotRow(
        snapshot_id=row["snapshot_id"],
        run_id=row["run_id"],
        scope_type=row["scope_type"],
        scope_id=row["scope_id"],
        state_type=row["state_type"],
        value=json.loads(row["value_json"]),
        confidence=float(row["confidence"]),
        data_quality=row["data_quality"],
        observed_from=row["observed_from"],
        observed_through=row["observed_through"],
        valid_until=row["valid_until"],
        computed_at=row["computed_at"],
    )


class LearnerStateRepository:
    """SQL boundary for disposable learner-state projections and bounded inputs."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def collect_inputs(self, *, user_id: str, limit: int = 5000) -> dict[str, Any]:
        if limit < 1 or limit > 10000:
            raise ValueError("limit must stay within 1..10000")

        def bounded(conn, sql: str, params: tuple[Any, ...] = ()) -> tuple[list[dict[str, Any]], bool]:
            rows = conn.execute(sql, (*params, limit + 1)).fetchall()
            return [dict(row) for row in rows[:limit]], len(rows) > limit

        with self._db.query() as conn:
            events, events_truncated = bounded(conn,
                """SELECT event_id,user_id,occurred_at,source,event_type,course_id,
                          subject_type,subject_id,outcome,data_quality
                   FROM learner_events WHERE user_id=?
                   ORDER BY occurred_at DESC,event_id DESC LIMIT ?""", (user_id,))
            sessions, sessions_truncated = bounded(conn,
                """SELECT id,user_id,started_at,ended_at,duration_seconds,status
                   FROM study_sessions WHERE user_id=? ORDER BY started_at DESC,id DESC LIMIT ?""", (user_id,))
            tasks, tasks_truncated = bounded(conn,
                """SELECT id,user_id,course_id,source,created_at,completed_at,deadline,
                          status,deleted_at
                   FROM personal_tasks WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT ?""", (user_id,))
            content, content_truncated = bounded(conn,
                """SELECT id,course_id,provider,kind,status,is_stale,last_synced_at
                   FROM course_content_items WHERE user_id=? ORDER BY last_synced_at DESC,id DESC LIMIT ?""", (user_id,))
            sections, sections_truncated = bounded(conn,
                """SELECT course_id,section,status,item_count,last_synced_at,error_code
                   FROM course_sync_sections WHERE user_id=? ORDER BY last_synced_at DESC,course_id DESC,section DESC LIMIT ?""", (user_id,))
            courses, courses_truncated = bounded(conn,
                """SELECT id,provider,owner_user_id,status,last_synced_at
                   FROM courses WHERE owner_user_id=? ORDER BY last_synced_at DESC,id DESC LIMIT ?""", (user_id,))
            credentials = conn.execute(
                "SELECT updated_at FROM chaoxing_credentials WHERE user_id=?", (user_id,)
            ).fetchone()
            edu_connections, edu_truncated = bounded(conn,
                """SELECT state,updated_at FROM edu_connections
                   WHERE user_id=? ORDER BY updated_at DESC LIMIT ?""", (user_id,))
        truncated_sources = [
            name for name, is_truncated in (
                ("events", events_truncated), ("sessions", sessions_truncated),
                ("tasks", tasks_truncated), ("content", content_truncated),
                ("sections", sections_truncated), ("courses", courses_truncated),
                ("edu_connections", edu_truncated),
            ) if is_truncated
        ]
        return {
            "events": events,
            "sessions": sessions,
            "tasks": tasks,
            "content": content,
            "sections": sections,
            "courses": courses,
            "chaoxing_credentials_updated_at": credentials["updated_at"] if credentials else None,
            "edu_connections": edu_connections,
            "input_metadata": {
                "hard_limit": limit,
                "truncated": bool(truncated_sources),
                "truncated_sources": truncated_sources,
                "truncation_policy": "latest_first",
                "selected_limit": limit,
            },
        }

    def save_projection(
        self,
        *,
        run: dict[str, Any],
        snapshots: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> ProjectionRunRow:
        """Persist run, snapshots, evidence and current switch in one transaction."""
        projection_kind = run.get("projection_kind", "CORE")
        projection_scope = run.get("projection_scope", "__user__")
        if projection_kind not in {"CORE", "KNOWLEDGE"}:
            raise ValueError("unsupported projection kind")
        if projection_kind == "CORE" and projection_scope != "__user__":
            raise ValueError("CORE projection must use the user scope")
        if projection_kind == "KNOWLEDGE" and not projection_scope:
            raise ValueError("KNOWLEDGE projection requires a course scope")
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO learner_state_projection_runs
                   (run_id,user_id,as_of,computed_at,estimator_version,input_digest,trigger,
                    projection_kind,projection_scope,is_current,warnings_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    run["run_id"], run["user_id"], run["as_of"], run["computed_at"],
                    run["estimator_version"], run["input_digest"], run["trigger"],
                    projection_kind, projection_scope, 0,
                    _json(run.get("warnings", [])),
                ),
            )
            for snapshot in snapshots:
                conn.execute(
                    """INSERT INTO learner_state_snapshots
                       (snapshot_id,run_id,scope_type,scope_id,state_type,value_json,confidence,
                        data_quality,observed_from,observed_through,valid_until,computed_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        snapshot["snapshot_id"], run["run_id"], snapshot["scope_type"], snapshot["scope_id"],
                        snapshot["state_type"], _json(snapshot["value"]), snapshot["confidence"],
                        snapshot["data_quality"], snapshot.get("observed_from"),
                        snapshot.get("observed_through"), snapshot.get("valid_until"), snapshot["computed_at"],
                    ),
                )
            for item in evidence:
                conn.execute(
                    """INSERT INTO learner_state_evidence
                       (evidence_id,snapshot_id,evidence_kind,event_id,source_type,source_id,role,quality,explanation_code)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        item["evidence_id"], item["snapshot_id"], item["evidence_kind"],
                        item.get("event_id"), item["source_type"], item["source_id"],
                        item["role"], item["quality"], item.get("explanation_code", "state_observed"),
                    ),
                )
            conn.execute(
                "UPDATE learner_state_projection_runs SET is_current=0 "
                "WHERE user_id=? AND projection_kind=? AND projection_scope=?",
                (run["user_id"], projection_kind, projection_scope),
            )
            conn.execute(
                "UPDATE learner_state_projection_runs SET is_current=1 WHERE run_id=?",
                (run["run_id"],),
            )
        current = self.get_run(run["run_id"], user_id=run["user_id"])
        if current is None:  # pragma: no cover
            raise RuntimeError("projection run disappeared after commit")
        return current

    def get_run(self, run_id: str, *, user_id: str) -> Optional[ProjectionRunRow]:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM learner_state_projection_runs WHERE run_id=? AND user_id=?",
                (run_id, user_id),
            ).fetchone()
        return _run(row) if row else None

    def get_current_run(
        self, *, user_id: str, projection_kind: str = "CORE", projection_scope: str = "__user__"
    ) -> Optional[ProjectionRunRow]:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM learner_state_projection_runs WHERE user_id=? "
                "AND projection_kind=? AND projection_scope=? AND is_current=1",
                (user_id, projection_kind, projection_scope),
            ).fetchone()
        return _run(row) if row else None

    def list_runs(
        self, *, user_id: str, page: int = 1, page_size: int = 50,
        projection_kind: str = "CORE", projection_scope: str = "__user__"
    ) -> tuple[list[ProjectionRunRow], int]:
        if page < 1 or page_size < 1 or page_size > 100:
            raise ValueError("invalid pagination")
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            total = int(conn.execute(
                "SELECT COUNT(*) AS n FROM learner_state_projection_runs "
                "WHERE user_id=? AND projection_kind=? AND projection_scope=?",
                (user_id, projection_kind, projection_scope),
            ).fetchone()["n"])
            rows = conn.execute(
                """SELECT r.*, COUNT(s.snapshot_id) AS snapshot_count
                   FROM learner_state_projection_runs r
                   LEFT JOIN learner_state_snapshots s ON s.run_id=r.run_id
                   WHERE r.user_id=? AND r.projection_kind=? AND r.projection_scope=?
                   GROUP BY r.run_id
                   ORDER BY r.computed_at DESC, r.run_id DESC
                   LIMIT ? OFFSET ?""",
                (user_id, projection_kind, projection_scope, page_size, offset),
            ).fetchall()
        return [_run(row) for row in rows], total

    def snapshot_count_for_run(self, *, run_id: str, user_id: str) -> int:
        with self._db.query() as conn:
            return int(conn.execute(
                """SELECT COUNT(*) AS n FROM learner_state_snapshots s
                   JOIN learner_state_projection_runs r ON r.run_id=s.run_id
                   WHERE s.run_id=? AND r.user_id=?""", (run_id, user_id)
            ).fetchone()["n"])

    def get_previous_run(
        self, *, user_id: str, before_run: ProjectionRunRow
    ) -> Optional[ProjectionRunRow]:
        with self._db.query() as conn:
            current_row = conn.execute(
                "SELECT rowid FROM learner_state_projection_runs WHERE run_id=? AND user_id=?",
                (before_run.run_id, user_id),
            ).fetchone()
            if current_row is None:
                return None
            row = conn.execute(
                """SELECT * FROM learner_state_projection_runs
                   WHERE user_id=? AND estimator_version=? AND rowid < ?
                   AND projection_kind=? AND projection_scope=?
                   ORDER BY rowid DESC LIMIT 1""",
                (user_id, before_run.estimator_version, current_row["rowid"],
                 before_run.projection_kind, before_run.projection_scope),
            ).fetchone()
        return _run(row) if row else None

    def list_changes(
        self, *, user_id: str, from_run_id: str | None, to_run_id: str,
        page: int = 1, page_size: int = 50, scope_type: str | None = None,
        state_type: str | None = None, include_unchanged: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        if page < 1 or page_size < 1 or page_size > 100:
            raise ValueError("invalid pagination")
        with self._db.query() as conn:
            to_run = conn.execute(
                "SELECT user_id,projection_kind,projection_scope "
                "FROM learner_state_projection_runs WHERE run_id=?", (to_run_id,)
            ).fetchone()
            from_run = conn.execute(
                "SELECT user_id,projection_kind,projection_scope "
                "FROM learner_state_projection_runs WHERE run_id=?", (from_run_id,)
            ).fetchone() if from_run_id else None
        if to_run is None or to_run["user_id"] != user_id or (
            from_run is not None and (
                from_run["user_id"] != user_id
                or from_run["projection_kind"] != to_run["projection_kind"]
                or from_run["projection_scope"] != to_run["projection_scope"]
            )
        ):
            raise LookupError("projection runs are not in the same family")
        params: list[Any] = [to_run_id]
        if from_run_id is None:
            cte = """WITH paired AS (
                SELECT NULL AS previous_snapshot_id, NULL AS previous_value_json,
                       NULL AS previous_confidence, NULL AS previous_quality,
                       b.snapshot_id AS current_snapshot_id, b.scope_type,
                       b.scope_id, b.state_type, b.value_json AS current_value_json,
                       b.confidence AS current_confidence, b.data_quality AS current_quality
                FROM learner_state_snapshots b WHERE b.run_id=?
            )"""
        else:
            params = [to_run_id, from_run_id, from_run_id, to_run_id]
            cte = """WITH paired AS (
                SELECT a.snapshot_id AS previous_snapshot_id, a.value_json AS previous_value_json,
                       a.confidence AS previous_confidence, a.data_quality AS previous_quality,
                       b.snapshot_id AS current_snapshot_id, COALESCE(a.scope_type,b.scope_type) AS scope_type,
                       COALESCE(a.scope_id,b.scope_id) AS scope_id,
                       COALESCE(a.state_type,b.state_type) AS state_type,
                       b.value_json AS current_value_json, b.confidence AS current_confidence,
                       b.data_quality AS current_quality
                FROM learner_state_snapshots a
                LEFT JOIN learner_state_snapshots b
                  ON b.run_id=? AND b.scope_type=a.scope_type AND b.scope_id=a.scope_id AND b.state_type=a.state_type
                WHERE a.run_id=?
                UNION ALL
                SELECT NULL, NULL, NULL, NULL, b.snapshot_id, b.scope_type, b.scope_id,
                       b.state_type, b.value_json, b.confidence, b.data_quality
                FROM learner_state_snapshots b
                LEFT JOIN learner_state_snapshots a
                  ON a.run_id=? AND a.scope_type=b.scope_type AND a.scope_id=b.scope_id AND a.state_type=b.state_type
                WHERE b.run_id=? AND a.snapshot_id IS NULL
            )"""
        conditions = ["1=1"]
        if scope_type:
            conditions.append("scope_type=?")
            params.append(scope_type)
        if state_type:
            conditions.append("state_type=?")
            params.append(state_type)
        if not include_unchanged:
            conditions.append(
                "(previous_snapshot_id IS NULL OR current_snapshot_id IS NULL OR "
                "previous_value_json != current_value_json OR "
                "previous_quality != current_quality OR previous_confidence != current_confidence)"
            )
        where = " AND ".join(conditions)
        offset = (page - 1) * page_size
        count_sql = f"{cte} SELECT COUNT(*) AS n FROM paired WHERE {where}"
        rows_sql = f"""{cte} SELECT * FROM paired WHERE {where}
                       ORDER BY scope_type,scope_id,state_type LIMIT ? OFFSET ?"""
        with self._db.query() as conn:
            total = int(conn.execute(count_sql, params).fetchone()["n"])
            rows = conn.execute(rows_sql, params + [page_size, offset]).fetchall()
        return [dict(row) for row in rows], total

    def list_all_current_snapshots(
        self, *, user_id: str, max_items: int = 10000,
        projection_kind: str = "CORE", projection_scope: str = "__user__"
    ) -> list[StateSnapshotRow]:
        """Read the current run with an explicit upper bound for projection reuse."""
        if max_items < 1 or max_items > 10000:
            raise ValueError("max_items must stay within 1..10000")
        rows, total = self.list_snapshots(
            user_id=user_id, page=1, page_size=100,
            projection_kind=projection_kind, projection_scope=projection_scope,
        )
        page = 2
        while len(rows) < min(total, max_items):
            next_rows, _ = self.list_snapshots(
                user_id=user_id, page=page, page_size=100,
                projection_kind=projection_kind, projection_scope=projection_scope,
            )
            if not next_rows:
                break
            rows.extend(next_rows)
            page += 1
        return rows[:max_items]

    def list_snapshots(
        self,
        *,
        user_id: str,
        page: int = 1,
        page_size: int = 50,
        scope_type: str | None = None,
        state_type: str | None = None,
        course_id: str | None = None,
        projection_kind: str = "CORE",
        projection_scope: str = "__user__",
    ) -> tuple[list[StateSnapshotRow], int]:
        if page < 1 or page_size < 1 or page_size > 100:
            raise ValueError("invalid pagination")
        conditions = [
            "r.user_id=?", "r.projection_kind=?", "r.projection_scope=?", "r.is_current=1"
        ]
        params: list[Any] = [user_id, projection_kind, projection_scope]
        if scope_type:
            conditions.append("s.scope_type=?")
            params.append(scope_type)
        if state_type:
            conditions.append("s.state_type=?")
            params.append(state_type)
        if course_id:
            conditions.extend(["s.scope_type='COURSE'", "s.scope_id=?"])
            params.append(course_id)
        where = " AND ".join(conditions)
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            total = int(conn.execute(
                f"SELECT COUNT(*) AS n FROM learner_state_snapshots s JOIN learner_state_projection_runs r ON r.run_id=s.run_id WHERE {where}",
                params,
            ).fetchone()["n"])
            rows = conn.execute(
                f"""SELECT s.* FROM learner_state_snapshots s
                    JOIN learner_state_projection_runs r ON r.run_id=s.run_id
                    WHERE {where} ORDER BY s.scope_type,s.scope_id,s.state_type
                    LIMIT ? OFFSET ?""",
                params + [page_size, offset],
            ).fetchall()
        return [_snapshot(row) for row in rows], total

    def get_snapshot(
        self, *, user_id: str, snapshot_id: str,
        projection_kind: str = "CORE", projection_scope: str = "__user__",
    ) -> Optional[StateSnapshotRow]:
        with self._db.query() as conn:
            row = conn.execute(
                """SELECT s.* FROM learner_state_snapshots s
                   JOIN learner_state_projection_runs r ON r.run_id=s.run_id
                   WHERE s.snapshot_id=? AND r.user_id=?
                   AND r.projection_kind=? AND r.projection_scope=?""",
                (snapshot_id, user_id, projection_kind, projection_scope),
            ).fetchone()
        return _snapshot(row) if row else None

    def get_snapshot_projection_family(
        self, *, user_id: str, snapshot_id: str,
    ) -> tuple[str, str] | None:
        """Resolve a snapshot's projection family only within the requesting user."""
        with self._db.query() as conn:
            row = conn.execute(
                """SELECT r.projection_kind, r.projection_scope
                   FROM learner_state_snapshots s
                   JOIN learner_state_projection_runs r ON r.run_id=s.run_id
                   WHERE s.snapshot_id=? AND r.user_id=?""",
                (snapshot_id, user_id),
            ).fetchone()
        if row is None:
            return None
        return row["projection_kind"], row["projection_scope"]

    def list_evidence(
        self, *, user_id: str, snapshot_id: str, page: int = 1, page_size: int = 50,
        projection_kind: str = "CORE", projection_scope: str = "__user__",
    ) -> tuple[list[StateEvidenceRow], int]:
        if page < 1 or page_size < 1 or page_size > 100:
            raise ValueError("invalid pagination")
        where = (
            "e.snapshot_id=? AND r.user_id=? AND r.projection_kind=? "
            "AND r.projection_scope=?"
        )
        params: list[Any] = [snapshot_id, user_id, projection_kind, projection_scope]
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            total = int(conn.execute(
                f"""SELECT COUNT(*) AS n FROM learner_state_evidence e
                    JOIN learner_state_snapshots s ON s.snapshot_id=e.snapshot_id
                    JOIN learner_state_projection_runs r ON r.run_id=s.run_id
                    WHERE {where}""", params,
            ).fetchone()["n"])
            rows = conn.execute(
                f"""SELECT e.*, le.source, le.event_type, le.occurred_at,
                           COALESCE(le.data_quality, e.quality) AS data_quality
                    FROM learner_state_evidence e
                    JOIN learner_state_snapshots s ON s.snapshot_id=e.snapshot_id
                    JOIN learner_state_projection_runs r ON r.run_id=s.run_id
                    LEFT JOIN learner_events le ON le.event_id=e.event_id AND le.user_id=r.user_id
                    WHERE {where} ORDER BY e.evidence_id LIMIT ? OFFSET ?""",
                params + [page_size, offset],
            ).fetchall()
        return [
            StateEvidenceRow(
                evidence_id=row["evidence_id"], snapshot_id=row["snapshot_id"],
                evidence_kind=row["evidence_kind"], event_id=row["event_id"],
                source_type=row["source_type"], source_id=row["source_id"],
                role=row["role"], quality=row["quality"],
                explanation_code=row["explanation_code"],
                source_category=self._source_category(row["source_type"]),
                event_type=row["event_type"],
                occurred_at=row["occurred_at"], data_quality=row["data_quality"],
            )
            for row in rows
        ], total

    @staticmethod
    def _source_category(source_type: str) -> str:
        return {
            "study_sessions": "study_session",
            "study": "study_session",
            "personal_task": "personal_task",
            "course_content_items": "course_content",
            "course_sync_sections": "course_sync",
            "core_learning_record": "core_learning_record",
            "chaoxing": "chaoxing",
        }.get(source_type, "unknown")


__all__ = ["LearnerStateRepository"]
