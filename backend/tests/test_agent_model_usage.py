"""模型调用用量记账:只存元数据与 token,不存 prompt/消息/推理。"""
from __future__ import annotations

import pytest

from app.database.sqlite_db import reset_db_for_tests
from app.repositories.agent_runtime_repository import AgentRuntimeRepository
from app.services.llm.base import LLMResponse
from app.services.llm.model_router import extract_token_usage


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


def _make_run(repo: AgentRuntimeRepository) -> str:
    job_id = repo.create_job(user_id="u1", job_kind="final_review", input_ref={})
    return repo.create_run(job_id=job_id, user_id="u1")


def test_usage_is_recorded_and_aggregated_per_run(repo: AgentRuntimeRepository):
    run_id = _make_run(repo)
    repo.record_model_call(
        run_id=run_id,
        provider="primary",
        route_policy="reasoning_primary",
        model="demo-model",
        status="succeeded",
        latency_ms=120,
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        cached_tokens=4,
    )

    usage = repo.model_usage(run_id)

    assert usage["calls"] == 1
    assert usage["prompt_tokens"] == 10
    assert usage["completion_tokens"] == 5
    assert usage["total_tokens"] == 15
    assert usage["cached_tokens"] == 4
    assert usage["latency_ms"] == 120


def test_missing_usage_is_not_counted_as_tokens(repo: AgentRuntimeRepository):
    run_id = _make_run(repo)
    repo.record_model_call(
        run_id=run_id,
        provider="primary",
        route_policy="fast_structured",
        model="demo-model",
        status="failed",
        latency_ms=5,
        fallback_reason="timeout",
    )

    usage = repo.model_usage(run_id)

    assert usage["calls"] == 1
    assert usage["total_tokens"] == 0
    assert usage["cached_tokens"] == 0


def test_usage_does_not_store_prompt_or_message_columns(repo: AgentRuntimeRepository):
    """用量记账不得把 prompt/消息带进表结构。"""
    conn = repo._conn()
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(agent_model_calls)")}
    finally:
        repo._release(conn)
    assert {"prompt_tokens", "completion_tokens", "total_tokens", "cached_tokens"} <= columns
    forbidden = {"prompt", "messages", "content", "authorization", "api_key"}
    assert not (forbidden & columns)


def test_extract_token_usage_supports_deepseek_and_openai_shapes():
    deepseek = LLMResponse(
        "ok",
        raw={
            "usage": {
                "prompt_tokens": 7,
                "completion_tokens": 3,
                "total_tokens": 10,
                "prompt_cache_hit_tokens": 2,
            }
        },
    )
    assert extract_token_usage(deepseek) == {
        "prompt_tokens": 7,
        "completion_tokens": 3,
        "total_tokens": 10,
        "cached_tokens": 2,
    }

    openai_style = LLMResponse(
        "ok",
        raw={
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 1,
                "prompt_tokens_details": {"cached_tokens": 4},
            }
        },
    )
    usage = extract_token_usage(openai_style)
    assert usage["total_tokens"] == 6
    assert usage["cached_tokens"] == 4

    assert extract_token_usage(None) == {}
    assert extract_token_usage(LLMResponse("ok")) == {}
