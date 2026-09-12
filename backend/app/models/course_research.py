"""课程研究/作业辅助数据行模型(§7.4、§8.2)。

纯数据容器,与 `course_research_sessions / reports / sources` schema 对齐。
Run 生命周期仍由 agent_runs 承载,本模块只承载领域输入、策略、报告与来源关系。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CourseResearchSessionRow:
    """一次课程研究会话(绑定到 agent_run)。"""

    session_id: str
    run_id: str
    user_id: str
    course_id: Optional[str]
    question: str
    assistance_mode: str
    academic_policy: str
    source_policy_json: str
    status: str
    created_at: str
    updated_at: str
    job_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    finished_at: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class CourseResearchSourceRow:
    """研究来源(课程资料 / 公共 Web / 用户上传)。"""

    source_id: str
    session_id: str
    user_id: str
    source_type: str  # course_material / web / user_upload
    title: str
    url: Optional[str]
    accessed_at: str
    created_at: str
    snippet: Optional[str] = None
    source_ref: Optional[str] = None  # 课程内容 item_id 或 URL 规范化形式
    is_verified: bool = False
    verification_note: Optional[str] = None
    supports_claim: Optional[bool] = None
    is_fabricated: bool = False
    metadata_json: str = "{}"


@dataclass
class CourseResearchReportRow:
    """研究报告产物引用(指向 agent_artifact)。"""

    report_id: str
    session_id: str
    user_id: str
    artifact_id: str
    content_hash: str
    mime_type: str
    size_bytes: int
    created_at: str
    verified_source_count: int = 0
    unverified_source_count: int = 0
    fallback_used: bool = False


__all__ = [
    "CourseResearchSessionRow",
    "CourseResearchSourceRow",
    "CourseResearchReportRow",
]