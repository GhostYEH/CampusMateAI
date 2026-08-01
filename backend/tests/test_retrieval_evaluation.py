"""测试检索评测脚本 (scripts/evaluate_retrieval.py) 的核心逻辑。

验证 EvalCase 解析、evaluate_one / compute_metrics 等函数。
"""
import json
import tempfile
from pathlib import Path

import pytest

from app.models.document import ChunkRow, DocumentRow, RetrievedChunk
from scripts.evaluate_retrieval import (
    EvalCase,
    EvalResult,
    compute_metrics,
    evaluate_one,
    load_fixtures,
    _title_match,
)


# ---------- helpers ----------

def _make_chunk(title: str, doc_id: str = "", content: str = "") -> RetrievedChunk:
    """构造测试用 RetrievedChunk。"""
    did = doc_id or f"doc-{title}"
    doc = DocumentRow(
        document_id=did,
        title=title,
        source_type="demo",
        source_department="测试",
        original_filename=f"{title}.md",
        is_official=True,
    )
    chunk = ChunkRow(
        chunk_id=f"{did}-chunk-0",
        document_id=did,
        section=None,
        position=0,
        content=content or f"这是 {title} 的正文内容。",
    )
    return RetrievedChunk(document=doc, chunk=chunk, score=2.5)


# ---------- _title_match ----------


def test_title_match_exact():
    assert _title_match("社会实践学分申请指南", "社会实践学分申请指南") is True


def test_title_match_substring():
    assert _title_match("校级奖学金申请办法(2025版)", "校级奖学金申请办法") is True
    assert _title_match("校级奖学金申请办法", "校级奖学金申请办法(2025版)") is True


def test_title_match_no_match():
    assert _title_match("课程补退选流程", "奖学金申请办法") is False


def test_title_match_empty():
    assert _title_match("", "something") is False
    assert _title_match("something", "") is False


# ---------- load_fixtures ----------


