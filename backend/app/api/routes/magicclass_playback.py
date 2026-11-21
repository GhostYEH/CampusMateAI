"""经典课堂原生播放与媒体读取（Android / iOS 共用契约）。

两个入口：
- 课程经典课堂：`/courses/{course_id}/interactive-classroom/{session_id}/...`
- 自主选题课堂：`/self-classroom/{session_id}/...`

权限：
- 课程课堂：current_user + assert_course_access + 当前用户在该课程下的 session。
- 自主选题：student 角色 + 本人 session（course_id=__self_study__）。
- 媒体每次请求都重新校验账号、课程与会话，不使用匿名签名直链。
"""
from __future__ import annotations

import mimetypes
import re
from contextlib import AsyncExitStack
from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, Header, Query
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response, StreamingResponse

from ...core.exceptions import Forbidden, NotFoundError
from ...models.multi_role import UserRow
from ...schemas.magicclass import ClassroomPlaybackOut
from ...schemas.magicclass_quiz import QuizAttemptIn, QuizAttemptStateOut
from ...services.container import ServiceContainer, get_container
from ...services.magicclass.classroom_service import MagicClassClassroomService
from ...services.magicclass.course_context import assert_course_access
from ...services.magicclass.errors import (
    ClassroomContentInvalid,
    ClassroomMediaNotFound,
    ClassroomMediaUpstreamError,
    ClassroomSceneNotFound,
    ClassroomSceneNotQuiz,
    MagicClassRateLimited,
)
from ...services.magicclass.playback import build_classroom_playback
from ...services.magicclass.public_url import project_session_url
from ...services.magicclass.quiz_attempt_store import QuizAttempt, root_attempt_id
from ..deps import current_user

