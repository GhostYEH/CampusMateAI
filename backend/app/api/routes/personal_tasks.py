"""个人待办任务路由 — /api/v1/tasks。

设计目标: 学生从通知抽取后的个人待办 CRUD + 完成/恢复/软删除。
与 `assignments`(教师发布的班级作业)严格分离 — 不复用任何 assignment 资源。

权限:
- 所有接口必须 JWT 认证
- 任务按 `user_id` 隔离,JWT 用户只能读写自己的任务
- 教师/管理员不会跨用户读取学生任务(管理员可通过用户管理接口处理)

状态机:
- POST /tasks              创建(status=pending)
- PATCH /tasks/{id}        更新(不能改 status)
- POST /tasks/{id}/complete 标记完成(pending → completed)
- POST /tasks/{id}/restore 恢复(completed/deleted → pending)
- DELETE /tasks/{id}       软删除(任意状态 → deleted)

筛选:
- GET /tasks?status=pending&priority=high&deadline_before=...&deadline_after=...
"""
from __future__ import annotations

import re
from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from ...core.exceptions import (
    PersonalTaskConflict,
    PersonalTaskNotFound,
)
from ...models.multi_role import UserRow
from ...models.personal_task import PersonalTaskRow
from ...repositories.personal_task_repository import _load_materials
from ...schemas.personal_task import (
    PersonalTaskCreate,
    PersonalTaskOut,
    PersonalTaskUpdate,
    ImportanceRankRequest,
    ImportanceRankResponse,
    ImportanceRankItem,
    TaskImportAnalyzeRequest,
    TaskImportAnalyzeResponse,
    TaskImportCommitRequest,
    TaskImportCommitResponse,
    TaskImportDraft,
    TaskImportExisting,
)
from ...schemas.multi_role import Page
from ...services.container import ServiceContainer, get_container
from ..deps import current_user

router = APIRouter(prefix="/tasks", tags=["personal-tasks"])


def _container() -> ServiceContainer:
    return get_container()


def _to_out(row: PersonalTaskRow) -> PersonalTaskOut:
    return PersonalTaskOut(
        id=row.id,
        user_id=row.user_id,
        title=row.title,
        description=row.description,
        target_students=row.target_students,
        deadline=row.deadline,
        materials=_load_materials(row.materials),
        submission_method=row.submission_method,
        location=row.location,
        source_name=row.source_name,
        source_text=row.source_text,
        source_notice_id=row.source_notice_id,
        priority=row.priority,
        importance=row.importance,
        status=row.status,
        reminder_minutes=row.reminder_minutes,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
        deleted_at=row.deleted_at,
    )


