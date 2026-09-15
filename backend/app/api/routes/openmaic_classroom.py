"""互动课堂路由 —— 课程智能辅导空间的 OpenMAIC 适配层。

权限：所有接口校验当前用户有权访问该课程(assert_course_access)。
边界：
- OpenMAIC 故障不得影响课程详情/CPM 基础聊天：status 接口 safe 降级，
  generate 等写接口在未启用时抛 503 OpenMAIC_NOT_ENABLED。
- 所有生成操作绑定当前用户与课程权限。
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from ...core.exceptions import NotFoundError
from ...models.multi_role import UserRow
from ...schemas.openmaic import (
    OpenMAICClassroomsOut,
    OpenMAICGenerateOut,
    OpenMAICGenerateRequest,
    OpenMAICSessionOut,
    OpenMAICStatusOut,
)
from ...services.container import ServiceContainer, get_container
from ...services.openmaic.classroom_service import OpenMAICClassroomService
from ...services.openmaic.course_context import assert_course_access, build_course_context
from ...services.openmaic.errors import OpenMAICNotEnabled
from ..deps import current_user

router = APIRouter(prefix="/courses", tags=["interactive-classroom"])


def _container() -> ServiceContainer:
    return get_container()


def _service(c: ServiceContainer = Depends(_container)) -> OpenMAICClassroomService:
    return c.openmaic_classroom_service


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
    if not payload.get("enabled"):
        payload["reason"] = "互动课堂服务未启用"
    return OpenMAICStatusOut(**payload)


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
    context = build_course_context(
        container,
        user,
        course,
        max_chars=container.settings.openmaic_course_context_max_chars,
    )
    session = await service.generate(
        user_id=user.id,
        course_id=course_id,
        course_context=context,
        mode=req.mode,
        learning_objective=req.learning_objective,
    )
    return OpenMAICGenerateOut(
        accepted=True,
        session=OpenMAICSessionOut.from_session(session),
        poll_interval_ms=5000,
        mode=req.mode,
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
    return OpenMAICSessionOut.from_session(session)


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
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: OpenMAICClassroomService = Depends(_service),
) -> OpenMAICGenerateOut:
    course = assert_course_access(container, user, course_id)
    session = service.get_session(user_id=user.id, course_id=course_id, session_id=session_id)
    if session is None:
        raise NotFoundError("课堂生成任务不存在")
    if session.status not in ("failed", "succeeded"):
        # 进行中任务返回现状，不重复提交
        session = await service.poll(session)
        return OpenMAICGenerateOut(
            accepted=False,
            session=OpenMAICSessionOut.from_session(session),
            poll_interval_ms=5000,
            mode=session.mode,
        )
    context = build_course_context(
        container,
        user,
        course,
        max_chars=container.settings.openmaic_course_context_max_chars,
    )
    new_session = await service.generate(
        user_id=user.id,
        course_id=course_id,
        course_context=context,
        mode=session.mode,
        learning_objective=None,
    )
    return OpenMAICGenerateOut(
        accepted=True,
        session=OpenMAICSessionOut.from_session(new_session),
        poll_interval_ms=5000,
        mode=new_session.mode,
    )


__all__ = ["router"]