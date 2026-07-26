"""LLM Stub 客户端测试。"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

os.environ.setdefault("LLM_PROVIDER", "none")


def test_llm_stub_chat():
    from app.services.llm.openai_compatible import StubLLMClient
    stub = StubLLMClient(response_text="hello world", chunk_size=4)
    resp = asyncio.run(stub.chat([{"role": "user", "content": "hi"}]))
    assert resp.content == "hello world"
    assert stub.calls  # 记录了调用


def test_llm_stub_stream():
    from app.services.llm.openai_compatible import StubLLMClient
    stub = StubLLMClient(response_text="abcdefg", chunk_size=2)

    async def collect():
        chunks = []
        async for c in stub.stream_chat([{"role": "user", "content": "hi"}]):
            chunks.append(c)
        return chunks

    chunks = asyncio.run(collect())
    assert "".join(chunks) == "abcdefg"


def test_build_llm_client_returns_none_when_not_configured():
    from app.core.config import get_settings
    from app.services.llm.fallback import build_llm_client
    get_settings.cache_clear()
    s = get_settings()  # LLM_PROVIDER=none
    assert s.llm_available is False
    client = build_llm_client(s)
    assert client is None


def test_rag_with_stub_llm(monkeypatch):
    """注入 stub LLM 后，RAG 应走 LLM 路径。"""
    from app.core.config import get_settings
    get_settings.cache_clear()
    settings = get_settings()
    # 强制启用 LLM 配置(便于走 LLM 分支)
    monkeypatch.setattr(settings, "llm_provider", "openai_compatible")
    monkeypatch.setattr(settings, "llm_base_url", "http://stub/v1")
    monkeypatch.setattr(settings, "llm_api_key", "stub_key")
    monkeypatch.setattr(settings, "llm_model", "stub-model")
    # llm_available 是 property，依赖以上字段
    assert settings.llm_available is True

    from app.services.container import reset_container_for_tests
    from app.services.llm.openai_compatible import StubLLMClient
    container = reset_container_for_tests(settings)
    # 替换 llm 为 stub
    stub = StubLLMClient(
        response_text="根据《社会实践学分申请指南》，需在 7 月 30 日前提交材料。"
    )
    container.rag._llm = stub
    container.notice_extraction._llm = stub
    container.llm = stub
    container.knowledge_ingestion.import_demo_documents()
    container.retrieval.rebuild()

    final = asyncio.run(container.rag.answer("实践学分截止时间？"))
    assert final.mode == "llm"
    assert len(final.sources) >= 1
    assert "材料" in final.answer or "实践" in final.answer
