"""通知工作流仓储 — notification_sources / notice_workflows / notice_workflow_actions。

封装 CRUD 与状态转换。不保存敏感数据(凭据、完整表单内容)。
表通过 `CREATE TABLE IF NOT EXISTS` 幂等创建(additive migration),不修改 sqlite_db.py。
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from ..database.sqlite_db import Database
from ..models.notice_workflow import (
    NoticeWorkflowActionRow,
    NoticeWorkflowRow,
    NotificationSourceRow,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS notification_sources (
    source_id TEXT PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    kind TEXT NOT NULL,
    automation_enabled INTEGER NOT NULL DEFAULT 0,
    permission_scope TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_source_preferences (
    user_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    automation_enabled INTEGER NOT NULL DEFAULT 0,
    display_name TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(user_id, source_id),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(source_id) REFERENCES notification_sources(source_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notice_workflows (
    workflow_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    notice_id TEXT NOT NULL,
    source_id TEXT,
    status TEXT NOT NULL DEFAULT 'CREATED',
    title TEXT,
    deadline TEXT,
    location TEXT,
    audience TEXT,
    materials_json TEXT,
    steps_json TEXT,
    source_evidence_json TEXT,
    confidence REAL NOT NULL DEFAULT 0.0,
    uncertainty_json TEXT,
    content_fingerprint TEXT NOT NULL,
    idempotency_key TEXT,
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    expired_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_notice_workflows_user ON notice_workflows(user_id);
CREATE INDEX IF NOT EXISTS idx_notice_workflows_notice ON notice_workflows(notice_id);
CREATE INDEX IF NOT EXISTS idx_notice_workflows_fp ON notice_workflows(user_id, content_fingerprint);

CREATE TABLE IF NOT EXISTS notice_workflow_actions (
    action_id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    title TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PROPOSED',
    params_json TEXT,
    result_json TEXT,
    idempotency_key TEXT,
    external_ref TEXT,
    expires_at TEXT,
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    executed_at TEXT,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_notice_workflow_actions_wf ON notice_workflow_actions(workflow_id);
CREATE INDEX IF NOT EXISTS idx_notice_workflow_actions_user ON notice_workflow_actions(user_id);
CREATE INDEX IF NOT EXISTS idx_notice_workflow_actions_idem ON notice_workflow_actions(user_id, idempotency_key);
"""


_LEGACY_TABLES = (
    "notification_sources",
    "notification_source_controls",
    "notification_workflows",
    "notification_workflow_actions",
)
_LEGACY_SUFFIX = "__legacy"
_MIGRATE_SUFFIX = "__migrate"

# 新结构表可能先于迁移被创建(此时 notification_sources 仍是旧结构)。
# 这类表的外键指向 notification_sources,一旦旧表被改名,SQLite 会把外键
# 改写成指向 notification_sources__legacy,而该列并不存在,后续写入会抛
# "foreign key mismatch"。迁移前需要把这些表备份后重建。
# 值 = (列清单, 数据回填时的保留条件)。
_REBUILD_ON_RENAME: dict[str, tuple[str, str]] = {
    "notification_source_preferences": (
        "user_id, source_id, automation_enabled, display_name, updated_at",
        "source_id IN (SELECT source_id FROM notification_sources)",
    ),
}


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }


def _foreign_key_parents(conn: sqlite3.Connection, table_name: str) -> set[str]:
    """返回该表外键引用的父表名集合。"""
    return {
        row[2]
        for row in conn.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
    }


def _has_legacy_schema(conn: sqlite3.Connection) -> bool:
    if not _table_exists(conn, "notification_sources"):
        return False
    columns = _table_columns(conn, "notification_sources")
    return "code" in columns and "source_id" not in columns


def _rebuild_targets(conn: sqlite3.Connection) -> list[str]:
    """需要"备份后重建"的表:存在且外键指向即将被改名的旧表。"""
    legacy = set(_LEGACY_TABLES)
    targets: list[str] = []
    for table in _REBUILD_ON_RENAME:
        if not _table_exists(conn, table):
            continue
        if _foreign_key_parents(conn, table) & legacy:
            targets.append(table)
    return targets


