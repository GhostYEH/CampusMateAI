"""测试 RagService 在 LLM 流式失败时的非流式兜底逻辑。"""

import asyncio
from typing import AsyncIterator, List

from app.core.config import Settings
from app.database.sqlite_db import Database
from app.repositories.document_repository import DocumentRepository
from app.services.llm.base import LLMResponse, LLMTimeoutError
from app.services.rag_service import RagService
from app.services.retrieval_service import RetrievalService


class FlakyStreamLLM:
    """流式失败、非流式可用的测试 LLM。"""

    def __init__(
        self,
        *,
        stream_error: bool = True,
        chat_answer: str = "非流式兜底回复。",
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
    repository = DocumentRepository(Database(None))
    retrieval = RetrievalService(repository)
    retrieval.rebuild()
    return RagService(retrieval, llm, _make_settings(), repository)


def _collect(rag: RagService, query: str) -> list:
    async def run() -> list:
        return [event async for event in rag.stream_answer(query)]

    return asyncio.run(run())


def test_stream_failure_falls_back_to_chat() -> None:
    """流式超时后应调用非流式 chat()，最终仍返回 llm 模式。"""
    llm = FlakyStreamLLM()
    rag = _make_rag(llm)

    events = _collect(rag, "今天有什么待办")
    final = events[-1]
    assert final.mode == "llm"
    assert final.answer == "非流式兜底回复。"
    assert llm.chat_calls == 1


def test_empty_stream_falls_back_to_chat() -> None:
    """流式返回空内容时也应走非流式兜底。"""
    llm = FlakyStreamLLM(stream_error=False, chat_answer="非流式回复")
    rag = _make_rag(llm)

    events = _collect(rag, "今天有什么待办")
    assert events[-1].mode == "llm"
    assert events[-1].answer == "非流式回复"
    assert llm.chat_calls == 1


def test_fallback_fails_returns_retrieval_summary() -> None:
    """流式与非流式都失败时返回明确的知识库检索摘要。"""
    llm = FlakyStreamLLM(chat_answer="")
    rag = _make_rag(llm)

    events = _collect(rag, "今天有什么待办")
    final = events[-1]
    assert final.mode == "retrieval_summary"
    assert "当前知识库中没有找到" in final.answer
    assert final.sources == []
    assert llm.chat_calls == 1


def test_llm_unavailable_returns_retrieval_summary() -> None:
    """LLM 未配置时返回知识库检索摘要。"""
    repository = DocumentRepository(Database(None))
    retrieval = RetrievalService(repository)
    retrieval.rebuild()
    rag = RagService(retrieval, None, _make_settings(), repository)

    events = _collect(rag, "今天有什么待办")
    final = events[-1]
    assert final.mode == "retrieval_summary"
    assert "当前知识库中没有找到" in final.answer
    assert final.sources == []


def test_greeting_goes_through_llm() -> None:
    """纯问候语也应真实调用 LLM，而不是返回固定文案。"""
    llm = FlakyStreamLLM(chat_answer="你好，我是小夏，有什么校园事务可以帮你？")
    rag = _make_rag(llm)

    events = _collect(rag, "你好！")
    final = events[-1]
    assert final.mode == "llm"
    assert final.sources == []
    assert final.answer == "你好，我是小夏，有什么校园事务可以帮你？"
    assert llm.chat_calls == 1


def test_no_knowledge_still_calls_llm() -> None:
    """知识库没有命中时仍调用 LLM，由系统提示约束其不能编造政策。"""
    llm = FlakyStreamLLM(chat_answer="这是模型对普通问题的回答。")
    rag = _make_rag(llm)

    events = _collect(rag, "一个随便的问题")
    final = events[-1]
    assert final.mode == "llm"
    assert final.sources == []
    assert final.answer == "这是模型对普通问题的回答。"
    assert llm.chat_calls == 1