def test_load_fixtures_from_json():
    """从 JSON 加载 fixtures。"""
    data = {
        "fixtures": [
            {
                "id": "test-1",
                "category": "test",
                "query": "测试问题",
                "expected_titles": ["测试文档"],
                "expected_document_ids": ["doc-001"],
                "should_answer": True,
                "expected_mode": "retrieval_summary",
                "notes": "测试样例",
            }
        ]
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(data, f)
        tmp_path = Path(f.name)

    try:
        cases = load_fixtures(tmp_path)
        assert len(cases) == 1
        case = cases[0]
        assert case.case_id == "test-1"
        assert case.query == "测试问题"
        assert case.expected_titles == ["测试文档"]
        assert case.expected_document_ids == ["doc-001"]
        assert case.should_answer is True
    finally:
        tmp_path.unlink(missing_ok=True)


def test_load_fixtures_empty():
    """空 fixtures 列表。"""
    data = {"fixtures": []}
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(data, f)
        tmp_path = Path(f.name)

    try:
        cases = load_fixtures(tmp_path)
        assert cases == []
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------- evaluate_one ----------


def test_evaluate_hit_at_1():
    """第一个结果命中。"""
    case = EvalCase(
        case_id="e1", category="test", query="q",
        expected_titles=["社会实践学分申请指南"],
        expected_document_ids=[], should_answer=True,
        expected_mode="retrieval_summary", notes="",
    )
    retrieved = [_make_chunk("社会实践学分申请指南")]
    result = evaluate_one(case, retrieved)
    assert result.hit_at_1 is True
    assert result.hit_at_3 is True
    assert result.reciprocal_rank == 1.0
    assert result.failure_reasons == []


def test_evaluate_hit_at_3():
    """第 3 个结果命中。"""
    case = EvalCase(
        case_id="e2", category="test", query="q",
        expected_titles=["课程补退选流程"],
        expected_document_ids=[], should_answer=True,
        expected_mode="retrieval_summary", notes="",
    )
    retrieved = [
        _make_chunk("社会实践学分申请指南"),
        _make_chunk("综合测评材料说明"),
        _make_chunk("课程补退选流程"),
    ]
    result = evaluate_one(case, retrieved)
    assert result.hit_at_1 is False
    assert result.hit_at_3 is True
    assert result.reciprocal_rank == 1.0 / 3


def test_evaluate_no_hit():
    """未命中期望文档。"""
    case = EvalCase(
        case_id="e3", category="test", query="q",
        expected_titles=["校级奖学金申请办法"],
        expected_document_ids=[], should_answer=True,
        expected_mode="retrieval_summary", notes="",
    )
    retrieved = [_make_chunk("课程补退选流程"), _make_chunk("活动报名常见问题")]
    result = evaluate_one(case, retrieved)
    assert result.hit_at_1 is False
    assert result.hit_at_3 is False
    assert result.reciprocal_rank == 0.0
    assert len(result.failure_reasons) > 0


def test_evaluate_should_reject_correctly():
    """应拒答且检索为空时正确拒答。"""
    case = EvalCase(
        case_id="e4", category="test", query="q",
        expected_titles=[], expected_document_ids=[],
        should_answer=False, expected_mode="reject", notes="",
    )
    result = evaluate_one(case, [])
    assert result.correctly_rejected is True
    assert result.failure_reasons == []


def test_evaluate_should_reject_but_found():
    """应拒答但仍返回结果时标记错误接受。"""
    case = EvalCase(
        case_id="e5", category="test", query="q",
        expected_titles=[], expected_document_ids=[],
        should_answer=False, expected_mode="reject", notes="",
    )
    result = evaluate_one(case, [_make_chunk("无关文档")])
    assert result.correctly_rejected is False
    assert len(result.failure_reasons) > 0


def test_evaluate_empty_retrieval_with_answerable():
    """应有答案但检索为空。"""
    case = EvalCase(
        case_id="e6", category="test", query="q",
        expected_titles=["某文档"], expected_document_ids=[],
        should_answer=True, expected_mode="retrieval_summary", notes="",
    )
    result = evaluate_one(case, [])
    assert result.failure_reasons == ["应当有答案,但检索结果为空"]


# ---------- compute_metrics ----------


def test_compute_metrics_all_hit():
    """全部命中时指标为 100%。"""
    cases = [
        EvalCase("t1", "", "q1", ["A"], [], True, "", ""),
        EvalCase("t2", "", "q2", ["B"], [], True, "", ""),
    ]
    results = [
        EvalResult(cases[0], hit_at_1=True, hit_at_3=True, reciprocal_rank=1.0),
        EvalResult(cases[1], hit_at_1=True, hit_at_3=True, reciprocal_rank=1.0),
    ]
    metrics = compute_metrics(results)
    assert metrics["total"] == 2
    assert metrics["hit_at_1_rate"] == 1.0
    assert metrics["hit_at_3_rate"] == 1.0
    assert metrics["mrr"] == 1.0
    assert metrics["failures"] == []


def test_compute_metrics_with_rejections():
    """包含拒答样例的指标计算。"""
    cases = [
        EvalCase("t1", "", "q1", ["A"], [], True, "", ""),
        EvalCase("t2", "", "q2", [], [], False, "reject", ""),
    ]
    results = [
        EvalResult(cases[0], hit_at_1=True, hit_at_3=True, reciprocal_rank=1.0),
        EvalResult(cases[1], correctly_rejected=True),
    ]
    metrics = compute_metrics(results)
    assert metrics["total"] == 2
    assert metrics["answerable_count"] == 1
    assert metrics["rejectable_count"] == 1
    assert metrics["correct_rejection_rate"] == 1.0
    assert metrics["false_acceptance_rate"] == 0.0


def test_compute_metrics_empty():
    """空结果集。"""
    metrics = compute_metrics([])
    assert metrics == {"total": 0}
