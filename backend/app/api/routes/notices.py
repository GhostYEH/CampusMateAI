"""通知结构化抽取路由。"""
from __future__ import annotations

from typing import List, Optional, Tuple
from datetime import datetime, timezone
import asyncio
import hashlib
import json
import re
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
    NoticeBatchIngestRequest,
    NoticeBatchIngestResponse,
    NoticeBatchItem,
    NoticeBatchItemResult,
    NoticeSemanticType,
)
from ...services.container import ServiceContainer, get_container
from ...services.notice_extraction_service import (
    AUTOMATION_EXTRACTOR_VERSION,
    SemanticDecision,
    compute_notice_hash,
)
from ..deps import current_user

router = APIRouter()


_RELATIVE_TIME_RE = re.compile(r"(今天|今晚|明天|明晚|后天|本周|下周|周[一二三四五六日天])")


def _ai_cache_key(item: NoticeBatchItem, container: ServiceContainer) -> Optional[str]:
    normalized = re.sub(r"\s+", " ", item.content).strip()
    if item.published_at is None and _RELATIVE_TIME_RE.search(normalized):
        return None
    published_context = item.published_at.isoformat() if item.published_at else "unknown"
    model = container.llm.name if container.llm is not None else "none"
    raw = "\x1f".join((normalized, published_context, model, AUTOMATION_EXTRACTOR_VERSION))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _persist_automation_result(
    *,
    item: NoticeBatchItem,
    decision: SemanticDecision,
    user: UserRow,
    container: ServiceContainer,
) -> tuple[bool, int, Optional[MultiNoticeExtractResponse]]:
    if decision.type is NoticeSemanticType.CHAT:
        return False, 0, None
    extraction: MultiNoticeExtractResponse
    if decision.tasks:
        extraction = MultiNoticeExtractResponse(
            tasks=decision.tasks,
            split_reason=decision.reason,
            needs_user_confirmation=decision.needs_confirmation,
        )
    elif decision.type is NoticeSemanticType.ACTIONABLE_NOTICE and decision.reason == "rule_first":
        extraction = container.notice_extraction._rule_extract_multi(
            item.content, item.source_name, item.published_at
        )
    else:
        extraction = MultiNoticeExtractResponse(
            tasks=[], split_reason=decision.reason, needs_user_confirmation=decision.needs_confirmation
        )

    primary = extraction.tasks[0] if extraction.tasks else None
    notice_key = f"notification:{item.client_fingerprint}"
    container.notice_repository.create_or_update_notice(
        user_id=user.id,
        source=item.source_name,
        external_id=notice_key,
        title=primary.title if primary else "校园通知",
        content=item.content,
        published_at=item.published_at.isoformat() if item.published_at else None,
    )
    tasks_created = 0
    for task in extraction.tasks:
        if decision.type is not NoticeSemanticType.ACTIONABLE_NOTICE or not task.actionable:
            continue
        identity = "\n".join((task.task, task.deadline.isoformat() if task.deadline else "", task.submission_method or "", task.location or ""))
        task_key = f"{notice_key}:{compute_notice_hash(identity)}"
        existing_task = container.personal_task_repository.get_task_by_source_notice_id(
            task_key, user_id=user.id
        )
        importance = task.importance if task.importance in ("urgent", "high", "important", "normal", "low", "unknown") else "unknown"
        container.personal_task_repository.create_task(
            user_id=user.id,
            title=task.task,
            description=task.source_text,
            target_students=task.target_students,
            deadline=task.deadline.isoformat() if task.deadline else None,
            materials=[material.name for material in task.materials],
            submission_method=task.submission_method,
            location=task.location,
            source_name=item.source_name,
            source_text=task.source_text,
            source_notice_id=task_key,
            priority={"urgent": "high", "high": "high", "important": "high", "normal": "medium", "low": "low", "unknown": "medium"}.get(importance, "medium"),
            importance=importance,
        )
        tasks_created += int(existing_task is None)
    return True, tasks_created, extraction


