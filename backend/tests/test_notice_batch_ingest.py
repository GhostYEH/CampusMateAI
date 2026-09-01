from __future__ import annotations

import json
import asyncio

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import get_container, reset_container_for_tests
from app.services.demo_seeder import seed_demo_data
from app.services.llm.base import LLMResponse
from app.services.notice_extraction_service import NoticeExtractionService


class BatchLLM:
    name = "mock:model"
    available = True

    def __init__(self, delay: float = 0.0) -> None:
        self.calls = 0
        self.delay = delay

    async def chat(self, messages, **kwargs):
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        items = json.loads(messages[-1]["content"])
        return LLMResponse(content=json.dumps({
            "results": [
                {"id": item["id"], "type": "ACTIONABLE_NOTICE", "tasks": []}
                for item in items
            ]
        }))


class ExtractingBatchLLM(BatchLLM):
    async def chat(self, messages, **kwargs):
        self.calls += 1
        items = json.loads(messages[-1]["content"])
        return LLMResponse(content=json.dumps({
            "results": [
                {
                    "id": item["id"],
                    "type": "ACTIONABLE_NOTICE",
                    "tasks": [{
                        "title": f"待确认事项{item['id']}",
                        "task": f"完成待确认事项{item['id']}",
                        "actionable": True,
                        "confidence": 0.8,
                    }],
                }
                for item in items
            ]
        }, ensure_ascii=False))


