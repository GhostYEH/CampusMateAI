"""学习计划证据查询的索引与批量加载回归。

覆盖:
- `WHERE plan_id IN (...) ORDER BY evidence_id` 使用 (plan_id, evidence_id) 索引
- 单计划查询不再需要临时排序结构；多计划全局排序允许保留临时结构
- 新库与旧库启动都能幂等补建索引，且不丢失已有数据
- 单计划 / 多计划 / 分页 / 证据排序 / 用户隔离保持正确
- 原有 item_id 索引保留，批量加载不退回逐条查询
"""
from __future__ import annotations

from app.database.sqlite_db import Database
from app.repositories.learning_plan_repository import LearningPlanRepository
from app.repositories.user_repository import UserRepository

_EVIDENCE_QUERY = (
    "SELECT item_id,evidence_type,reference_id,relevance_score,metadata_json "
    "FROM learning_plan_evidence WHERE plan_id IN ({}) ORDER BY evidence_id"
)


def _create_plan(repository, *, user_id, index, item_count=3, evidence_per_item=2):
    return repository.create_plan(user_id=user_id, run={
        "run_id": f"run-{index}", "planner_version": "test-v1", "input_digest": str(index),
        "as_of": "2026-10-04T00:00:00+00:00", "valid_until": "2026-10-05T00:00:00+00:00",
        "available_minutes": 120, "allocated_minutes": 60,
    }, items=[{
        "item_id": f"item-{index}-{item}", "item_type": "REVIEW_TASK",
        "estimated_minutes": 15, "priority_score": float(item),
        "priority_components": {"urgency": item}, "explanation_codes": ["test"],
        "evidence": [
            {"evidence_type": "TASK", "reference_id": f"task-{index}-{item}-{e}",
             "relevance_score": 0.8, "metadata": {"item": item, "e": e}}
            for e in range(evidence_per_item)
        ],
    } for item in range(item_count)])


def _index_names(db) -> set[str]:
    with db.query() as conn:
        return {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        }


def _query_plan(db, sql: str, params=()) -> str:
    with db.query() as conn:
        return " | ".join(row["detail"] for row in conn.execute("EXPLAIN QUERY PLAN " + sql, params))


def _seed_volume(db, plans: int, items: int = 5, evidence_per_item: int = 4) -> None:
    """填充足够多的证据行，让查询计划能体现索引收益。"""
    with db.transaction() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (id,username,password_hash,role,created_at,updated_at) "
            "VALUES ('u-bulk','u-bulk','x','student','t','t')"
        )
        for plan in range(plans):
            run_id, plan_id = f"bulk-run-{plan}", f"bulk-plan-{plan}"
            conn.execute(
                "INSERT INTO learning_plan_runs (run_id,user_id,planner_version,input_digest,as_of,"
                "valid_until,available_minutes,allocated_minutes,warning_codes_json,created_at) "
                "VALUES (?,?,'v','d','a','b',1,1,'[]','t')", (run_id, "u-bulk"),
            )
            conn.execute(
                "INSERT INTO learning_plans (plan_id,run_id,user_id,status,created_at) "
                "VALUES (?,?,?,'PROPOSED','t')", (plan_id, run_id, "u-bulk"),
            )
            for item in range(items):
                item_id = f"bulk-item-{plan}-{item}"
                conn.execute(
                    "INSERT INTO learning_plan_items (item_id,plan_id,item_type,estimated_minutes,"
                    "priority_score,priority_components_json,explanation_codes_json,created_at) "
                    "VALUES (?,?,'REVIEW',10,1.0,'{}','[]','t')", (item_id, plan_id),
                )
                for e in range(evidence_per_item):
                    conn.execute(
                        "INSERT INTO learning_plan_evidence (evidence_id,plan_id,item_id,evidence_type,"
                        "reference_id,metadata_json) VALUES (?,?,?,'e','ref','{}')",
                        (f"bulk-ev-{plan:04d}-{item:03d}-{e:03d}", plan_id, item_id),
                    )
        conn.execute("ANALYZE")


def test_single_plan_evidence_query_uses_composite_index_without_temp_sort(tmp_path):
    db = Database(tmp_path / "plans.sqlite3")
    try:
        _seed_volume(db, plans=60)
        plan = _query_plan(db, _EVIDENCE_QUERY.format("?"), ("bulk-plan-1",))
        assert "idx_learning_plan_evidence_plan" in plan
        # 单计划时 (plan_id, evidence_id) 同时覆盖过滤与排序。
        assert "TEMP B-TREE" not in plan
    finally:
        db.dispose()


