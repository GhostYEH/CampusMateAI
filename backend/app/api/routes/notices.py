"""通知结构化抽取路由。"""
from __future__ import annotations

from typing import Optional
from datetime import datetime, timezone
import asyncio
import hashlib
import json
import re

from fastapi import APIRouter, Depends, Header, Query
from starlette.concurrency import run_in_threadpool

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
from ...schemas.notice_workflow import ManualNoticeIn, ManualNoticeOut
from ..deps import current_user, student_only

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
    stats = {
        "received_count": len(req.items), "duplicate_count": 0,
        "rule_chat_count": 0, "rule_notice_count": 0, "rule_task_count": 0,
        "ai_candidate_count": 0, "ai_batch_count": 0, "ai_cache_hit": 0,
    }

    # 阶段 1：去重读取 + 认领（同步 SQLite）。整个阶段一次性下放到线程池，
    # 避免在事件循环里逐条阻塞，也不为每个条目单独创建线程任务。
    replay_results, pending, contested, duplicate_count = await run_in_threadpool(
        _claim_ingest_batch, automation_repo, user.id, req.items
    )
    results_by_id.update(replay_results)
    stats["duplicate_count"] = duplicate_count

    # 阶段 2：规则优先分类 + AI 缓存命中（同步 SQLite 读取，同样整阶段下放）。
    decisions, ai_misses, counters = await run_in_threadpool(
        _classify_pending_batch, automation_repo, container, pending
    )
    stats.update(counters)

    if ai_misses:
        stats["ai_batch_count"] = 1
        resolved = await container.notice_extraction.extract_ambiguous_batch([
            {"id": item.client_id, "content": item.content, "source_name": item.source_name, "published_at": item.published_at}
            for item, _ in ai_misses
        ])
        # 阶段 3：把 AI 结果写回缓存（同步 SQLite 写入）。
        await run_in_threadpool(
            _record_ai_batch_results, automation_repo, decisions, ai_misses, resolved
        )

    # 阶段 4：落库 / 释放认领（同步 SQLite 写入）。
    results_by_id.update(await run_in_threadpool(
        _persist_pending_batch, automation_repo, user, container, pending, decisions
    ))

    for item in contested:
        stored = None
        # 轮询上限固定 50 次；每次读取都是单条主键查询，整体有界。
        for _ in range(50):
            stored = await run_in_threadpool(
                automation_repo.get_ingest_result, user.id, item.client_fingerprint
            )
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


def _claim_ingest_batch(
    automation_repo, user_id: str, items: list[NoticeBatchItem]
) -> tuple[dict[str, NoticeBatchItemResult], list[NoticeBatchItem], list[NoticeBatchItem], int]:
    """阶段 1：读取已有结果做重放，否则认领；认领失败进入 contested。"""
    replay_results: dict[str, NoticeBatchItemResult] = {}
    pending: list[NoticeBatchItem] = []
    contested: list[NoticeBatchItem] = []
    duplicate_count = 0
    for item in items:
        stored = automation_repo.get_ingest_result(user_id, item.client_fingerprint)
        if stored:
            replay = NoticeBatchItemResult.model_validate_json(stored).model_copy(update={"duplicate": True})
            replay_results[item.client_id] = replay
            duplicate_count += 1
        elif automation_repo.try_claim_ingest(user_id, item.client_fingerprint):
            pending.append(item)
        else:
            contested.append(item)
    return replay_results, pending, contested, duplicate_count


def _classify_pending_batch(
    automation_repo, container: ServiceContainer, pending: list[NoticeBatchItem]
) -> tuple[dict[str, SemanticDecision], list[tuple[NoticeBatchItem, Optional[str]]], dict[str, int]]:
    """阶段 2：规则优先分类；模糊内容查 AI 缓存，未命中留给批量 AI。"""
    decisions: dict[str, SemanticDecision] = {}
    ai_misses: list[tuple[NoticeBatchItem, Optional[str]]] = []
    counters = {
        "rule_chat_count": 0, "rule_notice_count": 0, "rule_task_count": 0,
        "ai_candidate_count": 0, "ai_cache_hit": 0,
    }
    for item in pending:
        semantic = container.notice_extraction.classify_semantics(item.content)
        if semantic is not NoticeSemanticType.AMBIGUOUS:
            decisions[item.client_id] = SemanticDecision(item.client_id, semantic, reason="rule_first")
            counters[{
                NoticeSemanticType.CHAT: "rule_chat_count",
                NoticeSemanticType.NOTICE: "rule_notice_count",
                NoticeSemanticType.ACTIONABLE_NOTICE: "rule_task_count",
            }[semantic]] += 1
            continue
        counters["ai_candidate_count"] += 1
        cache_key = _ai_cache_key(item, container)
        cached = automation_repo.get_ai_cache(cache_key) if cache_key else None
        if cached:
            cached_data = json.loads(cached)
            cached_data["tasks"] = [
                NoticeExtractResponse.model_validate(task) for task in cached_data.get("tasks", [])
            ]
            decisions[item.client_id] = SemanticDecision(**cached_data)
            counters["ai_cache_hit"] += 1
        else:
            ai_misses.append((item, cache_key))
    return decisions, ai_misses, counters


