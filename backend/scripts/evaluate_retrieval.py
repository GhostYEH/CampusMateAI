"""检索评测脚本 — 真实调用 RetrievalService 评测 Hit@K / MRR / 拒答率等指标。

使用方式:
    cd backend
    python -m scripts.evaluate_retrieval                # 使用默认 fixtures
    python -m scripts.evaluate_retrieval --fixtures PATH # 指定自定义 fixtures

评测维度:
- Hit@1 / Hit@3: top-k 中是否命中期望文档
- MRR: 平均倒数排名
- 无答案问题正确拒答率(should_answer=false 时检索为空)
- 错误接受率(should_answer=false 时仍返回结果)
- 失败样例(便于人工复核)
- 平均检索耗时

不写死答案,所有结果由真实 RetrievalService.search() 返回。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# 确保 backend 包在 sys.path 中(支持直接 python scripts/evaluate_retrieval.py 运行)
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.database.sqlite_db import init_db  # noqa: E402
from app.repositories.document_repository import DocumentRepository  # noqa: E402
from app.services.knowledge_ingestion_service import KnowledgeIngestionService  # noqa: E402
from app.services.retrieval_service import RetrievalService  # noqa: E402


DEFAULT_FIXTURES_PATH = (
    _BACKEND_ROOT / "tests" / "fixtures" / "retrieval_evaluation.json"
)


@dataclass
class EvalCase:
    """单条评测样例。"""
    case_id: str
    category: str
    query: str
    expected_titles: List[str]
    expected_document_ids: List[str]
    should_answer: bool
    expected_mode: str
    notes: str


@dataclass
class EvalResult:
    """单条评测结果。"""
    case: EvalCase
    hit_at_1: bool = False
    hit_at_3: bool = False
    reciprocal_rank: float = 0.0  # 1/rank, 未命中为 0
    retrieved_titles: List[str] = field(default_factory=list)
    retrieved_doc_ids: List[str] = field(default_factory=list)
    correctly_rejected: Optional[bool] = None  # should_answer=False 时是否正确拒答
    elapsed_ms: float = 0.0
    failure_reasons: List[str] = field(default_factory=list)


def load_fixtures(path: Path) -> List[EvalCase]:
    """加载评测 fixtures。"""
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    cases: List[EvalCase] = []
    for item in data.get("fixtures", []):
        cases.append(
            EvalCase(
                case_id=item["id"],
                category=item.get("category", ""),
                query=item["query"],
                expected_titles=item.get("expected_titles", []) or [],
                expected_document_ids=item.get("expected_document_ids", []) or [],
                should_answer=bool(item.get("should_answer", True)),
                expected_mode=item.get("expected_mode", "retrieval_summary"),
                notes=item.get("notes", ""),
            )
        )
    return cases


def _title_match(retrieved_title: str, expected: str) -> bool:
    """标题匹配 — 支持子串包含(避免后缀差异导致漏判)。"""
    if not retrieved_title or not expected:
        return False
    a = retrieved_title.strip()
    b = expected.strip()
    if a == b:
        return True
    # 子串包含(任一方向)
    if b in a or a in b:
        return True
    return False


def evaluate_one(
    case: EvalCase,
    retrieved: list,
) -> EvalResult:
    """评测单条样例。

    Args:
        case: 评测样例
        retrieved: RetrievalService.search() 返回的 RetrievedChunk 列表
    """
    result = EvalResult(case=case)
    retrieved_titles = []
    retrieved_doc_ids = []
    for rc in retrieved:
        if rc.document is None:
            continue
        retrieved_titles.append(rc.document.title)
        retrieved_doc_ids.append(rc.document.document_id)
    result.retrieved_titles = retrieved_titles
    result.retrieved_doc_ids = retrieved_doc_ids

    # 应当拒答的场景
    if not case.should_answer:
        if not retrieved:
            result.correctly_rejected = True
        else:
            result.correctly_rejected = False
            result.failure_reasons.append(
                f"应当拒答,但检索到 {len(retrieved)} 条结果: {retrieved_titles[:2]}"
            )
        return result

    # 应当有答案,但检索为空
    if not retrieved:
        result.failure_reasons.append("应当有答案,但检索结果为空")
        return result

    # 期望文档集合
    expected_titles = case.expected_titles
    expected_ids = set(case.expected_document_ids) if case.expected_document_ids else set()

    # Hit@1
    if retrieved_titles:
        top1_title = retrieved_titles[0]
        top1_id = retrieved_doc_ids[0] if retrieved_doc_ids else ""
        hit1 = (
            any(_title_match(top1_title, e) for e in expected_titles)
            or (top1_id in expected_ids if expected_ids else False)
        )
        result.hit_at_1 = hit1
        if hit1:
            result.reciprocal_rank = 1.0

    # Hit@3 + MRR
    for idx, (t, d) in enumerate(zip(retrieved_titles[:3], retrieved_doc_ids[:3]), start=1):
        is_hit = (
            any(_title_match(t, e) for e in expected_titles)
            or (d in expected_ids if expected_ids else False)
        )
        if is_hit:
            result.hit_at_3 = True
            if result.reciprocal_rank == 0.0:
                result.reciprocal_rank = 1.0 / idx
            break

    if not result.hit_at_3:
        result.failure_reasons.append(
            f"top-3 未命中期望文档。期望: {expected_titles}, 实际: {retrieved_titles[:3]}"
        )

    return result


def evaluate_all(
    cases: List[EvalCase],
    retrieval: RetrievalService,
) -> List[EvalResult]:
    """执行全部评测样例。"""
    results: List[EvalResult] = []
    # 确保索引就绪
    retrieval.rebuild()
    for case in cases:
        t0 = time.perf_counter()
        retrieved = retrieval.search(case.query, k=5)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        result = evaluate_one(case, retrieved)
        result.elapsed_ms = elapsed_ms
        results.append(result)
    return results


def compute_metrics(results: List[EvalResult]) -> dict:
    """汇总指标。"""
    total = len(results)
    if total == 0:
        return {"total": 0}

    answerable = [r for r in results if r.case.should_answer]
    rejectable = [r for r in results if not r.case.should_answer]

    hit1 = sum(1 for r in answerable if r.hit_at_1)
    hit3 = sum(1 for r in answerable if r.hit_at_3)
    mrr = sum(r.reciprocal_rank for r in answerable)

    # 拒答率: should_answer=false 且 检索为空
    correct_reject = sum(1 for r in rejectable if r.correctly_rejected is True)
    # 错误接受率: should_answer=false 但仍返回结果
    false_accept = sum(1 for r in rejectable if r.correctly_rejected is False)

    avg_latency = sum(r.elapsed_ms for r in results) / total

    return {
        "total": total,
        "answerable_count": len(answerable),
        "rejectable_count": len(rejectable),
        "hit_at_1": hit1,
        "hit_at_1_rate": round(hit1 / len(answerable), 4) if answerable else 0.0,
        "hit_at_3": hit3,
        "hit_at_3_rate": round(hit3 / len(answerable), 4) if answerable else 0.0,
        "mrr": round(mrr / len(answerable), 4) if answerable else 0.0,
        "correct_rejection_rate": round(correct_reject / len(rejectable), 4) if rejectable else 1.0,
        "false_acceptance_rate": round(false_accept / len(rejectable), 4) if rejectable else 0.0,
        "avg_latency_ms": round(avg_latency, 2),
        "failures": [
            {
                "case_id": r.case.case_id,
                "category": r.case.category,
                "query": r.case.query,
                "reasons": r.failure_reasons,
                "retrieved_titles": r.retrieved_titles[:3],
                "expected_titles": r.case.expected_titles,
            }
            for r in results
            if r.failure_reasons
        ],
    }


def print_report(metrics: dict, results: List[EvalResult]) -> None:
    """打印评测报告。"""
    print("=" * 60)
    print("检索评测报告 — Retrieval Evaluation Report")
    print("=" * 60)
    print(f"总样例数: {metrics['total']}")
    print(f"应有答案样例数: {metrics['answerable_count']}")
    print(f"应拒答样例数: {metrics['rejectable_count']}")
    print("-" * 60)
    print(f"Hit@1:  {metrics['hit_at_1']}/{metrics['answerable_count']} "
          f"({metrics['hit_at_1_rate'] * 100:.2f}%)")
    print(f"Hit@3:  {metrics['hit_at_3']}/{metrics['answerable_count']} "
          f"({metrics['hit_at_3_rate'] * 100:.2f}%)")
    print(f"MRR:    {metrics['mrr']:.4f}")
    print(f"正确拒答率: {metrics['correct_rejection_rate'] * 100:.2f}%")
    print(f"错误接受率: {metrics['false_acceptance_rate'] * 100:.2f}%")
    print(f"平均检索耗时: {metrics['avg_latency_ms']:.2f} ms")
    print("-" * 60)
    failures = metrics.get("failures", [])
    if failures:
        print(f"失败样例 ({len(failures)} 条):")
        for f in failures:
            print(f"  - [{f['case_id']}] ({f['category']}) {f['query']}")
            for r in f["reasons"]:
                print(f"      原因: {r}")
            if f["retrieved_titles"]:
                print(f"      实际 top-3: {f['retrieved_titles']}")
            if f["expected_titles"]:
                print(f"      期望: {f['expected_titles']}")
    else:
        print("无失败样例。")
    print("=" * 60)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="检索评测脚本 — 评测 RetrievalService 的 Hit@K / MRR / 拒答率"
    )
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=DEFAULT_FIXTURES_PATH,
        help=f"评测 fixtures 文件路径(默认: {DEFAULT_FIXTURES_PATH})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出指标(便于 CI 解析)",
    )
    args = parser.parse_args(argv)

    if not args.fixtures.exists():
        print(f"ERROR: fixtures 文件不存在: {args.fixtures}", file=sys.stderr)
        return 2

    # 初始化服务(读取实际知识库)
    settings = get_settings()
    db = init_db(settings)
    repo = DocumentRepository(db)
    retrieval = RetrievalService(repo)
    ingestion = KnowledgeIngestionService(repo, retrieval, settings)
    # 确保演示资料已导入
    added = ingestion.import_demo_documents()
    if added > 0:
        print(f"[INFO] 已导入 {added} 份演示资料用于评测。")
    retrieval.rebuild()
    if retrieval.chunk_count == 0:
        print("ERROR: 知识库为空,无法进行评测。请先导入演示资料。", file=sys.stderr)
        return 3

    cases = load_fixtures(args.fixtures)
    if not cases:
        print("ERROR: fixtures 中未找到任何样例。", file=sys.stderr)
        return 4

    print(f"[INFO] 加载 {len(cases)} 条评测样例,知识库 chunk 数: {retrieval.chunk_count}")

    results = evaluate_all(cases, retrieval)
    metrics = compute_metrics(results)

    if args.json:
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
    else:
        print_report(metrics, results)

    # 失败样例过多时返回非零退出码(便于 CI 检测)
    failure_rate = (
        len(metrics.get("failures", [])) / max(1, metrics["total"])
    )
    if failure_rate > 0.5:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