def test_multi_plan_evidence_query_uses_composite_index(tmp_path):
    db = Database(tmp_path / "plans.sqlite3")
    try:
        _seed_volume(db, plans=60)
        plan = _query_plan(db, _EVIDENCE_QUERY.format("?,?,?"), ("bulk-plan-1", "bulk-plan-2", "bulk-plan-3"))
        assert "idx_learning_plan_evidence_plan" in plan
        # 多计划全局排序需要临时结构是允许的，不机械禁止所有排序。
        assert "idx_learning_plan_evidence_item" not in plan
    finally:
        db.dispose()


def test_existing_item_index_is_kept(tmp_path):
    db = Database(tmp_path / "plans.sqlite3")
    try:
        names = _index_names(db)
        assert "idx_learning_plan_evidence_item" in names
        assert "idx_learning_plan_evidence_plan" in names
    finally:
        db.dispose()


def test_index_is_recreated_idempotently_on_existing_database(tmp_path):
    """旧库（缺少新索引）启动后幂等补建，已有数据不丢失。"""
    path = tmp_path / "legacy.sqlite3"
    first = Database(path)
    users = UserRepository(first)
    owner = users.create_user(username="legacy-owner", password_hash="unused")
    repository = LearningPlanRepository(first)
    plan = _create_plan(repository, user_id=owner.id, index="legacy")
    with first.transaction() as conn:
        conn.execute("DROP INDEX idx_learning_plan_evidence_plan")
    assert "idx_learning_plan_evidence_plan" not in _index_names(first)
    first.dispose()

    reopened = Database(path)
    try:
        assert "idx_learning_plan_evidence_plan" in _index_names(reopened)
        restored = LearningPlanRepository(reopened).get_plan(plan.plan_id, user_id=owner.id)
        assert restored is not None
        assert len(restored.items) == 3
        # 条目按 priority_score DESC：最高优先级的 item-2 排在最前。
        assert [item.item_id for item in restored.items] == ["item-legacy-2", "item-legacy-1", "item-legacy-0"]
        with reopened.query() as conn:
            expected = [
                row["reference_id"]
                for row in conn.execute(
                    "SELECT reference_id FROM learning_plan_evidence WHERE plan_id=? AND item_id=? "
                    "ORDER BY evidence_id",
                    (plan.plan_id, "item-legacy-2"),
                )
            ]
        assert [e["reference_id"] for e in restored.items[0].evidence] == expected
        assert len(expected) == 2
    finally:
        reopened.dispose()


def test_batch_loading_keeps_single_plan_multi_plan_and_ordering(tmp_path, monkeypatch):
    db = Database(tmp_path / "plans.sqlite3")
    try:
        users = UserRepository(db)
        owner = users.create_user(username="owner", password_hash="unused")
        other = users.create_user(username="other", password_hash="unused")
        repository = LearningPlanRepository(db)
        plans = [_create_plan(repository, user_id=owner.id, index=index) for index in range(3)]
        _create_plan(repository, user_id=other.id, index="other")

        # 单计划：条目按 priority_score DESC；证据按 evidence_id 排序。
        single = repository.get_plan(plans[0].plan_id, user_id=owner.id)
        assert [item.item_id for item in single.items] == ["item-0-2", "item-0-1", "item-0-0"]
        with db.query() as conn:
            expected = [
                row["reference_id"]
                for row in conn.execute(
                    "SELECT reference_id FROM learning_plan_evidence WHERE plan_id=? AND item_id=? "
                    "ORDER BY evidence_id",
                    (plans[0].plan_id, "item-0-2"),
                )
            ]
        assert [e["reference_id"] for e in single.items[0].evidence] == expected
        assert len(expected) == 2

        # 多计划 + 分页 + 用户隔离。
        page, total = repository.list_plans(user_id=owner.id, page=1, page_size=2)
        assert total == 3
        assert len(page) == 2
        assert all(plan.user_id == owner.id for plan in page)
        other_page, other_total = repository.list_plans(user_id=other.id, page=1, page_size=10)
        assert other_total == 1
        assert other_page[0].user_id == other.id

        # 每页仍然只发一条证据查询（不退回逐条查询）。
        statements: list[str] = []
        original_connect = db._connect

        def traced_connect():
            conn = original_connect()
            conn.set_trace_callback(
                lambda sql: statements.append(sql) if sql.lstrip().upper().startswith("SELECT") else None
            )
            return conn

        monkeypatch.setattr(db, "_connect", traced_connect)
        repository.list_plans(user_id=owner.id, page=1, page_size=3)
        assert sum(1 for sql in statements if "learning_plan_evidence" in sql) == 1
    finally:
        db.dispose()
