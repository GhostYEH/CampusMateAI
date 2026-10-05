"""互动课堂路由 —— 课程智能辅导空间的 magicclass 适配层。

权限：所有接口校验当前用户有权访问该课程(assert_course_access)。
边界：
- magicclass 故障不得影响课程详情/CPM 基础聊天：status 接口 safe 降级，
  generate 等写接口在未启用时抛 503 magicclass_NOT_ENABLED。
- 所有生成操作绑定当前用户与课程权限。
- 课程上下文、资料正文一律由后端按 course_id 重新读取，绝不信任客户端提交的内容。
"""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from dataclasses import replace
from typing import Annotated, Any, Dict, Optional, Sequence

from fastapi import APIRouter, Body, Depends, Query

from ...core.exceptions import NotFoundError
from ...models.multi_role import UserRow
from ...schemas.magicclass import (
    MODE_INTENT_LABELS,
    MagicClassClassroomsOut,
    MagicClassCompositionOut,
    MagicClassGenerateOut,
    MagicClassGenerateRequest,
    MagicClassMaterialOut,
    MagicClassPlanOut,
    MagicClassSessionOut,
    MagicClassStatusOut,
)
from ...services.container import ServiceContainer, get_container
from ...services.magicclass.classroom_service import MagicClassClassroomService
from ...services.magicclass.course_context import (
    ContextLimits,
    LearningContext,
    assert_course_access,
    build_learning_context,
)
from ...services.magicclass.requirement_builder import (
    GenerationRequestSnapshot,
    StudentBrief,
    choose_adaptive_mode,
    mode_label,
    normalize_mode,
)
from ..deps import current_user

router = APIRouter(prefix="/courses", tags=["互动课堂"])


def _container() -> ServiceContainer:
    return get_container()


def _service(c: ServiceContainer = Depends(_container)) -> MagicClassClassroomService:
    return c.magicclass_classroom_service


def _limits(container: ServiceContainer) -> ContextLimits:
    return ContextLimits(total_chars=container.settings.magicclass_course_context_max_chars)


def _brief(req: MagicClassGenerateRequest, context: LearningContext) -> StudentBrief:
    """把请求里的补充信息与**服务端解析出的**资料标题合成学生简报。"""
    selected = set(context.selected_material_ids)
    titles = tuple(ref.title for ref in context.materials if ref.id in selected)
    return StudentBrief(
        learning_objective=req.learning_objective,
        current_difficulty=req.current_difficulty,
        desired_duration_minutes=req.desired_duration_minutes,
        difficulty_level=req.difficulty_level,
        wants_more_practice=req.wants_more_practice,
        selected_material_titles=titles,
    )


def _snapshot_of(req: MagicClassGenerateRequest) -> GenerationRequestSnapshot:
    """把**已通过校验**的请求固化成本次生成的学生输入快照。

    只保存业务引用（资料存 id 不存标题/正文），不含任何凭据。
    """
    return GenerationRequestSnapshot(
        requested_mode=req.mode,
        mode=req.mode,
        learning_objective=req.learning_objective,
        current_difficulty=req.current_difficulty,
        desired_duration_minutes=req.desired_duration_minutes,
        difficulty_level=req.difficulty_level,
        wants_more_practice=req.wants_more_practice,
        selected_material_ids=tuple(req.selected_material_ids),
    )


def _materials_warning(unresolved: Sequence[str]) -> Optional[str]:
    if not unresolved:
        return None
    return (
        "以下课程资料无法使用（不存在、已删除或无权访问），本次未采用："
        + "、".join(unresolved)
    )


def _resolve_retry_snapshot(
    session: Any, body: Optional[MagicClassGenerateRequest]
) -> tuple[GenerationRequestSnapshot, str, str]:
    """决定 retry 用哪份学生输入，并**显式**说明来源。

    优先级：原任务快照（权威） > 经过校验的请求体 > 仅沿用原任务形态。

    绝不出现"收到了请求体却完全忽略、又不告诉调用方"的情况。
    """
    stored = GenerationRequestSnapshot.from_dict(session.request_snapshot)
    if stored is not None:
        note = "已按原任务的个性化设置重试。"
        if body is not None:
            note += "本次请求体中的字段被忽略（以原任务快照为准）。"
        return stored, "snapshot", note
    if body is not None:
        return (
            _snapshot_of(body),
            "client_body",
            "原任务没有保存个性化设置，已使用本次请求体中的设置。",
        )
    mode = normalize_mode(session.requested_mode or session.mode)
    return (
        GenerationRequestSnapshot(requested_mode=mode, mode=mode),
        "legacy_mode_only",
        "原任务没有保存个性化设置，且本次未提供请求体：仅沿用原任务的生成意图，"
        "不包含学习目标、难度、时长与资料选择等个性化信息。",
    )


