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


@router.post("/classes/{class_id}/assignments", response_model=AssignmentOut, status_code=201)
def create_assignment(
    class_id: str,
    req: AssignmentCreate,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> AssignmentOut:
    cls = container.class_group_repository.get_class(class_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_manage_class(cls, user, container)
    a = container.assignment_repository.create_assignment(
        class_group_id=class_id,
        author_id=user.id,
        title=req.title,
        description=req.description,
        deadline=req.deadline,
        submission_types=req.submission_types,
        max_score=req.max_score,
        allow_resubmit=req.allow_resubmit,
        status=req.status,
    )
    return _assignment_to_out(a, author_name=user.display_name or user.username, container=container)


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


@router.patch("/assignments/{assignment_id}", response_model=AssignmentOut)
def update_assignment(
    assignment_id: str,
    req: AssignmentUpdate,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> AssignmentOut:
    a = container.assignment_repository.get_assignment(assignment_id)
    if a is None:
        raise AssignmentNotFound()
    cls = container.class_group_repository.get_class(a.class_group_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_manage_class(cls, user, container)
    if a.author_id != user.id and user.role != "admin":
        raise Forbidden("只能修改自己创建的任务")
    fields = req.model_dump(exclude_unset=True)
    updated = container.assignment_repository.update_assignment(assignment_id, fields=fields)
    if updated is None:
        raise AssignmentNotFound()
    return _assignment_to_out(updated, author_name=_author_name(container, updated.author_id), container=container)


@router.post("/assignments/{assignment_id}/publish", response_model=AssignmentOut)
def publish_assignment(
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
    _assert_can_manage_class(cls, user, container)
    if a.author_id != user.id and user.role != "admin":
        raise Forbidden("只能发布自己创建的任务")
    updated = container.assignment_repository.publish(assignment_id)
    if updated is None:
        raise InvalidTransition("任务当前状态不允许发布")
    return _assignment_to_out(updated, author_name=_author_name(container, updated.author_id), container=container)


@router.post("/assignments/{assignment_id}/close", response_model=AssignmentOut)
def close_assignment(
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
    _assert_can_manage_class(cls, user, container)
    if a.author_id != user.id and user.role != "admin":
        raise Forbidden("只能关闭自己创建的任务")
    updated = container.assignment_repository.close(assignment_id)
    if updated is None:
        raise InvalidTransition("任务当前状态不允许关闭")
    return _assignment_to_out(updated, author_name=_author_name(container, updated.author_id), container=container)


@router.get("/assignments/{assignment_id}/stats", response_model=AssignmentStatsOut)
def assignment_stats(
    assignment_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> AssignmentStatsOut:
    a = container.assignment_repository.get_assignment(assignment_id)
    if a is None:
        raise AssignmentNotFound()
    cls = container.class_group_repository.get_class(a.class_group_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_manage_class(cls, user, container)
    total_students = container.enrollment_repository.count_members(a.class_group_id)
    stats = container.submission_repository.assignment_stats(
        assignment_id, total_students=total_students
    )
    return AssignmentStatsOut(**stats)


@router.get("/assignments/{assignment_id}/student-status", response_model=Page)
def assignment_student_status(
    assignment_id: str,
    submission_status: Optional[str] = Query(
        None,
        description="not_submitted|draft|submitted|resubmitted|late",
    ),
    read_status: Optional[str] = Query(None, pattern="^(read|unread)$"),
    query: Optional[str] = Query(None, description="按姓名/学号搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> Page:
    a = container.assignment_repository.get_assignment(assignment_id)
    if a is None:
        raise AssignmentNotFound()
    cls = container.class_group_repository.get_class(a.class_group_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_manage_class(cls, user, container)
    rows, total = container.submission_repository.student_status(
        assignment_id=a.id,
        class_group_id=a.class_group_id,
        submission_status=submission_status,
        read_status=read_status,
        query=query,
        page=page,
        page_size=page_size,
    )
    items = [StudentStatusItem(**r) for r in rows]
    return Page.from_rows(items, total=total, page=page, page_size=page_size)


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


@router.post("/assignments/{assignment_id}/attachments", response_model=AssignmentAttachmentOut, status_code=201)
async def upload_assignment_attachment(
    assignment_id: str,
    file: UploadFile = File(...),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> AssignmentAttachmentOut:
    """上传任务附件(教师/管理员)。

    权限:
    - 教师: 只能给自己创建的任务上传附件
    - 管理员: 可以给任意任务上传附件
    """
    a = container.assignment_repository.get_assignment(assignment_id)
    if a is None:
        raise AssignmentNotFound()
    cls = container.class_group_repository.get_class(a.class_group_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_manage_class(cls, user, container)
    if a.author_id != user.id and user.role != "admin":
        raise Forbidden("只能给自己创建的任务上传附件")
    # 文件名安全校验
    try:
        safe_name = sanitize_filename(file.filename or "")
    except ValueError as e:
        raise FileNameUnsafe(str(e)) from e
    # 扩展名白名单
    ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
    if ext not in _ALLOWED_EXT:
        raise AttachmentTypeNotAllowed(f"不支持的文件类型: .{ext}")
    # 大小校验
    content = await file.read()
    size = len(content)
    if size > _MAX_SIZE_BYTES:
        raise AttachmentTooLarge("附件不能超过 10MB")
    if size == 0:
        raise FileNameUnsafe("文件为空")
    # 存储路径
    settings = get_settings()
    base_dir = settings.knowledge_base_dir.parent / "assignment_attachments" / assignment_id
    base_dir.mkdir(parents=True, exist_ok=True)
    import uuid
    stored_filename = f"{uuid.uuid4().hex[:16]}_{safe_name}"
    storage_path = base_dir / stored_filename
    if is_path_traversal(storage_path, base_dir):
        raise FileNameUnsafe("存储路径非法")
    storage_path.write_bytes(content)
    mime = file.content_type or _guess_mime(ext)
    att = container.assignment_repository.add_attachment(
        assignment_id=assignment_id,
        author_id=user.id,
        original_filename=safe_name,
        stored_filename=stored_filename,
        mime_type=mime,
        size_bytes=size,
        storage_path=str(storage_path),
    )
    return AssignmentAttachmentOut(
        id=att.id,
        assignment_id=att.assignment_id,
        author_id=att.author_id,
        original_filename=att.original_filename,
        stored_filename=att.stored_filename,
        mime_type=att.mime_type,
        size_bytes=att.size_bytes,
        created_at=att.created_at,
    )


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