def _legacy_upgrade_script(conn: sqlite3.Connection) -> str:
    """生成旧 schema 升级脚本。

    整个脚本包裹在单个事务里,失败可整体回滚;重复执行不会产生重复数据。
    """
    # 上一次迁移可能已提交备份表(异常中断),这里一并纳入回填范围。
    stashed = {
        table
        for table in _REBUILD_ON_RENAME
        if _table_exists(conn, f"{table}{_MIGRATE_SUFFIX}")
    }
    statements: list[str] = ["BEGIN;"]

    for table in _rebuild_targets(conn):
        stash = f"{table}{_MIGRATE_SUFFIX}"
        # 先清掉残留备份,保证 CREATE TABLE AS SELECT 不会因为同名报错。
        statements.append(f"DROP TABLE IF EXISTS {stash};")
        statements.append(f"CREATE TABLE {stash} AS SELECT * FROM {table};")
        statements.append(f"DROP TABLE {table};")
        stashed.add(table)

    for table in _LEGACY_TABLES:
        if not _table_exists(conn, table):
            continue
        # 旧备份属于上一次未完成的迁移,优先保留当前数据。
        statements.append(f"DROP TABLE IF EXISTS {table}{_LEGACY_SUFFIX};")
        statements.append(
            f"ALTER TABLE {table} RENAME TO {table}{_LEGACY_SUFFIX};"
        )

    statements.append(_SCHEMA_SQL)

    for required_tables, sql in _LEGACY_DATA_MIGRATIONS:
        if all(_table_exists(conn, table) for table in required_tables):
            statements.append(sql)

    for table in sorted(stashed):
        columns, keep_condition = _REBUILD_ON_RENAME[table]
        stash = f"{table}{_MIGRATE_SUFFIX}"
        statements.append(
            f"INSERT OR IGNORE INTO {table} ({columns}) "
            f"SELECT {columns} FROM {stash} WHERE {keep_condition};"
        )
        statements.append(f"DROP TABLE {stash};")

    statements.append("COMMIT;")
    return "\n".join(statements)


# 数据迁移语句按来源的旧表存在与否逐条启用(部分旧库可能缺表)。
# 全部使用 INSERT OR IGNORE,保证迁移可重复执行。
_LEGACY_DATA_MIGRATIONS: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("notification_sources",),
        """
INSERT OR IGNORE INTO notification_sources (
    source_id, code, display_name, kind, automation_enabled,
    permission_scope, created_at, updated_at
)
SELECT
    'legacy-notification-source-' || code,
    code,
    label,
    'legacy',
    automation_enabled,
    NULL,
    created_at,
    updated_at
FROM notification_sources__legacy;
""",
    ),
    (
        ("notification_source_controls",),
        """
INSERT OR IGNORE INTO notification_source_preferences (
    user_id, source_id, automation_enabled, display_name, updated_at
)
SELECT
    p.user_id,
    'legacy-notification-source-' || p.source_code,
    p.automation_enabled,
    NULL,
    p.updated_at
FROM notification_source_controls__legacy AS p;
""",
    ),
    (
        ("notification_workflows",),
        """
INSERT OR IGNORE INTO notice_workflows (
    workflow_id, user_id, notice_id, source_id, status, title, deadline,
    location, audience, materials_json, steps_json, source_evidence_json,
    confidence, uncertainty_json, content_fingerprint, idempotency_key,
    error_code, error_message, created_at, updated_at, completed_at, expired_at
)
SELECT
    w.id,
    w.user_id,
    w.notice_id,
    'legacy-notification-source-' || w.source_code,
    w.status,
    NULL,
    NULL,
    NULL,
    NULL,
    w.checklist_json,
    '[]',
    w.extracted_facts_json,
    0.0,
    w.uncertainty_json,
    w.content_digest,
    NULL,
    NULL,
    NULL,
    w.created_at,
    w.updated_at,
    CASE WHEN w.status = 'COMPLETED' THEN w.updated_at ELSE NULL END,
    CASE WHEN w.status = 'EXPIRED' THEN w.updated_at ELSE NULL END
FROM notification_workflows__legacy AS w;
""",
    ),
    (
        ("notification_workflow_actions", "notification_workflows"),
        """
INSERT OR IGNORE INTO notice_workflow_actions (
    action_id, workflow_id, user_id, action_type, title, risk_level,
    status, params_json, result_json, idempotency_key, external_ref,
    expires_at, error_code, error_message, created_at, updated_at,
    executed_at, completed_at
)
SELECT
    a.id,
    a.workflow_id,
    w.user_id,
    a.action_type,
    a.action_type,
    a.risk_level,
    a.status,
    NULL,
    NULL,
    a.idempotency_key,
    a.task_id,
    NULL,
    a.error_code,
    NULL,
    a.created_at,
    a.updated_at,
    NULL,
    NULL
FROM notification_workflow_actions__legacy AS a
JOIN notification_workflows__legacy AS w ON w.id = a.workflow_id;
""",
    ),
)


