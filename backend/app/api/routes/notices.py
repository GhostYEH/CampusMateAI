"""通知结构化抽取路由。"""
from __future__ import annotations

from fastapi import APIRouter

from ...schemas.notice import (
    DuplicateNoticeCheckRequest,
    DuplicateNoticeCheckResponse,
    MultiNoticeExtractResponse,
    NoticeExtractRequest,
    NoticeExtractResponse,
)
from ...services.container import get_container

router = APIRouter()


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
