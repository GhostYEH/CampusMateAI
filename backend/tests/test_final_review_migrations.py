from __future__ import annotations

import json
import sqlite3

from app.database.sqlite_db import Database
from app.repositories.final_review_repository import FinalReviewRepository


def _create_legacy_final_review_schema(db_path) -> None:
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

            CREATE TABLE final_review_campaigns (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                exam_id TEXT NOT NULL,
                status TEXT NOT NULL,
                active_version INTEGER,
                daily_capacity_minutes INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, exam_id)
            );
            INSERT INTO final_review_campaigns
                (id, user_id, exam_id, status, active_version, daily_capacity_minutes, created_at, updated_at)
            VALUES
                ('campaign-1', 'user-1', 'exam-1', 'draft', NULL, 90, '2026-01-01', '2026-01-01');

            CREATE TABLE final_review_plan_versions (
                id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                parent_version_id TEXT,
                content_json TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                change_reason TEXT NOT NULL,
                created_by_run TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(campaign_id) REFERENCES final_review_campaigns(id) ON DELETE CASCADE,
                FOREIGN KEY(parent_version_id) REFERENCES final_review_plan_versions(id),
                UNIQUE(campaign_id, version)
            );
            INSERT INTO final_review_plan_versions
                (id, campaign_id, version, parent_version_id, content_json, content_hash, change_reason, created_at)
            VALUES
                ('plan-1', 'campaign-1', 1, NULL, '{"days": []}', 'hash-1', 'legacy', '2026-01-01');

            CREATE TABLE final_review_daily_agendas (
                id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                plan_version INTEGER NOT NULL,
                agenda_date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(campaign_id) REFERENCES final_review_campaigns(id) ON DELETE CASCADE,
                UNIQUE(campaign_id, plan_version, agenda_date)
            );
            INSERT INTO final_review_daily_agendas
                (id, campaign_id, plan_version, agenda_date, created_at)
            VALUES ('agenda-1', 'campaign-1', 1, '2026-01-02', '2026-01-01');

            CREATE TABLE final_review_daily_items (
                id TEXT PRIMARY KEY,
                agenda_id TEXT NOT NULL,
                title TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                status TEXT NOT NULL,
                external_task_id TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY(agenda_id) REFERENCES final_review_daily_agendas(id) ON DELETE CASCADE,
                UNIQUE(agenda_id, title)
            );
            INSERT INTO final_review_daily_items
                (id, agenda_id, title, duration_minutes, status, external_task_id, created_at)
            VALUES ('item-1', 'agenda-1', '复习极限', 30, 'pending', 'task-1', '2026-01-01');

            CREATE TABLE final_review_checkins (
                id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                completion_percent INTEGER NOT NULL,
                actual_minutes INTEGER NOT NULL,
                difficulty_code TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(campaign_id) REFERENCES final_review_campaigns(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            INSERT INTO final_review_checkins
                (id, campaign_id, user_id, completion_percent, actual_minutes, difficulty_code, created_at)
            VALUES ('checkin-1', 'campaign-1', 'user-1', 100, 30, 'medium', '2026-01-02T12:00:00+00:00');

            CREATE TABLE final_review_adjustment_proposals (
                id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                base_version INTEGER NOT NULL,
                status TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                content_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                decided_at TEXT,
                FOREIGN KEY(campaign_id) REFERENCES final_review_campaigns(id) ON DELETE CASCADE
            );
            INSERT INTO final_review_adjustment_proposals
                (id, campaign_id, base_version, status, reason_code, content_json, created_at)
            VALUES ('proposal-1', 'campaign-1', 1, 'pending', 'too_hard', '{}', '2026-01-02');
            """
        )


def test_legacy_final_review_schema_is_upgraded_idempotently(tmp_path):
    db_path = tmp_path / "legacy-final-review.db"
    _create_legacy_final_review_schema(db_path)

    database = Database(db_path)
    repository = FinalReviewRepository(database)

    campaign = repository.get_campaign("campaign-1", user_id="user-1")
    assert campaign is not None
    assert json.loads(campaign.exam_ids_json) == ["exam-1"]

    versions = repository.list_plan_versions("campaign-1", user_id="user-1")
    assert len(versions) == 1
    assert versions[0].plan_json == '{"days": []}'
    assert versions[0].user_id == "user-1"

    agenda = repository.get_agenda("agenda-1", user_id="user-1")
    assert agenda is not None
    assert agenda.total_minutes == 0

    items = repository.list_items("agenda-1", user_id="user-1")
    assert len(items) == 1
    assert items[0].scheduled_minutes == 30
    assert items[0].sort_order == 0

    evidence = repository.list_checkin_evidence("campaign-1", user_id="user-1")
    assert evidence == [
        {
            "report_date": "2026-01-02",
            "plan_version": None,
            "completed_item_ids": [],
            "insufficient_time": False,
            "difficulty_notes": "medium",
        }
    ]

    proposals = repository.list_proposals("campaign-1", user_id="user-1")
    assert len(proposals) == 1
    assert proposals[0].source_version == 1
    assert proposals[0].reason == "too_hard"

    # A second startup must not rebuild or duplicate the upgraded tables.
    FinalReviewRepository(database)
    with database.query() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM final_review_campaigns"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM final_review_plan_versions"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM final_review_checkin_evidence"
        ).fetchone()[0] == 1

    database.dispose()


def test_fresh_database_uses_current_final_review_schema(tmp_path):
    database = Database(tmp_path / "fresh.db")
    FinalReviewRepository(database)

    with database.query() as conn:
        campaign_columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(final_review_campaigns)"
            ).fetchall()
        }
        plan_columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(final_review_plan_versions)"
            ).fetchall()
        }
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert {"campaign_id", "exam_ids_json", "idempotency_key"} <= campaign_columns
    assert {"campaign_id", "user_id", "plan_json", "risk_level"} <= plan_columns
    assert "final_review_checkins" not in tables

    database.dispose()
