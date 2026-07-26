"""检索评测脚本测试 — 确保评测脚本可运行且 fixtures 格式正确。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# 把 scripts 路径加进来
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


FIXTURES_PATH = _BACKEND_ROOT / "tests" / "fixtures" / "retrieval_evaluation.json"


def test_fixtures_file_exists():
    """fixtures 文件应存在。"""
    assert FIXTURES_PATH.exists(), f"fixtures 文件不存在: {FIXTURES_PATH}"


def test_fixtures_have_at_least_25_cases():
    """fixtures 应包含至少 25 个评测样例。"""
    with FIXTURES_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    cases = data.get("fixtures", [])
    assert len(cases) >= 25, f"评测样例不足 25 个: {len(cases)}"


def test_fixtures_cover_required_categories():
    """fixtures 应覆盖必需的评测类别。"""
    with FIXTURES_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    cases = data.get("fixtures", [])
    categories = {c.get("category", "") for c in cases}
    required = {
        "社会实践", "综合测评", "奖学金", "课程补退选", "活动报名",
        "办理地点", "同义表达", "短问题", "模糊问题", "无答案问题",
        "冲突资料", "过期资料", "Prompt Injection",
    }
    missing = required - categories
    assert not missing, f"缺少类别: {missing}"


def test_fixtures_have_no_answer_cases():
    """fixtures 应包含 should_answer=false 的拒答样例。"""
    with FIXTURES_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    cases = data.get("fixtures", [])
    rejectable = [c for c in cases if not c.get("should_answer", True)]
    assert len(rejectable) >= 3, f"拒答样例不足 3 个: {len(rejectable)}"


def test_fixtures_have_prompt_injection_cases():
    """fixtures 应包含 Prompt Injection 样例。"""
    with FIXTURES_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    cases = data.get("fixtures", [])
    injection = [c for c in cases if c.get("category") == "Prompt Injection"]
    assert len(injection) >= 3, f"Prompt Injection 样例不足 3 个: {len(injection)}"


def test_fixtures_each_case_has_required_fields():
    """每个样例应包含必需字段。"""
    with FIXTURES_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    cases = data.get("fixtures", [])
    required_fields = {"id", "query", "should_answer", "expected_mode"}
    for c in cases:
        missing = required_fields - set(c.keys())
        assert not missing, f"样例 {c.get('id')} 缺失字段: {missing}"


def test_evaluate_retrieval_script_importable():
    """评测脚本应可被导入。"""
    from scripts.evaluate_retrieval import (
        EvalCase,
        EvalResult,
        load_fixtures,
        evaluate_one,
        compute_metrics,
    )
    assert EvalCase is not None
    assert EvalResult is not None
    assert callable(load_fixtures)
    assert callable(evaluate_one)
    assert callable(compute_metrics)


def test_load_fixtures_returns_cases():
    """load_fixtures 应返回 EvalCase 列表。"""
    from scripts.evaluate_retrieval import load_fixtures, EvalCase
    cases = load_fixtures(FIXTURES_PATH)
    assert len(cases) > 0
    assert all(isinstance(c, EvalCase) for c in cases)


def test_evaluate_one_hit_at_1():
    """evaluate_one 应正确识别 Hit@1。"""
    from scripts.evaluate_retrieval import evaluate_one, EvalCase

    class FakeDoc:
        def __init__(self, title, document_id):
            self.title = title
            self.document_id = document_id

    class FakeChunk:
        pass

    class FakeRetrieved:
        def __init__(self, title, doc_id):
            self.chunk = FakeChunk()
            self.document = FakeDoc(title, doc_id)
            self.score = 1.0

    case = EvalCase(
        case_id="test1",
        category="测试",
        query="社会实践申请表",
        expected_titles=["社会实践指南"],
        expected_document_ids=[],
        should_answer=True,
        expected_mode="retrieval_summary",
        notes="",
    )
    retrieved = [FakeRetrieved("社会实践指南", "doc_1")]
    result = evaluate_one(case, retrieved)
    assert result.hit_at_1 is True
    assert result.hit_at_3 is True
    assert result.reciprocal_rank == 1.0
    assert not result.failure_reasons


def test_evaluate_one_miss():
    """evaluate_one 应正确识别未命中。"""
    from scripts.evaluate_retrieval import evaluate_one, EvalCase

    class FakeDoc:
        def __init__(self, title, document_id):
            self.title = title
            self.document_id = document_id

    class FakeChunk:
        pass

    class FakeRetrieved:
        def __init__(self, title, doc_id):
            self.chunk = FakeChunk()
            self.document = FakeDoc(title, doc_id)
            self.score = 1.0

    case = EvalCase(
        case_id="test2",
        category="测试",
        query="宿舍熄灯时间",
        expected_titles=["宿舍管理规定"],
        expected_document_ids=[],
        should_answer=True,
        expected_mode="retrieval_summary",
        notes="",
    )
    retrieved = [FakeRetrieved("社会实践指南", "doc_1")]
    result = evaluate_one(case, retrieved)
    assert result.hit_at_1 is False
    assert result.hit_at_3 is False
    assert result.failure_reasons


def test_evaluate_one_correct_reject():
    """should_answer=false 且检索为空时应当正确拒答。"""
    from scripts.evaluate_retrieval import evaluate_one, EvalCase

    case = EvalCase(
        case_id="test3",
        category="无答案问题",
        query="明天天气如何",
        expected_titles=[],
        expected_document_ids=[],
        should_answer=False,
        expected_mode="no_knowledge",
        notes="",
    )
    result = evaluate_one(case, [])
    assert result.correctly_rejected is True
    assert not result.failure_reasons


def test_evaluate_one_false_accept():
    """should_answer=false 但检索非空时应标记为错误接受。"""
    from scripts.evaluate_retrieval import evaluate_one, EvalCase

    class FakeDoc:
        def __init__(self, title, document_id):
            self.title = title
            self.document_id = document_id

    class FakeChunk:
        pass

    class FakeRetrieved:
        def __init__(self, title, doc_id):
            self.chunk = FakeChunk()
            self.document = FakeDoc(title, doc_id)
            self.score = 1.0

    case = EvalCase(
        case_id="test4",
        category="无答案问题",
        query="明天天气如何",
        expected_titles=[],
        expected_document_ids=[],
        should_answer=False,
        expected_mode="no_knowledge",
        notes="",
    )
    retrieved = [FakeRetrieved("天气预报", "doc_x")]
    result = evaluate_one(case, retrieved)
    assert result.correctly_rejected is False
    assert result.failure_reasons


def test_compute_metrics_summary():
    """compute_metrics 应正确汇总指标。"""
    from scripts.evaluate_retrieval import compute_metrics, EvalCase, EvalResult

    cases = [
        EvalCase("c1", "测试", "q1", ["T1"], [], True, "retrieval_summary", ""),
        EvalCase("c2", "无答案", "q2", [], [], False, "no_knowledge", ""),
    ]
    results = [
        EvalResult(case=cases[0], hit_at_1=True, hit_at_3=True, reciprocal_rank=1.0),
        EvalResult(case=cases[1], correctly_rejected=True),
    ]
    metrics = compute_metrics(results)
    assert metrics["total"] == 2
    assert metrics["answerable_count"] == 1
    assert metrics["rejectable_count"] == 1
    assert metrics["hit_at_1"] == 1
    assert metrics["hit_at_1_rate"] == 1.0
    assert metrics["correct_rejection_rate"] == 1.0
    assert metrics["false_acceptance_rate"] == 0.0


def test_evaluate_retrieval_runs_with_demo_kb(app_client):
    """使用 app_client 的演示知识库执行完整评测,应能成功运行。"""
    from scripts.evaluate_retrieval import (
        load_fixtures,
        evaluate_all,
        compute_metrics,
    )
    from app.services.container import get_container

    container = get_container()
    cases = load_fixtures(FIXTURES_PATH)
    # 只取前 5 个样例执行,加快测试速度
    sample_cases = cases[:5]
    results = evaluate_all(sample_cases, container.retrieval)
    metrics = compute_metrics(results)
    assert metrics["total"] == 5
    # 演示资料已导入,至少应有一些样例命中
    assert metrics["answerable_count"] >= 1