router = APIRouter(prefix="/courses", tags=["互动课堂"])
self_router = APIRouter(prefix="/self-classroom", tags=["互动课堂"])
SELF_COURSE_ID = "__self_study__"
_MEDIA_PATH_RE = re.compile(r"^(media|audio)/[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _container() -> ServiceContainer:
    return get_container()


def _service(c: ServiceContainer = Depends(_container)) -> MagicClassClassroomService:
    return c.magicclass_classroom_service


def _self_student(user: UserRow) -> None:
    if user.role != "student":
        raise Forbidden("仅学生可访问自主选题课堂")


async def _course_session(
    *,
    container: ServiceContainer,
    service: MagicClassClassroomService,
    user: UserRow,
    course_id: str,
    session_id: str,
):
    await run_in_threadpool(assert_course_access, container, user, course_id)
    session = await run_in_threadpool(
        service.get_session,
        user_id=str(user.id),
        course_id=course_id,
        session_id=session_id,
    )
    if session is None or str(session.user_id) != str(user.id):
        raise NotFoundError("课堂会话不存在")
    return session


async def _self_session(
    *, service: MagicClassClassroomService, user: UserRow, session_id: str
):
    _self_student(user)
    session = await run_in_threadpool(
        service.get_session,
        user_id=str(user.id),
        course_id=SELF_COURSE_ID,
        session_id=session_id,
    )
    if session is None or str(session.user_id) != str(user.id):
        raise NotFoundError("课堂会话不存在")
    return session


def _media_base_for_course(course_id: str, session_id: str) -> str:
    return f"/api/v1/courses/{course_id}/interactive-classroom/{session_id}/media"


def _media_base_for_self(session_id: str) -> str:
    return f"/api/v1/self-classroom/{session_id}/media"


async def _compat_context(
    container: ServiceContainer,
    service: MagicClassClassroomService,
    session,
):
    payload = await service.status()
    url, url_reason = project_session_url(container.settings, session)
    return {
        "browser_embed_available": bool(payload.get("browser_embed_available")),
        "browser_embed_reason": payload.get("browser_embed_reason"),
        "compat_url": url,
        "compat_url_unavailable_reason": url_reason,
    }


async def _build_playback(
    *,
    container: ServiceContainer,
    service: MagicClassClassroomService,
    session,
    media_base: str,
    scene_id: Optional[str],
):
    classroom, content_version = await service.load_playback_classroom(session)
    compat = await _compat_context(container, service, session)
    origins = tuple(
        origin
        for origin in (
            getattr(container.settings, "magicclass_origin", ""),
            getattr(container.settings, "magicclass_public_origin", ""),
        )
        if origin
    )
    try:
        return build_classroom_playback(
            document={"classroom": classroom},
            session=session,
            media_base=media_base,
            content_version=content_version,
            scene_id=scene_id,
            origins=origins,
            external_3d_available=bool(
                getattr(container.settings, "magicclass_external_3d_available", False)
            ),
            **compat,
        )
    except LookupError as exc:
        raise ClassroomSceneNotFound(details={"scene_id": scene_id}) from exc
    except ValueError as exc:
        raise ClassroomContentInvalid(details={"reason": str(exc)}) from exc


@router.get(
    "/{course_id}/interactive-classroom/{session_id}/playback",
    response_model=ClassroomPlaybackOut,
    summary="读取课程经典课堂原生播放数据",
)
async def get_course_classroom_playback(
    course_id: str,
    session_id: str,
    scene_id: Optional[str] = Query(
        default=None, description="续播场景 ID；不传从第一场开始"
    ),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: MagicClassClassroomService = Depends(_service),
) -> ClassroomPlaybackOut:
    session = await _course_session(
        container=container,
        service=service,
        user=user,
        course_id=course_id,
        session_id=session_id,
    )
    return await _build_playback(
        container=container,
        service=service,
        session=session,
        media_base=_media_base_for_course(course_id, session_id),
        scene_id=scene_id,
    )


@self_router.get(
    "/{session_id}/playback",
    response_model=ClassroomPlaybackOut,
    summary="读取自主选题课堂原生播放数据",
)
async def get_self_classroom_playback(
    session_id: str,
    scene_id: Optional[str] = Query(
        default=None, description="续播场景 ID；不传从第一场开始"
    ),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: MagicClassClassroomService = Depends(_service),
) -> ClassroomPlaybackOut:
    session = await _self_session(service=service, user=user, session_id=session_id)
    return await _build_playback(
        container=container,
        service=service,
        session=session,
        media_base=_media_base_for_self(session_id),
        scene_id=scene_id,
    )


def _validate_media_path(media_path: str) -> str:
    if not isinstance(media_path, str) or not _MEDIA_PATH_RE.match(media_path):
        raise ClassroomMediaNotFound(details={"reason": "invalid_media_path"})
    return media_path


def _upstream_headers(upstream, media_path: str) -> Dict[str, str]:
    headers: Dict[str, str] = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, no-cache",
        "X-Content-Type-Options": "nosniff",
    }
    for name in (
        "content-type",
        "content-length",
        "content-range",
        "etag",
        "last-modified",
    ):
        value = upstream.headers.get(name)
        if value:
            header_name = "-".join(part.capitalize() for part in name.split("-"))
            headers[header_name] = value
    if not any(name.lower() == "content-type" for name in headers):
        headers["Content-Type"] = (
            mimetypes.guess_type(media_path)[0] or "application/octet-stream"
        )
    return headers


