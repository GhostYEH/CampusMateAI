"""互动课堂路由 —— 课程智能辅导空间的 OpenMAIC 适配层。

权限：所有接口校验当前用户有权访问该课程(assert_course_access)。
边界：
- OpenMAIC 故障不得影响课程详情/CPM 基础聊天：status 接口 safe 降级，
  generate 等写接口在未启用时抛 503 OpenMAIC_NOT_ENABLED。
- 所有生成操作绑定当前用户与课程权限。
- 课程上下文、资料正文一律由后端按 course_id 重新读取，绝不信任客户端提交的内容。
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, Optional, Sequence

from fastapi import APIRouter, Body, Depends, Query

from ...core.exceptions import NotFoundError
from ...models.multi_role import UserRow
from ...schemas.openmaic import (
    MODE_INTENT_LABELS,
    OpenMAICClassroomsOut,
    OpenMAICCompositionOut,
    OpenMAICGenerateOut,
    OpenMAICGenerateRequest,
    OpenMAICMaterialOut,
    OpenMAICPlanOut,
    OpenMAICSessionOut,
    OpenMAICStatusOut,
)
from ...services.container import ServiceContainer, get_container
from ...services.openmaic.classroom_service import OpenMAICClassroomService
from ...services.openmaic.course_context import (
    ContextLimits,
    LearningContext,
    assert_course_access,
    build_learning_context,
)
from ...services.openmaic.requirement_builder import (
    GenerationRequestSnapshot,
    StudentBrief,
    choose_adaptive_mode,
    mode_label,
    normalize_mode,
)
from ..deps import current_user

router = APIRouter(prefix="/courses", tags=["interactive-classroom"])


def _container() -> ServiceContainer:
    return get_container()


def _service(c: ServiceContainer = Depends(_container)) -> OpenMAICClassroomService:
    return c.openmaic_classroom_service


def _limits(container: ServiceContainer) -> ContextLimits:
    return ContextLimits(total_chars=container.settings.openmaic_course_context_max_chars)


def _brief(req: OpenMAICGenerateRequest, context: LearningContext) -> StudentBrief:
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


def _snapshot_of(req: OpenMAICGenerateRequest) -> GenerationRequestSnapshot:
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
    session: Any, body: Optional[OpenMAICGenerateRequest]
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
    response_model=OpenMAICStatusOut,
)
async def get_status(
    course_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: OpenMAICClassroomService = Depends(_service),
) -> OpenMAICStatusOut:
    # 先校验权限（即使服务未启用，也只在有权限时暴露状态）
    assert_course_access(container, user, course_id)
    payload: Dict[str, Any] = await service.status()
    if payload.get("reason") is None and not payload.get("enabled"):
        payload["reason"] = "互动课堂服务未启用"
    return OpenMAICStatusOut(**payload)


@router.get(
    "/{course_id}/interactive-classroom/plan",
    response_model=OpenMAICPlanOut,
)
async def get_plan(
    course_id: str,
    mode: str = Query("adaptive", description="生成意图"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: OpenMAICClassroomService = Depends(_service),
) -> OpenMAICPlanOut:
    """生成**之前**给学生看的信息：课程、可选资料、推荐形态与理由。

    这个接口不产生任何外部任务、不产生费用；学生确认后才调用 generate。
    """
    course = assert_course_access(container, user, course_id)
    try:
        requested = normalize_mode(mode)
    except ValueError:
        requested = "adaptive"
    context = build_learning_context(
        container, user, course, limits=_limits(container)
    )
    resolved = requested
    adaptive_reason: Optional[str] = None
    if requested == "adaptive":
        signals = replace(
            context.signals,
            external_3d_available=bool(container.settings.openmaic_external_3d_available),
        )
        resolved, adaptive_reason = choose_adaptive_mode(signals)
    status = await service.status()
    return OpenMAICPlanOut(
        course_id=course_id,
        course_name=course.name,
        mode=resolved,
        mode_label=MODE_INTENT_LABELS.get(resolved, mode_label(resolved)),
        requested_mode=requested,
        adaptive_reason=adaptive_reason,
        materials=[
            OpenMAICMaterialOut(id=ref.id, title=ref.title, kind=ref.kind)
            for ref in context.materials
        ],
        selected_material_ids=[],
        context_sources=context.sources,
        context_updated_at=context.updated_at,
        context_truncated=context.truncated,
        context_warnings=list(context.warnings),
        capabilities=status.get("capabilities", {}) or {},
        external_3d_available=bool(container.settings.openmaic_external_3d_available),
        can_generate=bool(status.get("enabled")),
        reason=status.get("reason"),
    )


@router.post(
    "/{course_id}/interactive-classroom/generate",
    response_model=OpenMAICGenerateOut,
    status_code=202,
)
async def generate_classroom(
    course_id: str,
    req: OpenMAICGenerateRequest,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: OpenMAICClassroomService = Depends(_service),
) -> OpenMAICGenerateOut:
    course = assert_course_access(container, user, course_id)
    context = build_learning_context(
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
    return OpenMAICGenerateOut(
        accepted=True,
        session=OpenMAICSessionOut.from_session(session, settings=container.settings),
        poll_interval_ms=container.settings.openmaic_poll_interval_ms,
        # 复用已有任务时必须返回任务真实 mode，而不是本次请求的 mode
        mode=session.mode,
        requested_mode=session.requested_mode or req.mode,
        adaptive_reason=session.adaptive_reason,
        materials=[
            OpenMAICMaterialOut(id=ref.id, title=ref.title, kind=ref.kind)
            for ref in context.materials
        ],
        request_source="request",
        materials_unresolved=list(context.unresolved_material_ids),
        materials_warning=_materials_warning(context.unresolved_material_ids),
    )


@router.get(
    "/{course_id}/interactive-classroom/jobs/{session_id}",
    response_model=OpenMAICSessionOut,
)
async def get_progress(
    course_id: str,
    session_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: OpenMAICClassroomService = Depends(_service),
) -> OpenMAICSessionOut:
    assert_course_access(container, user, course_id)
    session = service.get_session(user_id=user.id, course_id=course_id, session_id=session_id)
    if session is None:
        raise NotFoundError("课堂生成任务不存在")
    session = await service.poll(session)
    return OpenMAICSessionOut.from_session(session, settings=container.settings)


@router.get(
    "/{course_id}/interactive-classroom/{session_id}/composition",
    response_model=OpenMAICCompositionOut,
)
async def get_composition(
    course_id: str,
    session_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: OpenMAICClassroomService = Depends(_service),
) -> OpenMAICCompositionOut:
    """回读这节课**真实**包含的内容（幻灯片/测验/交互/项目式学习 + widget 分布）。

    只读、按需调用（不在历史列表里批量拉取上游）。请求 mode 只是意图，
    这里返回的才是实际产出，UI 必须用这份数据向学生说明"已生成内容包含……"。
    """
    assert_course_access(container, user, course_id)
    session = service.get_session(user_id=user.id, course_id=course_id, session_id=session_id)
    if session is None:
        raise NotFoundError("课堂生成任务不存在")
    composition = await service.composition(session)
    return OpenMAICCompositionOut(**composition.to_dict())


@router.get(
    "/{course_id}/interactive-classroom",
    response_model=OpenMAICClassroomsOut,
)
async def list_classrooms(
    course_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: OpenMAICClassroomService = Depends(_service),
) -> OpenMAICClassroomsOut:
    assert_course_access(container, user, course_id)
    status = await service.status()
    items = service.list_classrooms(user_id=user.id, course_id=course_id)
    return OpenMAICClassroomsOut(enabled=status.get("enabled", False), items=items)


@router.post(
    "/{course_id}/interactive-classroom/{session_id}/retry",
    response_model=OpenMAICGenerateOut,
    status_code=202,
)
async def retry_session(
    course_id: str,
    session_id: str,
    body: Optional[OpenMAICGenerateRequest] = Body(default=None),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: OpenMAICClassroomService = Depends(_service),
) -> OpenMAICGenerateOut:
    """重新生成一节课堂。

    OpenMAIC **没有**原生 retry：这里始终是"以原任务的学生输入重新提交一个新任务"。

    - 个性化以原任务的 `request_snapshot` 为**权威**，绝不因为客户端没传就丢掉；
    - 旧任务没有快照时，接受经过校验的请求体；
    - 两者都没有时走明确记录、有测试覆盖的兼容降级（只沿用原形态）；
    - 课程权限、资料授权、用户身份一律重新校验；
    - 绝不篡改旧 session。
    """
    course = assert_course_access(container, user, course_id)
    session = service.get_session(user_id=user.id, course_id=course_id, session_id=session_id)
    if session is None:
        raise NotFoundError("课堂生成任务不存在")
    if session.status not in ("failed", "succeeded"):
        # 进行中任务返回现状，不重复提交
        session = await service.poll(session)
        return OpenMAICGenerateOut(
            accepted=False,
            session=OpenMAICSessionOut.from_session(session, settings=container.settings),
            poll_interval_ms=container.settings.openmaic_poll_interval_ms,
            mode=session.mode,
            requested_mode=session.requested_mode,
            adaptive_reason=session.adaptive_reason,
            request_source="in_progress",
            request_source_note="原任务仍在进行中，已返回当前进度，未重复提交生成。",
        )

    snapshot, source, note = _resolve_retry_snapshot(session, body)
    # 重新从服务端读取课程 / 资料 / 学生上下文，并重新做资料授权校验
    context = build_learning_context(
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
    return OpenMAICGenerateOut(
        accepted=True,
        session=OpenMAICSessionOut.from_session(new_session, settings=container.settings),
        poll_interval_ms=container.settings.openmaic_poll_interval_ms,
        mode=new_session.mode,
        requested_mode=new_session.requested_mode,
        adaptive_reason=new_session.adaptive_reason,
        materials=[
            OpenMAICMaterialOut(id=ref.id, title=ref.title, kind=ref.kind)
            for ref in context.materials
        ],
        request_source=source,
        request_source_note=note,
        materials_unresolved=list(context.unresolved_material_ids),
        materials_warning=_materials_warning(context.unresolved_material_ids),
    )


__all__ = ["router"]
