import asyncio
from datetime import datetime, timezone
from typing import AsyncIterator, List

from app.core.config import Settings
from app.database.sqlite_db import reset_db_for_tests
from app.repositories.document_repository import DocumentRepository
from app.schemas.chat import ChatRequest
from app.services.emotion_context import EmotionContextBuilder
from app.services.llm.base import LLMResponse
from app.services.rag_service import RagService
from app.services.retrieval_service import RetrievalService


class CapturingLlm:
    def __init__(self) -> None:
        self.messages: List[dict] = []

    @property
    def name(self) -> str:
        return "capturing"

    @property
    def available(self) -> bool:
        return True

    async def chat(self, messages: List[dict], **kwargs) -> LLMResponse:
        self.messages = messages
        return LLMResponse(content="我在这里陪你，我们可以慢慢来。")

    async def stream_chat(self, messages: List[dict], **kwargs) -> AsyncIterator[str]:
        self.messages = messages
        if False:
            yield ""


def _request(timestamp: int, **overrides) -> ChatRequest:
    signal = {
        "label": "SAD",
        "confidence": 0.82,
        "is_stable": True,
        "timestamp": timestamp,
        "model_version": "resnet18-int8",
    }
    signal.update(overrides)
    return ChatRequest(message="你好", expression_signal=signal)


def test_builder_accepts_fresh_high_precision_sad_signal() -> None:
    now_ms = 1_800_000_000_000
    guidance, warning = EmotionContextBuilder(now_ms=lambda: now_ms).build(
        _request(now_ms - 800).expression_signal
    )

    assert warning is None
    assert guidance is not None
    assert guidance.label == "SAD"
    assert "先用一句明确但不武断的关怀表达" in guidance.prompt
    assert "别难过" in guidance.prompt


def test_builder_rejects_stale_or_low_precision_sad_signal() -> None:
    now_ms = 1_800_000_000_000
    builder = EmotionContextBuilder(now_ms=lambda: now_ms)

    stale, stale_warning = builder.build(_request(now_ms - 5_001).expression_signal)
    low, low_warning = builder.build(
        _request(now_ms - 500, confidence=0.67).expression_signal
    )

    assert stale is None
    assert "过期" in (stale_warning or "")
    assert low is None
    assert "置信度" in (low_warning or "")


def test_small_talk_receives_expression_guidance() -> None:
    llm = CapturingLlm()
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        llm_provider="openai_compatible",
        llm_base_url="http://localhost",
        llm_api_key="test-key",
        llm_model="test-model",
    )
    repository = DocumentRepository(reset_db_for_tests())
    rag = RagService(RetrievalService(repository), llm, settings, repository)
    hint = "[可见表情辅助] 先用一句明确但不武断的关怀表达，例如：别难过。"

    async def collect() -> list:
        return [event async for event in rag.stream_answer("你好", expression_hint=hint)]

    events = asyncio.run(collect())

    assert events[-1].answer
    assert hint in llm.messages[-1]["content"]


def test_schema_rejects_out_of_range_expression_confidence() -> None:
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    try:
        _request(now_ms, confidence=1.2)
    except ValueError:
        return
    raise AssertionError("confidence above 1.0 must be rejected")
