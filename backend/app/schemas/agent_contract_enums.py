"""CampusAgentRuntime 稳定契约枚举。

本模块冻结 v1 跨客户端(Android / HarmonyOS / Web)共享的枚举值。
所有值均为字符串字面量,禁止改动已发布值:
- 新增值只能追加到末尾,不得插入或重排。
- 客户端遇到未知值必须渲染安全通用状态,不得崩溃或授予权限。

来源:docs/superpowers/specs/2026-09-12-campus-agent-runtime-v1-design.md §5.6-§5.9、§8.2、§9.2。
"""
from __future__ import annotations

from enum import Enum


class RunStatus(str, Enum):
    """Run 生命周期状态(§5.6)。"""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    PAUSED = "PAUSED"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RunPhase(str, Enum):
    """Run 当前阶段,独立于 RunStatus(§5.6)。"""

    CONTEXT_BUILDING = "CONTEXT_BUILDING"
    WAITING_FOR_MODEL = "WAITING_FOR_MODEL"
    VALIDATING_OUTPUT = "VALIDATING_OUTPUT"
    WAITING_FOR_TOOL = "WAITING_FOR_TOOL"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    PERSISTING_RESULT = "PERSISTING_RESULT"
    RECOVERY_CHECKING = "RECOVERY_CHECKING"
    IDLE = "IDLE"
    # 状态驱动干预的阶段进度。只能追加在末尾：客户端对未知 phase 安全降级。
    STATE_ANALYSIS = "STATE_ANALYSIS"
    STRATEGY_SELECTION = "STRATEGY_SELECTION"
    INTERVENTION_RECORD = "INTERVENTION_RECORD"
    PLAN_GENERATION = "PLAN_GENERATION"


class RiskLevel(str, Enum):
    """动作风险分级(§5.5)。"""

    AUTO_SAFE = "AUTO_SAFE"
    CONFIRM_REQUIRED = "CONFIRM_REQUIRED"
    MANUAL_ONLY = "MANUAL_ONLY"


class ApprovalStatus(str, Enum):
    """审批状态(§5.5)。过期绝不等于批准。"""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class AgentEventType(str, Enum):
    """SSE 事件类型(§5.7)。"""

    RUN_QUEUED = "RUN_QUEUED"
    RUN_STARTED = "RUN_STARTED"
    CONTEXT_READY = "CONTEXT_READY"
    MODEL_STARTED = "MODEL_STARTED"
    MODEL_COMPLETED = "MODEL_COMPLETED"
    MODEL_FALLBACK = "MODEL_FALLBACK"
    TOOL_STARTED = "TOOL_STARTED"
    TOOL_COMPLETED = "TOOL_COMPLETED"
    TOOL_FAILED = "TOOL_FAILED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVAL_RESOLVED = "APPROVAL_RESOLVED"
    ARTIFACT_CREATED = "ARTIFACT_CREATED"
    RUN_PARTIAL = "RUN_PARTIAL"
    RUN_COMPLETED = "RUN_COMPLETED"
    RUN_FAILED = "RUN_FAILED"
    RUN_CANCELLED = "RUN_CANCELLED"
    RUN_PAUSED = "RUN_PAUSED"
    RUN_RESUMED = "RUN_RESUMED"
    RUN_RETRIED = "RUN_RETRIED"
    # v2 追加:恢复与重试语义。只能加在末尾,客户端对未知类型安全降级。
    RUN_RETRY_SCHEDULED = "RUN_RETRY_SCHEDULED"
    RUN_RECOVERY_STARTED = "RUN_RECOVERY_STARTED"
    RUN_RECOVERED = "RUN_RECOVERED"
    # 审批通过、原 Run 重新排队时发出。
    # 注意：`agent_runtime` 审批路由与 `ToolInvocationGateway` 一直在发这个类型，
    # 但它曾经**不在**本枚举里 —— 于是 SSE 把它序列化成 AgentEventOut 时直接
    # ValidationError，学生看不到"审批已通过、继续执行"的事件。
    # 新增类型一律追加在末尾（客户端对未知类型安全降级）。
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    # 状态驱动干预的阶段进度：状态分析 → 策略选择 → 干预记录 → 计划生成。
    # 同样只能追加在末尾。事件 summary 只带枚举码与不透明 id，不带原始内容。
    STATE_ANALYZED = "STATE_ANALYZED"
    STRATEGY_SELECTED = "STRATEGY_SELECTED"
    INTERVENTION_RECORDED = "INTERVENTION_RECORDED"
    PLAN_GENERATED = "PLAN_GENERATED"


