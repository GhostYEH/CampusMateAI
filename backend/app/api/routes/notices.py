"""通知结构化抽取路由。"""
from __future__ import annotations

from typing import List, Optional, Tuple
import sqlite3

from fastapi import APIRouter, Depends, Query

from ...models.multi_role import UserRow
from ...schemas.multi_role import Page
from ...schemas.notice import (
    DuplicateNoticeCheckRequest,
    DuplicateNoticeCheckResponse,
    MultiNoticeExtractResponse,
    NoticeExtractRequest,
    NoticeExtractResponse,
    NoticeOut,
)
from ...services.container import ServiceContainer, get_container
from ...services.notice_extraction_service import compute_notice_hash
from ..deps import current_user

router = APIRouter()


def _container() -> ServiceContainer:
    return get_container()


def _user_visible_classes(
    user: UserRow, container: ServiceContainer
) -> List[Tuple[str, str, Optional[str]]]:
    """返回当前用户可见班级 (class_id, class_name, course_name) 列表。

    - student: 已加入的班级
    - admin: 全部班级
    """
    enrollment_repo = container.enrollment_repository
    class_repo = container.class_group_repository
    course_repo = container.course_repository

    if user.role == "student":
        rows = enrollment_repo.list_user_classes(user.id)
        return [
            (r["class_id"], r.get("class_name") or "", r.get("course_name"))
            for r in rows
        ]
    # admin
    classes, _ = class_repo.list_classes(page=1, page_size=200)
    result: List[Tuple[str, str, Optional[str]]] = []
    for c in classes:
        course = course_repo.get_course(c.course_id)
        result.append((c.id, c.name or "", course.name if course else None))
    return result


