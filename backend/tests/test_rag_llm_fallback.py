"""测试 RagService 在 LLM 流式失败时的非流式兜底逻辑。"""

import asyncio
from typing import AsyncIterator, List

from app.core.config import Settings
from app.database.sqlite_db import reset_db_for_tests
from app.repositories.document_repository import DocumentRepository
from app.services.knowledge_ingestion_service import KnowledgeIngestionService
from app.services.llm.base import LLMResponse, LLMTimeoutError
from app.services.rag_service import RagService
from app.services.retrieval_service import RetrievalService


class FlakyStreamLLM:
    """流式失败、非流式可用的测试 LLM。"""

    def __init__(
        self,
        *,
        stream_error: bool = True,
        chat_answer: str = "根据《校级奖学金申请办法》，需要满足申请条件。",
    ) -> None:
        self.stream_error = stream_error
        self.chat_answer = chat_answer
        self.chat_calls = 0

    @property
    def name(self) -> str:
        return "flaky-stream"

    @property
    def available(self) -> bool:
        return True

    async def chat(self, messages: List[dict], **kwargs) -> LLMResponse:
        self.chat_calls += 1
        return LLMResponse(content=self.chat_answer)

    async def stream_chat(self, messages: List[dict], **kwargs) -> AsyncIterator[str]:
        if self.stream_error:
            raise LLMTimeoutError("stream timeout")
        if False:
            yield ""


def _make_settings() -> Settings:
    return Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        llm_provider="openai_compatible",
        llm_base_url="http://localhost",
        llm_api_key="test-key",
        llm_model="test-model",
        enable_fallback_mode=True,
    )


def _make_rag(llm: FlakyStreamLLM) -> RagService:
    settings = _make_settings()
    db = reset_db_for_tests()
    repo = DocumentRepository(db)
    retrieval = RetrievalService(repo)
    KnowledgeIngestionService(repo, retrieval, settings).import_demo_documents()
    retrieval.rebuild()
    return RagService(retrieval, llm, settings, repo)


def test_stream_failure_falls_back_to_chat() -> None:
    """流式超时后应调用非流式 chat()，最终仍返回 llm 模式。"""
    llm = FlakyStreamLLM()
    rag = _make_rag(llm)

    async def collect() -> list:
        return [event async for event in rag.stream_answer("奖学金申请条件")]

    events = asyncio.run(collect())
    final = events[-1]
    assert final.mode == "llm"
    assert final.answer == "根据《校级奖学金申请办法》，需要满足申请条件。"
    assert llm.chat_calls == 1


def test_empty_stream_falls_back_to_chat() -> None:
    """流式返回空内容时也应走非流式兜底。"""
    llm = FlakyStreamLLM(stream_error=False, chat_answer="非流式回复")
    rag = _make_rag(llm)

    async def collect() -> list:
        return [event async for event in rag.stream_answer("奖学金申请条件")]

    events = asyncio.run(collect())
    assert events[-1].mode == "llm"
    assert events[-1].answer == "非流式回复"
    assert llm.chat_calls == 1


def test_fallback_fails_uses_retrieval_summary() -> None:
    """流式与非流式都失败时应降级到检索摘要，而不是返回空答案。"""
    llm = FlakyStreamLLM(chat_answer="")
    rag = _make_rag(llm)

    async def collect() -> list:
        return [event async for event in rag.stream_answer("奖学金申请条件")]

    events = asyncio.run(collect())
    final = events[-1]
    assert final.mode == "retrieval_summary"
    assert final.answer
    assert llm.chat_calls == 1


def test_greeting_goes_through_llm() -> None:
    """纯问候语也应真实调用 LLM，而不是返回固定知识库文案。"""
    llm = FlakyStreamLLM(chat_answer="你好，我是小夏，有什么校园事务可以帮你？")
    rag = _make_rag(llm)

    async def collect() -> list:
        return [event async for event in rag.stream_answer("你好！")]

    events = asyncio.run(collect())
    final = events[-1]
    assert final.mode == "llm"
    assert final.sources == []
    assert final.answer == "你好，我是小夏，有什么校园事务可以帮你？"
    assert llm.chat_calls == 1


def test_no_sources_still_calls_llm() -> None:
    """知识库没有命中时也必须继续调用 LLM，不能提前返回拒答。"""
    llm = FlakyStreamLLM(chat_answer="这是 DeepSeek 对无知识库问题的回答。")
    rag = _make_rag(llm)
    rag._retrieval.search = lambda query, k=8: []  # type: ignore[method-assign]

    async def collect() -> list:
        return [event async for event in rag.stream_answer("一个知识库之外的问题")]

    events = asyncio.run(collect())
    final = events[-1]
    assert final.mode == "llm"
    assert final.sources == []
    assert final.answer == "这是 DeepSeek 对无知识库问题的回答。"
    assert llm.chat_calls == 1