async def _media_response(
    *,
    service: MagicClassClassroomService,
    session,
    media_path: str,
    range_header: Optional[str],
):
    media_path = _validate_media_path(media_path)
    classroom_id = str(session.classroom_id or "")
    if not classroom_id:
        raise ClassroomMediaNotFound(details={"reason": "classroom_id_missing"})
    client = service.require_client()
    stack = AsyncExitStack()
    upstream = await stack.enter_async_context(
        client.open_classroom_media(
            classroom_id, media_path, range_header=range_header
        )
    )
    status_code = upstream.status_code
    if status_code in (200, 206):
        headers = _upstream_headers(upstream, media_path)

        async def body():
            async for chunk in upstream.aiter_raw():
                yield chunk

        return StreamingResponse(
            body(),
            status_code=status_code,
            headers=headers,
            background=BackgroundTask(stack.aclose),
        )
    if status_code == 416:
        content_range = upstream.headers.get("content-range") or "bytes */*"
        headers = {
            "Content-Range": content_range,
            "Accept-Ranges": "bytes",
            "Cache-Control": "private, no-cache",
        }
        upstream_content_type = upstream.headers.get("content-type") or mimetypes.guess_type(media_path)[0]
        if upstream_content_type:
            headers["Content-Type"] = upstream_content_type
        await stack.aclose()
        return Response(status_code=416, headers=headers)
    if status_code in (404, 410):
        await stack.aclose()
        raise ClassroomMediaNotFound(
            details={
                "media_id": media_path,
                "recovery": "reread_playback_or_use_compat",
            }
        )
    if status_code == 429:
        await stack.aclose()
        raise MagicClassRateLimited()
    await stack.aclose()
    if status_code >= 500:
        raise ClassroomMediaUpstreamError(details={"upstream_status": status_code})
    if status_code in (401, 403):
        raise ClassroomMediaUpstreamError(
            details={"upstream_status": status_code, "reason": "upstream_auth"}
        )
    raise ClassroomMediaNotFound(
        details={"reason": "upstream_status", "upstream_status": status_code}
    )