@router.get("/notices", response_model=Page)
def list_notices(
    unread_only: bool = Query(False, description="仅返回未读"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> Page:
    """校园通知列表 —— 聚合 notices 表和 announcements 表的通知。"""
    
    items: List[NoticeOut] = []
    
    # 1. 加载统一 notices 表中的通知（微信、学习通等）
    notice_repo = container.notice_repository
    unified_notices = notice_repo.list_notices(user.id)
    for n in unified_notices:
        # Notice 表数据暂时不维护 unread 状态（或统一默认已读）
        if unread_only:
            continue
        items.append(
            NoticeOut(
                id=n.id,
                title=n.title,
                source=n.source,
                time=n.published_at or n.created_at,
                unread=False,
                category=n.source,
                content=n.content,
            )
        )

    # 2. 加载旧 announcements 表中的通知（向后兼容）
    ann_repo = container.announcement_repository
    for class_id, class_name, course_name in _user_visible_classes(user, container):
        rows, _ = ann_repo.list_announcements(
            class_id, status="published", page=1, page_size=100
        )
        for ann in rows:
            unread = False
            if user.role == "student":
                unread = not ann_repo.is_read(ann.id, user.id)
            items.append(
                NoticeOut(
                    id=ann.id,
                    title=ann.title,
                    source=class_name or course_name or ann.author_id,
                    time=ann.published_at or ann.created_at,
                    unread=unread,
                    category=course_name,
                    content=ann.content,
                )
            )
    
    # 排序: 有时间者按时间倒序,无时间者排后
    items.sort(key=lambda n: n.time or "", reverse=True)
    if unread_only:
        items = [n for n in items if n.unread]
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return Page(
        items=items[start:end],
        total=total,
        page=page,
        page_size=page_size,
        has_more=end < total,
    )


@router.post("/notices/extract", response_model=NoticeExtractResponse)
async def extract_notice(req: NoticeExtractRequest) -> NoticeExtractResponse:
    container = get_container()
    return await container.notice_extraction.extract(
        req.content,
        source_name=req.source_name,
        published_at=req.published_at,
    )


@router.post("/notices/extract-multi", response_model=MultiNoticeExtractResponse)
async def extract_notice_multi(
    req: NoticeExtractRequest,
) -> MultiNoticeExtractResponse:
    """多任务抽取 — 自动识别通知中是否包含多个独立任务。

    - 当识别到 >=2 个独立截止/动作时返回多个任务
    - 无法可靠拆分时返回单任务,并标注 split_reason
    - needs_user_confirmation=true 时建议用户人工确认拆分结果
    """
    container = get_container()
    return await container.notice_extraction.extract_multi(
        req.content,
        source_name=req.source_name,
        published_at=req.published_at,
        allow_multi_task=req.allow_multi_task,
    )


@router.post("/notices/check-duplicate", response_model=DuplicateNoticeCheckResponse)
async def check_duplicate(
    req: DuplicateNoticeCheckRequest,
) -> DuplicateNoticeCheckResponse:
    """检测当前通知是否可能与最近已存在的通知重复。

    判定依据:
    - 原文内容 hash 一致 → 高度可能重复
    - 来源 + 截止 + 任务名 一致 → 可能重复
    - 任务名 + 截止 一致 → 可能重复
    - 文本 Jaccard 相似度 >= 0.85 → 可能重复

    发现重复时只提示,不自动覆盖。
    服务端无状态:客户端应将本地已保存的通知列表作为 recent_notices 传入。
    若 recent_notices 为空,则返回 is_duplicate=false(无对比基准)。
    """
    container = get_container()
    # 将客户端传入的 RecentNoticeItem 转为 NoticeExtractResponse(供服务层对比)
    from datetime import datetime

    recent_notices: list[NoticeExtractResponse] = []
    for item in req.recent_notices:
        recent_notices.append(
            NoticeExtractResponse(
                title=item.title or item.task or "",
                task=item.task or item.title or "",
                target_students=None,
                deadline=item.deadline,
                materials=[],
                submission_method=None,
                location=None,
                source_name=item.source_name,
                source_text=item.source_text or "",
                importance="unknown",
                confidence=0.0,
                needs_confirmation=False,
                warnings=[],
                extracted_at=datetime.utcnow(),
                extractor_mode="rules",
            )
        )

    return container.notice_extraction.check_duplicate(req, recent_notices=recent_notices)

@router.post("/notices/ingest", response_model=MultiNoticeExtractResponse)
async def ingest_notice(
    req: NoticeExtractRequest,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> MultiNoticeExtractResponse:
    """接收端侧校园通知并同步到所有客户端可见的通知、待办数据源。

    原始通知仅在客户端白名单和本地规则通过后才会到达这里。服务端
    以原文 hash 作为通知幂等键，使用多任务抽取，并只自动创建明确
    actionable 的待办；低置信度结果仍会保留在统一通知列表供确认。
    """
    extracted = await container.notice_extraction.extract_multi(
        req.content,
        source_name=req.source_name,
        published_at=req.published_at,
        allow_multi_task=req.allow_multi_task,
    )
    task_repo = container.personal_task_repository
    source = req.source_name or "微信通知"
    content_hash = compute_notice_hash(req.content)
    # The same announcement in two different allow-listed groups is meaningful
    # provenance, so its source participates in the idempotency boundary.
    notice_key = f"wechat:{compute_notice_hash(source)}:{content_hash}"
    primary = extracted.tasks[0] if extracted.tasks else None
    title = primary.title if primary else "校园通知"

    # This row is the shared Android/Web notification record. create_or_update
    # makes retrying a completed WorkManager job safe.
    container.notice_repository.create_or_update_notice(
        user_id=user.id,
        source=source,
        external_id=notice_key,
        title=title,
        content=req.content,
        published_at=req.published_at.isoformat() if req.published_at else None,
    )

    for index, task in enumerate(extracted.tasks):
        if not task.actionable:
            task.warnings.append("非行动型通知，未自动创建待办。")
            continue
        # Task titles can legitimately fall back to the same generic title when
        # rule extraction is conservative. Include stable task attributes so
        # distinct deadlines/actions in one long teacher notice stay separate.
        task_identity = "\n".join(
            [
                task.task,
                task.deadline.isoformat() if task.deadline else "",
                task.submission_method or "",
                task.location or "",
            ]
        )
        task_key = f"{notice_key}:{compute_notice_hash(task_identity)}"
        try:
            task_repo.create_task(
                user_id=user.id,
                title=task.task,
                description=task.source_text,
                target_students=task.target_students,
                deadline=task.deadline.isoformat() if task.deadline else None,
                materials=[item.name for item in task.materials],
                submission_method=task.submission_method,
                location=task.location,
                source_name=source,
                source_text=task.source_text,
                source_notice_id=task_key,
                priority={"urgent": "high", "important": "high", "normal": "medium"}.get(task.importance, "medium"),
            )
        except sqlite3.IntegrityError:
            task.warnings.append("重复通知，未重复创建待办。")

    return extracted
