"""期末复习迁移 SQL(§7.2)。

不修改共享文件 sqlite_db.py。本模块提供幂等 migration 函数,
由 final_review_repository 初始化时调用,或由集成智能体在 sqlite_db.py 中注册。

新库迁移为 additive + idempotent(CREATE TABLE IF NOT EXISTS);检测到旧版
重复 schema 时,会在保留旧表副本的前提下重建为当前结构。
"""
from __future__ import annotations

import sqlite3

FINAL_REVIEW_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS final_review_campaigns (
    campaign_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    exam_ids_json TEXT NOT NULL,
    daily_capacity_minutes INTEGER NOT NULL,
    preferred_periods_json TEXT NOT NULL DEFAULT '[]',
    rest_days_json TEXT NOT NULL DEFAULT '[]',
    intensity TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'draft',
    active_version INTEGER,
    idempotency_key TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_final_review_campaigns_user ON final_review_campaigns(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_final_review_campaigns_status ON final_review_campaigns(status);

CREATE TABLE IF NOT EXISTS final_review_plan_versions (
    campaign_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    source_snapshot_id TEXT,
    model_provider TEXT NOT NULL,
    route_policy TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    approval_id TEXT,
    supersedes_version INTEGER,
    created_at TEXT NOT NULL,
    PRIMARY KEY(campaign_id, version),
    FOREIGN KEY(campaign_id) REFERENCES final_review_campaigns(campaign_id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_final_review_plan_versions_user ON final_review_plan_versions(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS final_review_daily_agendas (
    agenda_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    plan_version INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    agenda_date TEXT NOT NULL,
    total_minutes INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(campaign_id) REFERENCES final_review_campaigns(campaign_id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(campaign_id, plan_version, agenda_date)
);
CREATE INDEX IF NOT EXISTS idx_final_review_daily_agendas_user_date ON final_review_daily_agendas(user_id, agenda_date DESC);

CREATE TABLE IF NOT EXISTS final_review_daily_items (
    item_id TEXT PRIMARY KEY,
    agenda_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    course_name TEXT,
    scheduled_minutes INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    personal_task_id TEXT,
    completed_at TEXT,
    difficulty TEXT,
    feedback TEXT,
    FOREIGN KEY(agenda_id) REFERENCES final_review_daily_agendas(agenda_id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(agenda_id, sort_order)
);
CREATE INDEX IF NOT EXISTS idx_final_review_daily_items_agenda ON final_review_daily_items(agenda_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_final_review_daily_items_task ON final_review_daily_items(personal_task_id);

CREATE TABLE IF NOT EXISTS final_review_checkin_evidence (
    checkin_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    plan_version INTEGER,
    user_id TEXT NOT NULL,
    report_date TEXT NOT NULL,
    completed_item_ids_json TEXT NOT NULL DEFAULT '[]',
    insufficient_time INTEGER NOT NULL DEFAULT 0,
    difficulty_notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(campaign_id) REFERENCES final_review_campaigns(campaign_id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(campaign_id, user_id, report_date)
);
CREATE INDEX IF NOT EXISTS idx_final_review_checkin_evidence_campaign_date
    ON final_review_checkin_evidence(campaign_id, user_id, report_date DESC);

CREATE TABLE IF NOT EXISTS final_review_adjustment_proposals (
    proposal_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    source_version INTEGER NOT NULL,
    proposal_json TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    approval_id TEXT,
    target_version INTEGER,
    model_provider TEXT,
    route_policy TEXT,
    reason TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    FOREIGN KEY(campaign_id) REFERENCES final_review_campaigns(campaign_id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    CHECK(status IN ('pending','approved','rejected','expired')),
    CHECK(risk_level IN ('AUTO_SAFE','CONFIRM_REQUIRED','MANUAL_ONLY'))
);
CREATE INDEX IF NOT EXISTS idx_final_review_adjustments_campaign ON final_review_adjustment_proposals(campaign_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_final_review_adjustments_status ON final_review_adjustment_proposals(status);
"""


_LEGACY_TABLES = (
    "final_review_campaigns",
    "final_review_plan_versions",
    "final_review_daily_agendas",
    "final_review_daily_items",
    "final_review_checkins",
    "final_review_adjustment_proposals",
)
_LEGACY_SUFFIX = "__legacy"


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


def _has_legacy_schema(conn: sqlite3.Connection) -> bool:
    """Return whether the duplicate pre-§7.2 schema is present."""
    if not _table_exists(conn, "final_review_campaigns"):
        return False
    columns = _table_columns(conn, "final_review_campaigns")
    return "id" in columns and "campaign_id" not in columns


def _legacy_upgrade_script() -> str:
    """Build a one-shot SQL upgrade from the old final-review schema.

    The old tables are retained with a suffix as a rollback/audit copy. The
    active tables are rebuilt because SQLite cannot drop or alter the old
    primary keys and foreign-key layout in place.
    """
    rename_sql = "\n".join(
        f"ALTER TABLE {table} RENAME TO {table}{_LEGACY_SUFFIX};"
        for table in _LEGACY_TABLES
    )
    return f"""
BEGIN;
{rename_sql}
{FINAL_REVIEW_SCHEMA_SQL}

INSERT INTO final_review_campaigns (
    campaign_id, user_id, exam_ids_json, daily_capacity_minutes,
    preferred_periods_json, rest_days_json, intensity, status,
    active_version, idempotency_key, created_at, updated_at
)
SELECT
    id, user_id, json_array(exam_id), daily_capacity_minutes,
    '[]', '[]', 'medium', status, active_version, NULL, created_at, updated_at
FROM final_review_campaigns__legacy;

INSERT INTO final_review_plan_versions (
    campaign_id, version, user_id, plan_json, source_snapshot_id,
    model_provider, route_policy, risk_level, approval_id,
    supersedes_version, created_at
)
SELECT
    p.campaign_id,
    p.version,
    c.user_id,
    p.content_json,
    NULL,
    'legacy',
    'legacy',
    'CONFIRM_REQUIRED',
    NULL,
    (
        SELECT parent.version
        FROM final_review_plan_versions__legacy AS parent
        WHERE parent.id = p.parent_version_id
    ),
    p.created_at
FROM final_review_plan_versions__legacy AS p
JOIN final_review_campaigns AS c ON c.campaign_id = p.campaign_id;

INSERT INTO final_review_daily_agendas (
    agenda_id, campaign_id, plan_version, user_id, agenda_date,
    total_minutes, created_at
)
SELECT
    a.id, a.campaign_id, a.plan_version, c.user_id, a.agenda_date, 0, a.created_at
FROM final_review_daily_agendas__legacy AS a
JOIN final_review_campaigns AS c ON c.campaign_id = a.campaign_id;

INSERT INTO final_review_daily_items (
    item_id, agenda_id, campaign_id, user_id, title, course_name,
    scheduled_minutes, sort_order, status, personal_task_id,
    completed_at, difficulty, feedback
)
SELECT
    i.id,
    i.agenda_id,
    a.campaign_id,
    a.user_id,
    i.title,
    NULL,
    i.duration_minutes,
    (
        SELECT COUNT(*)
        FROM final_review_daily_items__legacy AS prior
        WHERE prior.agenda_id = i.agenda_id AND prior.id < i.id
    ),
    CASE WHEN i.status IN ('pending', 'completed', 'skipped')
         THEN i.status ELSE 'pending' END,
    i.external_task_id,
    i.completed_at,
    NULL,
    NULL
FROM final_review_daily_items__legacy AS i
JOIN final_review_daily_agendas AS a ON a.agenda_id = i.agenda_id;

INSERT INTO final_review_checkin_evidence (
    checkin_id, campaign_id, plan_version, user_id, report_date,
    completed_item_ids_json, insufficient_time, difficulty_notes,
    created_at, updated_at
)
SELECT
    id,
    campaign_id,
    NULL,
    user_id,
    substr(created_at, 1, 10),
    '[]',
    CASE WHEN actual_minutes <= 0 THEN 1 ELSE 0 END,
    difficulty_code,
    created_at,
    created_at
FROM final_review_checkins__legacy;

INSERT INTO final_review_adjustment_proposals (
    proposal_id, campaign_id, user_id, source_version, proposal_json,
    risk_level, status, approval_id, target_version, model_provider,
    route_policy, reason, created_at, resolved_at
)
SELECT
    p.id,
    p.campaign_id,
    c.user_id,
    p.base_version,
    p.content_json,
    'CONFIRM_REQUIRED',
    CASE WHEN p.status IN ('pending', 'approved', 'rejected', 'expired')
         THEN p.status ELSE 'pending' END,
    NULL,
    NULL,
    'legacy',
    'legacy',
    p.reason_code,
    p.created_at,
    p.decided_at
FROM final_review_adjustment_proposals__legacy AS p
JOIN final_review_campaigns AS c ON c.campaign_id = p.campaign_id;

COMMIT;
"""


def apply_final_review_migration(conn) -> None:
    """幂等执行 final_review schema,并升级旧版重复表结构。"""
    if _has_legacy_schema(conn):
        try:
            conn.executescript(_legacy_upgrade_script())
        except Exception:
            conn.rollback()
            raise
        return
    conn.executescript(FINAL_REVIEW_SCHEMA_SQL)


__all__ = ["FINAL_REVIEW_SCHEMA_SQL", "apply_final_review_migration"]
