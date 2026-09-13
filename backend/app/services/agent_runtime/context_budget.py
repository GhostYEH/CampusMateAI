"""上下文预算与分级裁剪(§5.1)。

目的:长任务(课程研究多角色检索、复习计划长上下文)不能无限膨胀。
本模块不引入 tiktoken 等额外依赖,用保守估算 + 确定性裁剪:

- 结构化小字段(考试、容量、日期、状态)永不丢弃
- 长文本(资料片段、网页正文)按预算头尾保留,中间替换为截断标记
- 超长列表按"保留前 N 条"裁剪,并在报告里说明丢了多少

裁剪结果必须显式记录(truncated / dropped / estimated_tokens),
让调用方和界面知道"这是压缩过的上下文",而不是静默丢信息。
"""
from __future__ import annotations

from typing import Any

DEFAULT_BUDGET_TOKENS = 6000

# 工具结果分级:critical 基本保留,moderate 减半,low 只留占位说明。
_TOOL_TIER_CRITICAL = ("task.", "plan.", "personal_task", "exam.")
_TOOL_TIER_LOW = ("web_research", "web.search", "research.source.fetch")
_TIER_BUDGET_RATIO = {"critical": 1.0, "moderate": 0.5, "low": 0.15}

_TRIM_PLACEHOLDER = "(内容已按上下文预算省略)"
_MIN_TRIM_TOKENS = 16


def estimate_tokens(text: str) -> int:
    """保守估算 token 数:CJK 按 1 token/字,其余按 4 字符/token。"""
    if not text:
        return 0
    cjk = 0
    for ch in text:
        code = ord(ch)
        if 0x3000 <= code <= 0x303F or 0x4E00 <= code <= 0x9FFF or 0xFF00 <= code <= 0xFFEF:
            cjk += 1
    other = len(text) - cjk
    return cjk + (other + 3) // 4


def estimate_value_tokens(value: Any) -> int:
    """递归估算任意 JSON 值的 token 数。"""
    if value is None:
        return 0
    if isinstance(value, str):
        return estimate_tokens(value)
    if isinstance(value, (int, float, bool)):
        return 1
    if isinstance(value, (list, tuple)):
        return sum(estimate_value_tokens(item) for item in value)
    if isinstance(value, dict):
        return sum(
            estimate_tokens(str(key)) + estimate_value_tokens(item)
            for key, item in value.items()
        )
    return estimate_tokens(str(value))


def trim_text(text: str, max_tokens: int) -> tuple[str, bool]:
    """头尾保留式截断,保证结果不超过 max_tokens。"""
    if max_tokens <= 0:
        return "", True
    if estimate_tokens(text) <= max_tokens:
        return text, False
    if max_tokens < _MIN_TRIM_TOKENS:
        # 预算太小:连截断标记都放不下,退化为占位串。
        return _TRIM_PLACEHOLDER[:max_tokens], True

    total = estimate_tokens(text)
    # 先给截断标记预留 token,否则标记本身会把结果顶出预算。
    marker = "…(已截断)…"
    content_budget = max(1, max_tokens - estimate_tokens(marker))
    budget_chars = max(8, int(len(text) * content_budget / max(1, total)))
    for head_ratio in (0.25, 0.1, 0.0):
        head_chars = int(budget_chars * head_ratio)
        tail_chars = max(0, budget_chars - head_chars)
        candidate = text[:head_chars] + marker + (
            text[-tail_chars:] if tail_chars else ""
        )
        if estimate_tokens(candidate) <= max_tokens:
            return candidate, True
    return _TRIM_PLACEHOLDER, True


def tool_result_tier(tool_code: str) -> str:
    """按工具名给出裁剪档位。"""
    code = (tool_code or "").strip()
    if code.startswith(_TOOL_TIER_CRITICAL):
        return "critical"
    if code.startswith(_TOOL_TIER_LOW):
        return "low"
    return "moderate"