@router.get(
    "/{course_id}/interactive-classroom/status",
    response_model=MagicClassStatusOut,
    summary="读取互动课堂状态",
    responses={
        200: {
            "description": "互动课堂服务状态；未启用或不可用时 reason 给出说明",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "服务已启用",
                            "value": {
                                "enabled": True,
                                "configured": True,
                                "available": True,
                                "degraded": False,
                                "compatibility": "compatible",
                                "service": "magicclass",
                                "version": "1.0.3",
                                "capabilities": {"generate": True, "tts": True},
                                "unavailable_capabilities": [],
                                "unavailable": False,
                                "embed_origin": "https://classroom.example.edu",
                                "browser_embed_available": True,
                                "external_3d_available": True,
                                "poll_interval_ms": 5000,
                                "reason": None,
                            },
                        }
                    }
                }
            },
        },
    },
)
async def get_status(
    course_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: MagicClassClassroomService = Depends(_service),
) -> MagicClassStatusOut:
    """读取互动课堂服务的启用与可用状态。

    未启用或不可用时 reason 给出说明；客户端据此决定是否展示生成入口。
    """
    # 先校验权限（即使服务未启用，也只在有权限时暴露状态）
    await run_in_threadpool(assert_course_access, container, user, course_id)
    payload: Dict[str, Any] = await service.status()
    if payload.get("reason") is None and not payload.get("enabled"):
        payload["reason"] = "互动课堂服务未启用"
    return MagicClassStatusOut(**payload)


