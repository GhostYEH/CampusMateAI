"""Phase 6C: 合成演示数据注入脚本。

完全合成的演示数据，不含真实个人数据。
支持 3 个场景：deadline-pressure / stale-source-replan / shadow-model-blocked。

用法：
    python -m app.demo.learner_model seed --scenario deadline-pressure
    python -m app.demo.learner_model clear --scenario stale-source-replan

要求：
- 必须显式指定 scenario
- 默认拒绝在生产环境运行
- 幂等运行
- 可清理自身创建的数据
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from ..core.config import Settings, get_settings
from ..core.exceptions import DemoSeedRefused
from ..database.sqlite_db import Database, init_db
from ..repositories.learner_control_repository import LearnerControlRepository
from ..repositories.learner_event_repository import LearnerEventRepository
from ..repositories.learner_state_repository import LearnerStateRepository
from ..services.learner_event_service import LearnerEventService
from ..services.learner_state_service import LearnerStateProjectionService

SCENARIOS = (
    "deadline-pressure",

    "stale-source-replan",
    "shadow-model-blocked",
)

DEMO_USER_PREFIX = "demo_learner_model_"
DEMO_TAG = "__demo_learner_model__"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _uuid() -> str:
    return uuid.uuid4().hex


def _ensure_test_env(settings: Settings) -> None:
    """拒绝在生产环境运行。"""
    if settings.app_env not in ("test", "dev", "development", "local"):
        raise DemoSeedRefused()
    if "sqlite:///:memory:" not in (settings.database_url or "") and settings.database_url:
        if "demo" not in (settings.database_url or "").lower() and settings.app_env != "test":
            raise DemoSeedRefused()


def _get_or_create_demo_user(conn: sqlite3.Connection, scenario: str) -> str:
    """获取或创建合成演示用户。"""
    username = f"{DEMO_USER_PREFIX}{scenario}"
    row = conn.execute(
        "SELECT id FROM users WHERE username=?", (username,)
    ).fetchone()
    if row:
        return row["id"]
    user_id = f"demo_user_{scenario}_{_uuid()[:8]}"
    now = _utc_now().isoformat()
    conn.execute(
        """INSERT INTO users (id, username, password_hash, role, display_name, is_active, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?)""",
        (user_id, username, "demo_no_login", "student", f"演示用户-{scenario}", 1, now, now),
    )
    return user_id


def _clear_demo_user(conn: sqlite3.Connection, scenario: str) -> int:
    """清理指定场景的演示用户及其数据。"""
    username = f"{DEMO_USER_PREFIX}{scenario}"
    row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    if row is None:
        return 0
    user_id = row["id"]
    for table in (
        "learner_state_projection_runs",
        "learner_events",
        "learner_state_corrections",
        "learning_plan_decisions",
        "learning_plan_execution_actions",
        "learning_plan_feedback",
        "learning_plan_evaluation_runs",
        "learning_plans",
        "learning_plan_runs",
        "model_shadow_runs",
        "learner_product_events",
        "learner_data_source_controls",
        "learner_model_delete_requests",
    ):
        conn.execute(f"DELETE FROM {table} WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    return 1


def _seed_deadline_pressure(conn: sqlite3.Connection, user_id: str, as_of: datetime) -> None:
    """场景一：截止任务与时间预算。"""
    now = as_of.isoformat()
    for i, (title, offset_h, status) in enumerate([
        ("演示-近期作业-1", 12, "pending"),
        ("演示-近期作业-2", 36, "pending"),
        ("演示-已逾期作业", -6, "pending"),
    ]):
        deadline = (as_of + timedelta(hours=offset_h)).isoformat()
        conn.execute(
            """INSERT OR IGNORE INTO personal_tasks
            (id, user_id, title, status, deadline, created_at, updated_at, source)
            VALUES (?,?,?,?,?,?,?,?)""",
            (_uuid(), user_id, title, status, deadline, now, now, "demo"),
        )
    conn.execute(
        """INSERT OR IGNORE INTO learner_events
        (event_id, user_id, occurred_at, received_at, source, event_type,
         subject_type, subject_id, external_ref, outcome, duration_seconds,
         evidence_reference_json, data_quality, consent_scope, source_version,
         dedupe_key, payload_json, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            _uuid(), user_id, now, now, "study", "study_session_finished",
            "USER", user_id, None, "completed", 1800,
            json.dumps({"kind": "EVENT", "table": "study_sessions", "row_id": _uuid()}),
            "verified", "core_learning", "1",
            f"demo_deadline_session_{_uuid()[:8]}",
            json.dumps({"duration_minutes": 30}),
            now,
        ),
    )