def _client_with_llm() -> tuple[TestClient, dict[str, str], BatchLLM]:
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        llm_provider="openai_compatible",
        llm_base_url="https://llm.invalid/v1",
        llm_api_key="test",
        llm_model="mock",
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    llm = BatchLLM()
    container.llm = llm
    container.notice_extraction = NoticeExtractionService(llm, settings)
    client = TestClient(create_app())
    login = client.post("/api/v1/auth/login", json={"username": "student_demo", "password": "Demo123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    return client, headers, llm


def _item(index: int, content: str, fingerprint: str | None = None) -> dict:
    return {
        "client_id": f"bundle-{index}",
        "client_fingerprint": fingerprint or (f"fingerprint-{index:03d}" * 2),
        "source_name": "软件工程1班",
        "published_at": "2026-08-13T20:00:00+08:00",
        "messages": [{"text": content, "published_at": "2026-08-13T20:00:00+08:00"}],
    }


def test_rule_first_batch_filters_chat_and_uses_no_llm() -> None:
    client, headers, llm = _client_with_llm()
    payload = {
        "items": [
            _item(1, "哈哈哈哈"),
            _item(2, "请于8月20日17:00前提交实验报告"),
            _item(3, "学院明天停电检修"),
        ]
    }

    response = client.post("/api/v1/notices/ingest-batch", headers=headers, json=payload)

    assert response.status_code == 200
    assert [item["semantic_type"] for item in response.json()["items"]] == [
        "CHAT", "ACTIONABLE_NOTICE", "NOTICE"
    ]
    assert response.json()["items"][0]["status"] == "ignored"
    assert llm.calls == 0


def test_five_ambiguous_bundles_use_one_llm_call_and_retry_uses_none() -> None:
    client, headers, llm = _client_with_llm()
    payload = {"items": [_item(i, f"明晚记得带一下报名的东西{i}") for i in range(5)]}

    first = client.post("/api/v1/notices/ingest-batch", headers=headers, json=payload)
    second = client.post("/api/v1/notices/ingest-batch", headers=headers, json=payload)

    assert first.status_code == 200
    assert all(item["status"] == "completed" for item in first.json()["items"])
    assert llm.calls == 1
    assert second.status_code == 200
    assert all(item["duplicate"] is True for item in second.json()["items"])
    assert llm.calls == 1


def test_ai_cache_key_reuses_same_context_but_not_different_publish_time() -> None:
    client, headers, llm = _client_with_llm()
    first = _item(1, "明晚记得带一下报名的东西")
    same_context = _item(2, "明晚记得带一下报名的东西")
    different_context = _item(3, "明晚记得带一下报名的东西")
    different_context["published_at"] = "2026-08-20T20:00:00+08:00"

    assert client.post("/api/v1/notices/ingest-batch", headers=headers, json={"items": [first]}).status_code == 200
    assert client.post("/api/v1/notices/ingest-batch", headers=headers, json={"items": [same_context]}).status_code == 200
    assert llm.calls == 1
    assert client.post("/api/v1/notices/ingest-batch", headers=headers, json={"items": [different_context]}).status_code == 200
    assert llm.calls == 2


def test_ai_cache_hit_preserves_semantic_type() -> None:
    client, headers, llm = _client_with_llm()
    first = client.post("/api/v1/notices/ingest-batch", headers=headers, json={
        "items": [_item(1, "明晚记得带一下报名的东西")]
    })
    cached = client.post("/api/v1/notices/ingest-batch", headers=headers, json={
        "items": [_item(2, "明晚记得带一下报名的东西")]
    })

    assert first.json()["items"][0]["semantic_type"] == "ACTIONABLE_NOTICE"
    assert cached.json()["items"][0]["semantic_type"] == "ACTIONABLE_NOTICE"
    assert cached.json()["items"][0]["status"] == "completed"
    assert llm.calls == 1


def test_twenty_message_cost_statistics() -> None:
    client, headers, _ = _client_with_llm()
    container = reset_container_for_tests(Settings(
        app_env="test", database_url="sqlite:///:memory:", auto_seed_demo_users=True,
        llm_provider="openai_compatible", llm_base_url="https://llm.invalid/v1",
        llm_api_key="test", llm_model="mock",
    ))
    seed_demo_data(container, force=True)
    llm = ExtractingBatchLLM()
    container.llm = llm
    container.notice_extraction = NoticeExtractionService(llm, container.settings)
    client = TestClient(create_app())
    login = client.post("/api/v1/auth/login", json={"username": "student_demo", "password": "Demo123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    chats = ["哈哈哈哈", "好的收到", "在吗", "晚上吃饭吗", "验证码123456"] * 2
    rules = [
        "请于8月20日17:00前提交实验报告", "明天下午三点参加班会", "今晚完成线上签到",
        "8月21日前填写奖学金申请", "周五前交报名表",
    ]
    ambiguous = [f"明晚记得带一下报名的东西{i}" for i in range(5)]
    payload = {"items": [_item(i, text) for i, text in enumerate(chats + rules + ambiguous)]}

    response = client.post("/api/v1/notices/ingest-batch", headers=headers, json=payload)

    assert response.status_code == 200
    assert response.json()["stats"] == {
        "received_count": 20, "duplicate_count": 0,
        "rule_chat_count": 10, "rule_notice_count": 0, "rule_task_count": 5,
        "ai_candidate_count": 5, "ai_batch_count": 1, "ai_cache_hit": 0,
    }
    assert sum(item["tasks_created"] for item in response.json()["items"]) == 10
    assert llm.calls == 1


def test_tasks_created_is_correct_when_first_task_page_is_full() -> None:
    client, headers, _ = _client_with_llm()
    container = get_container()
    user = container.user_repository.get_user_by_username("student_demo")
    assert user is not None
    for index in range(200):
        container.personal_task_repository.create_task(
            user_id=user.id,
            title=f"existing-{index}",
            source_notice_id=f"existing-notice-{index}",
        )

    response = client.post(
        "/api/v1/notices/ingest-batch",
        headers=headers,
        json={"items": [_item(999, "请于8月20日17:00前提交实验报告")]},
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["tasks_created"] == 1


@pytest.mark.anyio
async def test_concurrent_same_fingerprint_invokes_llm_once() -> None:
    client, headers, llm = _client_with_llm()
    llm.delay = 0.05
    payload = {"items": [_item(1, "明晚记得带一下报名的东西", "same-fingerprint-0001" * 2)]}

    import httpx
    transport = httpx.ASGITransport(app=client.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        first, second = await asyncio.gather(
            async_client.post("/api/v1/notices/ingest-batch", headers=headers, json=payload),
            async_client.post("/api/v1/notices/ingest-batch", headers=headers, json=payload),
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert llm.calls == 1