@router.get(
    "/{course_id}/interactive-classroom/plan",
    response_model=MagicClassPlanOut,
    summary="读取生成前课堂方案",
    responses={
        200: {
            "description": "生成前给学生的课程、可选资料、推荐形态与理由",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "推荐概念讲解",
                            "value": {
                                "course_id": "course_db_2025",
                                "course_name": "数据库系统原理",
                                "mode": "explain",
                                "mode_label": "概念讲解",
                                "requested_mode": "adaptive",
                                "adaptive_reason": "课程包含较多文字资料，优先采用概念讲解。",
                                "intent_note": "内容形态只是生成意图，最终包含哪些形式由生成器根据课程内容决定。",
                                "materials": [
                                    {
                                        "id": "mat_1001",
                                        "title": "第 3 章 关系数据库设计.pdf",
                                        "kind": "资料",
                                    }
                                ],
                                "selected_material_ids": ["mat_1001"],
                                "context_truncated": False,
                                "capabilities": {"generate": True},
                                "external_3d_available": True,
                                "can_generate": True,
                                "reason": None,
                            },
                        }
                    }
                }
            },
        },
    },
)
async def get_plan(
    course_id: str,
    mode: str = Query("adaptive", description="生成意图"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: MagicClassClassroomService = Depends(_service),
) -> MagicClassPlanOut:
    """生成**之前**给学生看的信息：课程、可选资料、推荐形态与理由。

    这个接口不产生任何外部任务、不产生费用；学生确认后才调用 generate。
    """
    course = await run_in_threadpool(assert_course_access, container, user, course_id)
    try:
        requested = normalize_mode(mode)
    except ValueError:
        requested = "adaptive"
    context = await run_in_threadpool(build_learning_context,
        container, user, course, limits=_limits(container)
    )
    resolved = requested
    adaptive_reason: Optional[str] = None
    if requested == "adaptive":
        signals = replace(
            context.signals,
            external_3d_available=bool(container.settings.magicclass_external_3d_available),
        )
        resolved, adaptive_reason = choose_adaptive_mode(signals)
    status = await service.status()
    return MagicClassPlanOut(
        course_id=course_id,
        course_name=course.name,
        mode=resolved,
        mode_label=MODE_INTENT_LABELS.get(resolved, mode_label(resolved)),
        requested_mode=requested,
        adaptive_reason=adaptive_reason,
        materials=[
            MagicClassMaterialOut(id=ref.id, title=ref.title, kind=ref.kind)
            for ref in context.materials
        ],
        selected_material_ids=[],
        context_sources=context.sources,
        context_updated_at=context.updated_at,
        context_truncated=context.truncated,
        context_warnings=list(context.warnings),
        capabilities=status.get("capabilities", {}) or {},
        external_3d_available=bool(container.settings.magicclass_external_3d_available),
        can_generate=bool(status.get("enabled")),
        reason=status.get("reason"),
    )


@router.post(
    "/{course_id}/interactive-classroom/generate",
    response_model=MagicClassGenerateOut,
    status_code=202,
    summary="生成互动课堂",
    responses={
        202: {
            "description": "已受理，返回可轮询的课堂生成会话",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "已受理，排队生成",
                            "value": {
                                "accepted": True,
                                "session": {
                                    "session_id": "sess_9f2c1a",
                                    "course_id": "course_db_2025",
                                    "mode": "explain",
                                    "requested_mode": "adaptive",
                                    "job_id": "job_5b7e21",
                                    "status": "queued",
                                    "step": "queued",
                                    "progress": 0,
                                    "message": "已提交生成，请稍候。",
                                    "terminal": False,
                                    "retryable": False,
                                    "partial": False,
                                },
                                "poll_interval_ms": 5000,
                                "mode": "explain",
                                "requested_mode": "adaptive",
                                "request_source": "request",
                                "materials_unresolved": [],
                                "materials_warning": None,
                            },
                        }
                    }
                }
            },
        },
    },
)
async def generate_classroom(
    course_id: str,
    req: Annotated[
        MagicClassGenerateRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "生成概念讲解课堂",
                    "value": {
                        "mode": "explain",
                        "learning_objective": "掌握关系模型的三大要素",
                        "current_difficulty": "分不清主键与外键",
                        "desired_duration_minutes": 30,
                        "difficulty_level": "standard",
                        "wants_more_practice": True,
                        "selected_material_ids": ["mat_1001"],
                    },
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: MagicClassClassroomService = Depends(_service),
) -> MagicClassGenerateOut:
    """提交一次互动课堂生成，返回 202 与可轮询的会话。

    课程上下文与资料正文一律由服务端按 course_id 重新读取，客户端提交的正文不被信任。
    """
    course = await run_in_threadpool(assert_course_access, container, user, course_id)
    context = await run_in_threadpool(build_learning_context,
        container,
        user,
        course,
        limits=_limits(container),
        selected_material_ids=req.selected_material_ids,
    )
    session = await service.generate(
        user_id=user.id,
        course_id=course_id,
        context=context,
        mode=req.mode,
        brief=_brief(req, context),
        # 固化学生输入：retry 时以它为准，个性化不会再丢
        request_snapshot=_snapshot_of(req),
    )
    return MagicClassGenerateOut(
        accepted=True,
        session=MagicClassSessionOut.from_session(session, settings=container.settings),
        poll_interval_ms=container.settings.magicclass_poll_interval_ms,
        # 复用已有任务时必须返回任务真实 mode，而不是本次请求的 mode
        mode=session.mode,
        requested_mode=session.requested_mode or req.mode,
        adaptive_reason=session.adaptive_reason,
        materials=[
            MagicClassMaterialOut(id=ref.id, title=ref.title, kind=ref.kind)
            for ref in context.materials
        ],
        request_source="request",
        materials_unresolved=list(context.unresolved_material_ids),
        materials_warning=_materials_warning(context.unresolved_material_ids),
    )


@router.get(
    "/{course_id}/interactive-classroom/jobs/{session_id}",
    response_model=MagicClassSessionOut,
    summary="读取课堂生成进度",
    responses={
        200: {
            "description": "返回课堂生成任务的最新进度与会话状态",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "读取生成进度",
                            "value": {
                                "session_id": "sess_9f2c1a",
                                "course_id": "course_db_2025",
                                "mode": "explain",
                                "requested_mode": "adaptive",
                                "job_id": "job_5b7e21",
                                "status": "succeeded",
                                "step": "completed",
                                "progress": 100,
                                "message": "生成完成。",
                                "classroom_id": "cls_88aa12",
                                "url": "https://classroom.example.edu/classroom?id=cls_88aa12",
                                "scenes_count": 12,
                                "terminal": True,
                                "retryable": True,
                                "partial": False,
                            },
                        }
                    }
                }
            },
        }
    },
)
async def get_progress(
    course_id: str,
    session_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: MagicClassClassroomService = Depends(_service),
) -> MagicClassSessionOut:
    """读取课堂生成任务的最新进度。

    轮询并在必要时回读上游，用于展示生成状态、进度与终态。
    课堂生成任务不存在返回 404（NOT_FOUND）。
    """
    await run_in_threadpool(assert_course_access, container, user, course_id)
    session = await run_in_threadpool(service.get_session, user_id=user.id, course_id=course_id, session_id=session_id)
    if session is None:
        raise NotFoundError("课堂生成任务不存在")
    session = await service.poll(session)
    return MagicClassSessionOut.from_session(session, settings=container.settings)


