"""上下文预算与分级裁剪(§5.1)。"""
from __future__ import annotations

import pytest

from app.database.sqlite_db import reset_db_for_tests
from app.repositories.agent_runtime_repository import AgentRuntimeRepository
from app.services.agent_runtime.context_budget import (
    compact_facts,
    estimate_tokens,
    tool_result_tier,
    trim_text,
    trim_tool_result,
)
from app.services.agent_runtime.context_manager import ContextManager


@pytest.fixture
def repo():
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
    return AgentRuntimeRepository(db)


def test_estimate_tokens_counts_cjk_as_one_token_per_char():
    assert estimate_tokens("") == 0
    assert estimate_tokens("数据库事务") == 5
    assert estimate_tokens("abcdefgh") == 2  # 8 个 ASCII 字符 ≈ 2 tokens


def test_trim_text_keeps_head_and_tail_and_marks_truncation():
    text = "开头" + "很长的内容" * 200 + "结论"
    trimmed, was_trimmed = trim_text(text, 50)

    assert was_trimmed is True
    assert trimmed.startswith("开头")
    assert trimmed.endswith("结论")
    assert "截断" in trimmed
    assert estimate_tokens(trimmed) < estimate_tokens(text)


def test_short_text_is_not_trimmed():
    text = "短文本"
    assert trim_text(text, 100) == (text, False)


def test_tool_result_tiers():
    assert tool_result_tier("task.create") == "critical"
    assert tool_result_tier("web.search") == "low"
    assert tool_result_tier("knowledge.search") == "moderate"


def test_low_value_tool_result_is_replaced_by_placeholder():
    payload = "网页正文" * 500

    trimmed, was_trimmed = trim_tool_result("web.search", payload, budget_tokens=200)

    assert was_trimmed is True
    assert "省略" in trimmed
    assert estimate_tokens(trimmed) < estimate_tokens(payload)


def test_compact_facts_leaves_small_context_untouched():
    facts = {"daily_capacity_minutes": 120, "exams": [{"id": "e1"}]}

    compacted, report = compact_facts(facts, budget_tokens=1000)

    assert compacted == facts
    assert report["truncated"] is False


def test_compact_facts_trims_long_values_but_keeps_scalars():
    facts = {
        "daily_capacity_minutes": 120,
        "materials": "课程资料正文" * 400,
        "sources": [f"来源{i}" * 40 for i in range(20)],
    }

    compacted, report = compact_facts(facts, budget_tokens=300)

    assert report["truncated"] is True
    # 标量字段永不丢弃
    assert compacted["daily_capacity_minutes"] == 120
    assert report["estimated_tokens"] <= 300
    assert report["trimmed_keys"] or report["dropped_keys"]


def test_context_manager_records_budget_report_only_when_truncated(repo: AgentRuntimeRepository):
    manager = ContextManager(repo, budget_tokens=200)

    small = manager.build(user_id="u1", facts={"daily_capacity_minutes": 120})
    assert "_context_budget" not in small.facts
    assert small.budget_report["truncated"] is False

    big = manager.build(
        user_id="u1",
        facts={"materials": "课程资料正文" * 500, "daily_capacity_minutes": 120},
    )
    assert big.budget_report["truncated"] is True
    assert "_context_budget" in big.facts
    assert big.facts["daily_capacity_minutes"] == 120
    assert big.budget_report["estimated_tokens"] <= 200
