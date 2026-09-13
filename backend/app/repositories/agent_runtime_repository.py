from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ..core.exceptions import AppException
from ..database.sqlite_db import Database
from ..models.agent_runtime import AgentEventRow, AgentJobRow, AgentRunRow, AgentToolCallRow


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _job(row) -> AgentJobRow:
    return AgentJobRow(**dict(row))


def _run(row) -> AgentRunRow:
    return AgentRunRow(**dict(row))


def _event(row) -> AgentEventRow:
    return AgentEventRow(**dict(row))


def _tool(row) -> AgentToolCallRow:
    data = dict(row)
    data.pop("step_id", None)
    return AgentToolCallRow(**data)


class AgentRuntimeRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create_job(self, *, user_id: str, domain: str, objective_summary: str) -> AgentJobRow:
        job_id, now = _id("job"), _now()
        with self._db.transaction() as conn:
            conn.execute(
                "INSERT INTO agent_jobs(id,user_id,domain,objective_summary,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (job_id, user_id, domain, objective_summary[:500], "ACTIVE", now, now),
            )
            return _job(conn.execute("SELECT * FROM agent_jobs WHERE id=?", (job_id,)).fetchone())

    def create_run(self, *, job_id: str, user_id: str, domain: str, total_steps: int) -> AgentRunRow:
        run_id, now = _id("run"), _now()
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO agent_runs(id,job_id,user_id,domain,status,phase,progress_current,progress_total,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (run_id, job_id, user_id, domain, "QUEUED", "IDLE", 0, total_steps, now, now),
            )
            return _run(conn.execute("SELECT * FROM agent_runs WHERE id=?", (run_id,)).fetchone())

    def get_run(self, *, run_id: str, user_id: str | None = None) -> AgentRunRow | None:
        sql, params = "SELECT * FROM agent_runs WHERE id=?", [run_id]
        if user_id is not None:
            sql += " AND user_id=?"
            params.append(user_id)
        with self._db.query() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
        return _run(row) if row else None

    def update_run(self, *, run_id: str, status: str, phase: str, current_role: str | None = None) -> AgentRunRow:
        now = _now()
        finished = now if status in {"SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"} else None
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE agent_runs SET status=?,phase=?,current_role=?,updated_at=?,finished_at=COALESCE(?,finished_at) WHERE id=?",
                (status, phase, current_role, now, finished, run_id),
            )
            row = conn.execute("SELECT * FROM agent_runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise AppException(code="AGENT_RUN_NOT_FOUND", http_status=404, message="运行不存在")
        return _run(row)

    def list_incomplete_runs(self) -> list[AgentRunRow]:
        with self._db.query() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_runs WHERE status IN ('QUEUED','RUNNING','AWAITING_APPROVAL') ORDER BY created_at,id"
            ).fetchall()
        return [_run(row) for row in rows]

    def append_event(self, *, run_id: str, event_type: str, summary: str, artifact_id: str | None = None, approval_id: str | None = None) -> AgentEventRow:
        with self._db.transaction() as conn:
            run = conn.execute("SELECT * FROM agent_runs WHERE id=?", (run_id,)).fetchone()
            if not run:
                raise AppException(code="AGENT_RUN_NOT_FOUND", http_status=404, message="运行不存在")
            sequence = conn.execute(
                "SELECT COALESCE(MAX(sequence),0)+1 FROM agent_events WHERE run_id=?", (run_id,)
            ).fetchone()[0]
            event_id, now = _id("evt"), _now()
            conn.execute(
                """INSERT INTO agent_events(id,run_id,sequence,type,status,phase,role,summary,progress_current,progress_total,artifact_id,approval_id,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (event_id, run_id, sequence, event_type, run["status"], run["phase"], run["current_role"], summary[:500], run["progress_current"], run["progress_total"], artifact_id, approval_id, now),
            )
            return _event(conn.execute("SELECT * FROM agent_events WHERE id=?", (event_id,)).fetchone())

    def list_events(self, *, run_id: str, after_event_id: str | None = None, limit: int = 200) -> list[AgentEventRow]:
        after_sequence = 0
        with self._db.query() as conn:
            if after_event_id:
                row = conn.execute(
                    "SELECT sequence FROM agent_events WHERE id=? AND run_id=?", (after_event_id, run_id)
                ).fetchone()
                after_sequence = int(row[0]) if row else 0
            rows = conn.execute(
                "SELECT * FROM agent_events WHERE run_id=? AND sequence>? ORDER BY sequence LIMIT ?",
                (run_id, after_sequence, min(max(limit, 1), 500)),
            ).fetchall()
        return [_event(row) for row in rows]

    def begin_tool_call(self, *, run_id: str, tool_name: str, idempotency_key: str, request_hash: str) -> tuple[AgentToolCallRow, bool]:
        with self._db.transaction() as conn:
            existing = conn.execute(
                "SELECT * FROM agent_tool_calls WHERE run_id=? AND tool_name=? AND idempotency_key=?",
                (run_id, tool_name, idempotency_key),
            ).fetchone()
            if existing:
                if existing["request_hash"] != request_hash:
                    raise AppException(code="AGENT_IDEMPOTENCY_CONFLICT", http_status=409, message="幂等键已用于不同请求")
                return _tool(existing), True
            call_id = _id("tool")
            conn.execute(
                """INSERT INTO agent_tool_calls(id,run_id,tool_name,idempotency_key,request_hash,status,started_at)
                   VALUES(?,?,?,?,?,'STARTED',?)""",
                (call_id, run_id, tool_name, idempotency_key, request_hash, _now()),
            )
            return _tool(conn.execute("SELECT * FROM agent_tool_calls WHERE id=?", (call_id,)).fetchone()), False
