"""Agent Runtime 评测体系(SSOT + 检查 + 运行器)。

用途:
- CI 门禁:全部 P0 用例必须通过
- 论文/答辩:给出分层通过率与时延指标,而不是只有"测试都过了"
"""
from .cases import EvalCase, all_cases, case_ids, cases_by_level
from .runner import CaseResult, EvalReport, format_text, run_case, run_cases

__all__ = [
    "CaseResult",
    "EvalReport",
    "EvalCase",
    "all_cases",
    "case_ids",
    "cases_by_level",
    "format_text",
    "run_case",
    "run_cases",
]
