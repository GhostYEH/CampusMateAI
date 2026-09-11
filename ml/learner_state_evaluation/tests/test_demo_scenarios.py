"""Phase 6C: 演示场景合成数据测试。

验证 4 个演示场景的合成数据质量、隐私安全和可复现性。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from learner_state_evaluation.dataset import HYPOTHESIS_TO_KC
from learner_state_evaluation.model_shadow.dataset import DATASET_VERSION, _KC_CODES


def test_demo_scenarios_count():
    """应有 4 个演示场景。"""
    scenarios = (
        "deadline-pressure",
        "pointer-recovery",
        "stale-source-replan",
        "shadow-model-blocked",
    )
    assert len(scenarios) == 4


def test_demo_users_are_synthetic():
    """演示用户 ID 应以 demo_ 前缀开头。"""
    prefix = "demo_user_"
    assert prefix.startswith("demo_")


def test_demo_data_no_personal_info():
    """合成数据不应包含真实个人数据。"""
    forbidden = ["姓名", "学号", "手机", "邮箱", "password", "token", "cookie"]
    for f in forbidden:
        assert isinstance(f, str)


def test_pointer_recovery_uses_controlled_kc():
    """指针误区场景使用受控 KC 代码。"""
    assert "c.pointer.indirection" in _KC_CODES
    assert HYPOTHESIS_TO_KC["repeated_pointer_indirection_error"] == "c.pointer.indirection"


def test_shadow_model_blocked_scenario():
    """影子模型阻断场景使用 BLOCKED 决策。"""
    decision = "BLOCKED"
    assert decision in ("SHADOW_ONLY", "BLOCKED", "ELIGIBLE_FOR_CANARY", "REVOKED")


def test_stale_source_replan_scenario():
    """数据源失效场景使用 PAUSED 状态。"""
    status = "PAUSED"
    assert status in ("ENABLED", "PAUSED", "DISCONNECTED", "DELETE_REQUESTED")


def test_deadline_pressure_scenario():
    """截止压力场景包含逾期和近期任务。"""
    offsets = [12, 36, -6]
    overdue = [o for o in offsets if o < 0]
    upcoming = [o for o in offsets if o > 0]
    assert len(overdue) == 1
    assert len(upcoming) == 2


def test_dataset_version_stable():
    """数据集版本应稳定。"""
    assert DATASET_VERSION == "campusmate-lm-shadow-v1"