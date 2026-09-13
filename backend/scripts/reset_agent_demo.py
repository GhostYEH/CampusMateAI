"""重置 Agent runtime demo 数据(§14 隔离 demo)。

只删除 demo user(username=`agent_demo`)拥有的 runtime / final-review /
course-research / notice-workflow / personal_tasks 记录。不删除 demo user 本身,
也不删除其他用户的数据。生产环境拒绝执行。

用法:
    python -m scripts.reset_agent_demo           # 默认 dry-run,只报告将删除的行数
    python -m scripts.reset_agent_demo --apply   # 实际执行删除
    python -m scripts.reset_agent_demo --json    # JSON 输出

退出码: 0=成功, 1=拒绝/错误。
"""
from __future__ import annotations

import argparse
import json as _json
import sys
from typing import Optional

from app.core.config import Settings, get_settings
from app.database.sqlite_db import Database, init_db
from app.repositories.multi_role_repository import UserRepository


DEMO_USERNAME = "agent_demo"

# 按 user_id 删除的表(user_id 列名统一为 user_id)。
# 顺序考虑外键:先删子表,再删父表。SQLite ON DELETE CASCADE 会处理大部分,
# 但显式删除更安全(某些表可能没有 FK)。
USER_SCOPED_TABLES: list[tuple[str, str]] = [
    # course_research(子表先删)
    ("course_research_sources", "user_id"),
    ("course_research_reports", "user_id"),
    ("course_research_sessions", "user_id"),
    # notice_workflow(子表先删)
    ("notice_workflow_actions", "user_id"),
    ("notice_workflows", "user_id"),
    # final_review(子表先删)
    ("final_review_daily_items", "user_id"),
    ("final_review_daily_agendas", "user_id"),
    ("final_review_adjustment_proposals", "user_id"),
    ("final_review_plan_versions", "user_id"),
    ("final_review_campaigns", "user_id"),
    # agent runtime(子表先删)
    ("agent_artifacts", "user_id"),
    ("agent_citations", "user_id"),  # 无 user_id 列,按 run_id 处理(见下)
    ("agent_approvals", "user_id"),
    ("agent_memories", "user_id"),
    ("agent_events", "user_id"),  # 无 user_id 列,按 run_id 处理
    ("agent_model_calls", "user_id"),  # 无 user_id 列,按 run_id 处理
    ("agent_tool_calls", "user_id"),  # 无 user_id 列,按 run_id 处理
    ("agent_run_steps", "user_id"),  # 无 user_id 列,按 run_id 处理
    ("agent_context_snapshots", "user_id"),
    ("agent_runs", "user_id"),
    ("agent_jobs", "user_id"),
    # 通知与个人待办
    ("notices", "user_id"),
    ("personal_tasks", "user_id"),
    # 考试
    ("student_exams", "user_id"),
]

# 这些表没有 user_id 列,需要通过 run_id 关联 demo user 的 agent_runs 来删。
RUN_SCOPED_TABLES: list[str] = [
    "agent_run_steps",
    "agent_tool_calls",
    "agent_model_calls",
    "agent_events",
    "agent_citations",
]


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _has_column(conn, table: str, column: str) -> bool:
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    return column in cols


def _count_user_rows(conn, table: str, user_id: str) -> int:
    if not _table_exists(conn, table):
        return 0
    if not _has_column(conn, table, "user_id"):
        return 0
    return conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE user_id = ?", (user_id,)
    ).fetchone()[0]


def _delete_user_rows(conn, table: str, user_id: str) -> int:
    if not _table_exists(conn, table):
        return 0
    if not _has_column(conn, table, "user_id"):
        return 0
    cur = conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
    return cur.rowcount or 0


def _count_run_scoped(conn, table: str, demo_run_ids: set[str]) -> int:
    if not _table_exists(conn, table) or not demo_run_ids:
        return 0
    placeholders = ",".join("?" for _ in demo_run_ids)
    return conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE run_id IN ({placeholders})",
        tuple(demo_run_ids),
    ).fetchone()[0]


def _delete_run_scoped(conn, table: str, demo_run_ids: set[str]) -> int:
    if not _table_exists(conn, table) or not demo_run_ids:
        return 0
    placeholders = ",".join("?" for _ in demo_run_ids)
    cur = conn.execute(
        f"DELETE FROM {table} WHERE run_id IN ({placeholders})",
        tuple(demo_run_ids),
    )
    return cur.rowcount or 0


