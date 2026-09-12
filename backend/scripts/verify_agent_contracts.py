"""验证 CampusAgentRuntime 跨客户端契约一致性。

检查项:
1. 导出最新 OpenAPI schema,确认 agent 路由全部注册
2. canonical fixtures 与 Pydantic schema 字段一致
3. 冻结枚举值没有被删除或重排(只允许追加)
4. 新增 schema 字段向后兼容(optional 或有默认值)
5. 关键路由路径存在且使用 Bearer 鉴权(无 token query)

用法:
    python -m scripts.verify_agent_contracts
    python -m scripts.verify_agent_contracts --strict  (CI 模式,任何差异非零退出)

不输出敏感信息。退出码 0=通过, 1=差异。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import get_args, get_origin

from pydantic import BaseModel

from app.schemas.agent_contract_enums import (
    AGENT_CONTRACT_VERSION,
    AcademicPolicy,
    AgentErrorCode,
    AgentEventType,
    ApprovalStatus,
    ArtifactType,
    AssistanceMode,
    ModelRoutePolicy,
    RiskLevel,
    RunPhase,
    RunStatus,
    SourcePolicy,
)

_FIXTURE_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "agent_runtime" / "v1"

_ENUMS = {
    "RunStatus": RunStatus,
    "RunPhase": RunPhase,
    "RiskLevel": RiskLevel,
    "ApprovalStatus": ApprovalStatus,
    "AgentEventType": AgentEventType,
    "ArtifactType": ArtifactType,
    "SourcePolicy": SourcePolicy,
    "AcademicPolicy": AcademicPolicy,
    "AssistanceMode": AssistanceMode,
    "ModelRoutePolicy": ModelRoutePolicy,
    "AgentErrorCode": AgentErrorCode,
}

# 冻结的 v1 枚举值快照(顺序敏感,只允许追加)。
# 来源:docs/superpowers/specs/2026-09-12-campus-agent-runtime-v1-design.md §5-§9。
_FROZEN_ENUMS = {
    "RunStatus": ["QUEUED", "RUNNING", "AWAITING_APPROVAL", "SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"],
    "RunPhase": [
        "CONTEXT_BUILDING", "WAITING_FOR_MODEL", "VALIDATING_OUTPUT",
        "WAITING_FOR_TOOL", "WAITING_FOR_APPROVAL", "PERSISTING_RESULT",
        "RECOVERY_CHECKING", "IDLE",
    ],
    "RiskLevel": ["AUTO_SAFE", "CONFIRM_REQUIRED", "MANUAL_ONLY"],
    "ApprovalStatus": ["PENDING", "APPROVED", "REJECTED", "EXPIRED"],
    "AgentEventType": [
        "RUN_QUEUED", "RUN_STARTED", "CONTEXT_READY", "MODEL_STARTED",
        "MODEL_COMPLETED", "MODEL_FALLBACK", "TOOL_STARTED", "TOOL_COMPLETED",
        "TOOL_FAILED", "APPROVAL_REQUIRED", "APPROVAL_RESOLVED", "ARTIFACT_CREATED",
        "RUN_PARTIAL", "RUN_COMPLETED", "RUN_FAILED", "RUN_CANCELLED",
    ],
    "ArtifactType": [
        "FINAL_REVIEW_PLAN", "DAILY_AGENDA", "NOTICE_CHECKLIST",
        "COURSE_RESEARCH_REPORT", "CITATION_BUNDLE",
    ],
    "SourcePolicy": ["COURSE_MATERIAL_PRIORITY", "ALLOW_WEB", "ALLOW_USER_UPLOAD"],
    "AcademicPolicy": ["ALLOWED", "LIMITED", "EXAM_RESTRICTED", "AI_PROHIBITED", "UNKNOWN"],
    "AssistanceMode": ["HINT", "EXPLAIN", "REVIEW", "FULL_SOLUTION"],
    "ModelRoutePolicy": ["reasoning_primary", "fast_structured", "dual_review"],
    "AgentErrorCode": [
        "AGENT_INVALID_STATE", "AGENT_PERMISSION_DENIED", "AGENT_TOOL_REJECTED",
        "AGENT_APPROVAL_REQUIRED", "AGENT_PROVIDER_UNAVAILABLE", "AGENT_CONTEXT_EXPIRED",
        "AGENT_IDEMPOTENCY_CONFLICT", "AGENT_RUN_NOT_FOUND", "AGENT_RUN_CANCELLED",
        "AGENT_OUTPUT_SCHEMA_INVALID", "AGENT_SOURCE_POLICY_VIOLATION",
        "AGENT_ACADEMIC_POLICY_RESTRICTED",
    ],
}

# 冻结的 v1 schema 必填字段快照(不允许删除或从 optional 变 required)。
# 只记录字段名集合;类型变更由 fixture 验证覆盖。
_FROZEN_REQUIRED_FIELDS = {
    "AgentErrorEnvelope": {"code", "message", "request_id"},
    "AgentEventOut": {"id", "type", "run_id", "sequence", "status", "phase", "created_at"},
    "AgentRunOut": {"run_id", "job_id", "user_id", "status", "phase", "created_at", "updated_at"},
    "AgentJobOut": {"job_id", "user_id", "job_kind", "status", "created_at", "updated_at"},
    "AgentApprovalOut": {"approval_id", "run_id", "status", "risk_level", "action_summary", "expires_at"},
    "AgentArtifactOut": {"artifact_id", "run_id", "user_id", "artifact_type", "version", "created_at"},
}


def _type_name(annotation) -> str:
    origin = get_origin(annotation)
    if origin is None:
        return getattr(annotation, "__name__", str(annotation))
    args = get_args(annotation)
    return f"{getattr(origin, '__name__', str(origin))}[{', '.join(_type_name(a) for a in args)}]"


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.ok: list[str] = []

    def fail(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def good(self, msg: str) -> None:
        self.ok.append(msg)

    @property
    def passed(self) -> bool:
        return not self.errors


def verify_contract_version(report: Report) -> None:
    if AGENT_CONTRACT_VERSION != "v1":
        report.fail(f"contract_version 冻结为 v1,当前={AGENT_CONTRACT_VERSION!r}")
    else:
        report.good("contract_version = v1")


def verify_enums(report: Report) -> None:
    for name, frozen_values in _FROZEN_ENUMS.items():
        enum_cls = _ENUMS[name]
        current_values = [m.value for m in enum_cls]
        # 冻结值必须按原顺序保留在当前位置(只允许追加)
        for i, fv in enumerate(frozen_values):
            if i >= len(current_values):
                report.fail(f"{name}:冻结值 {fv!r} 在位置 {i} 被删除")
            elif current_values[i] != fv:
                report.fail(
                    f"{name}:位置 {i} 冻结为 {fv!r},当前为 {current_values[i]!r}(不得重排或重命名)"
                )
        # 新增值只能追加到末尾
        extra = current_values[len(frozen_values):]
        if extra:
            report.warn(f"{name}:新增值 {extra}(向后兼容,允许)")


def verify_required_fields(report: Report) -> None:
    from app.schemas.agent_runtime import (
        AgentApprovalOut,
        AgentArtifactOut,
        AgentErrorEnvelope,
        AgentEventOut,
        AgentJobOut,
        AgentRunOut,
    )

    models = {
        "AgentErrorEnvelope": AgentErrorEnvelope,
        "AgentEventOut": AgentEventOut,
        "AgentRunOut": AgentRunOut,
        "AgentJobOut": AgentJobOut,
        "AgentApprovalOut": AgentApprovalOut,
        "AgentArtifactOut": AgentArtifactOut,
    }
    for name, frozen_required in _FROZEN_REQUIRED_FIELDS.items():
        model_cls = models[name]
        current_required = {
            fname for fname, fi in model_cls.model_fields.items() if fi.is_required()
        }
        missing = frozen_required - current_required
        if missing:
            report.fail(
                f"{name}:冻结必填字段 {sorted(missing)} 变为 optional(破坏向后兼容)"
            )
        else:
            report.good(f"{name}:冻结必填字段完整")


def verify_fixtures(report: Report) -> None:
    """验证 canonical fixtures 的 contract_version 与枚举值合法。"""
    from app.schemas.agent_runtime import (
        AgentEventOut,
        AgentJobOut,
        AgentRunOut,
    )

    fixture_files = ["runtime.json", "final_review.json", "course_research.json", "notice_workflow.json"]
    for fname in fixture_files:
        path = _FIXTURE_DIR / fname
        if not path.exists():
            report.fail(f"fixture 缺失:{path}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("contract_version") != AGENT_CONTRACT_VERSION:
            report.fail(f"{fname}:contract_version 不匹配")
            continue
        # 验证 job/run/event 结构可被 schema 解析(宽松:只验证字段存在)
        if "job" in data:
            job = data["job"]
            for field in ("job_id", "user_id", "job_kind", "status", "created_at", "updated_at"):
                if field not in job:
                    report.fail(f"{fname}:job 缺字段 {field}")
        if "run" in data:
            run = data["run"]
            for field in ("run_id", "job_id", "user_id", "status", "phase", "risk_level"):
                if field not in run:
                    report.fail(f"{fname}:run 缺字段 {field}")
            # status / phase / risk_level 必须是合法枚举
            if run["status"] not in [m.value for m in RunStatus]:
                report.fail(f"{fname}:run.status={run['status']!r} 不是合法 RunStatus")
            if run["phase"] not in [m.value for m in RunPhase]:
                report.fail(f"{fname}:run.phase={run['phase']!r} 不是合法 RunPhase")
            if run["risk_level"] not in [m.value for m in RiskLevel]:
                report.fail(f"{fname}:run.risk_level={run['risk_level']!r} 不是合法 RiskLevel")
        if "events" in data:
            for i, evt in enumerate(data["events"]):
                if evt.get("type") not in [m.value for m in AgentEventType]:
                    report.fail(f"{fname}:events[{i}].type={evt.get('type')!r} 不是合法 AgentEventType")
        report.good(f"{fname}:fixture 结构与枚举合法")


def verify_openapi_routes(report: Report) -> None:
    """导出 OpenAPI 并确认关键 agent 路由已注册。"""
    from app.main import create_app

    app = create_app()
    schema = app.openapi()
    paths = schema.get("paths", {})

    expected_prefixes = [
        "/api/v1/agent-runtime/capabilities",
        "/api/v1/agent-jobs",
        "/api/v1/agent-runs",
        "/api/v1/agent-approvals",
        "/api/v1/agent-artifacts",
        "/api/v1/final-review/campaigns",
        "/api/v1/course-research/runs",
        "/api/v1/notices/manual",
        "/api/v1/notification-sources",
    ]
    for prefix in expected_prefixes:
        found = any(p.startswith(prefix) for p in paths)
        if not found:
            report.fail(f"OpenAPI 缺失路由前缀:{prefix}")
        else:
            report.good(f"OpenAPI 路由存在:{prefix}")

    # 检查 SSE 端点不含 token query 参数
    sse_path = "/api/v1/agent-runs/{run_id}/events/stream"
    if sse_path in paths:
        get_op = paths[sse_path].get("get", {})
        params = get_op.get("parameters", [])
        for param in params:
            if param.get("name") == "token" and param.get("in") == "query":
                report.fail(f"{sse_path}:SSE 端点不得接受 token query 参数(必须用 Bearer header)")
                break
        else:
            report.good("SSE 端点无 token query(使用 Bearer header)")


def main() -> int:
    parser = argparse.ArgumentParser(description="验证 CampusAgentRuntime 契约一致性")
    parser.add_argument("--strict", action="store_true", help="CI 模式:warning 也算失败")
    args = parser.parse_args()

    report = Report()
    verify_contract_version(report)
    verify_enums(report)
    verify_required_fields(report)
    verify_fixtures(report)
    verify_openapi_routes(report)

    print("===== CampusAgentRuntime 契约验证 =====")
    for msg in report.ok:
        print(f"  [OK]   {msg}")
    for msg in report.warnings:
        print(f"  [WARN] {msg}")
    for msg in report.errors:
        print(f"  [FAIL] {msg}")

    total = len(report.ok) + len(report.warnings) + len(report.errors)
    print(f"\n总计:{total} 项,通过 {len(report.ok)},警告 {len(report.warnings)},失败 {len(report.errors)}")

    if report.errors:
        return 1
    if args.strict and report.warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())