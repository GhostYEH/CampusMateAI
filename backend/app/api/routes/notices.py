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

@router.post("/notices/ingest", response_model=NoticeExtractResponse)
async def ingest_notice(
    req: NoticeExtractRequest,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> NoticeExtractResponse:
    """从外部源（如微信监听）接收通知并自动创建个人任务。

    - 结构化: 调用 NoticeExtractionService.extract()
    - 去重: 调用 check_duplicate()
    - 创建任务: 若无重复, 则自动创建 personal_task
    """
    # 1. 结构化提取
    extracted_notice = await container.notice_extraction.extract(
        req.content,
        source_name=req.source_name,
        published_at=req.published_at,
    )

    # 2. 去重检查
    task_repo = container.personal_task_repository
    recent_tasks, _ = task_repo.list_tasks(
        user.id, page=1, page_size=10
    )

    # 将 PersonalTaskRow 转换为 check_duplicate 需要的 NoticeExtractResponse
    recent_notices_for_check: list[NoticeExtractResponse] = []
    for task in recent_tasks:
        recent_notices_for_check.append(
            NoticeExtractResponse(
                title=task.title,
                task=task.title,
                target_students=task.target_students,
                deadline=task.deadline,
                materials=[], # 简化处理，因为 PersonalTaskRow 不直接存储 materials 结构
                submission_method=task.submission_method,
                location=task.location,
                source_name=task.source_name,
                source_text=task.source_text or "", # 用 task.source_text 作为原文
                importance=task.priority, # 字段类型不完全匹配，但可近似
                confidence=0.9, # 来自已有任务，可信度高
                needs_confirmation=False,
                warnings=[],
                extracted_at=task.created_at,
                extractor_mode="rules", # 假设
            )
        )

    check_req = DuplicateNoticeCheckRequest(
        title=extracted_notice.title,
        task=extracted_notice.task,
        deadline=extracted_notice.deadline,
        source_name=extracted_notice.source_name,
        content=req.content,
        recent_notices=[], # request体中的recent_notices应为空，因为我们从db加载
    )

    dup_check_result = container.notice_extraction.check_duplicate(
        check_req, recent_notices=recent_notices_for_check
    )

    if dup_check_result.is_duplicate:
        extracted_notice.warnings.append("Duplicate notice detected.")
        if dup_check_result.matches:
            similar_to_id = dup_check_result.matches[0].notice_id
            extracted_notice.warnings.append(f"Similar to task {similar_to_id}")
        # 如果是完全相同的哈希（similarity == 1.0），或者是 content_hash 匹配，则认为是真正的幂等重复，直接返回现有的，不新建
        if dup_check_result.matches and dup_check_result.matches[0].similarity == 1.0:
            return extracted_notice

    import sqlite3
    # 3. 创建个人任务
    # 使用包含群组名的字符串进行去重
    dedup_key = f"wechat_{extracted_notice.source_name}_{dup_check_result.content_hash}"[:100]
    
    try:
        # 创建统一通知记录
        container.notice_repository.create_or_update_notice(
            user_id=user.id,
            source=extracted_notice.source_name or "wechat",
            external_id=dedup_key,
            title=extracted_notice.title or extracted_notice.task,
            content=req.content,
            published_at=req.published_at.isoformat() if req.published_at else None,
        )
        
        # 创建新的个人任务，依赖底层数据库 UNIQUE(user_id, source_notice_id) 约束处理并发
        task_repo.create_task(
            user_id=user.id,
            title=extracted_notice.task,
            description=extracted_notice.source_text,
            deadline=extracted_notice.deadline.isoformat() if extracted_notice.deadline else None,
            source_name=extracted_notice.source_name,
            source_text=extracted_notice.source_text,
            source_notice_id=dedup_key,
            priority=extracted_notice.importance if extracted_notice.importance in ["low", "medium", "high"] else "medium"
        )
    except sqlite3.IntegrityError:
        extracted_notice.warnings.append("Duplicate notice detected by database unique constraint.")
        pass

    return extracted_notice
