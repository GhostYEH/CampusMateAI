"""任务路由 — 列表/创建/详情/更新/发布/关闭/统计/学生状态/附件。

权限:
- 列表: 学生只看已发布任务;教师/管理员可看草稿。
- 创建/更新/发布/关闭: 教师(须为本班级负责教师)或管理员。
- 统计/student-status: 教师或管理员。
- 附件: 上传(教师/管理员),下载(有权限的教师/学生/管理员),列表(有权限的教师/学生/管理员)。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse

from ...core.config import Settings, get_settings
from ...core.exceptions import (
    AssignmentNotFound,
    AttachmentTooLarge,
    AttachmentTypeNotAllowed,
    ClassGroupNotFound,
    FileNameUnsafe,
    Forbidden,
    InvalidTransition,
    NotFoundError,
)
from ...core.security import is_path_traversal, sanitize_filename
from ...models.multi_role import AssignmentRow, UserRow
from ...schemas.multi_role import (
    AssignmentAttachmentOut,
    AssignmentCreate,
    AssignmentOut,
    AssignmentStatsOut,
    AssignmentUpdate,
    Page,
    StudentStatusItem,
)
from ...services.container import ServiceContainer, get_container
from ..deps import current_user
from .classes import _assert_can_manage_class, _assert_can_view_class

router = APIRouter(tags=["assignments"])

# 允许的附件 MIME/扩展(与提交附件白名单一致)
_ALLOWED_EXT = {
    "txt", "md", "pdf", "doc", "docx", "xls", "xlsx",
    "ppt", "pptx", "png", "jpg", "jpeg", "gif", "zip", "py", "cpp", "java", "c",
}
_MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10MB


def _container() -> ServiceContainer:
    return get_container()


def _assignment_to_out(
    a: AssignmentRow,
    *,
    author_name: Optional[str] = None,
    container: Optional[ServiceContainer] = None,
) -> AssignmentOut:
    types = []
    if a.submission_types:
        try:
            types = json.loads(a.submission_types)
            if not isinstance(types, list):
                types = []
        except (ValueError, TypeError):
            types = []
    att_out: List[AssignmentAttachmentOut] = []
    if container is not None:
        att_rows = container.assignment_repository.list_attachments(a.id)
        att_out = [
            AssignmentAttachmentOut(
                id=r.id,
                assignment_id=r.assignment_id,
                author_id=r.author_id,
                original_filename=r.original_filename,
                stored_filename=r.stored_filename,
                mime_type=r.mime_type,
                size_bytes=r.size_bytes,
                created_at=r.created_at,
            ) for r in att_rows
        ]
    return AssignmentOut(
        id=a.id,
        class_group_id=a.class_group_id,
        author_id=a.author_id,
        author_name=author_name,
        title=a.title,
        description=a.description,
        deadline=a.deadline,
        submission_types=types,
        max_score=a.max_score,
        allow_resubmit=a.allow_resubmit,
        status=a.status,
        published_at=a.published_at,
        created_at=a.created_at,
        updated_at=a.updated_at,
        attachments=att_out,
    )


def _author_name(container: ServiceContainer, author_id: str) -> Optional[str]:
    u = container.user_repository.get_user_by_id(author_id)
    if u is None:
        return None
    return u.display_name or u.username


@router.get("/classes/{class_id}/assignments", response_model=Page)
def list_assignments(
    class_id: str,
    status: Optional[str] = Query(None, pattern="^(draft|published|closed|archived)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> Page:
    cls = container.class_group_repository.get_class(class_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_view_class(cls, user, container)
    status_filter = "published" if user.role == "student" else status
    rows, total = container.assignment_repository.list_assignments(
        class_id, status=status_filter, page=page, page_size=page_size,
    )
    items = [_assignment_to_out(r, author_name=_author_name(container, r.author_id), container=container) for r in rows]
    return Page.from_rows(items, total=total, page=page, page_size=page_size)


@router.get("/student/assignments", response_model=Page)
def list_student_assignments(
    status: Optional[str] = Query(
        None,
        pattern="^(pending|submitted|overdue|graded)$",
    ),
    search: Optional[str] = Query(None, max_length=200),
    sort_by: str = Query("deadline", pattern="^(deadline|created_at|title)$"),
    sort_desc: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> Page:
    if user.role != "student":
        raise Forbidden("仅学生可访问学生任务列表")
    items, total = container.assignment_repository.list_assignments_for_student(
        user.id,
        submission_status=status,
        search=search,
        sort_by=sort_by,
        sort_desc=sort_desc,
        page=page,
        page_size=page_size,
    )
    for item in items:
        item["author_name"] = _author_name(container, item["author_id"])
    return Page.from_rows(items, total=total, page=page, page_size=page_size)





@router.get("/assignments/{assignment_id}", response_model=AssignmentOut)
def get_assignment(
    assignment_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> AssignmentOut:
    a = container.assignment_repository.get_assignment(assignment_id)
    if a is None:
        raise AssignmentNotFound()
    cls = container.class_group_repository.get_class(a.class_group_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_view_class(cls, user, container)
    if user.role == "student" and a.status not in ("published", "closed"):
        raise AssignmentNotFound()
    return _assignment_to_out(a, author_name=_author_name(container, a.author_id), container=container)





# ===== 任务附件 =====


def _guess_mime(ext: str) -> str:
    return {
        "txt": "text/plain",
        "md": "text/markdown",
        "pdf": "application/pdf",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "zip": "application/zip",
        "py": "text/x-python",
        "cpp": "text/x-c++",
        "java": "text/x-java",
        "c": "text/x-c",
    }.get(ext, "application/octet-stream")





@router.get("/assignments/{assignment_id}/attachments")
def list_assignment_attachments(
    assignment_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> List[AssignmentAttachmentOut]:
    """列出任务的所有附件。

    权限:
    - 学生: 只能看到自己所在班级已发布任务的附件
    - 教师/管理员: 可查看任意有权限的任务的附件
    """
    a = container.assignment_repository.get_assignment(assignment_id)
    if a is None:
        raise AssignmentNotFound()
    cls = container.class_group_repository.get_class(a.class_group_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_view_class(cls, user, container)
    if user.role == "student" and a.status not in ("published", "closed"):
        raise AssignmentNotFound()
    rows = container.assignment_repository.list_attachments(assignment_id)
    return [
        AssignmentAttachmentOut(
            id=r.id,
            assignment_id=r.assignment_id,
            author_id=r.author_id,
            original_filename=r.original_filename,
            stored_filename=r.stored_filename,
            mime_type=r.mime_type,
            size_bytes=r.size_bytes,
            created_at=r.created_at,
        ) for r in rows
    ]


@router.get("/assignments/{assignment_id}/attachments/{attachment_id}")
def download_assignment_attachment(
    assignment_id: str,
    attachment_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
):
    """下载任务附件。

    权限:
    - 学生: 只能下载自己所在班级已发布任务的附件
    - 教师/管理员: 可下载任意有权限的任务的附件
    """
    a = container.assignment_repository.get_assignment(assignment_id)
    if a is None:
        raise AssignmentNotFound()
    cls = container.class_group_repository.get_class(a.class_group_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_view_class(cls, user, container)
    if user.role == "student" and a.status not in ("published", "closed"):
        raise AssignmentNotFound()
    att = container.assignment_repository.get_attachment(attachment_id)
    if att is None or att.assignment_id != assignment_id:
        raise NotFoundError("附件不存在或不属于该任务")
    settings = get_settings()
    attachments_root = (settings.knowledge_base_dir.parent / "assignment_attachments").resolve()
    storage_path = Path(att.storage_path).resolve()
    if is_path_traversal(storage_path, attachments_root):
        raise NotFoundError("附件文件已被删除")
    if not storage_path.exists() or not storage_path.is_file():
        raise NotFoundError("附件文件已被删除")
    return FileResponse(
        str(storage_path),
        filename=att.original_filename,
        media_type=att.mime_type or "application/octet-stream",
    )


__all__ = ["router"]
