"""学生作业读取与附件下载，按班级和发布状态检查权限。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from ...core.config import get_settings
from ...core.exceptions import (
    AssignmentNotFound,
    ClassGroupNotFound,
    Forbidden,
    NotFoundError,
)
from ...core.security import is_path_traversal
from ...models.multi_role import AssignmentAttachmentRow, AssignmentRow, UserRow
from ...schemas.multi_role import (
    AssignmentAttachmentOut,
    AssignmentOut,
    Page,
)
from ...services.container import ServiceContainer, get_container
from ..deps import current_user
from .classes import _assert_can_view_class

router = APIRouter(tags=["课程作业"])


def _container() -> ServiceContainer:
    return get_container()


def _assignment_to_out(
    a: AssignmentRow,
    *,
    course_id: Optional[str] = None,
    author_name: Optional[str] = None,
    container: Optional[ServiceContainer] = None,
    student_id: Optional[str] = None,
    submission_status: Optional[str] = None,
    attachment_rows: Optional[List[AssignmentAttachmentRow]] = None,
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
    if attachment_rows is not None or container is not None:
        att_rows = attachment_rows if attachment_rows is not None else container.assignment_repository.list_attachments(a.id)
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
    if submission_status is None and container is not None and student_id is not None:
        submission = container.submission_repository.get_submission_for_student(a.id, student_id)
        submission_status = submission.status if submission is not None else "not_submitted"
    return AssignmentOut(
        id=a.id,
        class_group_id=a.class_group_id,
        course_id=course_id,
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
        submission_status=submission_status,
        attachments=att_out,
    )


def _author_name(container: ServiceContainer, author_id: str) -> Optional[str]:
    u = container.user_repository.get_user_by_id(author_id)
    if u is None:
        return None
    return u.display_name or u.username


@router.get(
    "/classes/{class_id}/assignments",
    response_model=Page,
    summary="列出班级作业",
    responses={
        200: {
            "description": "班级任务分页列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "任务列表",
                            "value": {
                                "items": [
                                    {
                                        "id": "assign_001",
                                        "class_group_id": "class_001",
                                        "course_id": "course_001",
                                        "author_id": "u_teacher",
                                        "author_name": "张老师",
                                        "title": "第一章习题",
                                        "description": "完成教材第一章课后习题 1-10。",
                                        "deadline": "2026-10-10T15:59:59+00:00",
                                        "submission_types": ["text", "file"],
                                        "max_score": 100,
                                        "allow_resubmit": True,
                                        "status": "published",
                                        "published_at": "2026-09-25T08:00:00+00:00",
                                        "created_at": "2026-09-25T07:00:00+00:00",
                                        "updated_at": "2026-09-25T08:00:00+00:00",
                                        "submission_status": "not_submitted",
                                        "attachments": [],
                                    }
                                ],
                                "total": 1,
                                "page": 1,
                                "page_size": 20,
                                "has_more": False,
                            },
                        }
                    }
                }
            },
        },
    },
)
def list_assignments(
    class_id: str,
    status: Optional[str] = Query(None, pattern="^(draft|published|closed|archived)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> Page:
    """列出班级下的作业。

    - 学生只返回 published 作业并附带本人 submission_status，教师可按 status 过滤。
    - 班级不存在返回 404（CLASS_GROUP_NOT_FOUND）。
    """
    cls = container.class_group_repository.get_class(class_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_view_class(cls, user, container)
    status_filter = "published" if user.role == "student" else status
    rows, total = container.assignment_repository.list_assignments(
        class_id, status=status_filter, page=page, page_size=page_size,
    )
    submission_statuses = (
        container.submission_repository.get_submission_statuses_for_student(
            [row.id for row in rows], user.id,
        )
        if user.role == "student"
        else {}
    )
    names = container.user_repository.get_display_names([row.author_id for row in rows])
    attachments = container.assignment_repository.list_attachments_for_assignments([row.id for row in rows])
    items = [
        _assignment_to_out(
            r,
            course_id=cls.course_id,
            author_name=names.get(r.author_id),
            attachment_rows=attachments.get(r.id, []),
            container=container,
            student_id=user.id if user.role == "student" else None,
            submission_status=submission_statuses.get(r.id, "not_submitted") if user.role == "student" else None,
        )
        for r in rows
    ]
    return Page.from_rows(items, total=total, page=page, page_size=page_size)


@router.get(
    "/student/assignments",
    response_model=Page,
    summary="列出学生作业",
    responses={
        200: {
            "description": "跨班级的学生任务分页列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "学生任务列表",
                            "value": {
                                "items": [
                                    {
                                        "id": "assign_001",
                                        "class_group_id": "class_001",
                                        "course_id": "course_001",
                                        "author_id": "u_teacher",
                                        "author_name": "张老师",
                                        "title": "第一章习题",
                                        "description": "完成教材第一章课后习题 1-10。",
                                        "deadline": "2026-10-10T15:59:59+00:00",
                                        "submission_types": ["text", "file"],
                                        "max_score": 100,
                                        "allow_resubmit": True,
                                        "status": "published",
                                        "published_at": "2026-09-25T08:00:00+00:00",
                                        "created_at": "2026-09-25T07:00:00+00:00",
                                        "updated_at": "2026-09-25T08:00:00+00:00",
                                        "submission_status": "pending",
                                        "attachments": [],
                                    }
                                ],
                                "total": 1,
                                "page": 1,
                                "page_size": 20,
                                "has_more": False,
                            },
                        }
                    }
                }
            },
        },
    },
)
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
    """跨班级列出当前学生的作业。

    - 仅学生可访问，非学生返回 403（FORBIDDEN）。
    - 支持按提交状态、关键词搜索，并按 deadline/created_at/title 排序。
    """
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
    names = container.user_repository.get_display_names([item["author_id"] for item in items])
    for item in items:
        item["author_name"] = names.get(item["author_id"])
    return Page.from_rows(items, total=total, page=page, page_size=page_size)





@router.get(
    "/assignments/{assignment_id}",
    response_model=AssignmentOut,
    summary="读取作业详情",
    responses={
        200: {
            "description": "任务详情",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "任务详情",
                            "value": {
                                "id": "assign_001",
                                "class_group_id": "class_001",
                                "course_id": "course_001",
                                "author_id": "u_teacher",
                                "author_name": "张老师",
                                "title": "第一章习题",
                                "description": "完成教材第一章课后习题 1-10。",
                                "deadline": "2026-10-10T15:59:59+00:00",
                                "submission_types": ["text", "file"],
                                "max_score": 100,
                                "allow_resubmit": True,
                                "status": "published",
                                "published_at": "2026-09-25T08:00:00+00:00",
                                "created_at": "2026-09-25T07:00:00+00:00",
                                "updated_at": "2026-09-25T08:00:00+00:00",
                                "submission_status": "not_submitted",
                                "attachments": [
                                    {
                                        "id": "att_001",
                                        "assignment_id": "assign_001",
                                        "author_id": "u_teacher",
                                        "original_filename": "习题说明.pdf",
                                        "stored_filename": "a1b2c3d4_习题说明.pdf",
                                        "mime_type": "application/pdf",
                                        "size_bytes": 204800,
                                        "created_at": "2026-09-25T07:00:00+00:00",
                                    }
                                ],
                            },
                        }
                    }
                }
            },
        },
    },
)
def get_assignment(
    assignment_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> AssignmentOut:
    """读取单个作业详情。

    - 作业不存在或学生读取非 published/closed 作业返回 404（ASSIGNMENT_NOT_FOUND）。
    - 班级不存在返回 404（CLASS_GROUP_NOT_FOUND）。
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
    return _assignment_to_out(
        a,
        course_id=cls.course_id,
        author_name=_author_name(container, a.author_id),
        container=container,
        student_id=user.id if user.role == "student" else None,
    )





# ===== 任务附件 =====


@router.get(
    "/assignments/{assignment_id}/attachments",
    summary="列出任务附件",
    responses={
        200: {
            "description": "任务附件列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "附件列表",
                            "value": [
                                {
                                    "id": "att_001",
                                    "assignment_id": "assign_001",
                                    "author_id": "u_teacher",
                                    "original_filename": "习题说明.pdf",
                                    "stored_filename": "a1b2c3d4_习题说明.pdf",
                                    "mime_type": "application/pdf",
                                    "size_bytes": 204800,
                                    "created_at": "2026-09-25T07:00:00+00:00",
                                }
                            ],
                        }
                    }
                }
            },
        },
    },
)
def list_assignment_attachments(
    assignment_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> List[AssignmentAttachmentOut]:
    """列出任务的所有附件。

    权限:
    - 学生: 只能看到自己所在班级已发布任务的附件
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


@router.get(
    "/assignments/{assignment_id}/attachments/{attachment_id}",
    summary="下载任务附件",
)
def download_assignment_attachment(
    assignment_id: str,
    attachment_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
):
    """下载任务附件。

    权限:
    - 学生: 只能下载自己所在班级已发布任务的附件
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
