from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4

from ..core.exceptions import AppException
from ..database.sqlite_db import Database
from ..models.agent_runtime import (
    AgentApprovalRow,
    AgentEventRow,
    AgentJobRow,
    AgentRunRow,
    AgentRunStepRow,
    AgentToolCallRow,
)


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


def _approval(row) -> AgentApprovalRow:
    return AgentApprovalRow(**dict(row))


def _step(row) -> AgentRunStepRow:
    return AgentRunStepRow(**dict(row))


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

    def create_job_idempotent(self, *, user_id: str, domain: str, objective_summary: str,
                              total_steps: int, idempotency_key: str) -> tuple[AgentJobRow, AgentRunRow, bool]:
        request_hash = hashlib.sha256(json.dumps(
            {"domain": domain, "objective_summary": objective_summary, "total_steps": total_steps},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        now = _now()
        with self._db.transaction() as conn:
            existing = conn.execute(
                "SELECT request_hash,job_id FROM agent_job_requests WHERE user_id=? AND idempotency_key=?",
                (user_id, idempotency_key),
            ).fetchone()
            if existing:
                if existing["request_hash"] != request_hash:
                    raise AppException(code="AGENT_IDEMPOTENCY_CONFLICT", http_status=409, message="幂等键已用于不同请求")
                job = _job(conn.execute("SELECT * FROM agent_jobs WHERE id=?", (existing["job_id"],)).fetchone())
                run = _run(conn.execute(
                    "SELECT * FROM agent_runs WHERE job_id=? ORDER BY created_at DESC,id DESC LIMIT 1", (job.id,)
                ).fetchone())
                return job, run, True
            job_id, run_id = _id("job"), _id("run")
            conn.execute(
                "INSERT INTO agent_jobs(id,user_id,domain,objective_summary,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (job_id, user_id, domain, objective_summary[:500], "ACTIVE", now, now),
            )
            conn.execute(
                """INSERT INTO agent_runs(id,job_id,user_id,domain,status,phase,progress_current,progress_total,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (run_id, job_id, user_id, domain, "QUEUED", "IDLE", 0, total_steps, now, now),
            )
            conn.execute(
                "INSERT INTO agent_job_requests(user_id,idempotency_key,request_hash,job_id,created_at) VALUES(?,?,?,?,?)",
                (user_id, idempotency_key, request_hash, job_id, now),
            )
            return (
                _job(conn.execute("SELECT * FROM agent_jobs WHERE id=?", (job_id,)).fetchone()),
                _run(conn.execute("SELECT * FROM agent_runs WHERE id=?", (run_id,)).fetchone()),
                False,
            )

    def create_run(self, *, job_id: str, user_id: str, domain: str, total_steps: int) -> AgentRunRow:
        run_id, now = _id("run"), _now()
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO agent_runs(id,job_id,user_id,domain,status,phase,progress_current,progress_total,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (run_id, job_id, user_id, domain, "QUEUED", "IDLE", 0, total_steps, now, now),
            )
            return _run(conn.execute("SELECT * FROM agent_runs WHERE id=?", (run_id,)).fetchone())

    def get_job(self, *, job_id: str, user_id: str) -> AgentJobRow | None:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM agent_jobs WHERE id=? AND user_id=?", (job_id, user_id)
            ).fetchone()
        return _job(row) if row else None

    def latest_run_for_job(self, *, job_id: str, user_id: str) -> AgentRunRow | None:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM agent_runs WHERE job_id=? AND user_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
                (job_id, user_id),
            ).fetchone()
        return _run(row) if row else None

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

    def set_progress(self, *, run_id: str, current: int) -> None:
        """单调推进进度，避免恢复重放时进度倒退。"""
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE agent_runs SET progress_current=?,updated_at=? WHERE id=? AND progress_current<?",
                (current, _now(), run_id, current),
            )

    # ===== 运行步骤（线性状态机）=====

    def ensure_step(self, *, run_id: str, sequence: int, role: str, safe_summary: str) -> AgentRunStepRow:
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO agent_run_steps(id,run_id,sequence,role,status,safe_summary)
                   VALUES(?,?,?,?,'PENDING',?)""",
                (_id("step"), run_id, sequence, role, safe_summary[:500]),
            )
            row = conn.execute(
                "SELECT * FROM agent_run_steps WHERE run_id=? AND sequence=?", (run_id, sequence)
            ).fetchone()
        return _step(row)

    def start_step(self, *, run_id: str, sequence: int) -> AgentRunStepRow:
        with self._db.transaction() as conn:
            conn.execute(
                """UPDATE agent_run_steps SET status='RUNNING',started_at=COALESCE(started_at,?),finished_at=NULL
                   WHERE run_id=? AND sequence=?""",
                (_now(), run_id, sequence),
            )
            row = conn.execute(
                "SELECT * FROM agent_run_steps WHERE run_id=? AND sequence=?", (run_id, sequence)
            ).fetchone()
        if row is None:
            raise AppException(code="AGENT_RUN_NOT_FOUND", http_status=404, message="运行步骤不存在")
        return _step(row)

    def finish_step(self, *, run_id: str, sequence: int, status: str,
                    safe_summary: str | None = None) -> AgentRunStepRow:
        with self._db.transaction() as conn:
            if safe_summary is None:
                conn.execute(
                    "UPDATE agent_run_steps SET status=?,finished_at=? WHERE run_id=? AND sequence=?",
                    (status, _now(), run_id, sequence),
                )
            else:
                conn.execute(
                    "UPDATE agent_run_steps SET status=?,safe_summary=?,finished_at=? WHERE run_id=? AND sequence=?",
                    (status, safe_summary[:500], _now(), run_id, sequence),
                )
            row = conn.execute(
                "SELECT * FROM agent_run_steps WHERE run_id=? AND sequence=?", (run_id, sequence)
            ).fetchone()
        if row is None:
            raise AppException(code="AGENT_RUN_NOT_FOUND", http_status=404, message="运行步骤不存在")
        return _step(row)

    def list_steps(self, *, run_id: str) -> list[AgentRunStepRow]:
        with self._db.query() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_run_steps WHERE run_id=? ORDER BY sequence", (run_id,)
            ).fetchall()
        return [_step(row) for row in rows]

    # ===== 工具调用收尾 =====

    def finish_tool_call(self, *, call_id: str, status: str, result_digest: str | None = None,
                         error_code: str | None = None) -> AgentToolCallRow:
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE agent_tool_calls SET status=?,finished_at=?,result_digest=?,error_code=? WHERE id=?",
                (status, _now(), result_digest, error_code, call_id),
            )
            row = conn.execute("SELECT * FROM agent_tool_calls WHERE id=?", (call_id,)).fetchone()
        if row is None:
            raise AppException(code="AGENT_RUN_NOT_FOUND", http_status=404, message="工具调用不存在")
        return _tool(row)

    # ===== 审批查询 =====

    def latest_approval_for_run(self, *, run_id: str) -> AgentApprovalRow | None:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM agent_approvals WHERE run_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
                (run_id,),
            ).fetchone()
        return _approval(row) if row else None

    def pending_approval_for_run(self, *, run_id: str) -> AgentApprovalRow | None:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM agent_approvals WHERE run_id=? AND status='PENDING' ORDER BY created_at DESC,id DESC LIMIT 1",
                (run_id,),
            ).fetchone()
        return _approval(row) if row else None

    # ===== 上下文快照（Run ↔ 领域对象绑定）=====

    def create_context_snapshot(self, *, run_id: str, user_id: str, scope: dict, facts: dict,
                                source_refs: list[str], source_digest: str, valid_until: str) -> str:
        snapshot_id, now = _id("ctx"), _now()
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO agent_context_snapshots(id,run_id,user_id,scope_json,facts_json,source_refs_json,source_digest,generated_at,valid_until)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (snapshot_id, run_id, user_id,
                 json.dumps(scope, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                 json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                 json.dumps(source_refs, ensure_ascii=False), source_digest, now, valid_until),
            )
            conn.execute(
                "UPDATE agent_runs SET context_snapshot_id=?,updated_at=? WHERE id=?",
                (snapshot_id, now, run_id),
            )
        return snapshot_id

    def get_context_snapshot(self, *, snapshot_id: str, user_id: str) -> dict | None:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM agent_context_snapshots WHERE id=? AND user_id=?", (snapshot_id, user_id)
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["scope"] = json.loads(data.pop("scope_json"))
        data["facts"] = json.loads(data.pop("facts_json"))
        data["source_refs"] = json.loads(data.pop("source_refs_json"))
        return data

    def find_run_for_scope(self, *, user_id: str, domain: str, key: str, value: str) -> AgentRunRow | None:
        """按上下文快照的 scope 精确反查最近的运行；扫描条数有上限，且只在 Python 侧比对。"""
        with self._db.query() as conn:
            rows = conn.execute(
                """SELECT r.*, s.scope_json AS scope_json FROM agent_runs r
                   JOIN agent_context_snapshots s ON s.id=r.context_snapshot_id
                   WHERE r.user_id=? AND r.domain=? ORDER BY r.created_at DESC,r.id DESC LIMIT 50""",
                (user_id, domain),
            ).fetchall()
        for row in rows:
            data = dict(row)
            try:
                scope = json.loads(data.pop("scope_json"))
            except (TypeError, ValueError):
                continue
            if isinstance(scope, dict) and scope.get(key) == value:
                return _run(data)
        return None

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

    def create_approval(self, *, run_id: str, user_id: str, risk_level: str,
                        action_digest: str, summary: str, expires_at: str, now: str) -> AgentApprovalRow:
        approval_id = _id("approval")
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO agent_approvals(id,run_id,user_id,status,risk_level,action_digest,summary,expires_at,created_at)
                   VALUES(?,?,?,'PENDING',?,?,?,?,?)""",
                (approval_id, run_id, user_id, risk_level, action_digest, summary[:500], expires_at, now),
            )
            return _approval(conn.execute("SELECT * FROM agent_approvals WHERE id=?", (approval_id,)).fetchone())

    def get_approval(self, *, approval_id: str, user_id: str) -> AgentApprovalRow | None:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM agent_approvals WHERE id=? AND user_id=?", (approval_id, user_id)
            ).fetchone()
        return _approval(row) if row else None

    def decide_approval(self, *, approval_id: str, user_id: str, status: str, decided_at: str) -> AgentApprovalRow | None:
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE agent_approvals SET status=?,decided_at=? WHERE id=? AND user_id=? AND status='PENDING'",
                (status, decided_at, approval_id, user_id),
            )
            row = conn.execute(
                "SELECT * FROM agent_approvals WHERE id=? AND user_id=?", (approval_id, user_id)
            ).fetchone()
        return _approval(row) if row else None
