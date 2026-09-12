"""通知工作流数据行模型 — notification_sources / notice_workflows / notice_workflow_actions。

设计要点(§7.3、§8.3):
- `notice_workflows` 绑定 user_id + notice_id,跨用户禁止访问。
- `content_fingerprint` 用于去重:同一用户同一指纹至多一个活跃工作流。
- `materials` / `steps` / `uncertainty` 以 JSON 数组字符串存储。
- Action 的 `params_json` 仅保存非敏感参数,绝不保存凭据或完整表单内容。
- 所有时间字段以 ISO 8601 字符串存储(带时区)。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NotificationSourceRow:
    source_id: str
    code: str
    display_name: str
    kind: str
    automation_enabled: bool = False
    permission_scope: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row) -> "NotificationSourceRow":
        return cls(
            source_id=row["source_id"],
            code=row["code"],
            display_name=row["display_name"],
            kind=row["kind"],
            automation_enabled=bool(row["automation_enabled"]),
            permission_scope=row["permission_scope"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class NoticeWorkflowRow:
    workflow_id: str
    user_id: str
    notice_id: str
    source_id: Optional[str] = None
    status: str = "CREATED"
    title: Optional[str] = None
    deadline: Optional[str] = None
    location: Optional[str] = None
    audience: Optional[str] = None
    materials_json: Optional[str] = None
    steps_json: Optional[str] = None
    source_evidence_json: Optional[str] = None
    confidence: float = 0.0
    uncertainty_json: Optional[str] = None
    content_fingerprint: str = ""
    idempotency_key: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    completed_at: Optional[str] = None
    expired_at: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "NoticeWorkflowRow":
        keys = row.keys()
        return cls(
            workflow_id=row["workflow_id"],
            user_id=row["user_id"],
            notice_id=row["notice_id"],
            source_id=row["source_id"],
            status=row["status"],
            title=row["title"],
            deadline=row["deadline"],
            location=row["location"],
            audience=row["audience"],
            materials_json=row["materials_json"],
            steps_json=row["steps_json"],
            source_evidence_json=row["source_evidence_json"],
            confidence=float(row["confidence"]) if row["confidence"] is not None else 0.0,
            uncertainty_json=row["uncertainty_json"],
            content_fingerprint=row["content_fingerprint"],
            idempotency_key=row["idempotency_key"] if "idempotency_key" in keys else None,
            error_code=row["error_code"] if "error_code" in keys else None,
            error_message=row["error_message"] if "error_message" in keys else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
            expired_at=row["expired_at"],
        )


@dataclass
class NoticeWorkflowActionRow:
    action_id: str
    workflow_id: str
    user_id: str
    action_type: str
    title: str
    risk_level: str
    status: str = "PROPOSED"
    params_json: Optional[str] = None
    result_json: Optional[str] = None
    idempotency_key: Optional[str] = None
    external_ref: Optional[str] = None
    expires_at: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    executed_at: Optional[str] = None
    completed_at: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "NoticeWorkflowActionRow":
        keys = row.keys()
        return cls(
            action_id=row["action_id"],
            workflow_id=row["workflow_id"],
            user_id=row["user_id"],
            action_type=row["action_type"],
            title=row["title"],
            risk_level=row["risk_level"],
            status=row["status"],
            params_json=row["params_json"],
            result_json=row["result_json"],
            idempotency_key=row["idempotency_key"] if "idempotency_key" in keys else None,
            external_ref=row["external_ref"] if "external_ref" in keys else None,
            expires_at=row["expires_at"] if "expires_at" in keys else None,
            error_code=row["error_code"] if "error_code" in keys else None,
            error_message=row["error_message"] if "error_message" in keys else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            executed_at=row["executed_at"] if "executed_at" in keys else None,
            completed_at=row["completed_at"] if "completed_at" in keys else None,
        )


__all__ = [
    "NotificationSourceRow",
    "NoticeWorkflowRow",
    "NoticeWorkflowActionRow",
]