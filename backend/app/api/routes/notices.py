"""通知结构化抽取路由。"""
from __future__ import annotations

from typing import List, Optional, Tuple

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
from ..deps import current_user

router = APIRouter()


def _container() -> ServiceContainer:
    return get_container()


def _user_visible_classes(
    user: UserRow, container: ServiceContainer
) -> List[Tuple[str, str, Optional[str]]]:
    """返回当前用户可见班级 (class_id, class_name, course_name) 列表。

    - student: 已加入的班级
    - teacher: 其负责课程下的班级
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
    if user.role == "teacher":
        classes, _ = class_repo.list_classes(
            teacher_id=user.id, page=1, page_size=200
        )
        result: List[Tuple[str, str, Optional[str]]] = []
        for c in classes:
            course = course_repo.get_course(c.course_id)
            result.append((c.id, c.name or "", course.name if course else None))
        return result
    # admin
    classes, _ = class_repo.list_classes(page=1, page_size=200)
    result = []
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
    """校园通知列表 —— 聚合当前用户可见班级的已发布通知。

    - 学生: 看自己已加入班级的通知,`unread` 由已读记录计算
    - 教师: 看其负责课程下班级的通知
    - 管理员: 看全部通知
    - 按 `published_at` 倒序(无发布时间者排后)
    """
    ann_repo = container.announcement_repository
    items: List[NoticeOut] = []
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