def _record_ai_batch_results(
    automation_repo,
    decisions: dict[str, SemanticDecision],
    ai_misses: list[tuple[NoticeBatchItem, Optional[str]]],
    resolved: list[SemanticDecision],
) -> None:
    """阶段 3：合并批量 AI 结果并写入缓存。"""
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


def _persist_pending_batch(
    automation_repo,
    user: UserRow,
    container: ServiceContainer,
    pending: list[NoticeBatchItem],
    decisions: dict[str, SemanticDecision],
) -> dict[str, NoticeBatchItemResult]:
    """阶段 4：按决策落库或释放认领。"""
    results: dict[str, NoticeBatchItemResult] = {}
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
        results[item.client_id] = result
        if status in ("completed", "ignored", "failed"):
            automation_repo.save_ingest_result(user.id, item.client_fingerprint, result.model_dump_json())
        else:
            automation_repo.release_ingest_claim(user.id, item.client_fingerprint)
    return results


def _container() -> ServiceContainer:
    return get_container()


@router.get("/notices", response_model=Page)
def list_notices(
    unread_only: bool = Query(False, description="仅返回未读"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> Page:
    """校园通知列表 —— 聚合 notices 表和 announcements 表的通知。"""
    
    rows, total = container.notice_repository.list_visible_notices(
        user.id,
        student=user.role == "student",
        unread_only=unread_only,
        page=page,
        page_size=page_size,
    )
    items = [NoticeOut(**row) for row in rows]
    return Page.from_rows(items, total=total, page=page, page_size=page_size)


@router.post("/notices/extract", response_model=NoticeExtractResponse)
async def extract_notice(
    req: NoticeExtractRequest,
    _user: UserRow = Depends(current_user),
) -> NoticeExtractResponse:
    container = get_container()
    return await container.notice_extraction.extract(
        req.content,
        source_name=req.source_name,
        published_at=req.published_at,
    )


@router.post("/notices/extract-multi", response_model=MultiNoticeExtractResponse)
async def extract_notice_multi(
    req: NoticeExtractRequest,
    _user: UserRow = Depends(current_user),
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
def check_duplicate(
    req: DuplicateNoticeCheckRequest,
    _user: UserRow = Depends(current_user),
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

@router.post("/notices/manual", response_model=ManualNoticeOut)
def create_manual_notice(
    body: ManualNoticeIn,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> ManualNoticeOut:
    """手动提交通知文本,持久化为服务端 notice_id(§8.3)。

    先把粘贴文本写入 notices 表,返回 notice_id,客户端再调用
    POST /notices/{notice_id}/workflow 创建工作流。同内容幂等返回。
    """
    normalized = re.sub(r"\s+", " ", body.content).strip()
    fingerprint = hashlib.sha256(
        "\x1f".join((user.id, normalized)).encode("utf-8")
    ).hexdigest()
    external_id = f"manual:{fingerprint[:32]}"
    existing = container.notice_repository.find_by_external_id(
        user.id, "manual_input", external_id
    )
    notice = container.notice_repository.create_or_update_notice(
        user_id=user.id,
        source="manual_input",
        external_id=external_id,
        title=body.title,
        content=body.content,
        source_url=None,
        last_synced_at=datetime.now(timezone.utc).isoformat(),
    )
    return ManualNoticeOut(
        notice_id=notice.id,
        title=notice.title,
        duplicate=existing is not None,
    )


# 挂载通知工作流路由(§9.4),避免修改共享 router.py
from .notice_workflows import router as _notice_workflows_router  # noqa: E402

router.include_router(_notice_workflows_router)
