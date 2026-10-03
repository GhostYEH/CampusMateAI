"""通知来源注册表(§7.3、§8.3)。

服务端拥有稳定的来源代码。`automation_enabled` 默认关闭,
用户可按来源启用,但批准只对指定 action 生效,不扩大为永久授权。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ...repositories.notice_workflow_repository import NoticeWorkflowRepository


@dataclass(frozen=True)
class SourceDescriptor:
    """来源的代码级声明(不可变)。"""

    code: str
    display_name: str
    kind: str
    default_automation: bool = False
    permission_scope: str = "student_owned"


# 冻结的来源注册表。顺序稳定,新增只能追加。
_REGISTRY: tuple[SourceDescriptor, ...] = (
    SourceDescriptor("android_system", "Android 系统通知", "SYSTEM"),
    SourceDescriptor("chaoxing", "学习通", "LEARNING_PLATFORM"),
    SourceDescriptor("campus_announcement", "校园公告", "OFFICIAL_ACCOUNT"),
    SourceDescriptor("manual_input", "手动输入", "MANUAL"),
)


def descriptor_for_code(code: str) -> Optional[SourceDescriptor]:
    for d in _REGISTRY:
        if d.code == code:
            return d
    return None


def ensure_sources_seeded(repo: NoticeWorkflowRepository) -> None:
    """幂等播种 notification_sources 表。仅在表为空时写入默认来源。"""
    existing = repo.list_sources()
    if existing:
        return
    for d in _REGISTRY:
        repo.create_source(
            code=d.code,
            display_name=d.display_name,
            kind=d.kind,
            automation_enabled=d.default_automation,
            permission_scope=d.permission_scope,
        )


__all__ = [
    "SourceDescriptor",
    "descriptor_for_code",
    "ensure_sources_seeded",
]