@router.get(
    "/{course_id}/interactive-classroom/{session_id}/media/{media_path:path}",
    summary="读取课程经典课堂媒体",
    response_class=StreamingResponse,
)
async def get_course_classroom_media(
    course_id: str,
    session_id: str,
    media_path: str,
    range_header: Optional[str] = Header(default=None, alias="Range"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: MagicClassClassroomService = Depends(_service),
):
    session = await _course_session(
        container=container,
        service=service,
        user=user,
        course_id=course_id,
        session_id=session_id,
    )
    service.ensure_playback_ready(session)
    return await _media_response(
        service=service,
        session=session,
        media_path=media_path,
        range_header=range_header,
    )


@self_router.get(
    "/{session_id}/media/{media_path:path}",
    summary="读取自主选题课堂媒体",
    response_class=StreamingResponse,
)
async def get_self_classroom_media(
    session_id: str,
    media_path: str,
    range_header: Optional[str] = Header(default=None, alias="Range"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: MagicClassClassroomService = Depends(_service),
):
    session = await _self_session(service=service, user=user, session_id=session_id)
    service.ensure_playback_ready(session)
    return await _media_response(
        service=service,
        session=session,
        media_path=media_path,
        range_header=range_header,
    )


def _quiz_state(attempt: QuizAttempt | None) -> Optional[dict]:
    if attempt is None:
        return None
    return {
        "session_id": attempt.attempt_id,
        "phase": attempt.phase,
        "answers": attempt.answers,
        "results": attempt.results,
    }


def _find_quiz_scene(classroom: Dict[str, Any], scene_id: str) -> None:
    """按播放响应的稳定场景 ID 查找 quiz。

    旧课件可能缺 `id` 或有重复 `id`；播放层已经生成了 `sc_<type>_<n>` 回退 ID
    和重复后缀，这里必须使用完全相同的规则，否则移动端拿到的场景 ID 在
    quiz 入口会变成 404。
    """
    scenes = classroom.get("scenes")
    if not isinstance(scenes, list):
        raise ClassroomSceneNotFound(details={"scene_id": scene_id})
    used: set[str] = set()
    for source_index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            continue
        raw_id = scene.get("id") if isinstance(scene.get("id"), str) else ""
        scene_type = scene.get("type") if isinstance(scene.get("type"), str) else "unknown"
        if raw_id:
            public_id = raw_id
            if public_id in used:
                public_id = f"{public_id}_{source_index + 1}"
        else:
            safe_type = re.sub(r"[^A-Za-z0-9_-]", "_", scene_type) or "unknown"
            public_id = f"sc_{safe_type}_{source_index + 1}"
        used.add(public_id)
        if public_id != scene_id:
            continue
        if scene_type != "quiz":
            raise ClassroomSceneNotQuiz(details={"scene_id": scene_id})
        return
    raise ClassroomSceneNotFound(details={"scene_id": scene_id})


async def _quiz_context(*, service, session, scene_id: str) -> str:
    classroom, _ = await service.load_playback_classroom(session)
    _find_quiz_scene(classroom, scene_id)
    return str(session.classroom_id or "")


async def _get_quiz(
    *, container, service, user, session, scene_id: str, course_id: str
):
    classroom_id = await _quiz_context(
        service=service, session=session, scene_id=scene_id
    )
    root = root_attempt_id(str(user.id), classroom_id, scene_id)
    store = container.quiz_attempt_store
    current = store.latest(root, user_id=str(user.id))
    return QuizAttemptStateOut(
        attempt_id=current.attempt_id if current else root,
        state=_quiz_state(current),
    )


async def _save_quiz(
    *,
    container,
    service,
    user,
    session,
    scene_id: str,
    course_id: str,
    body: QuizAttemptIn,
):
    classroom_id = await _quiz_context(
        service=service, session=session, scene_id=scene_id
    )
    store = container.quiz_attempt_store
    attempt = store.update(
        attempt_id=body.attempt_id,
        user_id=str(user.id),
        course_id=course_id,
        workspace_id="",
        stage_id=classroom_id,
        scene_id=scene_id,
        phase=body.phase,
        answers=body.answers,
        results=body.results,
        start_new_attempt=body.start_new_attempt,
    )
    return QuizAttemptStateOut(
        attempt_id=attempt.attempt_id, state=_quiz_state(attempt)
    )


@router.get(
    "/{course_id}/interactive-classroom/{session_id}/scenes/{scene_id}/quiz-attempt",
    response_model=QuizAttemptStateOut,
    summary="读取课程经典课堂测验作答",
)
async def get_course_classroom_quiz_attempt(
    course_id: str,
    session_id: str,
    scene_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: MagicClassClassroomService = Depends(_service),
) -> QuizAttemptStateOut:
    session = await _course_session(
        container=container,
        service=service,
        user=user,
        course_id=course_id,
        session_id=session_id,
    )
    return await _get_quiz(
        container=container,
        service=service,
        user=user,
        session=session,
        scene_id=scene_id,
        course_id=course_id,
    )


@router.post(
    "/{course_id}/interactive-classroom/{session_id}/scenes/{scene_id}/quiz-attempt",
    response_model=QuizAttemptStateOut,
    summary="保存课程经典课堂测验作答",
)
async def save_course_classroom_quiz_attempt(
    course_id: str,
    session_id: str,
    scene_id: str,
    body: Annotated[QuizAttemptIn, Body()],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: MagicClassClassroomService = Depends(_service),
) -> QuizAttemptStateOut:
    session = await _course_session(
        container=container,
        service=service,
        user=user,
        course_id=course_id,
        session_id=session_id,
    )
    return await _save_quiz(
        container=container,
        service=service,
        user=user,
        session=session,
        scene_id=scene_id,
        course_id=course_id,
        body=body,
    )


@self_router.get(
    "/{session_id}/scenes/{scene_id}/quiz-attempt",
    response_model=QuizAttemptStateOut,
    summary="读取自主选题课堂测验作答",
)
async def get_self_classroom_quiz_attempt(
    session_id: str,
    scene_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: MagicClassClassroomService = Depends(_service),
) -> QuizAttemptStateOut:
    session = await _self_session(service=service, user=user, session_id=session_id)
    return await _get_quiz(
        container=container,
        service=service,
        user=user,
        session=session,
        scene_id=scene_id,
        course_id=SELF_COURSE_ID,
    )


@self_router.post(
    "/{session_id}/scenes/{scene_id}/quiz-attempt",
    response_model=QuizAttemptStateOut,
    summary="保存自主选题课堂测验作答",
)
async def save_self_classroom_quiz_attempt(
    session_id: str,
    scene_id: str,
    body: Annotated[QuizAttemptIn, Body()],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: MagicClassClassroomService = Depends(_service),
) -> QuizAttemptStateOut:
    session = await _self_session(service=service, user=user, session_id=session_id)
    return await _save_quiz(
        container=container,
        service=service,
        user=user,
        session=session,
        scene_id=scene_id,
        course_id=SELF_COURSE_ID,
        body=body,
    )


__all__ = ["router", "self_router"]
