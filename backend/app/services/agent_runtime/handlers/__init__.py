"""CampusAgentRuntime 工作流处理器。

只有在这里注册过的 `job_kind` 才能被 Worker 执行;HTTP 路由不直接执行业务。
"""
from __future__ import annotations

from .base import (
    HandlerContext,
    HandlerResult,
    JobHandler,
    JobHandlerRegistrationError,
    RecoveryAction,
    RecoveryDecision,
)
from .learning_goal import LearningGoalHandler, LearningGoalInput
from .registry import JobHandlerRegistry

__all__ = [
    "HandlerContext",
    "HandlerResult",
    "JobHandler",
    "JobHandlerRegistrationError",
    "JobHandlerRegistry",
    "LearningGoalHandler",
    "LearningGoalInput",
    "RecoveryAction",
    "RecoveryDecision",
]