def trim_tool_result(
    tool_code: str,
    payload: str,
    *,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
) -> tuple[str, bool]:
    """按档位裁剪单个工具结果。"""
    tier = tool_result_tier(tool_code)
    allowance = max(16, int(budget_tokens * _TIER_BUDGET_RATIO[tier]))
    if tier == "low" and estimate_tokens(payload) > allowance:
        return (
            f"(低价值工具结果已按预算省略,原始约 {estimate_tokens(payload)} tokens)",
            True,
        )
    return trim_text(payload, allowance)


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (int, float, bool))


def compact_facts(
    facts: dict,
    *,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
) -> tuple[dict, dict]:
    """把超出预算的上下文字段压回预算内。

    返回 (压缩后的 facts, 报告)。报告字段:
    budget_tokens / estimated_tokens / truncated / dropped_keys / trimmed_keys
    """
    original_tokens = estimate_value_tokens(facts)
    report: dict = {
        "budget_tokens": budget_tokens,
        "estimated_tokens": original_tokens,
        "truncated": False,
        "dropped_keys": [],
        "trimmed_keys": [],
    }
    if original_tokens <= budget_tokens:
        return facts, report

    # 标量字段永不裁剪,先为它们预留预算,保证裁剪后总量落在预算内。
    scalar_keys = {key for key, value in facts.items() if _is_scalar(value)}
    scalar_tokens = sum(estimate_value_tokens(facts[key]) for key in scalar_keys)

    compacted: dict = {key: facts[key] for key in scalar_keys}
    dropped: list[str] = []
    trimmed: list[str] = []
    remaining = max(0, budget_tokens - scalar_tokens)
    # 其余字段按占用从大到小处理,尽量少动小字段。
    weighted = sorted(
        (
            (key, estimate_value_tokens(value))
            for key, value in facts.items()
            if key not in scalar_keys
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    for key, _weight in weighted:
        value = facts[key]
        if remaining <= 0:
            dropped.append(key)
            continue
        if isinstance(value, str):
            if estimate_tokens(value) <= remaining:
                compacted[key] = value
                remaining -= estimate_tokens(value)
                continue
            text, _ = trim_text(value, remaining)
            compacted[key] = text
            remaining = max(0, remaining - estimate_tokens(text))
            trimmed.append(key)
            continue
        if isinstance(value, list):
            kept: list = []
            for item in value:
                item_tokens = estimate_value_tokens(item)
                if item_tokens > remaining:
                    break
                kept.append(item)
                remaining -= item_tokens
            if kept:
                compacted[key] = kept
                trimmed.append(key)
                report["dropped_keys"].append(f"{key}:{len(value) - len(kept)}")
            else:
                dropped.append(key)
            continue
        # dict 等复杂结构在预算不足时整体丢弃,不冒险部分保留。
        dropped.append(key)

    # 收尾:键名本身也占 token,做一次收敛,确保总量真正落在预算内。
    for _ in range(len(compacted) + 2):
        total = estimate_value_tokens(compacted)
        if total <= budget_tokens:
            break
        overflow = total - budget_tokens
        shrinkable = [
            (key, estimate_value_tokens(value))
            for key, value in compacted.items()
            if key not in scalar_keys and not _is_scalar(value)
        ]
        if not shrinkable:
            break
        key, _size = max(shrinkable, key=lambda item: item[1])
        value = compacted[key]
        if isinstance(value, str):
            compacted[key], _ = trim_text(
                value, max(1, estimate_tokens(value) - overflow - 1)
            )
        else:
            compacted.pop(key, None)
            dropped.append(key)

    report["truncated"] = True
    report["estimated_tokens"] = estimate_value_tokens(compacted)
    report["dropped_keys"] = sorted(set(report["dropped_keys"]) | set(dropped))
    report["trimmed_keys"] = sorted(set(trimmed))
    return compacted, report


__all__ = [
    "DEFAULT_BUDGET_TOKENS",
    "compact_facts",
    "estimate_tokens",
    "estimate_value_tokens",
    "tool_result_tier",
    "trim_text",
    "trim_tool_result",
]
