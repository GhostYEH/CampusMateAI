"""不可覆盖的硬拒绝清单(§5.5)。

在角色授权、风险分级、审批决定**之前**执行:即使 automation 全开、
审批已批准、会话策略为"全部允许",命中此清单的动作也永不执行。

这是把设计里"MANUAL_ONLY 永不自动执行"从约定变成代码级保证:
风险分级仍然决定"谁来确认",硬拒绝决定"无论如何都不做"。

新增危险模式时,在 _HARD_DENY_TOOL_PREFIXES 或 _HARD_DENY_ARG_PATTERNS
里追加即可,不要把它降级成普通风险前缀。
"""
from __future__ import annotations

import re
from typing import Optional

from ...core.exceptions import AgentToolRejected

# 动作前缀:身份认证、验证码、支付、正式报名、作业提交、学校系统写操作、外部提交执行。
# 这些动作只能由用户本人在官方入口手工完成。
_HARD_DENY_TOOL_PREFIXES: tuple[str, ...] = (
    "auth.",
    "captcha.",
    "payment.",
    "registration.",
    "assignment.submit",
    "school_system.mutate",
    "external_submission.execute",
)

# 参数级模式:即使工具名看起来无害,参数里出现这些语义也直接拒绝。
_HARD_DENY_ARG_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"验证码|captcha|sms[_\- ]?code", re.I), "涉及验证码"),
    (re.compile(r"支付|付款|缴费|payment|checkout", re.I), "涉及支付"),
    (re.compile(r"提交作业|assignment[_\- ]?submit", re.I), "涉及作业提交"),
    (re.compile(r"改成绩|成绩修改|grade[_\- ]?update", re.I), "涉及成绩写操作"),
    (re.compile(r"身份证号|银行卡|id[_\- ]?card[_\- ]?number", re.I), "涉及身份/金融信息"),
)


def hard_deny_reason(tool_code: str, args: Optional[dict] = None) -> Optional[str]:
    """返回硬拒绝原因;未命中返回 None。"""
    code = (tool_code or "").strip()
    for prefix in _HARD_DENY_TOOL_PREFIXES:
        if code.startswith(prefix):
            return f"动作 {code} 属于不可覆盖的硬拒绝清单"
    if args:
        serialized = " ".join(
            str(value) for value in args.values() if isinstance(value, (str, int, float))
        )
        if serialized:
            for pattern, reason in _HARD_DENY_ARG_PATTERNS:
                if pattern.search(serialized):
                    return f"动作 {code} 参数命中硬拒绝模式:{reason}"
    return None


def check_hard_deny(tool_code: str, args: Optional[dict] = None) -> None:
    """命中硬拒绝清单时抛出 AgentToolRejected(不可被审批或配置覆盖)。"""
    reason = hard_deny_reason(tool_code, args)
    if reason:
        raise AgentToolRejected(reason, code="AGENT_TOOL_REJECTED", http_status=403)


__all__ = ["check_hard_deny", "hard_deny_reason"]
