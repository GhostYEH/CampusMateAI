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
        with self._db.query() as conn:
            events = [dict(row) for row in conn.execute(
                """SELECT event_id,user_id,occurred_at,source,event_type,course_id,
                          subject_type,subject_id,outcome,data_quality
                   FROM learner_events WHERE user_id=?
                   ORDER BY occurred_at ASC,event_id ASC LIMIT ?""",
                (user_id, limit),
            ).fetchall()]
            sessions = [dict(row) for row in conn.execute(
                """SELECT id,user_id,started_at,ended_at,duration_seconds,status
                   FROM study_sessions WHERE user_id=? ORDER BY id ASC LIMIT ?""",
                (user_id, limit),
            ).fetchall()]
            tasks = [dict(row) for row in conn.execute(
                """SELECT id,user_id,course_id,source,created_at,completed_at,deadline,
                          status,deleted_at,updated_at
                   FROM personal_tasks WHERE user_id=? ORDER BY id ASC LIMIT ?""",
                (user_id, limit),
            ).fetchall()]
            content = [dict(row) for row in conn.execute(
                """SELECT id,course_id,provider,kind,status,is_stale,last_synced_at
                   FROM course_content_items WHERE user_id=? ORDER BY id ASC LIMIT ?""",
                (user_id, limit),
            ).fetchall()]
            sections = [dict(row) for row in conn.execute(
                """SELECT course_id,section,status,item_count,last_synced_at,error_code
                   FROM course_sync_sections WHERE user_id=? ORDER BY course_id,section LIMIT ?""",
                (user_id, limit),
            ).fetchall()]
            courses = [dict(row) for row in conn.execute(
                """SELECT id,provider,owner_user_id,status,last_synced_at
                   FROM courses WHERE owner_user_id=? ORDER BY id ASC LIMIT ?""",
                (user_id, limit),
            ).fetchall()]
            credentials = conn.execute(
                "SELECT updated_at FROM chaoxing_credentials WHERE user_id=?", (user_id,)
            ).fetchone()
            edu_connections = [dict(row) for row in conn.execute(
                """SELECT state,updated_at FROM edu_connections
                   WHERE user_id=? ORDER BY updated_at DESC LIMIT ?""",
                (user_id, limit),
            ).fetchall()]
        return {
            "events": events,
            "sessions": sessions,
            "tasks": tasks,
            "content": content,
            "sections": sections,
            "courses": courses,
            "chaoxing_credentials_updated_at": credentials["updated_at"] if credentials else None,
            "edu_connections": edu_connections,
        }

    def save_projection(
        self,
        *,
        run: dict[str, Any],
        snapshots: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> ProjectionRunRow:
        """Persist run, snapshots, evidence and current switch in one transaction."""
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO learner_state_projection_runs
                   (run_id,user_id,as_of,computed_at,estimator_version,input_digest,trigger,is_current,warnings_json)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    run["run_id"], run["user_id"], run["as_of"], run["computed_at"],
                    run["estimator_version"], run["input_digest"], run["trigger"], 0,
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
                       (evidence_id,snapshot_id,evidence_kind,event_id,source_type,source_id,role,quality)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        item["evidence_id"], item["snapshot_id"], item["evidence_kind"],
                        item.get("event_id"), item["source_type"], item["source_id"],
                        item["role"], item["quality"],
                    ),
                )
            conn.execute(
                "UPDATE learner_state_projection_runs SET is_current=0 WHERE user_id=?",
                (run["user_id"],),
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

    def get_current_run(self, *, user_id: str) -> Optional[ProjectionRunRow]:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM learner_state_projection_runs WHERE user_id=? AND is_current=1",
                (user_id,),
            ).fetchone()
        return _run(row) if row else None

    def list_all_current_snapshots(self, *, user_id: str, max_items: int = 10000) -> list[StateSnapshotRow]:
        """Read the current run with an explicit upper bound for projection reuse."""
        if max_items < 1 or max_items > 10000:
            raise ValueError("max_items must stay within 1..10000")
        rows, total = self.list_snapshots(user_id=user_id, page=1, page_size=100)
        page = 2
        while len(rows) < min(total, max_items):
            next_rows, _ = self.list_snapshots(user_id=user_id, page=page, page_size=100)
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
    ) -> tuple[list[StateSnapshotRow], int]:
        if page < 1 or page_size < 1 or page_size > 100:
            raise ValueError("invalid pagination")
        conditions = ["r.user_id=?", "r.is_current=1"]
        params: list[Any] = [user_id]
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

    def get_snapshot(self, *, user_id: str, snapshot_id: str) -> Optional[StateSnapshotRow]:
        with self._db.query() as conn:
            row = conn.execute(
                """SELECT s.* FROM learner_state_snapshots s
                   JOIN learner_state_projection_runs r ON r.run_id=s.run_id
                   WHERE s.snapshot_id=? AND r.user_id=?""",
                (snapshot_id, user_id),
            ).fetchone()
        return _snapshot(row) if row else None

    def list_evidence(
        self, *, user_id: str, snapshot_id: str, page: int = 1, page_size: int = 50
    ) -> tuple[list[StateEvidenceRow], int]:
        if page < 1 or page_size < 1 or page_size > 100:
            raise ValueError("invalid pagination")
        where = "e.snapshot_id=? AND r.user_id=?"
        params: list[Any] = [snapshot_id, user_id]
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            total = int(conn.execute(
                f"""SELECT COUNT(*) AS n FROM learner_state_evidence e
                    JOIN learner_state_snapshots s ON s.snapshot_id=e.snapshot_id
                    JOIN learner_state_projection_runs r ON r.run_id=s.run_id
                    WHERE {where}""", params,
            ).fetchone()["n"])
            rows = conn.execute(
                f"""SELECT e.*, le.source, le.event_type, le.occurred_at, le.data_quality
                    FROM learner_state_evidence e
                    JOIN learner_state_snapshots s ON s.snapshot_id=e.snapshot_id
                    JOIN learner_state_projection_runs r ON r.run_id=s.run_id
                    LEFT JOIN learner_events le ON le.event_id=e.event_id AND le.user_id=r.user_id
                    WHERE {where} ORDER BY e.evidence_id LIMIT ? OFFSET ?""",
                params + [page_size, offset],
            ).fetchall()
        return [StateEvidenceRow(**dict(row)) for row in rows], total


__all__ = ["LearnerStateRepository"]