class ArtifactType(str, Enum):
    """产物类型(§5.9)。"""

    FINAL_REVIEW_PLAN = "FINAL_REVIEW_PLAN"
    DAILY_AGENDA = "DAILY_AGENDA"
    NOTICE_CHECKLIST = "NOTICE_CHECKLIST"
    COURSE_RESEARCH_REPORT = "COURSE_RESEARCH_REPORT"
    CITATION_BUNDLE = "CITATION_BUNDLE"


class SourcePolicy(str, Enum):
    """课程研究来源策略(§8.2)。"""

    COURSE_MATERIAL_PRIORITY = "COURSE_MATERIAL_PRIORITY"
    ALLOW_WEB = "ALLOW_WEB"
    ALLOW_USER_UPLOAD = "ALLOW_USER_UPLOAD"


class AcademicPolicy(str, Enum):
    """学术策略(§8.2)。客户端输入不得强制 ALLOWED。"""

    ALLOWED = "ALLOWED"
    LIMITED = "LIMITED"
    EXAM_RESTRICTED = "EXAM_RESTRICTED"
    AI_PROHIBITED = "AI_PROHIBITED"
    UNKNOWN = "UNKNOWN"


class AssistanceMode(str, Enum):
    """课程研究辅助模式(§8.2)。FULL_SOLUTION 仅在策略允许的普通练习中可用。"""

    HINT = "HINT"
    EXPLAIN = "EXPLAIN"
    REVIEW = "REVIEW"
    FULL_SOLUTION = "FULL_SOLUTION"


class ModelRoutePolicy(str, Enum):
    """模型路由策略(§6)。"""

    REASONING_PRIMARY = "reasoning_primary"
    FAST_STRUCTURED = "fast_structured"
    DUAL_REVIEW = "dual_review"


class AgentErrorCode(str, Enum):
    """稳定错误码(§9.2)。HTTP 状态码表达传输/鉴权/冲突语义,客户端按 code 分支。"""

    AGENT_INVALID_STATE = "AGENT_INVALID_STATE"
    AGENT_PERMISSION_DENIED = "AGENT_PERMISSION_DENIED"
    AGENT_TOOL_REJECTED = "AGENT_TOOL_REJECTED"
    AGENT_APPROVAL_REQUIRED = "AGENT_APPROVAL_REQUIRED"
    AGENT_PROVIDER_UNAVAILABLE = "AGENT_PROVIDER_UNAVAILABLE"
    AGENT_CONTEXT_EXPIRED = "AGENT_CONTEXT_EXPIRED"
    AGENT_IDEMPOTENCY_CONFLICT = "AGENT_IDEMPOTENCY_CONFLICT"
    AGENT_RUN_NOT_FOUND = "AGENT_RUN_NOT_FOUND"
    AGENT_RUN_CANCELLED = "AGENT_RUN_CANCELLED"
    AGENT_OUTPUT_SCHEMA_INVALID = "AGENT_OUTPUT_SCHEMA_INVALID"
    AGENT_SOURCE_POLICY_VIOLATION = "AGENT_SOURCE_POLICY_VIOLATION"
    AGENT_ACADEMIC_POLICY_RESTRICTED = "AGENT_ACADEMIC_POLICY_RESTRICTED"
    # v2 追加:只能加在末尾,不得复用 provider 错误掩盖 runtime 状态。
    AGENT_CAPABILITY_DISABLED = "AGENT_CAPABILITY_DISABLED"
    AGENT_RUNTIME_UNAVAILABLE = "AGENT_RUNTIME_UNAVAILABLE"
    AGENT_CURSOR_INVALID = "AGENT_CURSOR_INVALID"


# 冻结的契约版本号。客户端可据此判断兼容性。
AGENT_CONTRACT_VERSION = "v1"


__all__ = [
    "AGENT_CONTRACT_VERSION",
    "RunStatus",
    "RunPhase",
    "RiskLevel",
    "ApprovalStatus",
    "AgentEventType",
    "ArtifactType",
    "SourcePolicy",
    "AcademicPolicy",
    "AssistanceMode",
    "ModelRoutePolicy",
    "AgentErrorCode",
]
