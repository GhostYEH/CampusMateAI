"""提交路由 — 列表/创建/详情/更新/提交/附件/评分/下载。

权限:
- 列表: 教师或管理员(看到该任务下所有学生的提交)。
- 创建/更新/提交: 学生只能创建/修改自己的提交。
- 详情: 学生只能看自己的;教师可看自己课程下任一学生的;管理员任意。
- 附件上传: 学生只能上传到自己的提交;教师/管理员不可上传(避免混淆)。
- 附件下载: 学生只能下载自己提交的附件;教师/管理员可下载自己课程下的任一附件。
- 评分: 教师或管理员。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse

from ...core.config import Settings, get_settings
from ...core.exceptions import (
    AssignmentClosed,
    AssignmentNotFound,
    AttachmentTooLarge,
    AttachmentTypeNotAllowed,
    FileNameUnsafe,
    Forbidden,
    NotFoundError,
    ResubmitNotAllowed,
    SubmissionNotFound,
)
from ...core.security import is_path_traversal, sanitize_filename
from ...models.multi_role import SubmissionRow, UserRow
from ...schemas.multi_role import (
    AttachmentOut,
    Page,
    SubmissionCreate,
    SubmissionGrade,
    SubmissionOut,
    SubmissionUpdate,
)
from ...services.container import ServiceContainer, get_container
from ..deps import current_user
from .classes import _assert_can_manage_class, _assert_can_view_class

router = APIRouter(tags=["submissions"])


def _container() -> ServiceContainer:
    return get_container()


# 允许的附件 MIME/扩展
_ALLOWED_EXT = {
    "txt", "md", "pdf", "doc", "docx", "xls", "xlsx",
    "ppt", "pptx", "png", "jpg", "jpeg", "gif", "zip", "py", "cpp", "java", "c",
}
_MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10MB


def _submission_to_out(
    sub: SubmissionRow,
    *,
    attachments: Optional[List[AttachmentOut]] = None,
    student_name: Optional[str] = None,
    student_number: Optional[str] = None,
    college: Optional[str] = None,
    major: Optional[str] = None,
    grade: Optional[str] = None,
) -> SubmissionOut:
    return SubmissionOut(
        id=sub.id,
        assignment_id=sub.assignment_id,
        student_id=sub.student_id,
        student_name=student_name,
        student_number=student_number,
        college=college,
        major=major,
        grade=grade,
        text_content=sub.text_content,
        status=sub.status,
        submitted_at=sub.submitted_at,
        updated_at=sub.updated_at,
        score=sub.score,
        teacher_comment=sub.teacher_comment,
        attachments=attachments or [],
    )


def _enrich_with_student_info(
    container: ServiceContainer, sub: SubmissionRow
) -> SubmissionOut:
    u = container.user_repository.get_user_by_id(sub.student_id)
    if u is None:
        return _submission_to_out(sub)
    return _submission_to_out(
        sub,
        student_name=u.display_name or u.username,
        student_number=u.student_number,
        college=u.college,
        major=u.major,
        grade=u.grade,
    )


def _load_attachments(
    container: ServiceContainer, submission_id: str
) -> List[AttachmentOut]:
    rows = container.submission_repository.list_attachments(submission_id)
    return [
        AttachmentOut(
            id=r.id,
            submission_id=r.submission_id,
            original_filename=r.original_filename,
            stored_filename=r.stored_filename,
            mime_type=r.mime_type,
            size_bytes=r.size_bytes,
            created_at=r.created_at,
        )
        for r in rows
    ]





@router.get(
    "/assignments/{assignment_id}/my-submission",
    response_model=SubmissionOut,
)
def get_my_submission(
    assignment_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> SubmissionOut:
    if user.role != "student":
        raise Forbidden("仅学生可查看自己的提交")
    sub = container.submission_repository.get_submission_for_student(
        assignment_id,
        user.id,
    )
    if sub is None:
        raise SubmissionNotFound()
    out = _enrich_with_student_info(container, sub)
    out.attachments = _load_attachments(container, sub.id)
    return out


@router.post("/assignments/{assignment_id}/submissions", response_model=SubmissionOut, status_code=201)
def create_submission(
    assignment_id: str,
    req: SubmissionCreate,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> SubmissionOut:
    a = container.assignment_repository.get_assignment(assignment_id)
    if a is None:
        raise AssignmentNotFound()
    cls = container.class_group_repository.get_class(a.class_group_id)
    if cls is None:
        raise AssignmentNotFound()
    _assert_can_view_class(cls, user, container)
    if user.role != "student":
        raise Forbidden("仅学生可创建提交")
    if a.status not in ("published", "closed"):
        raise AssignmentNotFound()
    # 检查截止后是否允许新建
    status = _compute_initial_status(a, req.submit)
    if a.status == "closed" and req.submit:
        raise AssignmentClosed()
    sub = container.submission_repository.upsert_submission(
        assignment_id=assignment_id,
        student_id=user.id,
        text_content=req.text_content,
        status=status,
    )
    return _enrich_with_student_info(container, sub)


def _compute_initial_status(a, submit: bool) -> str:
    """根据是否 submit 与 deadline 计算初始状态。"""
    if not submit:
        return "draft"
    now_iso = datetime.now(timezone.utc).isoformat()
    if a.deadline and now_iso > a.deadline:
        return "late"
    return "submitted"


@router.get("/submissions/{submission_id}", response_model=SubmissionOut)
def get_submission(
    submission_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> SubmissionOut:
    sub = container.submission_repository.get_submission(submission_id)
    if sub is None:
        raise SubmissionNotFound()
    a = container.assignment_repository.get_assignment(sub.assignment_id)
    if a is None:
        raise AssignmentNotFound()
    cls = container.class_group_repository.get_class(a.class_group_id)
    if cls is None:
        raise AssignmentNotFound()
    # 学生只能看自己的
    if user.role == "student":
        if sub.student_id != user.id:
            raise Forbidden("不能查看其他学生的提交")
        _assert_can_view_class(cls, user, container)
    else:
        _assert_can_manage_class(cls, user, container)
    out = _enrich_with_student_info(container, sub)
    out.attachments = _load_attachments(container, sub.id)
    return out


@router.patch("/submissions/{submission_id}", response_model=SubmissionOut)
def update_submission(
    submission_id: str,
    req: SubmissionUpdate,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> SubmissionOut:
    sub = container.submission_repository.get_submission(submission_id)
    if sub is None:
        raise SubmissionNotFound()
    a = container.assignment_repository.get_assignment(sub.assignment_id)
    if a is None:
        raise AssignmentNotFound()
    if user.role != "student" or sub.student_id != user.id:
        raise Forbidden("只能修改自己的提交")
    # 任务已关闭则不允许更新文本(若允许重新提交则例外)
    if a.status == "closed" and not a.allow_resubmit:
        raise AssignmentClosed()
    new_text = req.text_content if req.text_content is not None else sub.text_content
    # PATCH 保持原 status(draft 仍 draft,submitted 不变)
    sub = container.submission_repository.upsert_submission(
        assignment_id=sub.assignment_id,
        student_id=sub.student_id,
        text_content=new_text,
        status=sub.status,
    )
    return _enrich_with_student_info(container, sub)


@router.post("/submissions/{submission_id}/submit", response_model=SubmissionOut)
def submit_submission(
    submission_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> SubmissionOut:
    sub = container.submission_repository.get_submission(submission_id)
    if sub is None:
        raise SubmissionNotFound()
    a = container.assignment_repository.get_assignment(sub.assignment_id)
    if a is None:
        raise AssignmentNotFound()
    if user.role != "student" or sub.student_id != user.id:
        raise Forbidden("只能提交自己的提交")
    # 已提交且不允许重新提交
    if sub.status in ("submitted", "resubmitted", "late") and not a.allow_resubmit:
        raise ResubmitNotAllowed()
    # 任务已关闭
    if a.status == "closed" and not a.allow_resubmit:
        raise AssignmentClosed()
    now_iso = datetime.now(timezone.utc).isoformat()
    # 决定状态:逾期 → late;否则若之前已提交 → resubmitted;否则 → submitted
    if a.deadline and now_iso > a.deadline:
        new_status = "late"
    elif sub.status in ("submitted", "resubmitted", "late"):
        new_status = "resubmitted"
    else:
        new_status = "submitted"
    sub = container.submission_repository.upsert_submission(
        assignment_id=sub.assignment_id,
        student_id=sub.student_id,
        text_content=sub.text_content,
        status=new_status,
    )
    return _enrich_with_student_info(container, sub)


@router.post("/submissions/{submission_id}/attachments", response_model=AttachmentOut, status_code=201)
async def upload_attachment(
    submission_id: str,
    file: UploadFile = File(...),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> AttachmentOut:
    sub = container.submission_repository.get_submission(submission_id)
    if sub is None:
        raise SubmissionNotFound()
    a = container.assignment_repository.get_assignment(sub.assignment_id)
    if a is None:
        raise AssignmentNotFound()
    if user.role == "student":
        if sub.student_id != user.id:
            raise Forbidden("只能给自己的提交上传附件")
        if a.status == "closed":
            raise AssignmentClosed()
    else:
        # 教师也可为学生上传补充材料?当前不允许(避免混淆)
        _assert_can_manage_class(
            container.class_group_repository.get_class(a.class_group_id),  # type: ignore[arg-type]
            user, container,
        )
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
    # 存储路径: ./data/submission_attachments/<submission_id>/<uuid>_<safe_name>
    settings = get_settings()
    base_dir = settings.knowledge_base_dir.parent / "submission_attachments" / submission_id
    base_dir.mkdir(parents=True, exist_ok=True)
    import uuid
    stored_filename = f"{uuid.uuid4().hex[:16]}_{safe_name}"
    storage_path = base_dir / stored_filename
    # 路径穿越防御(二次校验)
    if is_path_traversal(storage_path, base_dir):
        raise FileNameUnsafe("存储路径非法")
    storage_path.write_bytes(content)
    mime = file.content_type or _guess_mime(ext)
    att = container.submission_repository.add_attachment(
        submission_id=submission_id,
        original_filename=safe_name,
        stored_filename=stored_filename,
        mime_type=mime,
        size_bytes=size,
        storage_path=str(storage_path),
    )
    return AttachmentOut(
        id=att.id,
        submission_id=att.submission_id,
        original_filename=att.original_filename,
        stored_filename=att.stored_filename,
        mime_type=att.mime_type,
        size_bytes=att.size_bytes,
        created_at=att.created_at,
    )


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


@router.get("/submissions/{submission_id}/attachments/{attachment_id}")
def download_attachment(
    submission_id: str,
    attachment_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
):
    """下载提交附件。

    权限:
    - 学生: 只能下载自己提交的附件
    - 教师/管理员: 只能下载自己课程下任一学生的附件

    安全:
    - 严格校验 storage_path 位于允许的根目录之下(防路径穿越)
    - 文件不存在则返回 404
    - submission_id 与 attachment_id 必须匹配
    """
    sub = container.submission_repository.get_submission(submission_id)
    if sub is None:
        raise SubmissionNotFound()
    a = container.assignment_repository.get_assignment(sub.assignment_id)
    if a is None:
        raise AssignmentNotFound()
    cls = container.class_group_repository.get_class(a.class_group_id)
    if cls is None:
        raise AssignmentNotFound()

    # 学生只能下载自己的附件;教师/管理员需有权限
    if user.role == "student":
        if sub.student_id != user.id:
            raise Forbidden("不能下载其他学生的附件")
        _assert_can_view_class(cls, user, container)
    else:
        _assert_can_manage_class(cls, user, container)

    att = container.submission_repository.get_attachment(attachment_id)
    if att is None or att.submission_id != submission_id:
        raise NotFoundError("附件不存在或不属于该提交")

    # 路径安全校验: storage_path 必须位于 knowledge_base_dir.parent / "submission_attachments" 之下
    settings = get_settings()
    attachments_root = (settings.knowledge_base_dir.parent / "submission_attachments").resolve()
    storage_path = Path(att.storage_path).resolve()
    if is_path_traversal(storage_path, attachments_root):
        # 路径异常:不返回文件,记录 404 避免泄露存在性
        raise NotFoundError("附件文件已被删除")

    if not storage_path.exists() or not storage_path.is_file():
        raise NotFoundError("附件文件已被删除")

    return FileResponse(
        str(storage_path),
        filename=att.original_filename,
        media_type=att.mime_type or "application/octet-stream",
    )





__all__ = ["router"]
