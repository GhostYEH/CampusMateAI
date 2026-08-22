from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app.core.config import Settings
from app.services.llm.base import LLMResponse
from app.services.notice_extraction_service import NoticeExtractionService, NoticeSemanticType


class CountingLLM:
    name = "mock:model"
    available = True

    def __init__(self, response: dict | str) -> None:
        self.response = response
        self.calls = 0

    async def chat(self, messages, **kwargs):
        self.calls += 1
        content = self.response if isinstance(self.response, str) else json.dumps(self.response, ensure_ascii=False)
        return LLMResponse(content=content)


def _settings() -> Settings:
    return Settings(
        app_env="test",
        llm_provider="openai_compatible",
        llm_base_url="https://llm.invalid/v1",
        llm_api_key="test",
        llm_model="mock",
    )


def test_chat_and_clear_rule_notices_need_zero_llm_calls() -> None:
    llm = CountingLLM({"results": []})
    service = NoticeExtractionService(llm, _settings())

    chats = ["哈哈哈哈", "好的收到", "在吗", "晚上吃饭吗", "验证码123456"] * 2
    rules = [
        "请于8月20日17:00前提交实验报告",
        "明天下午三点参加班会",
        "今晚完成线上签到",
        "8月21日前填写奖学金申请",
        "周五前交报名表",
    ]

    assert all(service.classify_semantics(text) is NoticeSemanticType.CHAT for text in chats)
    assert all(service.classify_semantics(text) is NoticeSemanticType.ACTIONABLE_NOTICE for text in rules)
    assert llm.calls == 0


@pytest.mark.anyio
async def test_five_ambiguous_items_are_one_structured_llm_call() -> None:
    response = {
        "results": [
            {"id": str(i), "type": "ACTIONABLE_NOTICE", "tasks": []}
            for i in range(5)
        ]
    }
    llm = CountingLLM(response)
    service = NoticeExtractionService(llm, _settings())
    items = [
        {"id": str(i), "content": f"明晚记得带一下报名的东西{i}", "source_name": "软件工程1班", "published_at": datetime.now(timezone.utc)}
        for i in range(5)
    ]

    results = await service.extract_ambiguous_batch(items)

    assert len(results) == 5
    assert llm.calls == 1


@pytest.mark.anyio
async def test_malformed_llm_json_falls_back_without_item_retries() -> None:
    llm = CountingLLM("not-json")
    service = NoticeExtractionService(llm, _settings())

    results = await service.extract_ambiguous_batch([
        {"id": "A", "content": "明晚记得带一下报名的东西", "source_name": "班群", "published_at": None}
    ])

    assert results[0].type is NoticeSemanticType.AMBIGUOUS
    assert results[0].needs_confirmation is True
    assert llm.calls == 1
