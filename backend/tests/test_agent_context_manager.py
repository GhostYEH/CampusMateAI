"""Context manager 测试。"""
from __future__ import annotations

import pytest

from app.core.exceptions import AgentContextExpired
from app.database.sqlite_db import reset_db_for_tests
from app.repositories.agent_runtime_repository import AgentRuntimeRepository
from app.services.agent_runtime.context_manager import ContextManager


@pytest.fixture
def ctx_manager():
    db = reset_db_for_tests()
    conn = db._connect()
    try:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
            "VALUES ('u1', 'u1', 'x', 'student', 't', 't')"
        )
        conn.commit()
    finally:
        db._release(conn)
    repo = AgentRuntimeRepository(db)
    return ContextManager(repo, ttl_minutes=15)


def test_build_snapshot(ctx_manager):
    snap = ctx_manager.build(
        user_id="u1",
        scope={"course_ids": ["c1"]},
        facts={"daily_capacity_minutes": 120},
        source_refs=["exam:1"],
    )
    assert snap.snapshot_id.startswith("ctx_")
    assert snap.source_digest.startswith("sha256:")
    assert snap.valid_until != ""


def test_load_snapshot(ctx_manager):
    snap = ctx_manager.build(
        user_id="u1", facts={"x": 1}, source_refs=["a"]
    )
    loaded = ctx_manager.load(snap.snapshot_id, "u1")
    assert loaded is not None
    assert loaded.facts == {"x": 1}
    assert loaded.expired is False


def test_load_snapshot_ownership_isolation(ctx_manager):
    snap = ctx_manager.build(user_id="u1", facts={"x": 1})
    # 其他用户不能加载
    assert ctx_manager.load(snap.snapshot_id, "u2") is None


def test_assert_not_expired(ctx_manager):
    snap = ctx_manager.build(user_id="u1", facts={"x": 1})
    ctx_manager.assert_not_expired(snap)  # 未过期,不抛


def test_assert_expired_raises(ctx_manager):
    from app.services.agent_runtime.context_manager import ContextSnapshot
    snap = ContextSnapshot(
        snapshot_id="x", user_id="u1", source_digest="d",
        generated_at="t", valid_until="t", expired=True,
    )
    with pytest.raises(AgentContextExpired):
        ctx_manager.assert_not_expired(snap)


def test_oversized_facts_are_compacted_before_persisting(ctx_manager):
    """超预算上下文先按预算确定性裁剪,而不是直接失败。"""
    big_facts = {"data": "x" * 100000, "daily_capacity_minutes": 120}
    snap = ctx_manager.build(user_id="u1", facts=big_facts)
    assert snap.budget_report["truncated"] is True
    assert snap.facts["daily_capacity_minutes"] == 120
    assert snap.budget_report["estimated_tokens"] <= 6000


def test_facts_size_limit_still_guards_uncompactable_input(ctx_manager):
    """标量字段不是可裁剪对象:极端输入仍由硬上限兜底。"""
    pathological = {f"k{index}": index for index in range(70000)}
    with pytest.raises(ValueError):
        ctx_manager.build(user_id="u1", facts=pathological)