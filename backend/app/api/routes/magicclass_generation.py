"""Course-bound generation and job recovery gateway."""

from __future__ import annotations

import base64
import hashlib
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field

from ...models.multi_role import UserRow
from ...services.container import ServiceContainer, get_container
from ...services.magicclass.course_context import assert_course_access, build_course_context
from ...services.magicclass.fusion_client import MagicClassFusionClient
from ...services.magicclass.fusion_errors import FusionInvalidRequest, FusionUnavailable
from ..deps import current_user
from .magicclass_archive import content_disposition

router = APIRouter(prefix="/courses", tags=["magicclass-generation"])

#: What the service worker is able to produce today. Keeping the list closed
#: means a future artifact type must be opted in here before the browser can
#: render it — no content-type sniffing surface.
ARTIFACT_MEDIA_TYPES = {
    "audio/wav": ("artifact.wav", "学习产物.wav"),
    "application/json": ("artifact.json", "学习产物.json"),
    "video/mp4": ("artifact.mp4", "学习内容.mp4"),
}


class GenerationIn(BaseModel):
    mode: str = Field(..., min_length=1, max_length=80)
    prompt: str = Field(..., min_length=1, max_length=2000)
    role_mode: str = Field("preset", pattern="^(preset|auto)$")
    selected_role_ids: list[str] = Field(default_factory=list, max_length=7)


class HomeGenerationIn(BaseModel):
    """The single homepage write contract.

    Resolving the workspace and enqueueing its first stage here keeps a browser
    retry from racing two separate create calls.
    """

    mode: str = Field("slide", min_length=1, max_length=80)
    # Reserve enough of the provider's 2,000-character payload for the
    # gateway instruction and authorized course context.
    prompt: str = Field(..., min_length=1, max_length=750)


def _container() -> ServiceContainer:
    return get_container()


def _client(container: ServiceContainer = Depends(_container)) -> MagicClassFusionClient:
    settings = container.settings
    return MagicClassFusionClient(base_url=settings.magicclass_service_url, secret=settings.magicclass_internal_secret, timeout_seconds=settings.magicclass_service_timeout_seconds)


def _require(container: ServiceContainer) -> None:
    if not container.settings.magicclass_fusion_enabled:
        raise FusionUnavailable("受管 magic class 服务未启用")


def _key(value: Optional[str]) -> str:
    text = (value or "").strip()
    # The gateway appends ``:workspace`` and ``:generation`` before forwarding
    # the key. Keep the caller budget below the managed service's 200-char cap.
    if not text or len(text) > 180:
        raise FusionInvalidRequest("生成请求必须携带有效的 Idempotency-Key")
    return text


def _home_workspace_key(user_id: object, course_id: str) -> str:
    """Return a bounded stable key without truncation collisions."""
    digest = hashlib.sha256(f"{user_id}\0{course_id}".encode("utf-8")).hexdigest()
    return f"home-workspace:{digest}"


def _utf16_length(value: str) -> int:
    """Match JavaScript/Zod string length used by the managed service."""
    return len(value.encode("utf-16-le")) // 2


def _truncate_utf16(value: str, budget: int) -> str:
    if budget <= 0:
        return ""
    used = 0
    result: list[str] = []
    for char in value:
        units = 2 if ord(char) > 0xFFFF else 1
        if used + units > budget:
            break
        result.append(char)
        used += units
    return "".join(result)


def _course_prompt(topic: str, context: str, budget: int = 2000) -> str:
    prefix = f"{topic.strip()}\n\n请结合以下已授权课程上下文生成内容：\n"
    remaining = max(0, budget - _utf16_length(prefix))
    return prefix + _truncate_utf16(context, remaining)


