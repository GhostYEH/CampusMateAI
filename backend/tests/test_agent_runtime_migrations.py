"""Agent runtime migration 测试 —— 验证 additive idempotent migration。"""
from __future__ import annotations

import sqlite3

import pytest

from app.database.sqlite_db import Database, AGENT_RUNTIME_SCHEMA_SQL


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