def reset_agent_demo(
    *,
    apply: bool = False,
    as_json: bool = False,
    settings: Optional[Settings] = None,
    db: Optional[Database] = None,
) -> dict:
    """重置 agent demo 数据。

    Args:
        apply: True=实际删除, False=dry-run 只统计。
        as_json: True=返回 JSON 友好的 dict(已经是 dict,无影响)。
        settings: 可选 Settings 实例(测试注入);默认 get_settings()。
        db: 可选 Database 实例(测试注入);默认 init_db(settings)。

    Returns:
        统计字典。
    """
    if settings is None:
        settings = get_settings()
    else:
        # 生产环境拒绝执行(§14)。同时检查注入的 settings。
        if getattr(settings, "app_env", None) == "production":
            result = {
                "status": "rejected",
                "reason": "production 环境禁止执行 demo 重置",
                "app_env": settings.app_env,
            }
            if as_json:
                print(_json.dumps(result, ensure_ascii=False))
            else:
                print(f"[reject] {result['reason']}")
            return result

    # 生产环境拒绝执行(§14)。
    if settings.app_env == "production":
        result = {
            "status": "rejected",
            "reason": "production 环境禁止执行 demo 重置",
            "app_env": settings.app_env,
        }
        if as_json:
            print(_json.dumps(result, ensure_ascii=False))
        else:
            print(f"[reject] {result['reason']}")
        return result

    if db is None:
        db = init_db(settings)
    conn = db._connect()
    try:
        user_repo = UserRepository(db)
        demo_user = user_repo.get_user_by_username(DEMO_USERNAME)
        if demo_user is None:
            result = {
                "status": "no_demo_user",
                "reason": f"未找到 demo user(username={DEMO_USERNAME})",
            }
            if as_json:
                print(_json.dumps(result, ensure_ascii=False))
            else:
                print(f"[skip] {result['reason']}")
            return result

        uid = demo_user.id

        # 收集 demo user 的 agent_run_ids(用于 run-scoped 表删除)
        demo_run_ids: set[str] = set()
        if _table_exists(conn, "agent_runs") and _has_column(conn, "agent_runs", "user_id"):
            for row in conn.execute(
                "SELECT run_id FROM agent_runs WHERE user_id = ?", (uid,)
            ).fetchall():
                demo_run_ids.add(row[0])

        # 统计
        counts: dict[str, int] = {}
        for table, _col in USER_SCOPED_TABLES:
            counts[table] = _count_user_rows(conn, table, uid)
        for table in RUN_SCOPED_TABLES:
            # 避免重复统计已有 user_id 列的表
            if any(t == table for t, _ in USER_SCOPED_TABLES) and _has_column(
                conn, table, "user_id"
            ):
                continue
            key = f"{table}(by_run)"
            counts[key] = _count_run_scoped(conn, table, demo_run_ids)

        total = sum(counts.values())

        if not apply:
            result = {
                "status": "dry_run",
                "demo_user": DEMO_USERNAME,
                "demo_user_id": uid,
                "demo_run_count": len(demo_run_ids),
                "counts": counts,
                "total": total,
            }
            if as_json:
                print(_json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"[dry-run] demo user={DEMO_USERNAME} (id={uid})")
                print(f"  demo runs: {len(demo_run_ids)}")
                for k, v in counts.items():
                    if v > 0:
                        print(f"  {k}: {v}")
                print(f"  total rows to delete: {total}")
                print("  使用 --apply 实际执行删除。")
            return result

        # 实际删除
        deleted: dict[str, int] = {}
        for table, _col in USER_SCOPED_TABLES:
            deleted[table] = _delete_user_rows(conn, table, uid)
        for table in RUN_SCOPED_TABLES:
            if any(t == table for t, _ in USER_SCOPED_TABLES) and _has_column(
                conn, table, "user_id"
            ):
                continue
            key = f"{table}(by_run)"
            deleted[key] = _delete_run_scoped(conn, table, demo_run_ids)

        conn.commit()
        total_deleted = sum(deleted.values())

        result = {
            "status": "ok",
            "demo_user": DEMO_USERNAME,
            "demo_user_id": uid,
            "demo_run_count": len(demo_run_ids),
            "deleted": deleted,
            "total_deleted": total_deleted,
        }
        if as_json:
            print(_json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"[ok] 已重置 demo user={DEMO_USERNAME} (id={uid})")
            print(f"  demo runs: {len(demo_run_ids)}")
            for k, v in deleted.items():
                if v > 0:
                    print(f"  {k}: {v}")
            print(f"  total deleted: {total_deleted}")
        return result
    finally:
        db._release(conn)


def main() -> int:
    parser = argparse.ArgumentParser(description="重置 Agent runtime demo 数据")
    parser.add_argument(
        "--apply", action="store_true", help="实际执行删除(默认 dry-run)"
    )
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    result = reset_agent_demo(apply=args.apply, as_json=args.json)
    if result.get("status") == "rejected":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
