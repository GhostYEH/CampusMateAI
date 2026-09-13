"""Provider 失败分类 -> 恢复动作。

把"失败就重试一次再切备用"的一刀切策略,换成按失败原因决定动作:

- rate_limit / overloaded / server_error / timeout / connection:可重试,可切备用
- auth / billing / model_not_found:重试无意义,直接切备用并把该 provider 标记为不可用
- context_overflow:重试同样会失败,应先压缩上下文(本版只标记 should_compress)
- format_error:模型输出格式问题,由调用方决定是否做修复重试

只依据异常文本做保守分类;无法识别时按"可重试"处理,避免误判导致直接失败。
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderFailure:
    """一次 provider 失败的分类结果与恢复建议。"""

    reason: str
    retryable: bool
    should_fallback: bool = True
    should_compress: bool = False


# (reason, 匹配模式, retryable, should_compress)
_RULES: tuple[tuple[str, re.Pattern[str], bool, bool], ...] = (
    ("context_overflow", re.compile(r"context[_\- ]?length|too many tokens|maximum context|超出.{0,4}上下文|context[_\- ]?overflow", re.I), False, True),
    ("rate_limit", re.compile(r"rate[_\- ]?limit|too many requests|429|限流|频率", re.I), True, False),
    ("overloaded", re.compile(r"overloaded|503|service unavailable|繁忙", re.I), True, False),
    ("billing", re.compile(r"insufficient[_\- ]?quota|billing|quota|欠费|余额不足|402", re.I), False, False),
    ("auth", re.compile(r"unauthorized|invalid[_\- ]?api[_\- ]?key|401|403|forbidden|鉴权|密钥", re.I), False, False),
    ("model_not_found", re.compile(r"model[_\- ]?not[_\- ]?found|unknown model|no such model|模型不存在", re.I), False, False),
    ("timeout", re.compile(r"timeout|timed out|超时", re.I), True, False),
    ("connection", re.compile(r"connection|connect|network|dns|ssl|网络", re.I), True, False),
    ("server_error", re.compile(r"internal server error|500|502|504|server[_\- ]?error", re.I), True, False),
    ("format_error", re.compile(r"json|schema|parse|格式", re.I), True, False),
)

# 这些原因重试不会改善结果,连续失败也不需要换 key。
_TERMINAL_REASONS = frozenset({"auth", "billing", "model_not_found"})


def classify_provider_error(error: object) -> ProviderFailure:
    """把 provider 异常归类为结构化恢复建议。"""
    text = f"{type(error).__name__}: {error}"
    for reason, pattern, retryable, should_compress in _RULES:
        if pattern.search(text):
            return ProviderFailure(
                reason=reason,
                retryable=retryable,
                should_compress=should_compress,
            )
    return ProviderFailure(reason="unknown", retryable=True)


def is_terminal_failure(failure: ProviderFailure) -> bool:
    """是否属于"该 provider 在当前进程内已不可用"的终局失败。"""
    return failure.reason in _TERMINAL_REASONS


__all__ = ["ProviderFailure", "classify_provider_error", "is_terminal_failure"]
