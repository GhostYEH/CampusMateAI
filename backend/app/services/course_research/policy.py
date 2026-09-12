"""AcademicPolicy / SourcePolicy 裁决(§8.2)。

关键约束:
- source_policy 是硬约束:禁用公开 Web 时绝不搜索 Web;课程资料优先时先检索已有课程素材。
- academic_policy 与 mode 解耦。受限考试/禁止代答场景即使请求 FULL_SOLUTION,
  也应降级为 HINT/EXPLAIN。
- AcademicPolicy 有效策略是最严格的,客户端输入不能强制 ALLOWED。
"""
from __future__ import annotations

from dataclasses import dataclass

from ...schemas.agent_contract_enums import (
    AcademicPolicy as AcademicPolicyEnum,
    AssistanceMode,
)


# 复用契约枚举,避免并行定义
AcademicPolicy = AcademicPolicyEnum


@dataclass(frozen=True)
class SourcePolicy:
    """来源策略(硬约束)。"""

    course_material_priority: bool = True
    allow_web: bool = True
    allow_user_upload: bool = True

    def may_fetch_web(self) -> bool:
        """是否允许公共 Web 检索。"""
        return self.allow_web

    def may_use_user_upload(self) -> bool:
        return self.allow_user_upload

    def course_first(self) -> bool:
        return self.course_material_priority


# AcademicPolicy 严格度排序(越严格越大)
_ACADEMIC_STRICTNESS: dict[AcademicPolicy, int] = {
    AcademicPolicy.ALLOWED: 0,
    AcademicPolicy.LIMITED: 1,
    AcademicPolicy.EXAM_RESTRICTED: 2,
    AcademicPolicy.AI_PROHIBITED: 3,
    AcademicPolicy.UNKNOWN: 4,  # 未知按最严格处理
}


def resolve_academic_policy(
    *candidates: AcademicPolicy,
) -> AcademicPolicy:
    """合并多个学术策略候选,返回最严格的支持结果。

    客户端输入不能强制 ALLOWED:服务端基于课程/作业元数据、用户声明、RiskEngine
    综合判定,取最严格者。UNKNOWN 视为最严格(保守)。
    """
    if not candidates:
        return AcademicPolicy.UNKNOWN
    result = candidates[0]
    for c in candidates[1:]:
        if _ACADEMIC_STRICTNESS[c] > _ACADEMIC_STRICTNESS[result]:
            result = c
    return result


# 受限策略下不允许 FULL_SOLUTION
_FULL_SOLUTION_BLOCKED_POLICIES = frozenset({
    AcademicPolicy.EXAM_RESTRICTED,
    AcademicPolicy.AI_PROHIBITED,
    AcademicPolicy.UNKNOWN,
})

# AI_PROHIBITED 下连 EXPLAIN/REVIEW 也受限,仅允许 HINT
_AI_PROHIBITED_ALLOWED = frozenset({AssistanceMode.HINT})

# EXAM_RESTRICTED / UNKNOWN 下允许 HINT/EXPLAIN
_EXAM_ALLOWED = frozenset({AssistanceMode.HINT, AssistanceMode.EXPLAIN})


def resolve_assistance_mode(
    requested: AssistanceMode,
    academic_policy: AcademicPolicy,
) -> AssistanceMode:
    """根据学术策略解析有效辅助模式。

    - ALLOWED / LIMITED: 原样返回请求模式
    - EXAM_RESTRICTED / UNKNOWN: FULL_SOLUTION 降级为 EXPLAIN,REVIEW 降级为 EXPLAIN
    - AI_PROHIBITED: 仅允许 HINT,其他降级为 HINT
    """
    if academic_policy == AcademicPolicy.AI_PROHIBITED:
        return AssistanceMode.HINT if requested in _AI_PROHIBITED_ALLOWED else AssistanceMode.HINT
    if academic_policy in _FULL_SOLUTION_BLOCKED_POLICIES:
        if requested in _EXAM_ALLOWED:
            return requested
        # FULL_SOLUTION / REVIEW 降级为 EXPLAIN
        return AssistanceMode.EXPLAIN
    return requested


@dataclass(frozen=True)
class EffectivePolicy:
    """有效策略(服务端裁决后)。"""

    academic_policy: AcademicPolicy
    requested_mode: AssistanceMode
    effective_mode: AssistanceMode
    source_policy: SourcePolicy
    degraded: bool  # 是否发生了 mode 降级


def build_effective_policy(
    *,
    requested_mode: AssistanceMode,
    academic_candidates: list[AcademicPolicy],
    source_policy: SourcePolicy,
) -> EffectivePolicy:
    """构建有效策略。"""
    academic = resolve_academic_policy(*academic_candidates)
    effective_mode = resolve_assistance_mode(requested_mode, academic)
    return EffectivePolicy(
        academic_policy=academic,
        requested_mode=requested_mode,
        effective_mode=effective_mode,
        source_policy=source_policy,
        degraded=effective_mode != requested_mode,
    )


__all__ = [
    "AcademicPolicy",
    "SourcePolicy",
    "resolve_academic_policy",
    "resolve_assistance_mode",
    "build_effective_policy",
    "EffectivePolicy",
]