def _seed_stale_source_replan(conn: sqlite3.Connection, user_id: str, as_of: datetime) -> None:
    """场景三：数据源失效。"""
    now = as_of.isoformat()
    conn.execute(
        """INSERT OR IGNORE INTO learner_data_source_controls
        (source_key, user_id, status, updated_at)
        VALUES ('CHAOXING', ?, 'PAUSED', ?)""",
        (user_id, now),
    )
    conn.execute(
        """INSERT OR IGNORE INTO learner_events
        (event_id, user_id, occurred_at, received_at, source, event_type,
         subject_type, subject_id, external_ref, outcome, duration_seconds,
         evidence_reference_json, data_quality, consent_scope, source_version,
         dedupe_key, payload_json, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            _uuid(), user_id, (as_of - timedelta(hours=48)).isoformat(), now,
            "chaoxing", "course_synced", "COURSE", "demo_course_stale",
            None, "synced", None,
            json.dumps({"kind": "SYNC_STATUS", "table": "courses", "row_id": "demo_course_stale"}),
            "stale", "chaoxing", "1",
            f"demo_stale_sync_{_uuid()[:8]}",
            json.dumps({}),
            now,
        ),
    )


def _seed_shadow_model_blocked(conn: sqlite3.Connection, user_id: str, as_of: datetime) -> None:
    """场景四：模型影子评测。"""
    now = as_of.isoformat()
    conn.execute(
        """INSERT OR IGNORE INTO model_promotion_decisions
        (decision_id, model_key, model_version, capability_name, capability_version,
         dataset_version, evaluator_version, threshold_version, metrics_digest,
         decision, failed_gates_json, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            _uuid(), "campusmate-lm", "demo-v1",
            "learning_summary_v1", "1.0",
            "campusmate-lm-shadow-v1", "campusmate-lm-shadow-evaluator-v1",
            "campusmate-lm-gates-v1", _uuid(),
            "BLOCKED",
            json.dumps(["quality_gate_micro_f1"]),
            now,
        ),
    )
    conn.execute(
        """INSERT OR IGNORE INTO learner_data_source_controls
        (source_key, user_id, status, updated_at)
        VALUES ('MODEL_SHADOW', ?, 'ENABLED', ?)""",
        (user_id, now),
    )


SEED_DISPATCH = {
    "deadline-pressure": _seed_deadline_pressure,

    "stale-source-replan": _seed_stale_source_replan,
    "shadow-model-blocked": _seed_shadow_model_blocked,
}


def seed(scenario: str, settings: Settings | None = None) -> dict[str, Any]:
    """注入演示数据。"""
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario: {scenario}")
    s = settings or get_settings()
    _ensure_test_env(s)
    db = init_db(s)
    as_of = _utc_now()
    with db.transaction() as conn:
        user_id = _get_or_create_demo_user(conn, scenario)
        SEED_DISPATCH[scenario](conn, user_id, as_of)
    return {"scenario": scenario, "demo_user_id": user_id, "seeded_at": as_of.isoformat()}


def clear(scenario: str, settings: Settings | None = None) -> dict[str, Any]:
    """清理演示数据。"""
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario: {scenario}")
    s = settings or get_settings()
    _ensure_test_env(s)
    db = init_db(s)
    with db.transaction() as conn:
        removed = _clear_demo_user(conn, scenario)
    return {"scenario": scenario, "removed_users": removed}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="演示数据注入")
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("seed", "clear"):
        p = sub.add_parser(action)
        p.add_argument("--scenario", required=True, choices=SCENARIOS)
    args = parser.parse_args(argv)
    if args.action == "seed":
        result = seed(args.scenario)
    else:
        result = clear(args.scenario)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())