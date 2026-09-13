"""CampusAgentRuntime 仓储。

封装 agent_jobs/runs/steps/events/traces/snapshots/memories/approvals/citations 的 CRUD。
不保存敏感数据(prompt、隐藏推理、凭据)。
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from ..database.sqlite_db import Database
from ..models.agent_runtime import AgentApprovalRow


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class AgentRuntimeRepository:
    """agent_jobs/runs/steps/events/traces 仓储。"""

    def __init__(self, db: Database) -> None:
        self._db = db

    def _conn(self) -> sqlite3.Connection:
        return self._db._connect()

    def _release(self, conn: sqlite3.Connection) -> None:
        self._db._release(conn)

    # ===== Job =====

    def create_job(
        self,
        *,
        user_id: str,
        job_kind: str,
        input_ref: dict | None = None,
        idempotency_key: Optional[str] = None,
    ) -> str:
        job_id = _uuid("job")
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO agent_jobs (job_id, user_id, job_kind, status, idempotency_key, "
                "input_ref_json, created_at, updated_at) VALUES (?, ?, ?, 'QUEUED', ?, ?, ?, ?)",
                (
                    job_id,
                    user_id,
                    job_kind,
                    idempotency_key,
                    json.dumps(input_ref or {}, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            conn.commit()
            return job_id
        finally:
            self._release(conn)

    def get_job(self, job_id: str) -> Optional[dict]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT job_id, user_id, job_kind, status, created_at, updated_at, "
                "idempotency_key, input_ref_json FROM agent_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if not row:
                return None
            return dict(row)
        finally:
            self._release(conn)

    def find_job_by_idempotency(self, user_id: str, idempotency_key: str) -> Optional[dict]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT job_id, user_id, job_kind, status, created_at, updated_at, "
                "idempotency_key, input_ref_json "
                "FROM agent_jobs WHERE user_id = ? AND idempotency_key = ?",
                (user_id, idempotency_key),
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._release(conn)

    def update_job_input_ref(self, job_id: str, input_ref: dict) -> None:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE agent_jobs SET input_ref_json = ?, updated_at = ? WHERE job_id = ?",
                (json.dumps(input_ref, ensure_ascii=False), _now(), job_id),
            )
            conn.commit()
        finally:
            self._release(conn)

    # ===== Run =====

    def create_run(
        self,
        *,
        job_id: str,
        user_id: str,
        request_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> str:
        run_id = _uuid("run")
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO agent_runs (run_id, job_id, user_id, status, phase, request_id, "
                "idempotency_key, created_at, updated_at) VALUES (?, ?, ?, 'QUEUED', 'IDLE', ?, ?, ?, ?)",
                (run_id, job_id, user_id, request_id, idempotency_key, now, now),
            )
            conn.execute(
                "UPDATE agent_jobs SET status = 'RUNNING', updated_at = ? WHERE job_id = ?",
                (now, job_id),
            )
            conn.commit()
            return run_id
        finally:
            self._release(conn)

    def get_run(self, run_id: str) -> Optional[dict]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT run_id, job_id, user_id, status, phase, risk_level, started_at, "
                "finished_at, error_code, error_message, request_id, idempotency_key, "
                "created_at, updated_at FROM agent_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._release(conn)

    def get_run_by_job(self, job_id: str) -> Optional[dict]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT run_id, job_id, user_id, status, phase, risk_level, started_at, "
                "finished_at, error_code, error_message, request_id, idempotency_key, "
                "created_at, updated_at FROM agent_runs WHERE job_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (job_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._release(conn)

    def update_run(
        self,
        run_id: str,
        *,
        status: Optional[str] = None,
        phase: Optional[str] = None,
        risk_level: Optional[str] = None,
        started_at: Optional[str] = None,
        finished_at: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        now = _now()
        fields: list[str] = ["updated_at = ?"]
        params: list = [now]
        for name, value in [
            ("status", status),
            ("phase", phase),
            ("risk_level", risk_level),
            ("started_at", started_at),
            ("finished_at", finished_at),
            ("error_code", error_code),
            ("error_message", error_message),
        ]:
            if value is not None:
                fields.append(f"{name} = ?")
                params.append(value)
        params.append(run_id)
        conn = self._conn()
        try:
            conn.execute(f"UPDATE agent_runs SET {', '.join(fields)} WHERE run_id = ?", params)
            conn.commit()
        finally:
            self._release(conn)

    def list_runs_by_job(self, job_id: str) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT run_id, job_id, user_id, status, phase, created_at, updated_at "
                "FROM agent_runs WHERE job_id = ? ORDER BY created_at DESC",
                (job_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            self._release(conn)

    def list_incomplete_runs(self) -> list[dict]:
        """列出所有未完成 run(用于 RECOVERY_CHECKING)。"""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT run_id, job_id, user_id, status, phase, created_at, updated_at "
                "FROM agent_runs WHERE status IN ('QUEUED', 'RUNNING', 'AWAITING_APPROVAL') "
                "ORDER BY created_at ASC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            self._release(conn)

    def list_stale_runs(self, *, older_than_iso: str) -> list[dict]:
        """列出超过阈值仍未结束的 run(用于僵尸 run 兜底清理)。"""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT run_id, job_id, user_id, status, phase, created_at, updated_at "
                "FROM agent_runs WHERE status IN ('QUEUED', 'RUNNING', 'AWAITING_APPROVAL') "
                "AND updated_at < ? ORDER BY updated_at ASC",
                (older_than_iso,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            self._release(conn)

    # ===== Step =====

    def create_step(
        self,
        *,
        run_id: str,
        role: str,
        phase: str,
        sequence: int,
        summary: Optional[str] = None,
    ) -> str:
        step_id = _uuid("step")
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO agent_run_steps (step_id, run_id, role, phase, sequence, "
                "started_at, status, summary) VALUES (?, ?, ?, ?, ?, ?, 'running', ?)",
                (step_id, run_id, role, phase, sequence, now, summary),
            )
            conn.commit()
            return step_id
        finally:
            self._release(conn)

    # ===== Event(单调序列) =====

    def append_event(
        self,
        *,
        run_id: str,
        type: str,
        status: str,
        phase: str,
        role: Optional[str] = None,
        summary: Optional[str] = None,
        progress: Optional[dict] = None,
        artifact_id: Optional[str] = None,
        approval_id: Optional[str] = None,
    ) -> tuple[str, int]:
        """追加事件,返回 (event_id, sequence)。sequence 在 run 内单调递增。"""
        event_id = _uuid("evt")
        now = _now()
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) AS max_seq FROM agent_events WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            sequence = int(row["max_seq"]) + 1
            conn.execute(
                "INSERT INTO agent_events (event_id, run_id, sequence, type, status, phase, "
                "role, summary, progress_json, artifact_id, approval_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    run_id,
                    sequence,
                    type,
                    status,
                    phase,
                    role,
                    summary,
                    json.dumps(progress) if progress else None,
                    artifact_id,
                    approval_id,
                    now,
                ),
            )
            conn.commit()
            return event_id, sequence
        finally:
            self._release(conn)

    def list_events(self, run_id: str, after_sequence: int = 0, limit: int = 100) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT event_id, run_id, sequence, type, status, phase, role, summary, "
                "progress_json, artifact_id, approval_id, created_at "
                "FROM agent_events WHERE run_id = ? AND sequence > ? "
                "ORDER BY sequence ASC LIMIT ?",
                (run_id, after_sequence, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            self._release(conn)

    # ===== Tool call trace =====

    def record_tool_call_start(
        self,
        *,
        run_id: str,
        tool_name: str,
        request_hash: str,
        step_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> str:
        call_id = _uuid("tcall")
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO agent_tool_calls (call_id, run_id, step_id, tool_name, "
                "idempotency_key, request_hash, status, started_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'running', ?)",
                (call_id, run_id, step_id, tool_name, idempotency_key, request_hash, now),
            )
            conn.commit()
            return call_id
        finally:
            self._release(conn)

    def record_tool_call_finish(
        self,
        call_id: str,
        *,
        status: str,
        result_digest: Optional[str] = None,
        error_code: Optional[str] = None,
    ) -> None:
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE agent_tool_calls SET status = ?, result_digest = ?, "
                "error_code = ?, finished_at = ? WHERE call_id = ?",
                (status, result_digest, error_code, now, call_id),
            )
            conn.commit()
        finally:
            self._release(conn)

    def find_tool_call_by_idempotency(
        self, run_id: str, idempotency_key: str, request_hash: str
    ) -> Optional[dict]:
        """幂等判重:相同 idempotency_key + request_hash 视为重复。"""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT call_id, status, result_digest, error_code FROM agent_tool_calls "
                "WHERE run_id = ? AND idempotency_key = ? AND request_hash = ?",
                (run_id, idempotency_key, request_hash),
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._release(conn)

    # ===== Model call trace =====

    def record_model_call(
        self,
        *,
        run_id: str,
        provider: str,
        route_policy: str,
        model: str,
        status: str,
        latency_ms: int,
        step_id: Optional[str] = None,
        fallback_reason: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        cached_tokens: Optional[int] = None,
    ) -> str:
        """记录一次模型调用。

        只保存元数据与 token 用量,绝不保存 prompt、消息或隐藏推理。
        """
        call_id = _uuid("mcall")
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO agent_model_calls (call_id, run_id, step_id, provider, "
                "route_policy, model, status, latency_ms, fallback_reason, "
                "prompt_tokens, completion_tokens, total_tokens, cached_tokens, "
                "started_at, finished_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    call_id,
                    run_id,
                    step_id,
                    provider,
                    route_policy,
                    model,
                    status,
                    latency_ms,
                    fallback_reason,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    cached_tokens,
                    now,
                    now,
                ),
            )
            conn.commit()
            return call_id
        finally:
            self._release(conn)

    def model_usage(self, run_id: str) -> dict:
        """汇总某个 run 的 token 用量与调用次数(用于成本展示与论文指标)。"""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS calls, "
                "COALESCE(SUM(total_tokens), 0) AS total_tokens, "
                "COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens, "
                "COALESCE(SUM(completion_tokens), 0) AS completion_tokens, "
                "COALESCE(SUM(cached_tokens), 0) AS cached_tokens, "
                "COALESCE(SUM(latency_ms), 0) AS latency_ms "
                "FROM agent_model_calls WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            return dict(row) if row is not None else {
                "calls": 0,
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cached_tokens": 0,
                "latency_ms": 0,
            }
        finally:
            self._release(conn)

    # ===== Context snapshot =====

    def save_snapshot(
        self,
        *,
        user_id: str,
        source_digest: str,
        valid_until: str,
        run_id: Optional[str] = None,
        scope: Optional[dict] = None,
        facts: Optional[dict] = None,
        source_refs: Optional[list] = None,
    ) -> str:
        snapshot_id = _uuid("ctx")
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO agent_context_snapshots (snapshot_id, run_id, user_id, scope_json, "
                "facts_json, source_refs_json, source_digest, generated_at, valid_until, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    snapshot_id,
                    run_id,
                    user_id,
                    json.dumps(scope or {}, ensure_ascii=False),
                    json.dumps(facts or {}, ensure_ascii=False),
                    json.dumps(source_refs or [], ensure_ascii=False),
                    source_digest,
                    now,
                    valid_until,
                    now,
                ),
            )
            conn.commit()
            return snapshot_id
        finally:
            self._release(conn)

    def get_snapshot(self, snapshot_id: str) -> Optional[dict]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT snapshot_id, run_id, user_id, scope_json, facts_json, source_refs_json, "
                "source_digest, generated_at, valid_until, created_at "
                "FROM agent_context_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._release(conn)

    # ===== Approval =====

    def create_approval(
        self,
        *,
        run_id: str,
        user_id: str,
        risk_level: str,
        action_summary: str,
        expires_at: str,
    ) -> str:
        approval_id = _uuid("apv")
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO agent_approvals (approval_id, run_id, user_id, status, risk_level, "
                "action_summary, expires_at, created_at) VALUES (?, ?, ?, 'PENDING', ?, ?, ?, ?)",
                (approval_id, run_id, user_id, risk_level, action_summary, expires_at, now),
            )
            conn.commit()
            return approval_id
        finally:
            self._release(conn)

    def get_approval(self, approval_id: str) -> Optional[AgentApprovalRow]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT approval_id, run_id, user_id, status, risk_level, action_summary, "
                "expires_at, resolved_at, decision_reason, created_at FROM agent_approvals "
                "WHERE approval_id = ?",
                (approval_id,),
            ).fetchone()
            if not row:
                return None
            return AgentApprovalRow(
                approval_id=row["approval_id"],
                run_id=row["run_id"],
                user_id=row["user_id"],
                risk_level=row["risk_level"],
                action_summary=row["action_summary"],
                expires_at=row["expires_at"],
                created_at=row["created_at"],
                status=row["status"],
                resolved_at=row["resolved_at"],
                decision_reason=row["decision_reason"],
            )
        finally:
            self._release(conn)

    def resolve_approval(
        self,
        approval_id: str,
        *,
        status: str,
        decision_reason: Optional[str] = None,
    ) -> None:
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE agent_approvals SET status = ?, resolved_at = ?, decision_reason = ? "
                "WHERE approval_id = ?",
                (status, now, decision_reason, approval_id),
            )
            conn.commit()
        finally:
            self._release(conn)

    def expire_approvals(self, now: Optional[str] = None) -> int:
        """过期审批。过期绝不等于批准。返回过期条数。"""
        now = now or _now()
        conn = self._conn()
        try:
            cur = conn.execute(
                "UPDATE agent_approvals SET status = 'EXPIRED' "
                "WHERE status = 'PENDING' AND expires_at < ?",
                (now,),
            )
            conn.commit()
            return cur.rowcount
        finally:
            self._release(conn)

    # ===== Memory =====

    def save_memory(
        self,
        *,
        user_id: str,
        kind: str,
        content_summary: str,
        sensitivity: str = "low",
        confirmed: bool = False,
        model_may_consume: bool = False,
        provenance: Optional[str] = None,
        valid_until: Optional[str] = None,
    ) -> str:
        memory_id = _uuid("mem")
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO agent_memories (memory_id, user_id, kind, content_summary, "
                "sensitivity, confirmed, model_may_consume, provenance, valid_until, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    memory_id,
                    user_id,
                    kind,
                    content_summary,
                    sensitivity,
                    int(confirmed),
                    int(model_may_consume),
                    provenance,
                    valid_until,
                    now,
                    now,
                ),
            )
            conn.commit()
            return memory_id
        finally:
            self._release(conn)

    def withdraw_memory(self, memory_id: str) -> None:
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE agent_memories SET withdrawn = 1, model_may_consume = 0, updated_at = ? "
                "WHERE memory_id = ?",
                (now, memory_id),
            )
            conn.commit()
        finally:
            self._release(conn)

    def list_memories(self, user_id: str) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT memory_id, user_id, kind, content_summary, sensitivity, confirmed, "
                "withdrawn, model_may_consume, created_at FROM agent_memories "
                "WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            self._release(conn)


__all__ = ["AgentRuntimeRepository"]
