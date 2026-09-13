from __future__ import annotations

import sqlite3

from app.database.sqlite_db import Database
from app.repositories.notice_workflow_repository import (
    _SCHEMA_SQL,
    NoticeWorkflowRepository,
)


def _create_legacy_notice_workflow_schema(db_path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO users (id, username, password_hash, role, created_at, updated_at)
            VALUES ('user-1', 'user-1', 'hash', 'student', '2026-01-01', '2026-01-01');

            CREATE TABLE notification_sources (
                code TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                automation_enabled INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO notification_sources
                (code, label, automation_enabled, created_at, updated_at)
            VALUES ('campus', '校园通知', 1, '2026-01-01', '2026-01-01');

            CREATE TABLE notification_source_controls (
                user_id TEXT NOT NULL,
                source_code TEXT NOT NULL,
                automation_enabled INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(user_id, source_code),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(source_code) REFERENCES notification_sources(code)
            );
            INSERT INTO notification_source_controls
                (user_id, source_code, automation_enabled, created_at, updated_at)
            VALUES ('user-1', 'campus', 1, '2026-01-01', '2026-01-01');

            CREATE TABLE notification_workflows (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                notice_id TEXT NOT NULL,
                status TEXT NOT NULL,
                source_code TEXT NOT NULL,
                source_revision INTEGER NOT NULL DEFAULT 1,
                content_digest TEXT NOT NULL,
                extracted_facts_json TEXT NOT NULL,
                uncertainty_json TEXT NOT NULL,
                checklist_json TEXT NOT NULL,
                action_risk TEXT NOT NULL,
                difference_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO notification_workflows
                (id, user_id, notice_id, status, source_code, content_digest,
                 extracted_facts_json, uncertainty_json, checklist_json, action_risk,
                 difference_json, created_at, updated_at)
            VALUES ('workflow-1', 'user-1', 'notice-1', 'CREATED', 'campus', 'digest-1',
                    '{}', '[]', '[]', 'CONFIRM_REQUIRED', '{}', '2026-01-01', '2026-01-01');

            CREATE TABLE notification_workflow_actions (
                id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                status TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                task_id TEXT,
                error_code TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO notification_workflow_actions
                (id, workflow_id, action_type, risk_level, status, idempotency_key, created_at, updated_at)
            VALUES ('action-1', 'workflow-1', 'create_task', 'CONFIRM_REQUIRED',
                    'PROPOSED', 'idem-1', '2026-01-01', '2026-01-01');
            """
        )


def test_legacy_notice_workflow_schema_is_upgraded_idempotently(tmp_path):
    db_path = tmp_path / "legacy-notice-workflow.db"
    _create_legacy_notice_workflow_schema(db_path)

    database = Database(db_path)
    repository = NoticeWorkflowRepository(database)

    source = repository.get_source_by_code_for_user("campus", "user-1")
    assert source is not None
    assert source.source_id == "legacy-notification-source-campus"
    assert source.display_name == "校园通知"
    assert source.automation_enabled is True

    workflow = repository.get_workflow("workflow-1")
    assert workflow is not None
    assert workflow.source_id == "legacy-notification-source-campus"
    assert workflow.content_fingerprint == "digest-1"

    actions = repository.list_actions_by_workflow("workflow-1")
    assert len(actions) == 1
    assert actions[0].user_id == "user-1"
    assert actions[0].title == "create_task"

    NoticeWorkflowRepository(database)
    with database.query() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM notification_sources"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM notice_workflows"
        ).fetchone()[0] == 1

    database.dispose()


def test_new_schema_created_before_upgrade_is_repaired(tmp_path):
    """新结构表先于迁移创建时,外键会指向改名后的旧表,必须被重建。"""
    db_path = tmp_path / "new-schema-created-first.db"
    _create_legacy_notice_workflow_schema(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO notification_sources "
            "(code, label, automation_enabled, created_at, updated_at) "
            "VALUES ('academic', '教务通知', 0, '2026-01-01', '2026-01-01')"
        )
        # 模拟新代码先建表:此时 notification_sources 仍是旧结构
        conn.executescript(_SCHEMA_SQL)
        conn.execute(
            "INSERT INTO notification_source_preferences "
            "(user_id, source_id, automation_enabled, display_name, updated_at) "
            "VALUES ('user-1', 'legacy-notification-source-academic', 1, '教务', '2026-01-02'), "
            "('user-1', 'ghost-source', 1, '孤儿来源', '2026-01-02')"
        )

    database = Database(db_path)
    repository = NoticeWorkflowRepository(database)

    with database.query() as conn:
        parents = {
            row[2]
            for row in conn.execute(
                "PRAGMA foreign_key_list(notification_source_preferences)"
            ).fetchall()
        }
        assert parents == {"users", "notification_sources"}
        # 备份表用完即弃
        assert conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='notification_source_preferences__migrate'"
        ).fetchone() is None
        prefs = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT source_id, display_name FROM notification_source_preferences"
            ).fetchall()
        }
        assert prefs == {
            "legacy-notification-source-campus": None,
            "legacy-notification-source-academic": "教务",
        }

    # 外键修复后仍可写入,不会再抛 foreign key mismatch
    updated = repository.update_source_preference(
        "legacy-notification-source-campus", "user-1", automation_enabled=True
    )
    assert updated is not None
    assert updated.automation_enabled is True

    # 重复执行不产生重复数据
    NoticeWorkflowRepository(database)
    with database.query() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM notification_sources"
        ).fetchone()[0] == 2
        assert conn.execute(
            "SELECT COUNT(*) FROM notification_source_preferences"
        ).fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM notice_workflows").fetchone()[0] == 1

    database.dispose()
