"""个人待办任务路由 — /api/v1/tasks。

设计目标: 学生从通知抽取后的个人待办 CRUD + 完成/恢复/软删除。
与 `assignments`(教师发布的班级作业)严格分离 — 不复用任何 assignment 资源。

权限:
- 所有接口必须 JWT 认证
- 任务按 `user_id` 隔离,JWT 用户只能读写自己的任务
- 所有用户仅能读取本人的任务

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
from typing import Annotated, List, Optional

from fastapi import APIRouter, Body, Depends, Query
from starlette.concurrency import run_in_threadpool

from ...core.exceptions import (
    PersonalTaskConflict,
    PersonalTaskNotFound,
)
from ...core.logging import logger
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
from ...services.learner_event_service import LearnerEventService
from ..deps import current_user

router = APIRouter(prefix="/tasks", tags=["个人待办"])


def _container() -> ServiceContainer:
    return get_container()


def _learner_event_service(
    c: ServiceContainer = Depends(_container),
) -> LearnerEventService:
    return c.learner_event_service


# 学习通作业/考试的状态由学习通决定，CampusMate 侧默认只读。
# 允许在这里勾选"完成"会让本地状态与学习通真实状态分叉(下一次同步又会翻回去)，
# 所以这些条目只能通过同步更新，不能在个人待办接口里伪造完成。
_READ_ONLY_SOURCES = {"chaoxing"}


def _assert_task_writable(row: PersonalTaskRow) -> None:
    if (row.source or "") in _READ_ONLY_SOURCES:
        raise PersonalTaskConflict(
            "学习通作业/考试的状态由学习通决定，请到课程详情查看原始任务"
        )


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
        source=row.source,
        external_id=row.external_id,
        course_id=row.course_id,
        source_url=row.source_url,
        last_synced_at=row.last_synced_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
        deleted_at=row.deleted_at,
    )


@router.get(
    "",
    response_model=Page,
    summary="列出个人待办",
    responses={
        200: {
            "description": "返回当前用户的个人待办分页列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "待办列表",
                            "value": {
                                "items": [
                                    {
                                        "id": "task_20261006_001",
                                        "user_id": "u_demo",
                                        "title": "提交暑期实践证明材料",
                                        "description": "填写实践申请表并附证明材料",
                                        "target_students": "2024级各班",
                                        "deadline": "2026-07-30T23:59:00+08:00",
                                        "materials": ["实践申请表", "实践证明材料"],
                                        "submission_method": "提交纸质版至学院办公室",
                                        "location": "信息工程学院办公室",
                                        "source_name": "信息工程学院通知",
                                        "priority": "high",
                                        "importance": "important",
                                        "status": "pending",
                                        "created_at": "2026-07-20T09:05:00+08:00",
                                        "updated_at": "2026-07-20T09:05:00+08:00",
                                    }
                                ],
                                "total": 1,
                                "page": 1,
                                "page_size": 50,
                                "has_more": False,
                            },
                        }
                    }
                }
            },
        },
    },
)
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


@router.post(
    "",
    response_model=PersonalTaskOut,
    status_code=201,
    summary="创建个人待办",
    responses={
        201: {
            "description": "创建成功，返回新建的个人待办",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "新建待办",
                            "value": {
                                "id": "task_20261006_001",
                                "user_id": "u_demo",
                                "title": "提交暑期实践证明材料",
                                "description": "填写实践申请表并附证明材料",
                                "target_students": "2024级各班",
                                "deadline": "2026-07-30T23:59:00+08:00",
                                "materials": ["实践申请表", "实践证明材料"],
                                "submission_method": "提交纸质版至学院办公室",
                                "location": "信息工程学院办公室",
                                "source_name": "信息工程学院通知",
                                "priority": "high",
                                "importance": "important",
                                "status": "pending",
                                "created_at": "2026-07-20T09:05:00+08:00",
                                "updated_at": "2026-07-20T09:05:00+08:00",
                            },
                        }
                    }
                }
            },
        },
    },
)
def create_personal_task(
    req: Annotated[
        PersonalTaskCreate,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "创建一条实践材料待办",
                    "value": {
                        "title": "提交暑期实践证明材料",
                        "description": "填写实践申请表并附证明材料",
                        "target_students": "2024级各班",
                        "deadline": "2026-07-30T23:59:00+08:00",
                        "materials": ["实践申请表", "实践证明材料"],
                        "submission_method": "提交纸质版至学院办公室",
                        "location": "信息工程学院办公室",
                        "source_name": "信息工程学院通知",
                        "source_text": "请2024级学生于7月30日前提交实践申请材料。",
                        "priority": "high",
                        "importance": "important",
                        "reminder_minutes": 1440,
                    },
                }
            }
        ),
    ],
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


@router.post(
    "/import/analyze",
    response_model=TaskImportAnalyzeResponse,
    summary="解析待办导入草稿",
    responses={
        200: {
            "description": "返回可编辑的待办草稿与拆分说明",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "结构化清单解析结果",
                            "value": {
                                "mode": "structured_text",
                                "split_reason": "识别到 2 条清单任务",
                                "needs_user_confirmation": False,
                                "tasks": [
                                    {
                                        "title": "提交暑期实践证明材料",
                                        "deadline": "2026-07-30T23:59:00+08:00",
                                        "materials": ["实践申请表", "实践证明材料"],
                                        "submission_method": "提交纸质版至学院办公室",
                                        "location": "信息工程学院办公室",
                                        "source_name": "信息工程学院通知",
                                        "priority": "high",
                                        "importance": "important",
                                        "confidence": 0.82,
                                        "needs_confirmation": False,
                                        "selected": True,
                                        "existing_task_id": None,
                                        "existing_status": None,
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
async def analyze_task_import(
    req: Annotated[
        TaskImportAnalyzeRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "解析课程材料为待办草稿",
                    "value": {
                        "content": "1. 7月30日前提交实践申请表\n2. 8月5日前完成线上安全考试",
                        "source_name": "信息工程学院通知",
                    },
                }
            }
        ),
    ],
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
    "/import/commit",
    response_model=TaskImportCommitResponse,
    status_code=201,
    summary="提交待办导入草稿",
    responses={
        201: {
            "description": "批量保存成功，返回新建与跳过的任务",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "批量保存结果",
                            "value": {
                                "created": [
                                    {
                                        "id": "task_20261006_001",
                                        "user_id": "u_demo",
                                        "title": "提交暑期实践证明材料",
                                        "description": "填写实践申请表并附证明材料",
                                        "deadline": "2026-07-30T23:59:00+08:00",
                                        "materials": ["实践申请表", "实践证明材料"],
                                        "submission_method": "提交纸质版至学院办公室",
                                        "location": "信息工程学院办公室",
                                        "source_name": "信息工程学院通知",
                                        "priority": "high",
                                        "importance": "important",
                                        "status": "pending",
                                        "created_at": "2026-07-20T09:05:00+08:00",
                                        "updated_at": "2026-07-20T09:05:00+08:00",
                                    }
                                ],
                                "skipped_existing": [
                                    {
                                        "task_id": "task_20260901_007",
                                        "title": "提交暑期实践证明材料",
                                        "status": "completed",
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
def commit_task_import(
    req: Annotated[
        TaskImportCommitRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "保存确认后的待办草稿",
                    "value": {
                        "tasks": [
                            {
                                "title": "提交暑期实践证明材料",
                                "deadline": "2026-07-30T23:59:00+08:00",
                                "materials": ["实践申请表", "实践证明材料"],
                                "source_name": "信息工程学院通知",
                                "priority": "high",
                                "importance": "important",
                            }
                        ]
                    },
                }
            }
        ),
    ],
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


@router.get(
    "/{task_id}",
    response_model=PersonalTaskOut,
    summary="获取个人待办详情",
    responses={
        200: {
            "description": "返回指定个人待办的详情",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "待办详情",
                            "value": {
                                "id": "task_20261006_001",
                                "user_id": "u_demo",
                                "title": "提交暑期实践证明材料",
                                "description": "填写实践申请表并附证明材料",
                                "target_students": "2024级各班",
                                "deadline": "2026-07-30T23:59:00+08:00",
                                "materials": ["实践申请表", "实践证明材料"],
                                "submission_method": "提交纸质版至学院办公室",
                                "location": "信息工程学院办公室",
                                "source_name": "信息工程学院通知",
                                "priority": "high",
                                "importance": "important",
                                "status": "pending",
                                "created_at": "2026-07-20T09:05:00+08:00",
                                "updated_at": "2026-07-20T09:05:00+08:00",
                            },
                        }
                    }
                }
            },
        },
    },
)
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


@router.patch(
    "/{task_id}",
    response_model=PersonalTaskOut,
    summary="更新个人待办",
    responses={
        200: {
            "description": "更新成功，返回更新后的个人待办",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "更新后的待办",
                            "value": {
                                "id": "task_20261006_001",
                                "user_id": "u_demo",
                                "title": "提交暑期实践证明材料（含电子版）",
                                "description": "填写实践申请表并附证明材料",
                                "target_students": "2024级各班",
                                "deadline": "2026-07-30T23:59:00+08:00",
                                "materials": ["实践申请表", "实践证明材料"],
                                "submission_method": "提交纸质版至学院办公室",
                                "location": "信息工程学院办公室",
                                "source_name": "信息工程学院通知",
                                "priority": "high",
                                "importance": "important",
                                "status": "pending",
                                "created_at": "2026-07-20T09:05:00+08:00",
                                "updated_at": "2026-07-22T14:30:00+08:00",
                            },
                        }
                    }
                }
            },
        },
    },
)
def update_personal_task(
    task_id: str,
    req: Annotated[
        PersonalTaskUpdate,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "修改标题与截止时间",
                    "value": {
                        "title": "提交暑期实践证明材料（含电子版）",
                        "deadline": "2026-07-30T23:59:00+08:00",
                        "priority": "high",
                        "reminder_minutes": 1440,
                    },
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> PersonalTaskOut:
    """更新个人待办字段(不允许通过此接口修改 status)。"""
    repo = container.personal_task_repository
    existing = repo.get_task(task_id, user_id=user.id)
    if existing is None:
        raise PersonalTaskNotFound()
    _assert_task_writable(existing)
    if existing.status == "deleted":
        raise PersonalTaskConflict("已删除的任务不能修改,请先恢复")
    fields = req.model_dump(exclude_unset=True)
    updated = repo.update_task(task_id, user_id=user.id, fields=fields)
    if updated is None:
        raise PersonalTaskNotFound()
    return _to_out(updated)


@router.post(
    "/{task_id}/complete",
    response_model=PersonalTaskOut,
    summary="完成个人待办",
    responses={
        200: {
            "description": "标记完成成功，返回已完成的个人待办",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "已完成待办",
                            "value": {
                                "id": "task_20261006_001",
                                "user_id": "u_demo",
                                "title": "提交暑期实践证明材料",
                                "deadline": "2026-07-30T23:59:00+08:00",
                                "materials": ["实践申请表", "实践证明材料"],
                                "source_name": "信息工程学院通知",
                                "priority": "high",
                                "importance": "important",
                                "status": "completed",
                                "created_at": "2026-07-20T09:05:00+08:00",
                                "updated_at": "2026-07-25T16:00:00+08:00",
                                "completed_at": "2026-07-25T16:00:00+08:00",
                            },
                        }
                    }
                }
            },
        },
    },
)
def complete_personal_task(
    task_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    event_service: LearnerEventService = Depends(_learner_event_service),
) -> PersonalTaskOut:
    """标记任务为已完成(pending → completed)。"""
    repo = container.personal_task_repository
    existing = repo.get_task(task_id, user_id=user.id)
    if existing is None:
        raise PersonalTaskNotFound()
    _assert_task_writable(existing)
    if existing.status == "deleted":
        raise PersonalTaskConflict("已删除的任务不能完成,请先恢复")
    if existing.status == "completed":
        # 幂等:已完成的任务再次调用 complete 直接返回当前状态
        return _to_out(existing)
    updated = repo.complete(task_id, user_id=user.id)
    if updated is None:
        raise PersonalTaskConflict("当前状态不允许完成")
    try:
        event_service.record_personal_task_completed(updated)
    except Exception as exc:
        logger.warning(
            "learner_event_append_failed action={} user_id={} subject_type={} subject_id={} exception_type={}",
            "task_completed",
            user.id,
            "personal_task",
            updated.id,
            type(exc).__name__,
        )
    return _to_out(updated)


@router.post(
    "/{task_id}/restore",
    response_model=PersonalTaskOut,
    summary="恢复个人待办",
    responses={
        200: {
            "description": "恢复成功，返回重新回到 pending 的个人待办",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "已恢复待办",
                            "value": {
                                "id": "task_20261006_001",
                                "user_id": "u_demo",
                                "title": "提交暑期实践证明材料",
                                "deadline": "2026-07-30T23:59:00+08:00",
                                "materials": ["实践申请表", "实践证明材料"],
                                "source_name": "信息工程学院通知",
                                "priority": "high",
                                "importance": "important",
                                "status": "pending",
                                "created_at": "2026-07-20T09:05:00+08:00",
                                "updated_at": "2026-07-26T09:00:00+08:00",
                            },
                        }
                    }
                }
            },
        },
    },
)
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
    _assert_task_writable(existing)
    updated = repo.restore(task_id, user_id=user.id)
    if updated is None:
        raise PersonalTaskConflict("当前状态不允许恢复")
    return _to_out(updated)


@router.delete(
    "/{task_id}",
    response_model=PersonalTaskOut,
    summary="软删除个人待办",
    responses={
        200: {
            "description": "软删除成功，返回 deleted 状态的个人待办",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "已删除待办",
                            "value": {
                                "id": "task_20261006_001",
                                "user_id": "u_demo",
                                "title": "提交暑期实践证明材料",
                                "deadline": "2026-07-30T23:59:00+08:00",
                                "materials": ["实践申请表", "实践证明材料"],
                                "source_name": "信息工程学院通知",
                                "priority": "high",
                                "importance": "important",
                                "status": "deleted",
                                "created_at": "2026-07-20T09:05:00+08:00",
                                "updated_at": "2026-07-28T10:00:00+08:00",
                                "deleted_at": "2026-07-28T10:00:00+08:00",
                            },
                        }
                    }
                }
            },
        },
    },
)
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


@router.post(
    "/rank-importance",
    response_model=ImportanceRankResponse,
    summary="批量评定任务重要程度",
    responses={
        200: {
            "description": "返回评定结果、跳过列表与实际使用模式",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "重要程度评定结果",
                            "value": {
                                "updated": [
                                    {
                                        "task_id": "task_20261006_001",
                                        "importance": "high",
                                        "reason": "涉及材料提交且有明确截止时间",
                                        "mode": "llm",
                                    }
                                ],
                                "skipped": [],
                                "mode": "llm",
                                "total": 1,
                            },
                        }
                    }
                }
            },
        },
    },
)
async def rank_importance(
    req: Annotated[
        ImportanceRankRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "评定指定任务的重要程度",
                    "value": {"task_ids": ["task_20261006_001", "task_20261006_002"]},
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> ImportanceRankResponse:
    """批量评定任务重要程度(AI 优先 + 规则降级)。

    - 不传 task_ids 时，评定当前用户所有 pending 任务(最多 50 条)
    - 传 task_ids 时，评定指定任务(跨用户或不存在的自动跳过)
    - 评定结果写回任务的 importance 字段

    保留 async（含真实 AI 调用）；同步 SQLite 读取/写回两个阶段分别整体
    下放到线程池，不在事件循环里逐条阻塞，也不为每个任务单独建线程任务。
    """
    repo = container.personal_task_repository
    tasks: List[PersonalTaskRow] = await run_in_threadpool(
        _load_tasks_for_ranking, repo, user.id, req.task_ids
    )

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

    updated_items, skipped = await run_in_threadpool(
        _apply_importance_results, repo, user.id, results, mode
    )
    return ImportanceRankResponse(
        updated=updated_items, skipped=skipped, mode=mode, total=len(updated_items)
    )


def _load_tasks_for_ranking(
    repo, user_id: str, task_ids: List[str]
) -> List[PersonalTaskRow]:
    """同步阶段：按显式 id 或 pending 列表读取待评定任务。"""
    if task_ids:
        tasks: List[PersonalTaskRow] = []
        for tid in task_ids:
            row = repo.get_task(tid, user_id=user_id)
            if row is not None:
                tasks.append(row)
        return tasks
    rows, _ = repo.list_tasks(user_id, status="pending", page=1, page_size=50)
    return list(rows)


def _apply_importance_results(
    repo, user_id: str, results: List[dict], mode: str
) -> tuple[List[ImportanceRankItem], List[str]]:
    """同步阶段：把评定结果写回任务。"""
    updated_items: List[ImportanceRankItem] = []
    skipped: List[str] = []
    for r in results:
        tid = r["id"]
        imp = r["importance"]
        row = repo.update_task(tid, user_id=user_id, fields={"importance": imp})
        if row is None:
            skipped.append(tid)
        else:
            updated_items.append(ImportanceRankItem(
                task_id=tid,
                importance=imp,
                reason=r.get("reason"),
                mode=mode,
            ))
    return updated_items, skipped


__all__ = ["router"]