@router.post("/{course_id}/workspaces/{workspace_id}/generate", status_code=201)
async def generate_stage(
    course_id: str,
    workspace_id: str,
    body: GenerationIn,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Dict[str, Any]:
    _require(container)
    assert_course_access(container, user, course_id)
    generated = await client.generate_stage(
        user_id=str(user.id), course_id=course_id, workspace_id=workspace_id,
        mode=body.mode, prompt=body.prompt, role_mode=body.role_mode,
        selected_role_ids=body.selected_role_ids,
        idempotency_key=_key(idempotency_key),
    )
    if generated.get("source") == "local-template":
        raise FusionUnavailable("课程生成模型当前不可用", details={"reason": "provider_unavailable"})
    return generated


@router.post("/{course_id}/home-generate", status_code=201)
async def generate_home(
    course_id: str,
    body: HomeGenerationIn,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Dict[str, Any]:
    """Resolve one course homepage submission into one workspace/job pair."""
    _require(container)
    course = assert_course_access(container, user, course_id)
    key = _key(idempotency_key)
    provider = await client.provider_status(user_id=str(user.id))
    if not provider.get("llm"):
        raise FusionUnavailable("课程生成模型当前不可用", details={"reason": "provider_unavailable"})
    # Course facts are rebuilt behind the gateway. The browser contributes only
    # the learner's topic; it cannot smuggle another course's materials into the
    # provider prompt.
    context = build_course_context(container, user, course)
    listed = await client.list_workspaces(user_id=str(user.id), course_id=course_id, limit=1)
    workspace = (listed.get("items") or [None])[0]
    if not workspace:
        workspace = await client.create_workspace(
            user_id=str(user.id), course_id=course_id,
            name="magic class 学习课堂", description="由课程首页主题生成，可继续编辑、播放与导出。",
            # Workspace identity is stable per learner/course. A different
            # topic must create a new stage, while concurrent first submits
            # must converge on one homepage workspace.
            idempotency_key=_home_workspace_key(user.id, course_id),
        )
    workspace_id = str(workspace.get("id") or "")
    if not workspace_id:
        raise FusionUnavailable("受管服务未返回工作台标识")
    generated = await client.generate_stage(
        user_id=str(user.id), course_id=course_id, workspace_id=workspace_id,
        mode=body.mode, prompt=_course_prompt(body.prompt, context), role_mode="preset", selected_role_ids=[],
        idempotency_key=f"{key}:generation",
    )
    if generated.get("source") == "local-template":
        raise FusionUnavailable("课程生成模型当前不可用", details={"reason": "provider_unavailable"})
    return {"workspace_id": workspace_id, "source": "provider", **generated}


@router.get("/{course_id}/jobs/{job_id}")
async def get_job(
    course_id: str,
    job_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Dict[str, Any]:
    _require(container)
    assert_course_access(container, user, course_id)
    return await client.get_job(user_id=str(user.id), course_id=course_id, job_id=job_id)


@router.get("/{course_id}/artifacts/{artifact_id}")
async def get_artifact(
    course_id: str,
    artifact_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Response:
    _require(container)
    assert_course_access(container, user, course_id)
    payload = await client.get_artifact(user_id=str(user.id), course_id=course_id, artifact_id=artifact_id)
    encoded = payload.get("content_base64")
    if not isinstance(encoded, str) or not encoded:
        raise FusionUnavailable("受管服务未返回可用产物")
    try:
        content = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise FusionUnavailable("受管服务返回的产物无法解码") from exc
    media_type = str(payload.get("media_type") or "").split(";", 1)[0]
    if media_type not in ARTIFACT_MEDIA_TYPES:
        raise FusionUnavailable("受管服务返回了不受支持的产物类型")
    ascii_fallback, fallback = ARTIFACT_MEDIA_TYPES[media_type]
    filename = str(payload.get("filename") or fallback)
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": content_disposition(filename, ascii_fallback=ascii_fallback, fallback=fallback),
            "Cache-Control": "no-store",
            "X-Artifact-Sha256": str(payload.get("sha256") or ""),
        },
    )


@router.post("/{course_id}/jobs/{job_id}/cancel")
async def cancel_job(
    course_id: str,
    job_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Dict[str, Any]:
    _require(container)
    assert_course_access(container, user, course_id)
    return await client.cancel_job(user_id=str(user.id), course_id=course_id, job_id=job_id)


@router.post("/{course_id}/jobs/{job_id}/retry")
async def retry_job(
    course_id: str,
    job_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Dict[str, Any]:
    _require(container)
    assert_course_access(container, user, course_id)
    return await client.retry_job(user_id=str(user.id), course_id=course_id, job_id=job_id)


__all__ = ["router", "GenerationIn", "HomeGenerationIn", "ARTIFACT_MEDIA_TYPES"]
