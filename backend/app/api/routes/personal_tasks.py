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
