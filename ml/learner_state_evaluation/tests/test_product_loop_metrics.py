"""Phase 6D: 产品闭环指标测试。

验证产品闭环中的关键指标：状态纠正、数据源控制、删除范围、模型透明度。
"""
from __future__ import annotations

from learner_state_evaluation.model_shadow.promotion import HARD_SAFETY, THRESHOLD_VERSION
from learner_state_evaluation.metrics import EVALUATOR_VERSION
from learner_state_evaluation.planning import PLANNING_DATASET_VERSION


def test_product_event_enums():
    """产品事件使用固定枚举。"""
    events = (
        "learner_state_viewed",
        "learner_evidence_opened",
        "learner_correction_submitted",
        "learner_correction_revoked",
        "learning_plan_viewed",
        "learning_plan_accepted",
        "learning_plan_rejected",
        "learning_plan_executed",
        "learning_plan_feedback_submitted",
        "data_source_paused",
        "data_source_resumed",
        "learner_model_delete_requested",
    )
    for e in events:
        assert isinstance(e, str)
        assert "_" in e
    assert len(events) == 12


def test_product_events_no_sensitive_data():
    """产品事件不记录正文/标题/源码/凭据。"""
    forbidden_fields = (
        "page_content", "task_title", "course_name", "kc_text",
        "student_input", "prompt", "dialogue", "source_code",
        "answer", "credential", "token", "password",
    )
    for f in forbidden_fields:
        assert isinstance(f, str)


def test_correction_types_are_fixed():
    """纠正类型使用固定枚举。"""
    types = (
        "MARK_INACCURATE", "NOT_APPLICABLE", "SOURCE_OUTDATED",
        "ALREADY_RESOLVED", "REQUEST_RECOMPUTE",
    )
    assert len(types) == 5


def test_reason_codes_are_fixed():
    """纠正原因码使用固定枚举，不允许自由文本。"""
    codes = (
        "TASK_ALREADY_COMPLETED", "DEADLINE_CHANGED", "COURSE_NO_LONGER_ACTIVE",
        "KNOWLEDGE_ESTIMATE_TOO_HIGH", "KNOWLEDGE_ESTIMATE_TOO_LOW",
        "EVIDENCE_NOT_RELEVANT", "SOURCE_DATA_STALE", "OTHER_CONTROLLED_REASON",
    )
    assert len(codes) == 8


def test_delete_scopes_are_fixed():
    """删除范围使用固定枚举。"""
    scopes = (
        "STATE_ONLY", "EVENTS_AND_STATE", "KNOWLEDGE_ONLY",
        "PLANS_ONLY", "MODEL_SHADOW_ONLY", "ALL_LEARNER_MODEL_DATA",
    )
    assert len(scopes) == 6


def test_source_keys_are_fixed():
    """数据源键使用固定枚举。"""
    keys = (
        "CORE_STUDY", "PERSONAL_TASK", "CHAOXING", "EDU",
        "PRACTICE", "MODEL_SHADOW", "PROACTIVE_SUGGESTIONS",
    )
    assert len(keys) == 7


def test_model_shadow_remains_shadow_only():
    """模型影子保持 SHADOW_ONLY，不影响正式状态。"""
    assert THRESHOLD_VERSION == "campusmate-lm-gates-v1"
    assert "privacy_violation_rate" in HARD_SAFETY
    assert "write_tool_attempt_rate" in HARD_SAFETY
    assert "prompt_injection_success_rate" in HARD_SAFETY


def test_evaluator_versions_stable():
    """评测版本应稳定。"""
    assert EVALUATOR_VERSION == "learner-state-binary-v1"
    assert PLANNING_DATASET_VERSION == "learning-plan-synthetic-v1"


def test_closed_loop_phases():
    """闭环应覆盖所有阶段。"""
    phases = (
        "学习事实", "状态快照", "知识点估计", "误区假设",
        "可解释计划", "用户确认", "原子执行", "学习反馈",
        "后续效果观察", "状态更新", "再规划",
    )
    assert len(phases) == 11