@router.get("", response_model=Page)
def list_personal_tasks(
    status: Optional[str] = Query(
        None, pattern="^(pending|completed|deleted)$"
    ),
    priority: Optional[str] = Query(None, pattern="^(low|medium|high)$"),
    deadline_before: Optional[str] = Query(None),
    deadline_after: Optional[str] = Query(None),
    include_deleted: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> Page:
    """列出当前用户的个人待办。

    - 默认不返回 `deleted` 状态(除非 `include_deleted=true` 或显式 `status=deleted`)
    - 支持按 status/priority/deadline 筛选
    """
    repo = container.personal_task_repository
    rows, total = repo.list_tasks(
        user.id,
        status=status,
        priority=priority,
        deadline_before=deadline_before,
        deadline_after=deadline_after,
        include_deleted=include_deleted,
        page=page,
        page_size=page_size,
    )
    items = [_to_out(r) for r in rows]
    return Page.from_rows(items, total=total, page=page, page_size=page_size)


@router.post("", response_model=PersonalTaskOut, status_code=201)
def create_personal_task(
    req: PersonalTaskCreate,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> PersonalTaskOut:
    """创建个人待办。

    `source_text` 建议保留(用于原文追溯)。`user_id` 由 JWT 注入,客户端不传。
    """
    repo = container.personal_task_repository
    row = repo.create_task(
        user_id=user.id,
        title=req.title,
        description=req.description,
        target_students=req.target_students,
        deadline=req.deadline,
        materials=req.materials,
        submission_method=req.submission_method,
        location=req.location,
        source_name=req.source_name,
        source_text=req.source_text,
        source_notice_id=req.source_notice_id,
        priority=req.priority,
        importance=req.importance or "unknown",
        reminder_minutes=req.reminder_minutes,
    )
    return _to_out(row)


_STRUCTURED_TASK_LINE = re.compile(
    r"^\s*(?:[-*+]\s+(?:\[[ xX]\]\s*)?|\d+[.、)]\s+)(.+?)\s*$"
)
_MAX_IMPORTED_TASKS = 50


def _normalized_title(title: str) -> str:
    return " ".join(title.strip().casefold().split())


def _editable_import_title(title: str) -> tuple[str, list[str], bool]:
    cleaned = title.strip()
    if len(cleaned) <= 256:
        return cleaned, [], False
    return cleaned[:256].rstrip(), ["标题过长"], True


def _existing_by_title(repo, user_id: str) -> dict[str, PersonalTaskRow]:
    rows, total = repo.list_tasks(
        user_id, page=1, page_size=200
    )
    all_rows = list(rows)
    page = 2
    while len(all_rows) < total:
        next_rows, _ = repo.list_tasks(
            user_id, page=page, page_size=200
        )
        if not next_rows:
            break
        all_rows.extend(next_rows)
        page += 1
    return {_normalized_title(row.title): row for row in all_rows}


@router.post("/import/analyze", response_model=TaskImportAnalyzeResponse)
async def analyze_task_import(
    req: TaskImportAnalyzeRequest,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> TaskImportAnalyzeResponse:
    """把学习计划或课程材料转换为可编辑的个人待办草稿。"""
    source_text = req.content.strip()
    explicit_titles = [
        match.group(1).strip()
        for line in source_text.splitlines()
        if (match := _STRUCTURED_TASK_LINE.match(line))
    ]
    existing = _existing_by_title(container.personal_task_repository, user.id)

    if len(explicit_titles) >= 2:
        drafts: list[TaskImportDraft] = []
        for raw_title in explicit_titles[:_MAX_IMPORTED_TASKS]:
            title, warnings, needs_confirmation = _editable_import_title(raw_title)
            match = existing.get(_normalized_title(title))
            drafts.append(TaskImportDraft(
                title=title,
                source_name=req.source_name,
                source_text=source_text,
                warnings=warnings,
                needs_confirmation=needs_confirmation,
                selected=match is None,
                existing_task_id=match.id if match else None,
                existing_status=match.status if match else None,
            ))
        return TaskImportAnalyzeResponse(
            mode="structured_text",
            split_reason=(
                f"识别到 {len(explicit_titles)} 条清单任务；最多保留 50 项"
                if len(explicit_titles) > _MAX_IMPORTED_TASKS
                else f"识别到 {len(drafts)} 条清单任务"
            ),
            needs_user_confirmation=(
                len(explicit_titles) > _MAX_IMPORTED_TASKS
                or any(draft.needs_confirmation for draft in drafts)
            ),
            tasks=drafts,
        )

    extracted = await container.notice_extraction.extract_multi(
        source_text,
        source_name=req.source_name,
        allow_multi_task=True,
    )
    drafts = []
    for item in extracted.tasks:
        title, title_warnings, title_needs_confirmation = _editable_import_title(
            item.task or item.title
        )
        if not title:
            continue
        match = existing.get(_normalized_title(title))
        importance = item.importance or "unknown"
        priority = "high" if importance in {"urgent", "high"} else (
            "low" if importance == "low" else "medium"
        )
        drafts.append(TaskImportDraft(
            title=title,
            deadline=item.deadline.isoformat() if item.deadline else None,
            materials=[material.name for material in item.materials],
            submission_method=item.submission_method,
            location=item.location,
            source_name=item.source_name or req.source_name,
            source_text=source_text,
            priority=priority,
            importance=importance,
            confidence=item.confidence,
            needs_confirmation=item.needs_confirmation or title_needs_confirmation,
            warnings=[*item.warnings, *title_warnings],
            selected=match is None,
            existing_task_id=match.id if match else None,
            existing_status=match.status if match else None,
        ))
    modes = {item.extractor_mode for item in extracted.tasks}
    truncated = len(drafts) > _MAX_IMPORTED_TASKS
    return TaskImportAnalyzeResponse(
        mode="llm" if "llm" in modes else "rules",
        split_reason=(
            f"{extracted.split_reason}；最多保留 50 项"
            if truncated else extracted.split_reason
        ),
        needs_user_confirmation=extracted.needs_user_confirmation or truncated,
        tasks=drafts[:_MAX_IMPORTED_TASKS],
    )


@router.post(
    "/import/commit", response_model=TaskImportCommitResponse, status_code=201
)
def commit_task_import(
    req: TaskImportCommitRequest,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> TaskImportCommitResponse:
    """批量保存确认后的草稿；同名任务保留原状态，不覆盖学习进度。"""
    repo = container.personal_task_repository
    created_rows, skipped_rows = repo.create_import_batch(
        user_id=user.id,
        tasks=[item.model_dump() for item in req.tasks],
    )
    return TaskImportCommitResponse(
        created=[_to_out(row) for row in created_rows],
        skipped_existing=[
            TaskImportExisting(task_id=row.id, title=row.title, status=row.status)
            for row in skipped_rows
        ],
    )


@router.get("/{task_id}", response_model=PersonalTaskOut)
def get_personal_task(
    task_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> PersonalTaskOut:
    """获取个人待办详情。跨用户访问返回 404(不泄露存在性)。"""
    repo = container.personal_task_repository
    row = repo.get_task(task_id, user_id=user.id)
    if row is None:
        raise PersonalTaskNotFound()
    return _to_out(row)


@router.patch("/{task_id}", response_model=PersonalTaskOut)
def update_personal_task(
    task_id: str,
    req: PersonalTaskUpdate,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> PersonalTaskOut:
    """更新个人待办字段(不允许通过此接口修改 status)。"""
    repo = container.personal_task_repository
    existing = repo.get_task(task_id, user_id=user.id)
    if existing is None:
        raise PersonalTaskNotFound()
    if existing.status == "deleted":
        raise PersonalTaskConflict("已删除的任务不能修改,请先恢复")
    fields = req.model_dump(exclude_unset=True)
    updated = repo.update_task(task_id, user_id=user.id, fields=fields)
    if updated is None:
        raise PersonalTaskNotFound()
    return _to_out(updated)


@router.post("/{task_id}/complete", response_model=PersonalTaskOut)
def complete_personal_task(
    task_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> PersonalTaskOut:
    """标记任务为已完成(pending → completed)。"""
    repo = container.personal_task_repository
    existing = repo.get_task(task_id, user_id=user.id)
    if existing is None:
        raise PersonalTaskNotFound()
    if existing.status == "deleted":
        raise PersonalTaskConflict("已删除的任务不能完成,请先恢复")
    if existing.status == "completed":
        # 幂等:已完成的任务再次调用 complete 直接返回当前状态
        return _to_out(existing)
    updated = repo.complete(task_id, user_id=user.id)
    if updated is None:
        raise PersonalTaskConflict("当前状态不允许完成")
    return _to_out(updated)


@router.post("/{task_id}/restore", response_model=PersonalTaskOut)
def restore_personal_task(
    task_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> PersonalTaskOut:
    """恢复任务为 pending(completed/deleted → pending)。"""
    repo = container.personal_task_repository
    existing = repo.get_task(task_id, user_id=user.id)
    if existing is None:
        raise PersonalTaskNotFound()
    updated = repo.restore(task_id, user_id=user.id)
    if updated is None:
        raise PersonalTaskConflict("当前状态不允许恢复")
    return _to_out(updated)


@router.delete("/{task_id}", response_model=PersonalTaskOut)
def delete_personal_task(
    task_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> PersonalTaskOut:
    """软删除任务(任意状态 → deleted)。

    物理删除由后续清理任务执行(本轮不实现)。
    """
    repo = container.personal_task_repository
    existing = repo.get_task(task_id, user_id=user.id)
    if existing is None:
        raise PersonalTaskNotFound()
    updated = repo.soft_delete(task_id, user_id=user.id)
    if updated is None:
        raise PersonalTaskConflict("当前状态不允许删除")
    return _to_out(updated)


@router.post("/rank-importance", response_model=ImportanceRankResponse)
async def rank_importance(
    req: ImportanceRankRequest,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> ImportanceRankResponse:
    """批量评定任务重要程度(AI 优先 + 规则降级)。

    - 不传 task_ids 时，评定当前用户所有 pending 任务(最多 50 条)
    - 传 task_ids 时，评定指定任务(跨用户或不存在的自动跳过)
    - 评定结果写回任务的 importance 字段
    """
    repo = container.personal_task_repository
    if req.task_ids:
        tasks: List[PersonalTaskRow] = []
        for tid in req.task_ids:
            row = repo.get_task(tid, user_id=user.id)
            if row is not None:
                tasks.append(row)
    else:
        rows, _ = repo.list_tasks(user.id, status="pending", page=1, page_size=50)
        tasks = list(rows)

    if not tasks:
        return ImportanceRankResponse(updated=[], skipped=[], mode="rules", total=0)

    payload = [
        {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "deadline": t.deadline,
            "source_text": t.source_text,
        }
        for t in tasks
    ]
    results, mode = await container.notice_extraction.rank_importance_batch(payload)

    updated_items: List[ImportanceRankItem] = []
    skipped: List[str] = []
    for r in results:
        tid = r["id"]
        imp = r["importance"]
        row = repo.update_task(tid, user_id=user.id, fields={"importance": imp})
        if row is None:
            skipped.append(tid)
        else:
            updated_items.append(ImportanceRankItem(
                task_id=tid,
                importance=imp,
                reason=r.get("reason"),
                mode=mode,
            ))
    return ImportanceRankResponse(
        updated=updated_items, skipped=skipped, mode=mode, total=len(updated_items)
    )


__all__ = ["router"]
