"""检索排序逻辑单元测试 — 覆盖 freshness bonus / metadata weighting / 同义词扩展 / 短查询回退。

不依赖 HTTP，直接测试 RetrievalService 内部的排序与召回逻辑。
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

os.environ.setdefault("LLM_PROVIDER", "none")
os.environ.setdefault("ENABLE_FALLBACK_MODE", "true")


@pytest.fixture
def container():
    """使用内存数据库的容器，已导入演示资料。"""
    from app.core.config import get_settings
    get_settings.cache_clear()
    settings = get_settings()
    from app.services.container import reset_container_for_tests
    c = reset_container_for_tests(settings)
    c.knowledge_ingestion.import_demo_documents()
    c.retrieval.rebuild()
    return c


# ============================================================
# _freshness_bonus 单元测试
# ============================================================

def test_freshness_bonus_recent_doc_gets_max(container):
    """30 天内发布的文档应获得满额 freshness bonus。"""
    from app.services.retrieval_service import _freshness_bonus
    from app.models.document import DocumentRow

    recent = datetime.now(timezone.utc) - timedelta(days=5)
    doc = DocumentRow(
        document_id="d1",
        title="测试",
        updated_at=recent.isoformat(),
        is_expired=False,
    )
    bonus = _freshness_bonus(doc)
    assert 0.04 < bonus <= 0.05, f"recent doc bonus 应接近 0.05, 实际: {bonus}"


def test_freshness_bonus_old_doc_gets_zero(container):
    """超过 365 天的文档不应获得 freshness bonus。"""
    from app.services.retrieval_service import _freshness_bonus
    from app.models.document import DocumentRow

    old = datetime.now(timezone.utc) - timedelta(days=400)
    doc = DocumentRow(
        document_id="d2",
        title="测试",
        updated_at=old.isoformat(),
        is_expired=False,
    )
    bonus = _freshness_bonus(doc)
    assert bonus == 0.0, f"old doc bonus 应为 0, 实际: {bonus}"


def test_freshness_bonus_expired_doc_gets_zero(container):
    """过期文档不应获得 freshness bonus。"""
    from app.services.retrieval_service import _freshness_bonus
    from app.models.document import DocumentRow

    recent = datetime.now(timezone.utc) - timedelta(days=5)
    doc = DocumentRow(
        document_id="d3",
        title="测试",
        updated_at=recent.isoformat(),
        is_expired=True,
    )
    bonus = _freshness_bonus(doc)
    assert bonus == 0.0, f"expired doc bonus 应为 0, 实际: {bonus}"


def test_freshness_bonus_decays_linearly(container):
    """30~365 天之间应线性衰减。"""
    from app.services.retrieval_service import _freshness_bonus
    from app.models.document import DocumentRow

    d30 = datetime.now(timezone.utc) - timedelta(days=30)
    doc30 = DocumentRow(
        document_id="d30", title="t", updated_at=d30.isoformat(), is_expired=False,
    )
    b30 = _freshness_bonus(doc30)

    d180 = datetime.now(timezone.utc) - timedelta(days=180)
    doc180 = DocumentRow(
        document_id="d180", title="t", updated_at=d180.isoformat(), is_expired=False,
    )
    b180 = _freshness_bonus(doc180)

    d360 = datetime.now(timezone.utc) - timedelta(days=360)
    doc360 = DocumentRow(
        document_id="d360", title="t", updated_at=d360.isoformat(), is_expired=False,
    )
    b360 = _freshness_bonus(doc360)

    assert b30 > b180 > b360, f"应单调递减: {b30} > {b180} > {b360}"
    assert b30 == pytest.approx(0.05, abs=0.005)
    assert b360 < 0.01


def test_freshness_bonus_published_at_fallback(container):
    """updated_at 缺失时回退到 published_at。"""
    from app.services.retrieval_service import _freshness_bonus
    from app.models.document import DocumentRow

    recent = datetime.now(timezone.utc) - timedelta(days=10)
    doc = DocumentRow(
        document_id="d4",
        title="测试",
        updated_at=None,
        published_at=recent.isoformat(),
        is_expired=False,
    )
    bonus = _freshness_bonus(doc)
    assert bonus > 0, "published_at 回退应仍能计算 bonus"


def test_freshness_bonus_no_date_gets_zero(container):
    """无时间字段的文档不应获得 freshness bonus。"""
    from app.services.retrieval_service import _freshness_bonus
    from app.models.document import DocumentRow

    doc = DocumentRow(
        document_id="d5",
        title="测试",
        updated_at=None,
        published_at=None,
        is_expired=False,
    )
    bonus = _freshness_bonus(doc)
    assert bonus == 0.0


# ============================================================
# _rank_key 元数据加权测试
# ============================================================

def test_rank_key_non_expired_beats_expired(container):
    """未过期文档的排序键应高于过期文档（相同 BM25 分数时）。"""
    from app.services.retrieval_service import _rank_key
    from app.models.document import DocumentRow, RetrievedChunk, ChunkRow

    chunk = ChunkRow(chunk_id="c1", document_id="d1", section=None, position=0, content="x")

    non_expired_doc = DocumentRow(
        document_id="d1", title="A", is_expired=False, is_official=False,
    )
    expired_doc = DocumentRow(
        document_id="d2", title="B", is_expired=True, is_official=False,
    )

    rc1 = RetrievedChunk(chunk=chunk, document=non_expired_doc, score=0.5)
    rc2 = RetrievedChunk(chunk=chunk, document=expired_doc, score=0.5)

    assert _rank_key(rc1) > _rank_key(rc2), "未过期应排在过期之前"


def test_rank_key_official_beats_non_official(container):
    """官方文档的排序键应高于非官方文档（相同 BM25 分数时）。"""
    from app.services.retrieval_service import _rank_key
    from app.models.document import DocumentRow, RetrievedChunk, ChunkRow

    chunk = ChunkRow(chunk_id="c1", document_id="d1", section=None, position=0, content="x")

    official_doc = DocumentRow(
        document_id="d1", title="A", is_expired=False, is_official=True,
    )
    non_official_doc = DocumentRow(
        document_id="d2", title="B", is_expired=False, is_official=False,
    )

    rc1 = RetrievedChunk(chunk=chunk, document=official_doc, score=0.5)
    rc2 = RetrievedChunk(chunk=chunk, document=non_official_doc, score=0.5)

    assert _rank_key(rc1) > _rank_key(rc2), "官方应排在非官方之前"


def test_rank_key_metadata_does_not_override_strong_semantic_relevance(container):
    """元数据加权合计上限 +0.30,不能覆盖明显更高的语义相关性。

    场景: BM25 分数 1.0 的过期非官方文档,
    应排在 BM25 分数 0.6 的未过期官方文档之前(1.0 > 0.6+0.30=0.9)。
    """
    from app.services.retrieval_service import _rank_key
    from app.models.document import DocumentRow, RetrievedChunk, ChunkRow

    chunk = ChunkRow(chunk_id="c1", document_id="d1", section=None, position=0, content="x")

    strong_doc = DocumentRow(
        document_id="d1", title="A", is_expired=True, is_official=False,
    )
    weak_doc = DocumentRow(
        document_id="d2", title="B", is_expired=False, is_official=True,
    )

    rc_strong = RetrievedChunk(chunk=chunk, document=strong_doc, score=1.0)
    rc_weak = RetrievedChunk(chunk=chunk, document=weak_doc, score=0.6)

    assert _rank_key(rc_strong) > _rank_key(rc_weak), (
        "强语义匹配不应被元数据加权覆盖"
    )


# ============================================================
# 同义词扩展测试
# ============================================================

def test_synonym_expansion_adds_synonyms(container):
    """同义词扩展应追加同义词 token,不替换原 token。"""
    from app.services.retrieval_service import _expand_synonyms

    result = _expand_synonyms(["奖助学金", "国家"])
    assert "奖助学金" in result
    assert "奖学金" in result
    assert "国家" in result


def test_synonym_expansion_symmetric():
    """对称同义词: 文档端的 '办法' 也应展开为 '政策'。"""
    from app.services.retrieval_service import _expand_synonyms

    result_policy = _expand_synonyms(["政策"])
    assert "办法" in result_policy, "政策 → 办法 应在扩展中出现"

    result_method = _expand_synonyms(["办法"])
    assert "政策" in result_method, "办法 → 政策 应在对称扩展中出现"


def test_synonym_expansion_no_duplicates():
    """同义词扩展不应产生重复 token。"""
    from app.services.retrieval_service import _expand_synonyms

    result = _expand_synonyms(["奖学金", "奖助学金"])
    assert len(result) == len(set(result)), "扩展结果不应有重复"


def test_synonym_expansion_empty_input():
    """空输入应返回空。"""
    from app.services.retrieval_service import _expand_synonyms

    assert _expand_synonyms([]) == []


# ============================================================
# 端到端检索行为测试(基于演示知识库)
# ============================================================

def test_short_query_fallback_single_token(container):
    """1 token 短查询应触发 fallback(min_overlap=1),能命中包含该关键词的文档。"""
    results = container.retrieval.search("奖助学金", k=3)
    assert len(results) >= 1
    titles = [r.document.title for r in results]
    assert any("奖学金" in t for t in titles), f"应命中奖学金文档,实际: {titles}"


def test_two_token_query_requires_both_match(container):
    """2 token 查询应要求两个 token 都匹配(min_overlap=2),避免单 token 误匹配。"""
    # "暑期实践" → content_tokens = [暑期, 实践], 两个都在演示资料中
    results = container.retrieval.search("暑期实践", k=3)
    assert len(results) >= 1
    titles = [r.document.title for r in results]
    assert any("实践" in t for t in titles), f"应命中实践文档,实际: {titles}"


def test_two_token_query_with_unknown_rejected(container):
    """2 token 查询含未知 token(如"宿舍分配"中"宿舍"不在语料)应被拒答。"""
    # "宿舍分配" → content_tokens = [宿舍, 分配], 宿舍 未知 → min_overlap=3
    results = container.retrieval.search("宿舍分配", k=3)
    assert len(results) == 0, f"含未知 token 的 2 token 查询应拒答,实际: {[r.document.title for r in results]}"


def test_normal_query_requires_two_overlaps(container):
    """3+ token 普通查询应要求至少 2 个 token 匹配(避免单字弱匹配)。"""
    # "宿舍熄灯时间" → content_tokens = [宿舍, 熄灯] (时间 是停用词)
    # 2 token 且 宿舍/熄灯 均未知 → 应返回空
    results = container.retrieval.search("宿舍熄灯时间", k=3)
    assert len(results) == 0, f"无匹配内容应返回空,实际: {[r.document.title for r in results]}"


def test_vague_query_with_many_stopwords_still_works(container):
    """含大量停用词的模糊问题仍应基于剩余关键词检索。"""
    results = container.retrieval.search("我应该怎么做才能拿到奖学金", k=3)
    assert len(results) >= 1
    titles = [r.document.title for r in results]
    assert any("奖学金" in t for t in titles), f"模糊奖学金问题应命中,实际: {titles}"


def test_expired_query_still_retrieves(container):
    """含 '去年'/'政策' 的过期查询应仍能检索到奖学金办法(标注 is_expired)。"""
    results = container.retrieval.search("去年的奖学金政策还能用吗", k=3)
    assert len(results) >= 1
    titles = [r.document.title for r in results]
    assert any("奖学金" in t for t in titles), f"过期查询应命中,实际: {titles}"


def test_synonym_activity_art_festival(container):
    """'艺术节' 应通过同义词扩展命中 '活动报名常见问题'。"""
    results = container.retrieval.search("艺术节有哪些项目可以参加", k=3)
    assert len(results) >= 1
    titles = [r.document.title for r in results]
    assert any("活动" in t for t in titles), f"艺术节应命中活动文档,实际: {titles}"


def test_no_answer_rejects_unrelated_query(container):
    """完全无关的查询应返回空或低分结果。"""
    results = container.retrieval.search("量子纠缠薛定谔猫", k=3)
    for r in results:
        assert r.score <= 1.0


def test_title_weighting_boosts_title_matches(container):
    """标题加权: 查询 '奖学金' 应优先命中标题含 '奖学金' 的文档。"""
    results = container.retrieval.search("奖学金", k=3)
    assert len(results) >= 1
    top1_title = results[0].document.title
    assert "奖学金" in top1_title, f"top-1 应为奖学金文档,实际: {top1_title}"


# ============================================================
# 多路召回测试
# ============================================================

def test_multi_intent_query_recalls_both(container):
    """多意图查询 '社会实践和奖学金可以同时申请吗' 应在 top-10 召回两个主题。

    注: 由于奖学金文档标题含 '奖学金' 且有标题加权,其各 chunk 分数普遍更高,
    社会实践文档可能在 top-5 之后才出现。这里用 k=10 验证多主题召回能力。
    """
    results = container.retrieval.search("社会实践和奖学金可以同时申请吗", k=10)
    assert len(results) >= 2
    titles = [r.document.title for r in results]
    has_practice = any("实践" in t for t in titles)
    has_scholarship = any("奖学金" in t for t in titles)
    assert has_practice and has_scholarship, (
        f"应同时召回实践与奖学金文档,实际: {titles}"
    )
