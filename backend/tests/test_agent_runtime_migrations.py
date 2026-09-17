"""Agent runtime migration 测试 —— 验证 additive idempotent migration。"""
from __future__ import annotations

import sqlite3

import pytest

from app.database.sqlite_db import Database, AGENT_RUNTIME_SCHEMA_SQL

# v1 旧库 agent_runs 的列 —— 不含 v2 的 handler/attempt/lease/checkpoint 字段。
_LEGACY_AGENT_RUN_COLUMNS = """
CREATE TABLE agent_runs (
    run_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'QUEUED',
    phase TEXT NOT NULL DEFAULT 'IDLE',
    risk_level TEXT,
    started_at TEXT,
    finished_at TEXT,
    error_code TEXT,
    error_message TEXT,
    request_id TEXT,
    idempotency_key TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(job_id) REFERENCES agent_jobs(job_id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""

V2_AGENT_RUN_COLUMNS = (
    "handler_code",
    "handler_version",
    "attempt_no",
    "next_attempt_at",
    "lease_owner",
    "lease_expires_at",
    "heartbeat_at",
    "checkpoint_json",
)


def test_agent_runtime_tables_exist_after_init() -> None:
    db = Database(None)  # 内存库
    conn = db._connect()
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'agent_%'"
            ).fetchall()
        }
        expected = {
            "agent_jobs",
            "agent_runs",
            "agent_run_steps",
            "agent_context_snapshots",
            "agent_tool_calls",
            "agent_model_calls",
            "agent_events",
            "agent_memories",
            "agent_approvals",
            "agent_citations",
            "agent_artifacts",
        }
        assert expected <= tables, f"缺失表: {expected - tables}"
    finally:
        db._release(conn)


def test_migration_is_idempotent() -> None:
    db = Database(None)
    conn = db._connect()
    try:
        # 再次执行 schema 应不报错
        conn.executescript(AGENT_RUNTIME_SCHEMA_SQL)
        conn.commit()
        # 验证表仍存在
        count = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='agent_runs'"
        ).fetchone()[0]
        assert count == 1
    finally:
        db._release(conn)


def _seed_user(conn):
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
        "VALUES ('u1', 'u1', 'x', 'student', 't', 't')"
    )


def test_agent_tool_calls_has_idempotency_unique_index() -> None:
    db = Database(None)
    conn = db._connect()
    try:
        _seed_user(conn)
        conn.execute(
            "INSERT INTO agent_jobs (job_id, user_id, job_kind, status, created_at, updated_at) "
            "VALUES ('j1', 'u1', 'final_review', 'QUEUED', 't', 't')"
        )
        conn.execute(
            "INSERT INTO agent_runs (run_id, job_id, user_id, status, phase, "
            "created_at, updated_at) VALUES ('r1', 'j1', 'u1', 'QUEUED', 'IDLE', 't', 't')"
        )
        conn.execute(
            "INSERT INTO agent_tool_calls (call_id, run_id, tool_name, idempotency_key, "
            "request_hash, status, started_at) VALUES ('c1', 'r1', 't', 'k1', 'h1', 'running', 't')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO agent_tool_calls (call_id, run_id, tool_name, idempotency_key, "
                "request_hash, status, started_at) VALUES ('c2', 'r1', 't', 'k1', 'h1', 'running', 't')"
            )
    finally:
        db._release(conn)


def test_agent_events_sequence_unique_per_run() -> None:
    db = Database(None)
    conn = db._connect()
    try:
        _seed_user(conn)
        conn.execute(
            "INSERT INTO agent_jobs (job_id, user_id, job_kind, status, created_at, updated_at) "
            "VALUES ('j1', 'u1', 'final_review', 'QUEUED', 't', 't')"
        )
        conn.execute(
            "INSERT INTO agent_runs (run_id, job_id, user_id, status, phase, "
            "created_at, updated_at) VALUES ('r1', 'j1', 'u1', 'QUEUED', 'IDLE', 't', 't')"
        )
        conn.execute(
            "INSERT INTO agent_events (event_id, run_id, sequence, type, status, phase, created_at) "
            "VALUES ('e1', 'r1', 1, 'RUN_STARTED', 'RUNNING', 'IDLE', 't')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO agent_events (event_id, run_id, sequence, type, status, phase, created_at) "
                "VALUES ('e2', 'r1', 1, 'RUN_COMPLETED', 'SUCCEEDED', 'IDLE', 't')"
            )
    finally:
        db._release(conn)


def test_agent_memories_kind_check_constraint() -> None:
    db = Database(None)
    conn = db._connect()
    try:
        _seed_user(conn)
        conn.execute(
            "INSERT INTO agent_memories (memory_id, user_id, kind, content_summary, "
            "sensitivity, confirmed, withdrawn, model_may_consume, created_at, updated_at) "
            "VALUES ('m1', 'u1', 'CONFIRMED_PREFERENCE', 'x', 'low', 0, 0, 0, 't', 't')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO agent_memories (memory_id, user_id, kind, content_summary, "
                "sensitivity, confirmed, withdrawn, model_may_consume, created_at, updated_at) "
                "VALUES ('m2', 'u1', 'RAW_CONVERSATION', 'x', 'low', 0, 0, 0, 't', 't')"
            )
    finally:
        db._release(conn)


def test_agent_approvals_status_check_constraint() -> None:
    db = Database(None)
    conn = db._connect()
    try:
        _seed_user(conn)
        conn.execute(
            "INSERT INTO agent_jobs (job_id, user_id, job_kind, status, created_at, updated_at) "
            "VALUES ('j1', 'u1', 'final_review', 'QUEUED', 't', 't')"
        )
        conn.execute(
            "INSERT INTO agent_runs (run_id, job_id, user_id, status, phase, "
            "created_at, updated_at) VALUES ('r1', 'j1', 'u1', 'QUEUED', 'IDLE', 't', 't')"
        )
        conn.execute(
            "INSERT INTO agent_approvals (approval_id, run_id, user_id, status, risk_level, "
            "action_summary, expires_at, created_at) "
            "VALUES ('a1', 'r1', 'u1', 'PENDING', 'CONFIRM_REQUIRED', 'x', 't', 't')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO agent_approvals (approval_id, run_id, user_id, status, risk_level, "
                "action_summary, expires_at, created_at) "
                "VALUES ('a2', 'r1', 'u1', 'AUTO_APPROVED', 'AUTO_SAFE', 'x', 't', 't')"
            )
    finally:
        db._release(conn)

def _build_legacy_v1_db(tmp_path) -> "Database":
    """构造 v1 旧库：agent_runs 缺少 v2 队列字段，且保留旧数据。"""
    db_path = tmp_path / "legacy_v1.db"
    seed = Database(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
            "VALUES ('u1', 'u1', 'x', 'student', 't', 't')"
        )
        conn.execute(
            "INSERT INTO agent_jobs (job_id, user_id, job_kind, status, created_at, updated_at) "
            "VALUES ('j1', 'u1', 'learning_goal', 'QUEUED', 't', 't')"
        )
        conn.execute("DROP TABLE agent_runs")
        conn.executescript(_LEGACY_AGENT_RUN_COLUMNS)
        conn.execute(
            "INSERT INTO agent_runs (run_id, job_id, user_id, status, phase, "
            "created_at, updated_at) VALUES ('r1', 'j1', 'u1', 'RUNNING', 'IDLE', 't', 't')"
        )
        conn.commit()
    finally:
        conn.close()
    seed.dispose()
    return Database(db_path)


def test_v1_agent_runs_gains_v2_queue_columns(tmp_path) -> None:
    db = _build_legacy_v1_db(tmp_path)
    conn = db._connect()
    try:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(agent_runs)")}
        assert set(V2_AGENT_RUN_COLUMNS) <= cols, f"缺失列: {set(V2_AGENT_RUN_COLUMNS) - cols}"
        # 旧数据必须保留，不能被重建表抹掉。
        row = conn.execute("SELECT * FROM agent_runs WHERE run_id='r1'").fetchone()
        assert row is not None
        assert row["status"] == "RUNNING"
        # 新增列必须有可用默认值，旧行不能被 NULL 破坏。
        assert row["attempt_no"] == 0
        assert row["lease_owner"] is None
    finally:
        db._release(conn)
    db.dispose()


def test_idempotency_claims_table_exists(tmp_path) -> None:
    db = Database(tmp_path / "claims.db")
    conn = db._connect()
    try:
        cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(agent_idempotency_claims)")
        }
        assert {
            "scope",
            "user_id",
            "idempotency_key",
            "request_hash",
            "resource_id",
            "created_at",
        } <= cols
        _seed_user(conn)
        conn.execute(
            "INSERT INTO agent_idempotency_claims "
            "(scope, user_id, idempotency_key, request_hash, resource_id, created_at) "
            "VALUES ('agent_job', 'u1', 'k1', 'h1', 'job_1', 't')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO agent_idempotency_claims "
                "(scope, user_id, idempotency_key, request_hash, resource_id, created_at) "
                "VALUES ('agent_job', 'u1', 'k1', 'h2', 'job_2', 't')"
            )
    finally:
        db._release(conn)
    db.dispose()


def test_agent_events_has_run_event_cursor_index(tmp_path) -> None:
    db = Database(tmp_path / "cursor.db")
    conn = db._connect()
    try:
        indexes = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='agent_events'"
            )
        }
        assert "idx_agent_events_run_event" in indexes
    finally:
        db._release(conn)
    db.dispose()