class NoticeWorkflowRepository:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._db.transaction() as conn:
            if _has_legacy_schema(conn):
                try:
                    conn.executescript(_legacy_upgrade_script(conn))
                except Exception:
                    conn.rollback()
                    raise
            else:
                conn.executescript(_SCHEMA_SQL)

    # ===== notification_sources =====

    def create_source(
        self,
        *,
        code: str,
        display_name: str,
        kind: str,
        automation_enabled: bool = False,
        permission_scope: Optional[str] = None,
    ) -> NotificationSourceRow:
        source_id = _uuid("nwfsrc")
        now = _now()
        with self._db.transaction() as conn:
            conn.execute(
                "INSERT INTO notification_sources "
                "(source_id, code, display_name, kind, automation_enabled, permission_scope, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (source_id, code, display_name, kind, int(automation_enabled),
                 permission_scope, now, now),
            )
        return self.get_source(source_id)  # type: ignore[return-value]

    def get_source(self, source_id: str) -> Optional[NotificationSourceRow]:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM notification_sources WHERE source_id = ?",
                (source_id,),
            ).fetchone()
        return NotificationSourceRow.from_row(row) if row else None

    def get_source_by_code(self, code: str) -> Optional[NotificationSourceRow]:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM notification_sources WHERE code = ?", (code,)
            ).fetchone()
        return NotificationSourceRow.from_row(row) if row else None

    def list_sources(self) -> list[NotificationSourceRow]:
        with self._db.query() as conn:
            rows = conn.execute(
                "SELECT * FROM notification_sources ORDER BY code ASC"
            ).fetchall()
        return [NotificationSourceRow.from_row(r) for r in rows]

    def list_sources_for_user(self, user_id: str) -> list[NotificationSourceRow]:
        """返回来源定义叠加当前用户偏好；偏好不存在时默认关闭。"""
        with self._db.query() as conn:
            rows = conn.execute(
                "SELECT s.*, COALESCE(p.automation_enabled, 0) AS user_automation_enabled, "
                "p.display_name AS user_display_name "
                "FROM notification_sources s LEFT JOIN notification_source_preferences p "
                "ON p.source_id = s.source_id AND p.user_id = ? ORDER BY s.code ASC",
                (user_id,),
            ).fetchall()
        result: list[NotificationSourceRow] = []
        for row in rows:
            source = NotificationSourceRow.from_row(row)
            source.automation_enabled = bool(row["user_automation_enabled"])
            if row["user_display_name"]:
                source.display_name = row["user_display_name"]
            result.append(source)
        return result

    def get_source_for_user(
        self, source_id: str, user_id: str
    ) -> Optional[NotificationSourceRow]:
        return next(
            (s for s in self.list_sources_for_user(user_id) if s.source_id == source_id),
            None,
        )

    def get_source_by_code_for_user(
        self, code: str, user_id: str
    ) -> Optional[NotificationSourceRow]:
        return next(
            (s for s in self.list_sources_for_user(user_id) if s.code == code),
            None,
        )

    def update_source_preference(
        self,
        source_id: str,
        user_id: str,
        *,
        automation_enabled: Optional[bool] = None,
        display_name: Optional[str] = None,
    ) -> Optional[NotificationSourceRow]:
        """只更新当前用户偏好，绝不修改全局来源定义。"""
        if self.get_source(source_id) is None:
            return None
        current = self.get_source_for_user(source_id, user_id)
        enabled = bool(current and current.automation_enabled)
        name = None
        with self._db.query() as conn:
            pref = conn.execute(
                "SELECT display_name FROM notification_source_preferences "
                "WHERE user_id = ? AND source_id = ?",
                (user_id, source_id),
            ).fetchone()
            if pref:
                name = pref["display_name"]
        if automation_enabled is not None:
            enabled = automation_enabled
        if display_name is not None:
            name = display_name
        now = _now()
        with self._db.transaction() as conn:
            conn.execute(
                "INSERT INTO notification_source_preferences "
                "(user_id, source_id, automation_enabled, display_name, updated_at) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(user_id, source_id) DO UPDATE SET "
                "automation_enabled=excluded.automation_enabled, "
                "display_name=excluded.display_name, updated_at=excluded.updated_at",
                (user_id, source_id, int(enabled), name, now),
            )
        return self.get_source_for_user(source_id, user_id)

    def update_source(
        self,
        source_id: str,
        *,
        automation_enabled: Optional[bool] = None,
        display_name: Optional[str] = None,
    ) -> Optional[NotificationSourceRow]:
        now = _now()
        with self._db.transaction() as conn:
            sets: list[str] = []
            params: list = []
            if automation_enabled is not None:
                sets.append("automation_enabled = ?")
                params.append(int(automation_enabled))
            if display_name is not None:
                sets.append("display_name = ?")
                params.append(display_name)
            if not sets:
                return self.get_source(source_id)
            sets.append("updated_at = ?")
            params.append(now)
            params.append(source_id)
            conn.execute(
                f"UPDATE notification_sources SET {', '.join(sets)} WHERE source_id = ?",
                params,
            )
        return self.get_source(source_id)

    # ===== notice_workflows =====

    def create_workflow(
        self,
        *,
        user_id: str,
        notice_id: str,
        content_fingerprint: str,
        source_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> NoticeWorkflowRow:
        workflow_id = _uuid("nwf")
        now = _now()
        with self._db.transaction() as conn:
            conn.execute(
                "INSERT INTO notice_workflows "
                "(workflow_id, user_id, notice_id, source_id, status, content_fingerprint, "
                "idempotency_key, confidence, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'CREATED', ?, ?, 0.0, ?, ?)",
                (workflow_id, user_id, notice_id, source_id, content_fingerprint,
                 idempotency_key, now, now),
            )
        return self.get_workflow(workflow_id)  # type: ignore[return-value]

    def get_workflow(self, workflow_id: str) -> Optional[NoticeWorkflowRow]:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM notice_workflows WHERE workflow_id = ?",
                (workflow_id,),
            ).fetchone()
        return NoticeWorkflowRow.from_row(row) if row else None

    def get_workflow_by_notice(
        self, notice_id: str, *, user_id: str
    ) -> Optional[NoticeWorkflowRow]:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM notice_workflows WHERE notice_id = ? AND user_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (notice_id, user_id),
            ).fetchone()
        return NoticeWorkflowRow.from_row(row) if row else None

    def get_active_workflow_by_fingerprint(
        self, user_id: str, content_fingerprint: str
    ) -> Optional[NoticeWorkflowRow]:
        """返回非终态的同指纹工作流(用于去重)。"""
        terminal = ("COMPLETED", "EXPIRED", "FAILED")
        placeholders = ",".join("?" for _ in terminal)
        with self._db.query() as conn:
            row = conn.execute(
                f"SELECT * FROM notice_workflows WHERE user_id = ? AND content_fingerprint = ? "
                f"AND status NOT IN ({placeholders}) ORDER BY created_at DESC LIMIT 1",
                (user_id, content_fingerprint, *terminal),
            ).fetchone()
        return NoticeWorkflowRow.from_row(row) if row else None

    def find_workflow_by_idempotency(
        self, user_id: str, idempotency_key: str
    ) -> Optional[NoticeWorkflowRow]:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM notice_workflows WHERE user_id = ? AND idempotency_key = ?",
                (user_id, idempotency_key),
            ).fetchone()
        return NoticeWorkflowRow.from_row(row) if row else None

    def update_workflow_status(
        self,
        workflow_id: str,
        status: str,
        *,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        now = _now()
        completed_at = now if status == "COMPLETED" else None
        expired_at = now if status == "EXPIRED" else None
        with self._db.transaction() as conn:
            sets = ["status = ?", "updated_at = ?"]
            params: list = [status, now]
            if error_code is not None:
                sets.append("error_code = ?")
                params.append(error_code)
            if error_message is not None:
                sets.append("error_message = ?")
                params.append(error_message)
            if completed_at is not None:
                sets.append("completed_at = ?")
                params.append(completed_at)
            if expired_at is not None:
                sets.append("expired_at = ?")
                params.append(expired_at)
            params.append(workflow_id)
            conn.execute(
                f"UPDATE notice_workflows SET {', '.join(sets)} WHERE workflow_id = ?",
                params,
            )

    def update_workflow_interpretation(
        self,
        workflow_id: str,
        *,
        title: Optional[str] = None,
        deadline: Optional[str] = None,
        location: Optional[str] = None,
        audience: Optional[str] = None,
        materials: Optional[list[str]] = None,
        steps: Optional[list[str]] = None,
        source_evidence: Optional[list[str]] = None,
        confidence: float = 0.0,
        uncertainty: Optional[list[str]] = None,
    ) -> None:
        now = _now()
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE notice_workflows SET title=?, deadline=?, location=?, audience=?, "
                "materials_json=?, steps_json=?, source_evidence_json=?, confidence=?, "
                "uncertainty_json=?, updated_at=? WHERE workflow_id=?",
                (
                    title, deadline, location, audience,
                    json.dumps(materials or [], ensure_ascii=False),
                    json.dumps(steps or [], ensure_ascii=False),
                    json.dumps(source_evidence or [], ensure_ascii=False),
                    float(confidence),
                    json.dumps(uncertainty or [], ensure_ascii=False),
                    now, workflow_id,
                ),
            )

    def mark_step_done(self, workflow_id: str, step_index: int) -> None:
        """标记步骤完成(不覆盖已完成步骤)。"""
        wf = self.get_workflow(workflow_id)
        if not wf or not wf.steps_json:
            return
        try:
            steps = json.loads(wf.steps_json)
        except (ValueError, TypeError):
            return
        if 0 <= step_index < len(steps) and not steps[step_index].get("done"):
            steps[step_index]["done"] = True
            now = _now()
            with self._db.transaction() as conn:
                conn.execute(
                    "UPDATE notice_workflows SET steps_json=?, updated_at=? WHERE workflow_id=?",
                    (json.dumps(steps, ensure_ascii=False), now, workflow_id),
                )

    # ===== notice_workflow_actions =====

    def create_action(
        self,
        *,
        workflow_id: str,
        user_id: str,
        action_type: str,
        title: str,
        risk_level: str,
        params: Optional[dict] = None,
        idempotency_key: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> NoticeWorkflowActionRow:
        action_id = _uuid("nwfact")
        now = _now()
        with self._db.transaction() as conn:
            conn.execute(
                "INSERT INTO notice_workflow_actions "
                "(action_id, workflow_id, user_id, action_type, title, risk_level, status, "
                "params_json, idempotency_key, expires_at, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'PROPOSED', ?, ?, ?, ?, ?)",
                (action_id, workflow_id, user_id, action_type, title, risk_level,
                 json.dumps(params or {}, ensure_ascii=False),
                 idempotency_key, expires_at, now, now),
            )
        return self.get_action(action_id)  # type: ignore[return-value]

    def get_action(self, action_id: str) -> Optional[NoticeWorkflowActionRow]:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM notice_workflow_actions WHERE action_id = ?",
                (action_id,),
            ).fetchone()
        return NoticeWorkflowActionRow.from_row(row) if row else None

    def list_actions_by_workflow(
        self, workflow_id: str
    ) -> list[NoticeWorkflowActionRow]:
        with self._db.query() as conn:
            rows = conn.execute(
                "SELECT * FROM notice_workflow_actions WHERE workflow_id = ? "
                "ORDER BY created_at ASC",
                (workflow_id,),
            ).fetchall()
        return [NoticeWorkflowActionRow.from_row(r) for r in rows]

    def find_action_by_idempotency(
        self, user_id: str, idempotency_key: str
    ) -> Optional[NoticeWorkflowActionRow]:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM notice_workflow_actions "
                "WHERE user_id = ? AND idempotency_key = ?",
                (user_id, idempotency_key),
            ).fetchone()
        return NoticeWorkflowActionRow.from_row(row) if row else None

    def update_action_status(
        self,
        action_id: str,
        status: str,
        *,
        external_ref: Optional[str] = None,
        result: Optional[dict] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        now = _now()
        executed_at = now if status in ("EXECUTING", "DONE", "FAILED") else None
        completed_at = now if status in ("DONE", "REJECTED", "EXPIRED") else None
        with self._db.transaction() as conn:
            sets = ["status = ?", "updated_at = ?"]
            params: list = [status, now]
            if external_ref is not None:
                sets.append("external_ref = ?")
                params.append(external_ref)
            if result is not None:
                sets.append("result_json = ?")
                params.append(json.dumps(result, ensure_ascii=False))
            if error_code is not None:
                sets.append("error_code = ?")
                params.append(error_code)
            if error_message is not None:
                sets.append("error_message = ?")
                params.append(error_message)
            if executed_at is not None:
                sets.append("executed_at = ?")
                params.append(executed_at)
            if completed_at is not None:
                sets.append("completed_at = ?")
                params.append(completed_at)
            params.append(action_id)
            conn.execute(
                f"UPDATE notice_workflow_actions SET {', '.join(sets)} WHERE action_id = ?",
                params,
            )

    def expire_pending_actions(self, workflow_id: str, *, before_iso: str) -> int:
        """过期指定时间前仍为 PROPOSED/APPROVED 的 action。返回过期数量。"""
        now = _now()
        with self._db.transaction() as conn:
            cur = conn.execute(
                "UPDATE notice_workflow_actions SET status='EXPIRED', completed_at=?, updated_at=? "
                "WHERE workflow_id=? AND status IN ('PROPOSED','APPROVED') AND expires_at IS NOT NULL "
                "AND expires_at < ?",
                (now, now, workflow_id, before_iso),
            )
            return cur.rowcount


__all__ = ["NoticeWorkflowRepository"]
