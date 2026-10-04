"""互动课堂路由 —— 课程智能辅导空间的 magicclass 适配层。

权限：所有接口校验当前用户有权访问该课程(assert_course_access)。
边界：
- magicclass 故障不得影响课程详情/CPM 基础聊天：status 接口 safe 降级，
  generate 等写接口在未启用时抛 503 magicclass_NOT_ENABLED。
- 所有生成操作绑定当前用户与课程权限。
- 课程上下文、资料正文一律由后端按 course_id 重新读取，绝不信任客户端提交的内容。
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, Optional, Sequence

from fastapi import APIRouter, Body, Depends, File, Header, HTTPException, Query, UploadFile, status

from ...core.exceptions import Forbidden, NotFoundError
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
from ...schemas.magicclass_fusion import MaterialOut
from ...services.container import ServiceContainer, get_container
from ...services.magicclass.classroom_service import MagicClassClassroomService
from ...services.magicclass.course_context import (
    ContextLimits,
    LearningContext,
    MaterialRef,
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
from ...services.magicclass.fusion_client import MagicClassFusionClient
from ...services.magicclass.material_extraction import MAX_MATERIAL_BYTES, extract_material
from ..deps import current_user

router = APIRouter(prefix="/courses", tags=["interactive-classroom"])
self_router = APIRouter(prefix="/self-classroom", tags=["interactive-classroom"])
SELF_COURSE_ID = "__self_study__"


def _container() -> ServiceContainer:
    return get_container()


def _service(c: ServiceContainer = Depends(_container)) -> MagicClassClassroomService:
    return c.magicclass_classroom_service


def _self_student(user: UserRow) -> None:
    if user.role != "student":
        raise Forbidden("仅学生可生成互动课堂")


@self_router.get("/status", response_model=MagicClassStatusOut)
async def self_classroom_status(
    user: UserRow = Depends(current_user),
    service: MagicClassClassroomService = Depends(_service),
) -> MagicClassStatusOut:
    _self_student(user)
    return MagicClassStatusOut(**await service.status())


@self_router.post("/generate", response_model=MagicClassGenerateOut, status_code=202)
async def generate_self_classroom(
    req: MagicClassGenerateRequest,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: MagicClassClassroomService = Depends(_service),
) -> MagicClassGenerateOut:
    _self_student(user)
    topic = (req.learning_objective or "").strip()
    if not topic:
        raise HTTPException(status_code=400, detail="请先输入想学的内容")
    context = LearningContext(
        text=f"学生自主选题：{topic}", sources={"topic": "student"},
        unresolved_material_ids=tuple(req.selected_material_ids),
    )
    if req.selected_material_ids:
        if not container.settings.magicclass_fusion_enabled:
            raise HTTPException(status_code=503, detail="资料服务暂时不可用")
        context = await _attach_uploaded_materials(container, user, SELF_COURSE_ID, context)
        if context.unresolved_material_ids:
            raise HTTPException(status_code=400, detail="所选资料不存在、尚未完成提取，或不属于当前账号")
    session = await service.generate(
        user_id=user.id,
        course_id=SELF_COURSE_ID,
        context=context,
        mode=req.mode,
        brief=_brief(req, context),
        request_snapshot=_snapshot_of(req),
    )
    return MagicClassGenerateOut(
        accepted=True,
        session=MagicClassSessionOut.from_session(session, settings=container.settings),
        poll_interval_ms=container.settings.magicclass_poll_interval_ms,
        mode=session.mode,
        requested_mode=session.requested_mode or req.mode,
        adaptive_reason=session.adaptive_reason,
        request_source="request",
    )


@self_router.post("/materials", response_model=MaterialOut, status_code=status.HTTP_201_CREATED)
async def upload_self_classroom_material(
    file: UploadFile = File(...),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> MaterialOut:
    _self_student(user)
    if not container.settings.magicclass_fusion_enabled:
        raise HTTPException(status_code=503, detail="资料服务暂时不可用")
    if not idempotency_key.strip() or len(idempotency_key) > 200:
        raise HTTPException(status_code=400, detail="无效的上传请求标识")
    extracted = extract_material(
        filename=file.filename or "", content=await file.read(MAX_MATERIAL_BYTES + 1)
    )
    payload = await _material_client(container).create_material(
        user_id=str(user.id), course_id=SELF_COURSE_ID,
        filename=extracted.filename, media_type=extracted.media_type,
        byte_size=extracted.byte_size, sha256=extracted.sha256,
        extraction_status=extracted.extraction_status, text=extracted.text,
        content_base64=extracted.content_base64, idempotency_key=idempotency_key,
    )
    return MaterialOut(**{key: payload[key] for key in MaterialOut.model_fields if key in payload})


@self_router.get("/jobs/{session_id}", response_model=MagicClassSessionOut)
async def self_classroom_job(
    session_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: MagicClassClassroomService = Depends(_service),
) -> MagicClassSessionOut:
    _self_student(user)
    session = service.get_session(user_id=user.id, course_id=SELF_COURSE_ID, session_id=session_id)
    if session is None:
        raise NotFoundError("课堂生成任务不存在")
    return MagicClassSessionOut.from_session(await service.poll(session), settings=container.settings)


@self_router.get("", response_model=MagicClassClassroomsOut)
async def list_self_classrooms(
    user: UserRow = Depends(current_user),
    service: MagicClassClassroomService = Depends(_service),
) -> MagicClassClassroomsOut:
    _self_student(user)
    status = await service.status()
    return MagicClassClassroomsOut(
        enabled=status.get("enabled", False),
        items=service.list_classrooms(user_id=user.id, course_id=SELF_COURSE_ID),
    )


def _limits(container: ServiceContainer) -> ContextLimits:
    return ContextLimits(total_chars=container.settings.magicclass_course_context_max_chars)


def _material_client(container: ServiceContainer) -> MagicClassFusionClient:
    settings = container.settings
    return MagicClassFusionClient(
        base_url=settings.magicclass_service_url,
        secret=settings.magicclass_internal_secret,
        timeout_seconds=settings.magicclass_service_timeout_seconds,
    )


async def _uploaded_materials_for_plan(
    container: ServiceContainer, user: UserRow, course_id: str
) -> tuple[list[MagicClassMaterialOut], list[str]]:
    if not container.settings.magicclass_fusion_enabled:
        return [], []
    try:
        payload = await _material_client(container).list_materials(
            user_id=str(user.id), course_id=course_id, limit=50, cursor=None
        )
    except Exception:
        return [], ["个人上传资料暂时无法读取"]
    return [
        MagicClassMaterialOut(id=item["id"], title=item["filename"], kind="个人上传")
        for item in payload.get("items", [])
        if item.get("extraction_status") == "extracted" and item.get("text_chars", 0) > 0
    ], []


async def _attach_uploaded_materials(
    container: ServiceContainer, user: UserRow, course_id: str, context: LearningContext
) -> LearningContext:
    missing = list(context.unresolved_material_ids)
    if not missing or not container.settings.magicclass_fusion_enabled:
        return context
    try:
        client = _material_client(container)
        resolved = await client.resolve_materials(
            user_id=str(user.id), course_id=course_id, material_ids=missing
        )
        refs = list(context.materials)
        paragraphs = []
        accepted = list(context.selected_material_ids)
        limit = container.settings.magicclass_course_context_max_chars
        per_file = max(0, limit // max(2, len(missing) * 2) - 100)
        clipped = False
        for item in resolved.get("resolved", []):
            if item.get("extraction_status") != "extracted":
                continue
            detail = await client.get_material(
                user_id=str(user.id), course_id=course_id, material_id=item["id"]
            )
            body = str(detail.get("text") or "").strip()
            if not body or per_file == 0:
                continue
            if len(body) > per_file:
                clipped = True
                body = body[:per_file] + "\n[资料正文已截断]"
            accepted.append(item["id"])
            refs.append(MaterialRef(id=item["id"], title=item["filename"], kind="个人上传"))
            paragraphs.append(f"[个人上传资料：{item['filename']}]\n{body}")
        extra = "\n".join(paragraphs)
        remaining = max(0, limit - len(extra) - 1)
        return replace(
            context,
            materials=tuple(refs),
            selected_material_ids=tuple(accepted),
            unresolved_material_ids=tuple(mid for mid in missing if mid not in accepted),
            text=(extra + "\n" + context.text[:remaining])[:limit],
            material_text=(extra + "\n" + context.material_text[:remaining])[:limit],
            truncated=context.truncated or clipped,
            warnings=[*context.warnings, *(["个人上传资料正文较长，已截取片段用于课堂"] if clipped else [])],
        )
    except Exception:
        return replace(context, warnings=[*context.warnings, "个人上传资料读取失败，请稍后重试"])


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
)
async def get_status(
    course_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: MagicClassClassroomService = Depends(_service),
) -> MagicClassStatusOut:
    # 先校验权限（即使服务未启用，也只在有权限时暴露状态）
    assert_course_access(container, user, course_id)
    payload: Dict[str, Any] = await service.status()
    if payload.get("reason") is None and not payload.get("enabled"):
        payload["reason"] = "互动课堂服务未启用"
    return MagicClassStatusOut(**payload)


@router.get(
    "/{course_id}/interactive-classroom/plan",
    response_model=MagicClassPlanOut,
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
    course = assert_course_access(container, user, course_id)
    try:
        requested = normalize_mode(mode)
    except ValueError:
        requested = "adaptive"
    context = build_learning_context(
        container, user, course, limits=_limits(container)
    )
    uploaded, upload_warnings = await _uploaded_materials_for_plan(container, user, course_id)
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
        ] + uploaded,
        selected_material_ids=[],
        context_sources=context.sources,
        context_updated_at=context.updated_at,
        context_truncated=context.truncated,
        context_warnings=[*context.warnings, *upload_warnings],
        capabilities=status.get("capabilities", {}) or {},
        external_3d_available=bool(container.settings.magicclass_external_3d_available),
        can_generate=bool(status.get("enabled")),
        reason=status.get("reason"),
    )


@router.post(
    "/{course_id}/interactive-classroom/generate",
    response_model=MagicClassGenerateOut,
    status_code=202,
)
async def generate_classroom(
    course_id: str,
    req: MagicClassGenerateRequest,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: MagicClassClassroomService = Depends(_service),
) -> MagicClassGenerateOut:
    course = assert_course_access(container, user, course_id)
    context = build_learning_context(
        container,
        user,
        course,
        limits=_limits(container),
        selected_material_ids=req.selected_material_ids,
    )
    context = await _attach_uploaded_materials(container, user, course_id, context)
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
)
async def get_progress(
    course_id: str,
    session_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: MagicClassClassroomService = Depends(_service),
) -> MagicClassSessionOut:
    assert_course_access(container, user, course_id)
    session = service.get_session(user_id=user.id, course_id=course_id, session_id=session_id)
    if session is None:
        raise NotFoundError("课堂生成任务不存在")
    session = await service.poll(session)
    return MagicClassSessionOut.from_session(session, settings=container.settings)


@router.get(
    "/{course_id}/interactive-classroom/{session_id}/composition",
    response_model=MagicClassCompositionOut,
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
    assert_course_access(container, user, course_id)
    session = service.get_session(user_id=user.id, course_id=course_id, session_id=session_id)
    if session is None:
        raise NotFoundError("课堂生成任务不存在")
    composition = await service.composition(session)
    return MagicClassCompositionOut(**composition.to_dict())


@router.get(
    "/{course_id}/interactive-classroom",
    response_model=MagicClassClassroomsOut,
)
async def list_classrooms(
    course_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: MagicClassClassroomService = Depends(_service),
) -> MagicClassClassroomsOut:
    assert_course_access(container, user, course_id)
    status = await service.status()
    items = service.list_classrooms(user_id=user.id, course_id=course_id)
    return MagicClassClassroomsOut(enabled=status.get("enabled", False), items=items)


@router.post(
    "/{course_id}/interactive-classroom/{session_id}/retry",
    response_model=MagicClassGenerateOut,
    status_code=202,
)
async def retry_session(
    course_id: str,
    session_id: str,
    body: Optional[MagicClassGenerateRequest] = Body(default=None),
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
    course = assert_course_access(container, user, course_id)
    session = service.get_session(user_id=user.id, course_id=course_id, session_id=session_id)
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
    context = build_learning_context(
        container,
        user,
        course,
        limits=_limits(container),
        selected_material_ids=snapshot.selected_material_ids,
    )
    context = await _attach_uploaded_materials(container, user, course_id, context)
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
