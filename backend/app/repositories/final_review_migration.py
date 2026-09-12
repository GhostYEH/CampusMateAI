"""期末复习迁移 SQL(§7.2)。

不修改共享文件 sqlite_db.py。本模块提供幂等 migration 函数,
由 final_review_repository 初始化时调用,或由集成智能体在 sqlite_db.py 中注册。

所有迁移均为 additive + idempotent(CREATE TABLE IF NOT EXISTS)。
"""
from __future__ import annotations

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


def apply_final_review_migration(conn) -> None:
    """幂等执行 final_review schema。可在任何 sqlite3.Connection 上调用。"""
    conn.executescript(FINAL_REVIEW_SCHEMA_SQL)


__all__ = ["FINAL_REVIEW_SCHEMA_SQL", "apply_final_review_migration"]