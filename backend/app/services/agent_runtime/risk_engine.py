"""RiskEngine —— 动作风险分类(§5.5)。

AUTO_SAFE: 内部、可逆或幂等且用户显式启用的动作。
CONFIRM_REQUIRED: 改变计划、消息、日程或外部动作草稿。
MANUAL_ONLY: 认证、验证码、支付、正式注册、作业提交、外部学校系统变更。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ...schemas.agent_contract_enums import RiskLevel


@dataclass
class RiskAssessment:
    """风险评估结果。"""

    risk_level: RiskLevel
    reason: str
    requires_approval: bool


class RiskEngine:
    """风险分类引擎。"""

    # MANUAL_ONLY 动作前缀(§5.5、§8.3)
    _MANUAL_ONLY_PREFIXES: tuple[str, ...] = (
        "auth.",
        "captcha.",
        "payment.",
        "registration.",
        "assignment.submit",
        "external_submission.execute",
        "school_system.mutate",
    )

    # CONFIRM_REQUIRED 动作前缀
    _CONFIRM_PREFIXES: tuple[str, ...] = (
        "plan.activate",
        "plan.update",
        "task.update",
        "reminder.reschedule",
        "message.prepare",
        "research.source.fetch",
        "external_submission.prepare",
    )

    def assess(self, action: str, *, user_enabled_auto: bool = False) -> RiskAssessment:
        """评估动作风险。返回最严格的支持级别。"""
        for prefix in self._MANUAL_ONLY_PREFIXES:
            if action.startswith(prefix):
                return RiskAssessment(
                    RiskLevel.MANUAL_ONLY, f"动作 {action} 属于 MANUAL_ONLY", False
                )
        for prefix in self._CONFIRM_PREFIXES:
            if action.startswith(prefix):
                return RiskAssessment(
                    RiskLevel.CONFIRM_REQUIRED, f"动作 {action} 需要确认", True
                )
        # 默认 AUTO_SAFE(仅当用户启用)
        if user_enabled_auto:
            return RiskAssessment(
                RiskLevel.AUTO_SAFE, f"动作 {action} 用户已启用自动", False
            )
        return RiskAssessment(
            RiskLevel.CONFIRM_REQUIRED, f"动作 {action} 默认需要确认", True
        )

    @staticmethod
    def can_auto_execute(assessment: RiskAssessment) -> bool:
        """是否可自动执行(无审批)。MANUAL_ONLY 永不自动执行。"""
        return assessment.risk_level == RiskLevel.AUTO_SAFE and not assessment.requires_approval

    @staticmethod
    def is_manual_only(assessment: RiskAssessment) -> bool:
        return assessment.risk_level == RiskLevel.MANUAL_ONLY


__all__ = ["RiskEngine", "RiskAssessment"]