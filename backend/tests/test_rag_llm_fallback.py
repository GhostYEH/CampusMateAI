"""测试 RagService 在 LLM 流式失败时的非流式兜底逻辑。"""

import asyncio
from typing import AsyncIterator, List

import pytest

from app.core.config import Settings
from app.database.sqlite_db import Database
from app.models.document import ChunkRow, DocumentRow, RetrievedChunk
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
        stream_chunks: tuple[str, ...] = (),
    ) -> None:
        self.stream_error = stream_error
        self.chat_answer = chat_answer
        self.stream_chunks = stream_chunks
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
        for chunk in self.stream_chunks:
            yield chunk
        if self.stream_error:
            raise LLMTimeoutError("stream timeout")


def _make_settings() -> Settings:
    return Settings(
        _env_file=None,
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


def _collect(rag: RagService, query: str, **kwargs) -> list:
    async def run() -> list:
        return [event async for event in rag.stream_answer(query, **kwargs)]

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


@pytest.mark.parametrize("query", ["奖学金怎么申请", "你好！"])
@pytest.mark.parametrize("stream_error", [False, True])
def test_nonempty_stream_keeps_buffered_answer_without_chat_retry(query, stream_error) -> None:
    llm = FlakyStreamLLM(stream_error=stream_error, stream_chunks=("第一段", "第二段"))
    events = _collect(_make_rag(llm), query)

    assert events[-1].answer == "第一段第二段"
    assert events[-1].mode == "llm"
    assert any(event.answer == "第一段" for event in events)
    assert llm.chat_calls == 0


@pytest.mark.parametrize("stream_error", [False, True])
@pytest.mark.parametrize("chat_answer", ["非流式回复", ""])
def test_knowledge_events_preserve_sources_and_context_on_fallback(
    monkeypatch, stream_error, chat_answer
) -> None:
    rag = _make_rag(FlakyStreamLLM(stream_error=stream_error, chat_answer=chat_answer))
    document = DocumentRow(document_id="policy", title="奖学金申请通知", is_expired=True)
    chunk = ChunkRow(
        chunk_id="policy-chunk", document_id="policy", section="材料", position=0,
        content="申请奖学金需要提交成绩单。",
    )
    monkeypatch.setattr(
        rag, "_retrieve_context",
        lambda query: [RetrievedChunk(chunk=chunk, document=document, score=0.8)],
    )
    context_used = {"recent_tasks_accepted_count": 1}
    context_warnings = ["一个待办不存在"]
    events = _collect(
        rag, "奖学金怎么申请", conversation_id="conversation-test",
        context_used=context_used, context_warnings=context_warnings,
    )

    assert events[0].answer == ""
    assert events[0].mode == "llm"
    assert events[-1].mode == ("llm" if chat_answer else "retrieval_summary")
    metadata = events[0].model_dump(exclude={"answer", "mode", "warnings"})
    assert metadata["sources"][0]["document_id"] == "policy"
    assert metadata["conversation_id"] == "conversation-test"
    assert metadata["context_used"] == context_used
    assert metadata["context_warnings"] == context_warnings
    for event in events:
        assert event.model_dump(exclude={"answer", "mode", "warnings"}) == metadata
        expected_warnings = list(events[0].warnings)
        if event.mode == "retrieval_summary":
            expected_warnings.append("LLM 不可用，当前为检索摘要模式")
        assert event.warnings == expected_warnings


def test_greeting_uses_fixed_fallback_after_empty_chat_with_context() -> None:
    events = _collect(
        _make_rag(FlakyStreamLLM(chat_answer="")), "你好！",
        conversation_id="greeting-test", context_used={"self_report_present": True},
        context_warnings=["一个待办不存在"],
    )

    assert len(events) == 1
    assert events[0].answer
    assert events[0].mode == "chat"
    assert events[0].sources == []
    assert events[0].warnings == []
    assert events[0].conversation_id == "greeting-test"
    assert events[0].context_used == {"self_report_present": True}
    assert events[0].context_warnings == ["一个待办不存在"]
