"""CampusAgentRuntime 契约测试。

验证:
- schema 拒绝隐藏字段(extra="forbid")
- 错误信封包含 request_id
- fixture round-trip 验证
- 枚举值冻结
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.agent_contract_enums import (
    AGENT_CONTRACT_VERSION,
    AcademicPolicy,
    AgentErrorCode,
    AgentEventType,
    ApprovalStatus,
    ArtifactType,
    RiskLevel,
    RunPhase,
    RunStatus,
)
from app.schemas.agent_observability import (
    AgentRunTraceOut,
    AgentRuntimeOverviewOut,
)
from app.schemas.agent_runtime import (
    AgentApprovalOut,
    AgentArtifactOut,
    AgentCapabilitiesOut,
    AgentCapabilityOut,
    AgentContextSnapshotOut,
    AgentErrorEnvelope,
    AgentEventOut,
    AgentJobOut,
    AgentMemoryOut,
    AgentModelCallOut,
    AgentRunOut,
    AgentToolCallOut,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "agent_runtime" / "v1"


# ===== 枚举冻结 =====


def test_contract_version_is_v1() -> None:
    assert AGENT_CONTRACT_VERSION == "v1"


@pytest.mark.parametrize(
    "enum_cls,expected",
    [
        (
            RunStatus,
            {
                "QUEUED",
                "RUNNING",
                "AWAITING_APPROVAL",
                "PAUSED",
                "SUCCEEDED",
                "PARTIAL",
                "FAILED",
                "CANCELLED",
            },
        ),
        (
            RunPhase,
            {
                "CONTEXT_BUILDING",
                "WAITING_FOR_MODEL",
                "VALIDATING_OUTPUT",
                "WAITING_FOR_TOOL",
                "WAITING_FOR_APPROVAL",
                "PERSISTING_RESULT",
                "RECOVERY_CHECKING",
                "IDLE",
            },
        ),
        (RiskLevel, {"AUTO_SAFE", "CONFIRM_REQUIRED", "MANUAL_ONLY"}),
        (ApprovalStatus, {"PENDING", "APPROVED", "REJECTED", "EXPIRED"}),
        (
            AgentEventType,
            {
                "RUN_QUEUED",
                "RUN_STARTED",
                "CONTEXT_READY",
                "MODEL_STARTED",
                "MODEL_COMPLETED",
                "MODEL_FALLBACK",
                "TOOL_STARTED",
                "TOOL_COMPLETED",
                "TOOL_FAILED",
                "APPROVAL_REQUIRED",
                "APPROVAL_RESOLVED",
                "ARTIFACT_CREATED",
                "RUN_PARTIAL",
                "RUN_COMPLETED",
                "RUN_FAILED",
                "RUN_CANCELLED",
                "RUN_PAUSED",
                    "RUN_RESUMED",
                    "RUN_RETRIED",
                    "RUN_RETRY_SCHEDULED",
                    "RUN_RECOVERY_STARTED",
                    "RUN_RECOVERED",
            },
        ),
        (
            ArtifactType,
            {
                "FINAL_REVIEW_PLAN",
                "DAILY_AGENDA",
                "NOTICE_CHECKLIST",
                "COURSE_RESEARCH_REPORT",
                "CITATION_BUNDLE",
            },
        ),
        (
            AcademicPolicy,
            {"ALLOWED", "LIMITED", "EXAM_RESTRICTED", "AI_PROHIBITED", "UNKNOWN"},
        ),
    ],
)
def test_enum_values_frozen(enum_cls, expected) -> None:
    actual = {member.value for member in enum_cls}
    assert actual == expected, f"{enum_cls.__name__} 枚举值被改动"


def test_agent_error_codes_frozen() -> None:
    expected = {
        "AGENT_INVALID_STATE",
        "AGENT_PERMISSION_DENIED",
        "AGENT_TOOL_REJECTED",
        "AGENT_APPROVAL_REQUIRED",
        "AGENT_PROVIDER_UNAVAILABLE",
        "AGENT_CONTEXT_EXPIRED",
        "AGENT_IDEMPOTENCY_CONFLICT",
        "AGENT_RUN_NOT_FOUND",
        "AGENT_RUN_CANCELLED",
        "AGENT_OUTPUT_SCHEMA_INVALID",
        "AGENT_SOURCE_POLICY_VIOLATION",
        "AGENT_ACADEMIC_POLICY_RESTRICTED",
        # v2 追加:能力准入、runtime 不可用、SSE 游标无效
        "AGENT_CAPABILITY_DISABLED",
        "AGENT_RUNTIME_UNAVAILABLE",
        "AGENT_CURSOR_INVALID",
    }
    actual = {member.value for member in AgentErrorCode}
    assert actual == expected


# ===== extra="forbid" =====


def test_error_envelope_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AgentErrorEnvelope(
            code="AGENT_RUN_NOT_FOUND",
            message="not found",
            request_id="req_1",
            hidden_prompt="secret",  # type: ignore[call-arg]
        )


def test_event_out_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AgentEventOut(
            id="evt_1",
            type="RUN_STARTED",
            run_id="run_1",
            sequence=1,
            status="RUNNING",
            phase="IDLE",
            raw_model_response="secret",  # type: ignore[call-arg]
            created_at="2026-09-12T10:00:00+08:00",
        )


def test_run_out_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AgentRunOut(
            run_id="run_1",
            job_id="job_1",
            user_id="user_1",
            status="RUNNING",
            phase="IDLE",
            created_at="2026-09-12T10:00:00+08:00",
            updated_at="2026-09-12T10:00:00+08:00",
            full_prompt="secret",  # type: ignore[call-arg]
        )


def test_artifact_out_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AgentArtifactOut(
            artifact_id="art_1",
            run_id="run_1",
            user_id="user_1",
            artifact_type="FINAL_REVIEW_PLAN",
            version=1,
            mime_type="application/json",
            size_bytes=100,
            content_hash="sha256:abc",
            created_at="2026-09-12T10:00:00+08:00",
            internal_path="/secret",  # type: ignore[call-arg]
        )


def test_model_call_out_has_no_prompt_or_raw_fields() -> None:
    fields = set(AgentModelCallOut.model_fields.keys())
    forbidden = {"prompt", "raw_response", "hidden_reasoning", "messages"}
    assert not (fields & forbidden), f"模型调用摘要包含敏感字段: {fields & forbidden}"


def test_tool_call_out_has_no_sensitive_args() -> None:
    fields = set(AgentToolCallOut.model_fields.keys())
    forbidden = {"request_args", "result_body", "raw_result", "prompt"}
    assert not (fields & forbidden), f"工具调用摘要包含敏感字段: {fields & forbidden}"


# ===== request_id 必填 =====


def test_error_envelope_requires_request_id() -> None:
    with pytest.raises(ValidationError):
        AgentErrorEnvelope(code="AGENT_RUN_NOT_FOUND", message="not found")  # type: ignore[call-arg]


def test_error_envelope_accepts_valid() -> None:
    env = AgentErrorEnvelope(
        code="AGENT_APPROVAL_REQUIRED",
        message="需要确认",
        request_id="req_abc",
        details={"run_id": "run_1"},
    )
    assert env.code == AgentErrorCode.AGENT_APPROVAL_REQUIRED
    assert env.request_id == "req_abc"


# ===== fixture round-trip =====


@pytest.mark.parametrize(
    "fixture_name",
    ["runtime.json", "final_review.json", "course_research.json", "notice_workflow.json"],
)
def test_fixture_contract_version_is_v1(fixture_name: str) -> None:
    data = json.loads((FIXTURE_DIR / fixture_name).read_text(encoding="utf-8"))
    assert data["contract_version"] == "v1"


def test_runtime_fixture_round_trip() -> None:
    data = json.loads((FIXTURE_DIR / "runtime.json").read_text(encoding="utf-8"))
    AgentJobOut(**data["job"])
    AgentRunOut(**data["run"])
    for evt in data["events"]:
        AgentEventOut(**evt)
    AgentApprovalOut(**data["approval"])
    AgentArtifactOut(**data["artifact"])
    AgentErrorEnvelope(**data["error_envelope"])


def test_runtime_fixture_v2_increments_round_trip() -> None:
    """v2 增量契约与 v1 共用同一份 fixture,四端据此避免各自手写漂移。"""
    data = json.loads((FIXTURE_DIR / "runtime.json").read_text(encoding="utf-8"))
    v2 = data["v2"]

    # 202 创建:只有入队保证,创建响应里没有 plan_id
    creation = v2["creation_202"]
    assert creation["http_status"] == 202
    AgentJobOut(**creation["job"])
    assert creation["job"]["status"] == "QUEUED"
    assert "plan_id" not in creation["job"]["input_ref"]
    assert creation["job"]["latest_run_id"]

    # 幂等重放与冲突
    assert v2["idempotent_replay"]["http_status"] == 200
    assert v2["idempotent_replay"]["replayed"] is True
    conflict = AgentErrorEnvelope(**v2["idempotency_conflict"]["error_envelope"])
    assert conflict.code.value == "AGENT_IDEMPOTENCY_CONFLICT"
    assert v2["idempotency_conflict"]["http_status"] == 409

    # 能力准入与 runtime 不可用的稳定映射
    disabled = AgentErrorEnvelope(**v2["capability_disabled"]["error_envelope"])
    assert disabled.code.value == "AGENT_CAPABILITY_DISABLED"
    assert v2["capability_disabled"]["http_status"] == 409
    unavailable = AgentErrorEnvelope(**v2["runtime_unavailable"]["error_envelope"])
    assert unavailable.code.value == "AGENT_RUNTIME_UNAVAILABLE"
    assert v2["runtime_unavailable"]["http_status"] == 503

    # 游标失效:客户端必须能识别并改走 REST 全量归并
    cursor = AgentErrorEnvelope(**v2["cursor_invalid"]["error_envelope"])
    assert cursor.code.value == "AGENT_CURSOR_INVALID"
    assert v2["cursor_invalid"]["http_status"] == 409

    # 恢复事件全部是合法的 AgentEventOut
    assert {e["type"] for e in v2["recovery_events"]} == {
        "RUN_RETRY_SCHEDULED", "RUN_RECOVERY_STARTED", "RUN_RECOVERED",
    }
    for event in v2["recovery_events"]:
        AgentEventOut(**event)

    # 未知未来事件:不得进入强类型校验,客户端按"记录游标、不提升权限、不崩溃"降级
    unknown = v2["unknown_future_event"]["frame"]
    assert unknown["event"] not in {member.value for member in AgentEventType}
    assert unknown["data"]["sequence"] == 99


def test_admin_observability_fixture_is_privacy_safe() -> None:
    """管理员观测 fixture 与真实响应一样脱敏。"""
    data = json.loads((FIXTURE_DIR / "runtime.json").read_text(encoding="utf-8"))
    observability = data["v2"]["admin_observability"]
    AgentRuntimeOverviewOut(**observability["overview"])
    AgentRunTraceOut(**observability["run_trace"])

    # 只扫描实际响应体;comment 是给人看的说明,不算载荷。
    serialized = json.dumps(
        {"overview": observability["overview"], "run_trace": observability["run_trace"]},
        ensure_ascii=False,
    )
    for forbidden in (
        "prompt", "model_response", "credential", "memory_content",
        "raw_arguments", "hidden_reasoning", "arguments",
    ):
        assert forbidden not in serialized, f"观测 fixture 不得包含 {forbidden}"


def test_final_review_fixture_round_trip() -> None:
    data = json.loads((FIXTURE_DIR / "final_review.json").read_text(encoding="utf-8"))
    AgentJobOut(**data["job"])
    AgentRunOut(**data["run"])
    for evt in data["events"]:
        AgentEventOut(**evt)
    AgentArtifactOut(**data["artifact"])


def test_course_research_fixture_round_trip() -> None:
    data = json.loads((FIXTURE_DIR / "course_research.json").read_text(encoding="utf-8"))
    AgentJobOut(**data["job"])
    AgentRunOut(**data["run"])
    for evt in data["events"]:
        AgentEventOut(**evt)
    AgentArtifactOut(**data["artifact"])


def test_notice_workflow_fixture_round_trip() -> None:
    data = json.loads((FIXTURE_DIR / "notice_workflow.json").read_text(encoding="utf-8"))
    AgentJobOut(**data["job"])
    AgentRunOut(**data["run"])
    for evt in data["events"]:
        AgentEventOut(**evt)
    AgentApprovalOut(**data["approval"])
    AgentErrorEnvelope(**data["error_envelope"])


# ===== 能力声明 =====


def test_capabilities_out_round_trip() -> None:
    caps = AgentCapabilitiesOut(
        capabilities=[
            AgentCapabilityOut(
                name="final_review.plan",
                version="1.0",
                route_policy="reasoning_primary",
                risk_level="CONFIRM_REQUIRED",
                requires_approval=True,
            ),
            AgentCapabilityOut(
                name="notice.extract",
                version="1.0",
                route_policy="fast_structured",
                risk_level="AUTO_SAFE",
                requires_approval=False,
            ),
        ]
    )
    assert caps.contract_version == "v1"
    assert len(caps.capabilities) == 2


# ===== 上下文快照 =====


def test_context_snapshot_round_trip() -> None:
    snap = AgentContextSnapshotOut(
        snapshot_id="ctx_1",
        scope={"user_id": "user_1", "course_ids": ["c1"], "campaign_id": None},
        facts={"daily_capacity_minutes": 120},
        source_refs=["exam:1", "task:2"],
        source_digest="sha256:abc",
        generated_at="2026-09-12T10:00:00+08:00",
        valid_until="2026-09-12T10:15:00+08:00",
    )
    assert snap.scope.user_id == "user_1"


# ===== 记忆 =====


def test_memory_kind_is_allowlisted() -> None:
    AgentMemoryOut(
        memory_id="mem_1",
        user_id="user_1",
        kind="CONFIRMED_PREFERENCE",
        content_summary="偏好晚上学习",
        sensitivity="low",
        confirmed=True,
        created_at="2026-09-12T10:00:00+08:00",
    )
    with pytest.raises(ValidationError):
        AgentMemoryOut(
            memory_id="mem_2",
            user_id="user_1",
            kind="RAW_CONVERSATION",  # 不在允许列表
            content_summary="x",
            sensitivity="low",
            confirmed=True,
            created_at="2026-09-12T10:00:00+08:00",
        )
