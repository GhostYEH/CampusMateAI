"""课堂 AI 同学的原生接入网关。

浏览器只把「当前页 + 记忆」交给 CampusMate，本网关负责三件浏览器不能做的事：

1. **身份**：课程可见性按统一策略复核，不允许借同学接口读取他人课程；
2. **人设**：同学名单由服务端固定提供，浏览器不能伪造或替换；
3. **凭据**：模型与供应商 Key 只在服务端解析，代理请求不携带任何客户端密钥。

上游仍是受管 magic class 的同学接口；本模块只做受控转发，不复制其路由、
沉默与预算策略，避免两套实现漂移。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends

from ...models.multi_role import UserRow
from ...schemas.magicclass_classmates import (
    CLASSMATE_PERSONAS,
    ClassmateAnswerOut,
    ClassmateAskIn,
    ClassmateBudgetOut,
    ClassmateRespondIn,
    ClassmateRespondOut,
    ClassmateRosterOut,
    MAX_QUESTION_LENGTH,
)
from ...core.exceptions import Forbidden
from ...services.container import ServiceContainer, get_container
from ...services.course_access import can_view_course
from ...services.magicclass.client import MagicClassClient
from ...services.magicclass.errors import (
    MagicClassAuthError,
    MagicClassInvalidOrigin,
    MagicClassNotEnabled,
    MagicClassProtocolError,
    MagicClassRateLimited,
    MagicClassServerError,
    MagicClassUnavailable,
)
from ..deps import current_user

router = APIRouter(prefix="/magicclass/classmates", tags=["课堂 AI 同学"])

RESPOND_TIMEOUT_SECONDS = 60.0
ASK_TIMEOUT_SECONDS = 50.0
TOKEN_BUDGET = 240_000
MEMORY_PAGES = 8
MEMORY_LINES = 12
ANSWER_CHARS = 2_000


def _container() -> ServiceContainer:
    return get_container()


def _client(container: ServiceContainer = Depends(_container)) -> MagicClassClient:
    settings = container.settings
    return MagicClassClient(
        base_url=settings.magicclass_base_url,
        timeout_seconds=settings.magicclass_request_timeout_seconds,
        origin=settings.magicclass_origin,
        access_code=settings.magicclass_access_code,
        probe_timeout_seconds=settings.magicclass_health_timeout_seconds,
    )


def _require_ready(container: ServiceContainer) -> None:
    if not container.settings.magicclass_available:
        raise MagicClassNotEnabled()


def _require_course(container: ServiceContainer, user: UserRow, course_id: str) -> None:
    course = container.course_repository.get_course(course_id)
    if course is None or not can_view_course(container, user, course):
        raise Forbidden("无权访问该课程")


def _persona(agent_id: str) -> Dict[str, str]:
    for persona in CLASSMATE_PERSONAS:
        if persona["id"] == agent_id:
            return dict(persona)
    raise MagicClassProtocolError("同学标识不在名单内")


def _memory_payload(memory: Any, *, agent_ids: Optional[set[str]] = None) -> Optional[Dict[str, Any]]:
    if memory is None:
        return None
    payload = memory.model_dump(by_alias=True)
    if agent_ids is not None:
        known = set(agent_ids)
        payload["lines"] = [line for line in payload["lines"] if line["agentId"] in known]
        payload["recentAgentIds"] = [item for item in payload["recentAgentIds"] if item in known]
    return payload


@router.get(
    "/roster",
    response_model=ClassmateRosterOut,
    summary="读取课堂 AI 同学名单",
)
def classmates_roster(user: UserRow = Depends(current_user)) -> ClassmateRosterOut:
    """固定名单，不依赖浏览器传入。需要已登录。"""
    return ClassmateRosterOut(items=[dict(persona) for persona in CLASSMATE_PERSONAS])


@router.get(
    "/budget",
    response_model=ClassmateBudgetOut,
    summary="读取课堂同学预算口径",
)
def classmates_budget(user: UserRow = Depends(current_user)) -> ClassmateBudgetOut:
    """预算由客户端累计，服务端只给同一套口径，避免两端数值漂移。"""
    return ClassmateBudgetOut(
        token_budget=TOKEN_BUDGET,
        memory_pages=MEMORY_PAGES,
        memory_lines=MEMORY_LINES,
        question_chars=MAX_QUESTION_LENGTH,
        answer_chars=ANSWER_CHARS,
    )


@router.post(
    "/respond",
    response_model=ClassmateRespondOut,
    summary="生成当前页的 AI 同学发言",
)
async def classmates_respond(
    payload: ClassmateRespondIn,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassClient = Depends(_client),
) -> ClassmateRespondOut:
    """只为当前页生成同学发言；是否开口由上游路由决定，本网关不改写。"""
    _require_ready(container)
    _require_course(container, user, payload.course_id)
    roster = {persona["id"] for persona in CLASSMATE_PERSONAS}
    body: Dict[str, Any] = {
        "scene": payload.scene.model_dump(),
        "agents": [dict(persona) for persona in CLASSMATE_PERSONAS],
        # 记忆只允许引用真实存在的同学，顺手丢掉伪造 id。
        "memory": _memory_payload(payload.memory, agent_ids=roster),
    }
    if payload.language:
        body["language"] = payload.language
    try:
        result = await client.chat("/api/chat/classmates", body, timeout=RESPOND_TIMEOUT_SECONDS)
    except MagicClassRateLimited:
        raise
    except MagicClassUnavailable as exc:
        raise MagicClassUnavailable(str(exc)) from exc
    except (MagicClassAuthError, MagicClassServerError, MagicClassInvalidOrigin, MagicClassProtocolError) as exc:
        raise MagicClassProtocolError(str(exc)) from exc
    return ClassmateRespondOut.model_validate(result)


@router.post(
    "/ask",
    response_model=ClassmateAnswerOut,
    summary="点名一位 AI 同学回答问题",
)
async def classmates_ask(
    payload: ClassmateAskIn,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassClient = Depends(_client),
) -> ClassmateAnswerOut:
    """学生点名提问时必须真答：不返回沉默，也不替同学解测验题。"""
    _require_ready(container)
    _require_course(container, user, payload.course_id)
    persona = _persona(payload.agent_id)
    body: Dict[str, Any] = {
        "scene": payload.scene.model_dump(),
        "agents": [persona],
        "memory": _memory_payload(payload.memory, agent_ids={persona["id"]}),
        "question": payload.question,
    }
    if payload.language:
        body["language"] = payload.language
    try:
        result = await client.chat("/api/chat/classmates/ask", body, timeout=ASK_TIMEOUT_SECONDS)
    except MagicClassRateLimited:
        raise
    except (MagicClassAuthError, MagicClassServerError, MagicClassInvalidOrigin, MagicClassProtocolError) as exc:
        raise MagicClassProtocolError(str(exc)) from exc
    return ClassmateAnswerOut.model_validate(result)


__all__ = ["router"]
