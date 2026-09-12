"""导出 CampusAgentRuntime 契约(JSON)供客户端解析测试使用。

输出包含:
- contract_version
- 所有枚举值
- Pydantic 模型字段签名(名称 + 类型 + 是否必填)

用法:
    python scripts/export_agent_contracts.py
    python scripts/export_agent_contracts.py --output contracts.json

不输出任何敏感默认值或凭据。
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
from app.schemas.agent_runtime import (
    AgentApprovalDecisionIn,
    AgentApprovalOut,
    AgentArtifactOut,
    AgentCapabilitiesOut,
    AgentCapabilityOut,
    AgentContextSnapshotOut,
    AgentErrorEnvelope,
    AgentEventOut,
    AgentJobCreateIn,
    AgentJobOut,
    AgentMemoryOut,
    AgentModelCallOut,
    AgentProgressOut,
    AgentRoleOut,
    AgentRunCancelIn,
    AgentRunOut,
    AgentToolCallOut,
    AgentToolOut,
    CourseResearchPolicyIn,
    NoticeManualIn,
)

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

_MODELS = {
    "AgentErrorEnvelope": AgentErrorEnvelope,
    "AgentProgressOut": AgentProgressOut,
    "AgentEventOut": AgentEventOut,
    "AgentApprovalOut": AgentApprovalOut,
    "AgentApprovalDecisionIn": AgentApprovalDecisionIn,
    "AgentArtifactOut": AgentArtifactOut,
    "AgentJobCreateIn": AgentJobCreateIn,
    "AgentJobOut": AgentJobOut,
    "AgentRunOut": AgentRunOut,
    "AgentRunCancelIn": AgentRunCancelIn,
    "AgentCapabilityOut": AgentCapabilityOut,
    "AgentCapabilitiesOut": AgentCapabilitiesOut,
    "AgentContextSnapshotOut": AgentContextSnapshotOut,
    "AgentMemoryOut": AgentMemoryOut,
    "AgentRoleOut": AgentRoleOut,
    "AgentToolOut": AgentToolOut,
    "AgentModelCallOut": AgentModelCallOut,
    "AgentToolCallOut": AgentToolCallOut,
    "CourseResearchPolicyIn": CourseResearchPolicyIn,
    "NoticeManualIn": NoticeManualIn,
}


def _type_name(annotation) -> str:
    origin = get_origin(annotation)
    if origin is None:
        return getattr(annotation, "__name__", str(annotation))
    args = get_args(annotation)
    return f"{getattr(origin, '__name__', str(origin))}[{', '.join(_type_name(a) for a in args)}]"


def _model_schema(model_cls: type[BaseModel]) -> dict:
    fields = {}
    for name, field_info in model_cls.model_fields.items():
        fields[name] = {
            "type": _type_name(field_info.annotation),
            "required": field_info.is_required(),
        }
    return {"fields": fields, "extra": "forbid"}


def export_contracts() -> dict:
    return {
        "contract_version": AGENT_CONTRACT_VERSION,
        "enums": {name: [m.value for m in cls] for name, cls in _ENUMS.items()},
        "models": {name: _model_schema(cls) for name, cls in _MODELS.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="导出 CampusAgentRuntime 契约")
    parser.add_argument("--output", "-o", default=None, help="输出文件路径(默认 stdout)")
    args = parser.parse_args()
    payload = export_contracts()
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"已导出到 {args.output}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())