@router.get(
    "/{course_id}/interactive-classroom/{session_id}/composition",
    response_model=MagicClassCompositionOut,
    summary="回读课堂实际组成",
    responses={
        200: {
            "description": "返回这节课真实包含的场景与 widget 分布",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "回读课堂实际组成",
                            "value": {
                                "classroom_id": "cls_88aa12",
                                "scene_total": 12,
                                "scenes": [
                                    {"type": "slide", "count": 6},
                                    {"type": "interactive", "count": 3},
                                    {"type": "quiz", "count": 2},
                                ],
                                "widget_types": [
                                    {"widget_type": "drag_drop", "count": 2},
                                    {"widget_type": "simulation", "count": 1},
                                ],
                                "has_whiteboard": True,
                                "has_tts": True,
                                "has_multi_agent": False,
                                "has_unknown_scene_type": False,
                                "has_unknown_widget_type": False,
                                "requires_external_3d": False,
                                "external_3d_available": True,
                                "degraded": False,
                                "read_at": "2026-10-06T08:06:00+00:00",
                                "error": None,
                            },
                        }
                    }
                }
            },
        }
    },
)
async def get_composition(
    course_id: str,
    session_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: MagicClassClassroomService = Depends(_service),
) -> MagicClassCompositionOut:
    """回读这节课**真实**包含的内容（幻灯片/测验/交互/项目式学习 + widget 分布）。

    只读、按需调用（不在历史列表里批量拉取上游）。请求 mode 只是意图，
    这里返回的才是实际产出，UI 必须用这份数据向学生说明"已生成内容包含……"。
    """
    await run_in_threadpool(assert_course_access, container, user, course_id)
    session = await run_in_threadpool(service.get_session, user_id=user.id, course_id=course_id, session_id=session_id)
    if session is None:
        raise NotFoundError("课堂生成任务不存在")
    composition = await service.composition(session)
    return MagicClassCompositionOut(**composition.to_dict())


@router.get(
    "/{course_id}/interactive-classroom",
    response_model=MagicClassClassroomsOut,
    summary="列出课程课堂",
    responses={
        200: {
            "description": "返回该课程已生成课堂列表与启用状态",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "列出课程课堂",
                            "value": {
                                "enabled": True,
                                "items": [
                                    {
                                        "session_id": "sess_9f2c1a",
                                        "classroom_id": "cls_88aa12",
                                        "url": "https://classroom.example.edu/classroom?id=cls_88aa12",
                                        "url_unavailable_reason": None,
                                        "mode": "explain",
                                        "scenes_count": 12,
                                        "created_at": "2026-10-06T08:00:00+00:00",
                                        "composition": None,
                                    }
                                ],
                            },
                        }
                    }
                }
            },
        }
    },
)
async def list_classrooms(
    course_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: MagicClassClassroomService = Depends(_service),
) -> MagicClassClassroomsOut:
    """列出该课程已生成的课堂。

    enabled 表示互动课堂服务是否启用；items 只包含当前用户在该课程下的课堂。
    """
    await run_in_threadpool(assert_course_access, container, user, course_id)
    status = await service.status()
    items = await run_in_threadpool(service.list_classrooms, user_id=user.id, course_id=course_id)
    return MagicClassClassroomsOut(enabled=status.get("enabled", False), items=items)


