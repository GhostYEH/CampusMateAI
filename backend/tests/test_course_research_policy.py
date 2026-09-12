"""课程研究策略裁决测试(§8.2)。

覆盖:
- 三种 source_policy 组合和越权素材拒绝
- academic_policy 降级与 mode 独立
- 客户端输入不能强制 ALLOWED
"""
from __future__ import annotations

import pytest

from app.schemas.agent_contract_enums import AcademicPolicy, AssistanceMode
from app.services.course_research.policy import (
    SourcePolicy,
    build_effective_policy,
    resolve_academic_policy,
    resolve_assistance_mode,
)


class TestSourcePolicy:
    def test_default_allows_all(self):
        sp = SourcePolicy()
        assert sp.may_fetch_web()
        assert sp.may_use_user_upload()
        assert sp.course_first()

    def test_disable_web_blocks_fetch(self):
        sp = SourcePolicy(allow_web=False)
        assert not sp.may_fetch_web()
        # 其他不受影响
        assert sp.may_use_user_upload()
        assert sp.course_first()

    def test_disable_course_priority(self):
        sp = SourcePolicy(course_material_priority=False)
        assert not sp.course_first()
        assert sp.may_fetch_web()

    def test_disable_user_upload(self):
        sp = SourcePolicy(allow_user_upload=False)
        assert not sp.may_use_user_upload()


class TestAcademicPolicyResolution:
    def test_allowed_is_least_strict(self):
        assert resolve_academic_policy(
            AcademicPolicy.ALLOWED, AcademicPolicy.LIMITED
        ) == AcademicPolicy.LIMITED

    def test_exam_restricted_overrides_allowed(self):
        assert resolve_academic_policy(
            AcademicPolicy.ALLOWED, AcademicPolicy.EXAM_RESTRICTED
        ) == AcademicPolicy.EXAM_RESTRICTED

    def test_ai_prohibited_is_strictest(self):
        assert resolve_academic_policy(
            AcademicPolicy.LIMITED, AcademicPolicy.AI_PROHIBITED
        ) == AcademicPolicy.AI_PROHIBITED

    def test_unknown_treated_as_strictest(self):
        # UNKNOWN 按最严格处理(保守)
        assert resolve_academic_policy(
            AcademicPolicy.ALLOWED, AcademicPolicy.UNKNOWN
        ) == AcademicPolicy.UNKNOWN

    def test_client_cannot_force_allowed(self):
        # 客户端传 ALLOWED,服务端有 EXAM_RESTRICTED 证据
        result = resolve_academic_policy(
            AcademicPolicy.ALLOWED,  # 客户端
            AcademicPolicy.EXAM_RESTRICTED,  # 服务端课程元数据
        )
        assert result == AcademicPolicy.EXAM_RESTRICTED

    def test_single_candidate(self):
        assert resolve_academic_policy(AcademicPolicy.LIMITED) == AcademicPolicy.LIMITED

    def test_no_candidates_returns_unknown(self):
        assert resolve_academic_policy() == AcademicPolicy.UNKNOWN


class TestAssistanceModeResolution:
    def test_allowed_keeps_full_solution(self):
        assert resolve_assistance_mode(
            AssistanceMode.FULL_SOLUTION, AcademicPolicy.ALLOWED
        ) == AssistanceMode.FULL_SOLUTION

    def test_limited_keeps_full_solution(self):
        assert resolve_assistance_mode(
            AssistanceMode.FULL_SOLUTION, AcademicPolicy.LIMITED
        ) == AssistanceMode.FULL_SOLUTION

    def test_exam_restricted_degrades_full_solution(self):
        assert resolve_assistance_mode(
            AssistanceMode.FULL_SOLUTION, AcademicPolicy.EXAM_RESTRICTED
        ) == AssistanceMode.EXPLAIN

    def test_exam_restricted_degrades_review(self):
        assert resolve_assistance_mode(
            AssistanceMode.REVIEW, AcademicPolicy.EXAM_RESTRICTED
        ) == AssistanceMode.EXPLAIN

    def test_exam_restricted_keeps_hint(self):
        assert resolve_assistance_mode(
            AssistanceMode.HINT, AcademicPolicy.EXAM_RESTRICTED
        ) == AssistanceMode.HINT

    def test_exam_restricted_keeps_explain(self):
        assert resolve_assistance_mode(
            AssistanceMode.EXPLAIN, AcademicPolicy.EXAM_RESTRICTED
        ) == AssistanceMode.EXPLAIN

    def test_ai_prohibited_forces_hint(self):
        for mode in AssistanceMode:
            assert resolve_assistance_mode(
                mode, AcademicPolicy.AI_PROHIBITED
            ) == AssistanceMode.HINT

    def test_unknown_degrades_full_solution(self):
        # UNKNOWN 保守降级
        assert resolve_assistance_mode(
            AssistanceMode.FULL_SOLUTION, AcademicPolicy.UNKNOWN
        ) == AssistanceMode.EXPLAIN

    def test_mode_independent_of_policy_for_hint(self):
        # HINT 在所有策略下都保持 HINT
        for policy in AcademicPolicy:
            assert resolve_assistance_mode(
                AssistanceMode.HINT, policy
            ) == AssistanceMode.HINT


class TestEffectivePolicy:
    def test_degraded_flag(self):
        ep = build_effective_policy(
            requested_mode=AssistanceMode.FULL_SOLUTION,
            academic_candidates=[AcademicPolicy.EXAM_RESTRICTED],
            source_policy=SourcePolicy(),
        )
        assert ep.degraded
        assert ep.effective_mode == AssistanceMode.EXPLAIN

    def test_not_degraded_when_allowed(self):
        ep = build_effective_policy(
            requested_mode=AssistanceMode.FULL_SOLUTION,
            academic_candidates=[AcademicPolicy.ALLOWED],
            source_policy=SourcePolicy(),
        )
        assert not ep.degraded
        assert ep.effective_mode == AssistanceMode.FULL_SOLUTION

    def test_source_policy_preserved(self):
        sp = SourcePolicy(allow_web=False)
        ep = build_effective_policy(
            requested_mode=AssistanceMode.EXPLAIN,
            academic_candidates=[AcademicPolicy.ALLOWED],
            source_policy=sp,
        )
        assert not ep.source_policy.may_fetch_web()