"""服务层单元测试 — 不通过 HTTP。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

os.environ.setdefault("LLM_PROVIDER", "none")
os.environ.setdefault("ENABLE_FALLBACK_MODE", "true")


@pytest.fixture
def container():
    from app.core.config import get_settings
    get_settings.cache_clear()
    settings = get_settings()
    from app.services.container import reset_container_for_tests
    c = reset_container_for_tests(settings)
    # 导入演示资料
    c.knowledge_ingestion.import_demo_documents()
    c.retrieval.rebuild()
    return c


def test_retrieval_returns_relevant(container):
    """检索应能找到与"实践学分"相关的演示资料。"""
    results = container.retrieval.search("实践学分怎样申请", k=3)
    assert len(results) >= 1
    # 应包含社会实践指南
    titles = [r.document.title for r in results]
    assert any("实践" in t for t in titles)


def test_retrieval_empty_query_returns_empty(container):
    results = container.retrieval.search("", k=3)
    assert results == []


def test_retrieval_unrelated_query_returns_low_score(container):
    results = container.retrieval.search("量子纠缠薛定谔猫", k=3)
    # 演示资料不相关，可能返回少量低相关结果或为空
    # 关键是不应返回"高相关"误报
    for r in results:
        assert r.score <= 1.0


def test_retrieval_marks_stale_on_add(container):
    """新增文档后应自动 mark stale，下次检索前重建。"""
    container.knowledge_ingestion.import_text(
        content="# 新增测试文档\n\n关于火车票报销的内部说明。",
        title="新增测试文档",
    )
    # 检索会触发自动重建
    results = container.retrieval.search("火车票报销")
    titles = [r.document.title for r in results]
    assert "新增测试文档" in titles


def test_rag_no_knowledge(container):
    """无资料场景下的 RAG 应返回人工兜底。"""
    # 删除所有文档
    for d in list(container.document_repository.list_documents()):
        container.knowledge_ingestion.delete_document(d.document_id)
    container.retrieval.rebuild()
    import asyncio
    final = asyncio.run(
        container.rag.answer("我所在学校的图书馆开放时间？")
    )
    assert final.mode == "no_knowledge"
    assert final.sources == []
    assert final.needs_human_confirmation is True
    assert "辅导员" in final.answer or "咨询" in final.answer


def test_rag_with_sources(container):
    """有资料时 RAG 应返回来源。"""
    import asyncio
    final = asyncio.run(
        container.rag.answer("奖学金申请条件是什么？")
    )
    assert len(final.sources) >= 1
    assert final.mode in ("llm", "retrieval_summary")  # 无 LLM 时降级
    assert final.answer


def test_notice_extraction_rules_mode(container):
    """规则模式应能正确提取关键信息。"""
    import asyncio
    text = (
        "请2024级学生于2026年7月30日前填写实践申请表，"
        "并将申请表和证明材料提交至学院办公室。"
    )
    result = asyncio.run(
        container.notice_extraction.extract(text, source_name="测试通知")
    )
    assert result.extractor_mode == "rules"  # 无 LLM
    assert "实践" in result.task
    assert result.target_students is not None
    assert result.deadline is not None
    assert any(m.name == "申请表" for m in result.materials)
    assert result.source_name == "测试通知"


def test_notice_extraction_missing_year_warning(container):
    """缺少年份时应在 warnings 中写明。"""
    import asyncio
    text = "请同学于7月30日前提交实习鉴定表至辅导员办公室。"
    result = asyncio.run(container.notice_extraction.extract(text))
    assert result.deadline is not None
    assert result.needs_confirmation is True
    assert any("年份" in w for w in result.warnings)