@router.post(
    "/{course_id}/interactive-classroom/{session_id}/retry",
    response_model=MagicClassGenerateOut,
    status_code=202,
    summary="重试生成课堂",
    responses={
        202: {
            "description": "已受理，以原任务的学生输入重新提交生成，返回新的可轮询会话",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "重新提交生成",
                            "value": {
                                "accepted": True,
                                "session": {
                                    "session_id": "sess_7d3b02",
                                    "course_id": "course_db_2025",
                                    "mode": "explain",
                                    "requested_mode": "explain",
                                    "job_id": "job_2c9f44",
                                    "status": "queued",
                                    "step": "queued",
                                    "progress": 0,
                                    "message": "已提交生成，请稍候。",
                                    "terminal": False,
                                    "retryable": False,
                                    "partial": False,
                                },
                                "poll_interval_ms": 5000,
                                "mode": "explain",
                                "requested_mode": "explain",
                                "request_source": "snapshot",
                                "request_source_note": "已按原任务的个性化设置重试。",
                                "materials_unresolved": [],
                                "materials_warning": None,
                            },
                        }
                    }
                }
            },
        }
    },
)
async def retry_session(
    course_id: str,
    session_id: str,
    body: Optional[MagicClassGenerateRequest] = Body(
        default=None,
        openapi_examples={
            "成功": {
                "summary": "以原任务设置重试生成",
                "value": {
                    "mode": "explain",
                    "learning_objective": "掌握关系模型的三大要素",
                    "current_difficulty": "分不清主键与外键",
                    "desired_duration_minutes": 30,
                    "difficulty_level": "standard",
                    "wants_more_practice": True,
                    "selected_material_ids": ["mat_1001"],
                },
            }
        },
    ),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: MagicClassClassroomService = Depends(_service),
) -> MagicClassGenerateOut:
    """重新生成一节课堂。

    magic class **没有**原生 retry：这里始终是"以原任务的学生输入重新提交一个新任务"。

    - 个性化以原任务的 `request_snapshot` 为**权威**，绝不因为客户端没传就丢掉；
    - 旧任务没有快照时，接受经过校验的请求体；
    - 两者都没有时走明确记录、有测试覆盖的兼容降级（只沿用原形态）；
    - 课程权限、资料授权、用户身份一律重新校验；
    - 绝不篡改旧 session。
    """
    course = await run_in_threadpool(assert_course_access, container, user, course_id)
    session = await run_in_threadpool(service.get_session, user_id=user.id, course_id=course_id, session_id=session_id)
    if session is None:
        raise NotFoundError("课堂生成任务不存在")
    if session.status not in ("failed", "succeeded"):
        # 进行中任务返回现状，不重复提交
        session = await service.poll(session)
        return MagicClassGenerateOut(
            accepted=False,
            session=MagicClassSessionOut.from_session(session, settings=container.settings),
            poll_interval_ms=container.settings.magicclass_poll_interval_ms,
            mode=session.mode,
            requested_mode=session.requested_mode,
            adaptive_reason=session.adaptive_reason,
            request_source="in_progress",
            request_source_note="原任务仍在进行中，已返回当前进度，未重复提交生成。",
        )

    snapshot, source, note = _resolve_retry_snapshot(session, body)
    # 重新从服务端读取课程 / 资料 / 学生上下文，并重新做资料授权校验
    context = await run_in_threadpool(build_learning_context,
        container,
        user,
        course,
        limits=_limits(container),
        selected_material_ids=snapshot.selected_material_ids,
    )
    resolved = set(context.selected_material_ids)
    titles = tuple(ref.title for ref in context.materials if ref.id in resolved)
    new_session = await service.generate(
        user_id=user.id,
        course_id=course_id,
        context=context,
        # 用原始意图（可能是 adaptive）重跑确定性解析，而不是硬套上次的结果
        mode=snapshot.requested_mode,
        brief=snapshot.to_brief(selected_material_titles=titles),
        request_snapshot=snapshot,
    )
    return MagicClassGenerateOut(
        accepted=True,
        session=MagicClassSessionOut.from_session(new_session, settings=container.settings),
        poll_interval_ms=container.settings.magicclass_poll_interval_ms,
        mode=new_session.mode,
        requested_mode=new_session.requested_mode,
        adaptive_reason=new_session.adaptive_reason,
        materials=[
            MagicClassMaterialOut(id=ref.id, title=ref.title, kind=ref.kind)
            for ref in context.materials
        ],
        request_source=source,
        request_source_note=note,
        materials_unresolved=list(context.unresolved_material_ids),
        materials_warning=_materials_warning(context.unresolved_material_ids),
    )


__all__ = ["router"]