async def _ingest_batch(
    req: NoticeBatchIngestRequest,
    user: UserRow,
    container: ServiceContainer,
) -> NoticeBatchIngestResponse:
    automation_repo = container.notice_automation_repository
    results_by_id: dict[str, NoticeBatchItemResult] = {}
    pending: list[NoticeBatchItem] = []
    contested: list[NoticeBatchItem] = []
    stats = {
        "received_count": len(req.items), "duplicate_count": 0,
        "rule_chat_count": 0, "rule_notice_count": 0, "rule_task_count": 0,
        "ai_candidate_count": 0, "ai_batch_count": 0, "ai_cache_hit": 0,
    }

    for item in req.items:
        stored = automation_repo.get_ingest_result(user.id, item.client_fingerprint)
        if stored:
            replay = NoticeBatchItemResult.model_validate_json(stored).model_copy(update={"duplicate": True})
            results_by_id[item.client_id] = replay
            stats["duplicate_count"] += 1
        elif automation_repo.try_claim_ingest(user.id, item.client_fingerprint):
            pending.append(item)
        else:
            contested.append(item)

    decisions: dict[str, SemanticDecision] = {}
    ai_misses: list[tuple[NoticeBatchItem, Optional[str]]] = []
    for item in pending:
        semantic = container.notice_extraction.classify_semantics(item.content)
        if semantic is not NoticeSemanticType.AMBIGUOUS:
            decisions[item.client_id] = SemanticDecision(item.client_id, semantic, reason="rule_first")
            stats[{
                NoticeSemanticType.CHAT: "rule_chat_count",
                NoticeSemanticType.NOTICE: "rule_notice_count",
                NoticeSemanticType.ACTIONABLE_NOTICE: "rule_task_count",
            }[semantic]] += 1
            continue
        stats["ai_candidate_count"] += 1
        cache_key = _ai_cache_key(item, container)
        cached = automation_repo.get_ai_cache(cache_key) if cache_key else None
        if cached:
            cached_data = json.loads(cached)
            cached_data["tasks"] = [
                NoticeExtractResponse.model_validate(task) for task in cached_data.get("tasks", [])
            ]
            decisions[item.client_id] = SemanticDecision(**cached_data)
            stats["ai_cache_hit"] += 1
        else:
            ai_misses.append((item, cache_key))

    if ai_misses:
        stats["ai_batch_count"] = 1
        resolved = await container.notice_extraction.extract_ambiguous_batch([
            {"id": item.client_id, "content": item.content, "source_name": item.source_name, "published_at": item.published_at}
            for item, _ in ai_misses
        ])
        for decision, (_, cache_key) in zip(resolved, ai_misses):
            decisions[decision.id] = decision
            if decision.type is not NoticeSemanticType.AMBIGUOUS and cache_key:
                automation_repo.save_ai_cache(cache_key, json.dumps({
                    "id": decision.id,
                    "type": decision.type.value,
                    "tasks": [task.model_dump(mode="json") for task in decision.tasks],
                    "needs_confirmation": decision.needs_confirmation,
                    "reason": decision.reason,
                }, ensure_ascii=False))

    for item in pending:
        decision = decisions[item.client_id]
        if decision.type is NoticeSemanticType.AMBIGUOUS:
            status, reason = "retryable", decision.reason
            notice_created, tasks_created, extraction = False, 0, None
        else:
            notice_created, tasks_created, extraction = _persist_automation_result(
                item=item, decision=decision, user=user, container=container
            )
            status = "ignored" if decision.type is NoticeSemanticType.CHAT else "completed"
            reason = decision.reason
        result = NoticeBatchItemResult(
            client_id=item.client_id,
            client_fingerprint=item.client_fingerprint,
            status=status,
            semantic_type=decision.type,
            notice_created=notice_created,
            tasks_created=tasks_created,
            extraction=extraction,
            reason=reason,
        )
        results_by_id[item.client_id] = result
        if status in ("completed", "ignored", "failed"):
            automation_repo.save_ingest_result(user.id, item.client_fingerprint, result.model_dump_json())
        else:
            automation_repo.release_ingest_claim(user.id, item.client_fingerprint)

    for item in contested:
        stored = None
        for _ in range(50):
            stored = automation_repo.get_ingest_result(user.id, item.client_fingerprint)
            if stored:
                break
            await asyncio.sleep(0.02)
        if stored:
            results_by_id[item.client_id] = NoticeBatchItemResult.model_validate_json(stored).model_copy(
                update={"client_id": item.client_id, "duplicate": True}
            )
            stats["duplicate_count"] += 1
        else:
            results_by_id[item.client_id] = NoticeBatchItemResult(
                client_id=item.client_id,
                client_fingerprint=item.client_fingerprint,
                status="retryable",
                semantic_type=NoticeSemanticType.AMBIGUOUS,
                reason="ingest_in_progress",
            )

    return NoticeBatchIngestResponse(items=[results_by_id[item.client_id] for item in req.items], stats=stats)


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
                    kind="unified",
                    source_url=n.source_url,
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
                        kind="announcement",
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
    source = req.source_name or "校园通知"
    published = req.published_at.isoformat() if req.published_at else datetime.now(timezone.utc).date().isoformat()
    fingerprint = hashlib.sha256(
        "\x1f".join((source, req.content, published)).encode("utf-8")
    ).hexdigest()
    batch = NoticeBatchIngestRequest(items=[NoticeBatchItem(
        client_id=f"legacy:{fingerprint[:16]}",
        client_fingerprint=fingerprint,
        source_name=source,
        published_at=req.published_at,
        messages=[{"text": req.content, "published_at": req.published_at}],
    )])
    processed = await _ingest_batch(batch, user, container)
    result = processed.items[0]
    return result.extraction or MultiNoticeExtractResponse(
        tasks=[], split_reason=result.reason or result.semantic_type.value,
        needs_user_confirmation=result.status == "retryable",
    )


@router.post("/notices/ingest-batch", response_model=NoticeBatchIngestResponse)
async def ingest_notice_batch(
    req: NoticeBatchIngestRequest,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> NoticeBatchIngestResponse:
    return await _ingest_batch(req, user, container)
