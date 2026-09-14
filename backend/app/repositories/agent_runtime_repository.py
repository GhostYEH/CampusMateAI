"""CampusAgentRuntime 仓储。

封装 agent_jobs/runs/steps/events/traces/snapshots/memories/approvals/citations 的 CRUD。
不保存敏感数据(prompt、隐藏推理、凭据)。
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from ..core.exceptions import AgentIdempotencyConflict, AgentRuntimeError
from ..database.sqlite_db import Database
from ..models.agent_runtime import AgentApprovalRow


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


# agent_runs 的完整列清单。新增列必须同步到这里,否则领取/恢复读到的行会缺字段。
_RUN_COLUMNS = (
    "run_id, job_id, user_id, status, phase, risk_level, started_at, finished_at, "
    "error_code, error_message, request_id, idempotency_key, retry_of, "
    "handler_code, handler_version, attempt_no, next_attempt_at, lease_owner, "
    "lease_expires_at, heartbeat_at, checkpoint_json, created_at, updated_at"
)

# 幂等声明的默认作用域。工具调用等其它写路径可复用同一张表,只需换 scope。
IDEMPOTENCY_SCOPE_AGENT_JOB = "agent_job"

# 只有这些标量类型允许写回 job.input_ref —— 避免把大对象或敏感载荷塞进公开字段。
_SAFE_PATCH_TYPES = (str, int, float, bool, type(None))


def build_request_hash(job_kind: str, input_ref: dict | None) -> str:
    """由规范化后的 `job_kind + input_ref` 生成请求哈希。

    只取决于内容,不受 Header 顺序或 JSON 键顺序影响。
    """
    normalized = json.dumps(
        {"job_kind": job_kind, "input_ref": input_ref or {}},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _safe_input_ref_patch(patch: dict | None) -> dict:
    """过滤只能承载安全业务引用的写回补丁。"""
    if not patch:
        return {}
    safe: dict[str, Any] = {}
    for key, value in patch.items():
        if not isinstance(key, str) or not key:
            continue
        if isinstance(value, _SAFE_PATCH_TYPES):
            safe[key] = value
    return safe


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

    def list_jobs(self, user_id: str, *, page: int = 1, page_size: int = 50) -> list[dict]:
        offset = max(page - 1, 0) * page_size
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT job_id, user_id, job_kind, status, created_at, updated_at, "
                "idempotency_key, input_ref_json FROM agent_jobs WHERE user_id = ? "
                "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (user_id, page_size, offset),
            ).fetchall()
            return [dict(row) for row in rows]
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

    # ===== 原子复合写(v2 持久化队列) =====
    #
    # 以下方法把"运行状态变化 + 对应事件 + 必要的业务写回"放进同一个事务。
    # 任何一步失败都会整体回滚,避免事件与状态不一致的孤儿记录。
    # 状态更新一律带期望状态 / 租约持有者条件,更新行数不为 1 即视为并发冲突。

    def _insert_event(
        self,
        conn: sqlite3.Connection,
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
        """在给定连接上追加事件,返回 (event_id, sequence)。"""
        event_id = _uuid("evt")
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
                event_id, run_id, sequence, type, status, phase, role, summary,
                json.dumps(progress, ensure_ascii=False) if progress else None,
                artifact_id, approval_id, _now(),
            ),
        )
        return event_id, sequence

    def _fetch_run(self, conn: sqlite3.Connection, run_id: str) -> Optional[dict]:
        row = conn.execute(
            f"SELECT {_RUN_COLUMNS} FROM agent_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        return dict(row) if row else None

    def _load_claim(
        self, conn: sqlite3.Connection, user_id: str, idempotency_key: str,
        scope: str = IDEMPOTENCY_SCOPE_AGENT_JOB,
    ) -> Optional[dict]:
        row = conn.execute(
            "SELECT scope, user_id, idempotency_key, request_hash, resource_id, created_at "
            "FROM agent_idempotency_claims "
            "WHERE scope = ? AND user_id = ? AND idempotency_key = ?",
            (scope, user_id, idempotency_key),
        ).fetchone()
        return dict(row) if row else None

    def create_job_with_run_and_event(
        self,
        *,
        user_id: str,
        job_kind: str,
        input_ref: dict | None = None,
        idempotency_key: Optional[str] = None,
        request_hash: Optional[str] = None,
        handler_code: Optional[str] = None,
        handler_version: Optional[str] = None,
        scope: str = IDEMPOTENCY_SCOPE_AGENT_JOB,
    ) -> dict:
        """原子创建 Job + 首个 Run + 幂等声明 + `RUN_QUEUED` 事件。

        相同 `(scope, user_id, idempotency_key)` 且相同 `request_hash` 时重放既有 Job;
        哈希不同抛 `AgentIdempotencyConflict`,并且不留下任何新记录。
        返回 `{"job_id", "run_id", "event_id", "sequence", "replayed", "job"}`。
        """
        now = _now()
        fingerprint = request_hash or ""
        with self._db.transaction() as conn:
            if idempotency_key:
                claim = self._load_claim(conn, user_id, idempotency_key, scope)
                if claim is not None:
                    if claim["request_hash"] != fingerprint:
                        raise AgentIdempotencyConflict("幂等键已用于不同的请求。")
                    replay_job = conn.execute(
                        "SELECT job_id, user_id, job_kind, status, created_at, updated_at, "
                        "idempotency_key, input_ref_json FROM agent_jobs WHERE job_id = ?",
                        (claim["resource_id"],),
                    ).fetchone()
                    if replay_job is not None:
                        replay_run = conn.execute(
                            f"SELECT {_RUN_COLUMNS} FROM agent_runs WHERE job_id = ? "
                            "ORDER BY created_at DESC, run_id DESC LIMIT 1",
                            (claim["resource_id"],),
                        ).fetchone()
                        return {
                            "job_id": claim["resource_id"],
                            "run_id": replay_run["run_id"] if replay_run else None,
                            "event_id": None,
                            "sequence": None,
                            "replayed": True,
                            "job": dict(replay_job),
                        }
            job_id = _uuid("job")
            conn.execute(
                "INSERT INTO agent_jobs (job_id, user_id, job_kind, status, idempotency_key, "
                "input_ref_json, created_at, updated_at) VALUES (?, ?, ?, 'QUEUED', ?, ?, ?, ?)",
                (
                    job_id, user_id, job_kind, idempotency_key,
                    json.dumps(input_ref or {}, ensure_ascii=False), now, now,
                ),
            )
            run_id = _uuid("run")
            conn.execute(
                "INSERT INTO agent_runs (run_id, job_id, user_id, status, phase, request_id, "
                "idempotency_key, handler_code, handler_version, attempt_no, next_attempt_at, "
                "created_at, updated_at) "
                "VALUES (?, ?, ?, 'QUEUED', 'IDLE', NULL, ?, ?, ?, 0, ?, ?, ?)",
                (run_id, job_id, user_id, idempotency_key, handler_code, handler_version,
                 now, now, now),
            )
            event_id, sequence = self._insert_event(
                conn, run_id=run_id, type="RUN_QUEUED", status="QUEUED", phase="IDLE",
                summary="任务已加入队列，等待执行",
            )
            if idempotency_key:
                conn.execute(
                    "INSERT INTO agent_idempotency_claims "
                    "(scope, user_id, idempotency_key, request_hash, resource_id, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (scope, user_id, idempotency_key, fingerprint, job_id, now),
                )
        return {
            "job_id": job_id,
            "run_id": run_id,
            "event_id": event_id,
            "sequence": sequence,
            "replayed": False,
            "job": self.get_job(job_id),
        }

    def transition_run_with_event(
        self,
        run_id: str,
        to_status: str,
        *,
        expected_statuses: Optional[Sequence[str]] = None,
        lease_owner: Optional[str] = None,
        phase: Optional[str] = None,
        risk_level: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        next_attempt_at: Optional[str] = None,
        checkpoint: Optional[dict] = None,
        clear_lease: bool = False,
        event_type: Optional[str] = None,
        event_status: Optional[str] = None,
        event_phase: Optional[str] = None,
        event_role: Optional[str] = None,
        event_summary: Optional[str] = None,
        event_progress: Optional[dict] = None,
        event_artifact_id: Optional[str] = None,
        event_approval_id: Optional[str] = None,
    ) -> dict:
        """原子地把 Run 转换到 `to_status` 并追加对应事件。

        `expected_statuses` / `lease_owner` 是乐观并发条件;更新行数不为 1 说明
        后到的 Worker 或用户操作已经改变了状态,抛 `AGENT_INVALID_STATE` 而不是覆盖。
        """
        now = _now()
        with self._db.transaction() as conn:
            run = self._fetch_run(conn, run_id)
            if run is None:
                raise AgentRuntimeError("Run 不存在", code="AGENT_RUN_NOT_FOUND", http_status=404)
            if expected_statuses is not None and run["status"] not in set(expected_statuses):
                raise AgentRuntimeError(
                    f"Run 当前状态({run['status']})不允许本次转换",
                    code="AGENT_INVALID_STATE", http_status=409,
                )
            if lease_owner is not None and run["lease_owner"] != lease_owner:
                raise AgentRuntimeError(
                    "Run 的租约不属于当前执行者",
                    code="AGENT_INVALID_STATE", http_status=409,
                )
            assignments = [
                "status = ?", "updated_at = ?",
            ]
            params: list[Any] = [to_status, now]
            if phase is not None:
                assignments.append("phase = ?")
                params.append(phase)
            if risk_level is not None:
                assignments.append("risk_level = ?")
                params.append(risk_level)
            if error_code is not None:
                assignments.append("error_code = ?")
                params.append(error_code)
            if error_message is not None:
                assignments.append("error_message = ?")
                params.append(error_message)
            if next_attempt_at is not None:
                assignments.append("next_attempt_at = ?")
                params.append(next_attempt_at)
            if checkpoint is not None:
                assignments.append("checkpoint_json = ?")
                params.append(json.dumps(checkpoint, ensure_ascii=False))
            if clear_lease:
                assignments.extend(["lease_owner = NULL", "lease_expires_at = NULL"])
            if to_status == "RUNNING" and not run["started_at"]:
                assignments.append("started_at = ?")
                params.append(now)
            if to_status in {"SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"}:
                assignments.append("finished_at = ?")
                params.append(now)
            params.append(run_id)
            cursor = conn.execute(
                f"UPDATE agent_runs SET {', '.join(assignments)} WHERE run_id = ?", params
            )
            if cursor.rowcount != 1:
                raise AgentRuntimeError(
                    "Run 状态已被并发修改，放弃本次转换",
                    code="AGENT_INVALID_STATE", http_status=409,
                )
            conn.execute(
                "UPDATE agent_jobs SET status = ?, updated_at = ? WHERE job_id = ?",
                (to_status, now, run["job_id"]),
            )
            if event_type:
                self._insert_event(
                    conn, run_id=run_id, type=event_type,
                    status=event_status or to_status, phase=event_phase or phase or run["phase"],
                    role=event_role, summary=event_summary, progress=event_progress,
                    artifact_id=event_artifact_id, approval_id=event_approval_id,
                )
        return self.get_run(run_id) or {}

    def complete_run_with_job_output_and_event(
        self,
        run_id: str,
        to_status: str,
        *,
        lease_owner: Optional[str] = None,
        expected_statuses: Optional[Sequence[str]] = None,
        job_input_ref_patch: Optional[dict] = None,
        phase: Optional[str] = None,
        risk_level: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        event_type: str = "RUN_COMPLETED",
        event_role: Optional[str] = None,
        event_summary: Optional[str] = None,
        event_progress: Optional[dict] = None,
        event_artifact_id: Optional[str] = None,
    ) -> dict:
        """原子地把结果引用写回 Job、置 Run 终态并追加完成事件。

        `job_input_ref_patch` 只接受标量值,并且与终态事件在同一事务提交;
        客户端在看到完成事件后重新 GET Job 时,必然已经能读到新的 `input_ref`。
        """
        now = _now()
        patch = _safe_input_ref_patch(job_input_ref_patch)
        with self._db.transaction() as conn:
            run = self._fetch_run(conn, run_id)
            if run is None:
                raise AgentRuntimeError("Run 不存在", code="AGENT_RUN_NOT_FOUND", http_status=404)
            if expected_statuses is not None and run["status"] not in set(expected_statuses):
                raise AgentRuntimeError(
                    f"Run 当前状态({run['status']})不允许本次转换",
                    code="AGENT_INVALID_STATE", http_status=409,
                )
            if lease_owner is not None and run["lease_owner"] != lease_owner:
                raise AgentRuntimeError(
                    "Run 的租约不属于当前执行者",
                    code="AGENT_INVALID_STATE", http_status=409,
                )
            if patch:
                row = conn.execute(
                    "SELECT input_ref_json FROM agent_jobs WHERE job_id = ?", (run["job_id"],)
                ).fetchone()
                current: dict = {}
                if row and row["input_ref_json"]:
                    try:
                        loaded = json.loads(row["input_ref_json"])
                        if isinstance(loaded, dict):
                            current = loaded
                    except (TypeError, ValueError):
                        current = {}
                current.update(patch)
                conn.execute(
                    "UPDATE agent_jobs SET input_ref_json = ?, status = ?, updated_at = ? "
                    "WHERE job_id = ?",
                    (json.dumps(current, ensure_ascii=False), to_status, now, run["job_id"]),
                )
            else:
                conn.execute(
                    "UPDATE agent_jobs SET status = ?, updated_at = ? WHERE job_id = ?",
                    (to_status, now, run["job_id"]),
                )
            assignments = ["status = ?", "finished_at = ?", "updated_at = ?",
                           "lease_owner = NULL", "lease_expires_at = NULL"]
            params: list[Any] = [to_status, now, now]
            if phase is not None:
                assignments.append("phase = ?")
                params.append(phase)
            if risk_level is not None:
                assignments.append("risk_level = ?")
                params.append(risk_level)
            if error_code is not None:
                assignments.append("error_code = ?")
                params.append(error_code)
            if error_message is not None:
                assignments.append("error_message = ?")
                params.append(error_message)
            params.append(run_id)
            cursor = conn.execute(
                f"UPDATE agent_runs SET {', '.join(assignments)} WHERE run_id = ?", params
            )
            if cursor.rowcount != 1:
                raise AgentRuntimeError(
                    "Run 状态已被并发修改，放弃本次完成",
                    code="AGENT_INVALID_STATE", http_status=409,
                )
            self._insert_event(
                conn, run_id=run_id, type=event_type, status=to_status,
                phase=phase or run["phase"], role=event_role, summary=event_summary,
                progress=event_progress, artifact_id=event_artifact_id,
            )
        return self.get_run(run_id) or {}

    # ===== 租约队列 =====

    def claim_next_run(
        self,
        *,
        owner: str,
        now: str,
        lease_expires_at: str,
        max_candidates: int = 5,
    ) -> Optional[dict]:
        """领取下一个可执行的 Run,并持有租约。

        只有 `QUEUED`、`next_attempt_at` 已到期且没有有效租约的运行可被领取。
        租约已过期的运行会被接管(崩溃恢复),未过期的不会被抢占。
        """
        with self._db.transaction() as conn:
            rows = conn.execute(
                "SELECT run_id FROM agent_runs "
                "WHERE status = 'QUEUED' "
                "AND (next_attempt_at IS NULL OR next_attempt_at <= ?) "
                "AND (lease_owner IS NULL OR lease_expires_at IS NULL OR lease_expires_at <= ?) "
                "ORDER BY created_at ASC, run_id ASC LIMIT ?",
                (now, now, max_candidates),
            ).fetchall()
            for row in rows:
                cursor = conn.execute(
                    "UPDATE agent_runs SET status = 'RUNNING', lease_owner = ?, "
                    "lease_expires_at = ?, heartbeat_at = ?, "
                    "started_at = COALESCE(started_at, ?), attempt_no = attempt_no + 1, "
                    "updated_at = ? "
                    "WHERE run_id = ? AND status = 'QUEUED' "
                    "AND (next_attempt_at IS NULL OR next_attempt_at <= ?) "
                    "AND (lease_owner IS NULL OR lease_expires_at IS NULL "
                    "OR lease_expires_at <= ?)",
                    (owner, lease_expires_at, now, now, now, row["run_id"], now, now),
                )
                if cursor.rowcount == 1:
                    claimed = self._fetch_run(conn, row["run_id"])
                    conn.execute(
                        "UPDATE agent_jobs SET status = 'RUNNING', updated_at = ? WHERE job_id = ?",
                        (now, claimed["job_id"]),
                    )
                    self._insert_event(
                        conn,
                        run_id=row["run_id"],
                        type="RUN_STARTED",
                        status="RUNNING",
                        phase="CONTEXT_BUILDING",
                        role="runtime",
                        summary="任务开始执行",
                    )
                    return claimed
        return None

    def renew_run_lease(
        self, run_id: str, owner: str, *, heartbeat_at: str, lease_expires_at: str
    ) -> dict:
        """续租。只有当前持有者可以续租。"""
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE agent_runs SET heartbeat_at = ?, lease_expires_at = ?, updated_at = ? "
                "WHERE run_id = ? AND lease_owner = ? AND status = 'RUNNING'",
                (heartbeat_at, lease_expires_at, heartbeat_at, run_id, owner),
            )
            if cursor.rowcount != 1:
                raise AgentRuntimeError(
                    "租约已失效或不属于当前执行者",
                    code="AGENT_INVALID_STATE", http_status=409,
                )
            return self._fetch_run(conn, run_id) or {}

    def save_checkpoint(
        self,
        run_id: str,
        owner: str,
        checkpoint: dict,
        *,
        heartbeat_at: str,
        lease_expires_at: Optional[str] = None,
    ) -> dict:
        """写入恢复点。租约过期后拒绝写入,防止僵尸 Worker 覆盖新进度。"""
        with self._db.transaction() as conn:
            if lease_expires_at:
                cursor = conn.execute(
                    "UPDATE agent_runs SET checkpoint_json = ?, heartbeat_at = ?, "
                    "lease_expires_at = ?, updated_at = ? "
                    "WHERE run_id = ? AND lease_owner = ? AND status = 'RUNNING' "
                    "AND (lease_expires_at IS NULL OR lease_expires_at >= ?)",
                    (json.dumps(checkpoint, ensure_ascii=False), heartbeat_at,
                     lease_expires_at, heartbeat_at, run_id, owner, heartbeat_at),
                )
            else:
                cursor = conn.execute(
                    "UPDATE agent_runs SET checkpoint_json = ?, heartbeat_at = ?, updated_at = ? "
                    "WHERE run_id = ? AND lease_owner = ? AND status = 'RUNNING' "
                    "AND (lease_expires_at IS NULL OR lease_expires_at >= ?)",
                    (json.dumps(checkpoint, ensure_ascii=False), heartbeat_at,
                     heartbeat_at, run_id, owner, heartbeat_at),
                )
            if cursor.rowcount != 1:
                raise AgentRuntimeError(
                    "租约已失效，无法写入恢复点",
                    code="AGENT_INVALID_STATE", http_status=409,
                )
            return self._fetch_run(conn, run_id) or {}

    def release_run_lease(self, run_id: str, owner: str) -> dict:
        """主动释放租约(正常结束或让出执行权)。"""
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE agent_runs SET lease_owner = NULL, lease_expires_at = NULL, "
                "heartbeat_at = ?, updated_at = ? WHERE run_id = ? AND lease_owner = ?",
                (_now(), _now(), run_id, owner),
            )
            if cursor.rowcount != 1:
                raise AgentRuntimeError(
                    "租约已失效或不属于当前执行者",
                    code="AGENT_INVALID_STATE", http_status=409,
                )
            return self._fetch_run(conn, run_id) or {}

    def list_expired_lease_runs(self, *, now: str, limit: int = 50) -> list[dict]:
        """列出租约已过期但仍未终态的运行(用于 Worker 崩溃恢复)。"""
        conn = self._conn()
        try:
            rows = conn.execute(
                f"SELECT {_RUN_COLUMNS} FROM agent_runs "
                "WHERE status IN ('RUNNING', 'QUEUED') AND lease_owner IS NOT NULL "
                "AND lease_expires_at IS NOT NULL AND lease_expires_at <= ? "
                "ORDER BY lease_expires_at ASC LIMIT ?",
                (now, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            self._release(conn)

    # ===== 事件游标 =====

    def get_event_sequence(self, run_id: str, event_id: str) -> Optional[int]:
        """由 `(run_id, event_id)` 直接定位 sequence,供 Last-Event-ID 续传使用。"""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT sequence FROM agent_events WHERE run_id = ? AND event_id = ?",
                (run_id, event_id),
            ).fetchone()
            return int(row["sequence"]) if row else None
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
        retry_of: Optional[str] = None,
        handler_code: Optional[str] = None,
        handler_version: Optional[str] = None,
    ) -> str:
        run_id = _uuid("run")
        now = _now()
        with self._db.transaction() as conn:
            conn.execute(
                "INSERT INTO agent_runs (run_id, job_id, user_id, status, phase, request_id, "
                "idempotency_key, retry_of, handler_code, handler_version, created_at, updated_at) "
                "VALUES (?, ?, ?, 'QUEUED', 'IDLE', ?, ?, ?, ?, ?, ?, ?)",
                (run_id, job_id, user_id, request_id, idempotency_key, retry_of,
                 handler_code, handler_version, now, now),
            )
            conn.execute(
                "UPDATE agent_jobs SET status = 'QUEUED', updated_at = ? WHERE job_id = ?",
                (now, job_id),
            )
            self._insert_event(
                conn, run_id=run_id, type="RUN_QUEUED", status="QUEUED", phase="IDLE",
                summary="任务已加入队列，等待执行",
            )
        return run_id

    def get_run(self, run_id: str) -> Optional[dict]:
        conn = self._conn()
        try:
            row = conn.execute(
                f"SELECT {_RUN_COLUMNS} FROM agent_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._release(conn)

    def get_run_by_job(self, job_id: str) -> Optional[dict]:
        conn = self._conn()
        try:
            row = conn.execute(
                f"SELECT {_RUN_COLUMNS} FROM agent_runs WHERE job_id = ? "
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
                "SELECT run_id, job_id, user_id, status, phase, retry_of, created_at, updated_at "
                "FROM agent_runs WHERE job_id = ? ORDER BY created_at DESC",
                (job_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            self._release(conn)

    def update_job_status(self, job_id: str, status: str) -> None:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE agent_jobs SET status = ?, updated_at = ? WHERE job_id = ?",
                (status, _now(), job_id),
            )
            conn.commit()
        finally:
            self._release(conn)

    def list_runs_for_user(self, user_id: str, *, page: int = 1, page_size: int = 50) -> list[dict]:
        offset = max(page - 1, 0) * page_size
        conn = self._conn()
        try:
            rows = conn.execute(
                f"SELECT {_RUN_COLUMNS} FROM agent_runs WHERE user_id = ? "
                "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (user_id, page_size, offset),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            self._release(conn)

    def find_run_by_idempotency(self, user_id: str, idempotency_key: str) -> Optional[dict]:
        conn = self._conn()
        try:
            row = conn.execute(
                f"SELECT {_RUN_COLUMNS} FROM agent_runs WHERE user_id = ? AND idempotency_key = ?",
                (user_id, idempotency_key),
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._release(conn)

    def find_control(self, run_id: str, idempotency_key: str) -> Optional[dict]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT command_id, run_id, user_id, action, idempotency_key, resulting_status, created_at "
                "FROM agent_run_controls WHERE run_id = ? AND idempotency_key = ?",
                (run_id, idempotency_key),
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._release(conn)

    def record_control(self, *, run_id: str, user_id: str, action: str,
                       idempotency_key: str, resulting_status: str) -> dict:
        command_id = _uuid("cmd")
        conn = self._conn()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO agent_run_controls "
                "(command_id, run_id, user_id, action, idempotency_key, resulting_status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (command_id, run_id, user_id, action, idempotency_key, resulting_status, _now()),
            )
            row = conn.execute(
                "SELECT command_id, run_id, user_id, action, idempotency_key, resulting_status, created_at "
                "FROM agent_run_controls WHERE run_id = ? AND idempotency_key = ?",
                (run_id, idempotency_key),
            ).fetchone()
            conn.commit()
            return dict(row)
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
        """追加不伴随状态变化事件,返回 (event_id, sequence)。

        只用于进度/观测类事件。任何伴随 `agent_runs.status` 变化的事件都必须走
        `transition_run_with_event()` 或 `complete_run_with_job_output_and_event()`。
        """
        with self._db.transaction() as conn:
            return self._insert_event(
                conn, run_id=run_id, type=type, status=status, phase=phase, role=role,
                summary=summary, progress=progress, artifact_id=artifact_id,
                approval_id=approval_id,
            )

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

    def get_memory(self, memory_id: str, user_id: str) -> Optional[dict]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT memory_id, user_id, kind, content_summary, sensitivity, confirmed, "
                "withdrawn, model_may_consume, provenance, valid_until, created_at, updated_at "
                "FROM agent_memories WHERE memory_id = ? AND user_id = ?",
                (memory_id, user_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._release(conn)

    def withdraw_memory(self, memory_id: str, user_id: str) -> bool:
        now = _now()
        conn = self._conn()
        try:
            cur = conn.execute(
                "UPDATE agent_memories SET withdrawn = 1, model_may_consume = 0, updated_at = ? "
                "WHERE memory_id = ? AND user_id = ?",
                (now, memory_id, user_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            self._release(conn)

    def list_memories(self, user_id: str) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT memory_id, user_id, kind, content_summary, sensitivity, confirmed, "
                "withdrawn, model_may_consume, provenance, valid_until, created_at, updated_at "
                "FROM agent_memories "
                "WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            self._release(conn)


__all__ = ["AgentRuntimeRepository"]
