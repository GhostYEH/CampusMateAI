"""Course-bound generation and job recovery gateway."""

from __future__ import annotations

import base64
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field

from ...models.multi_role import UserRow
from ...services.container import ServiceContainer, get_container
from ...services.openmaic.course_context import assert_course_access
from ...services.openmaic.fusion_client import OpenMAICFusionClient
from ...services.openmaic.fusion_errors import FusionInvalidRequest, FusionUnavailable
from ..deps import current_user
from .openmaic_archive import content_disposition

router = APIRouter(prefix="/courses", tags=["openmaic-generation"])

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


def _container() -> ServiceContainer:
    return get_container()


def _client(container: ServiceContainer = Depends(_container)) -> OpenMAICFusionClient:
    settings = container.settings
    return OpenMAICFusionClient(base_url=settings.openmaic_service_url, secret=settings.openmaic_internal_secret, timeout_seconds=settings.openmaic_service_timeout_seconds)


def _require(container: ServiceContainer) -> None:
    if not container.settings.openmaic_fusion_enabled:
        raise FusionUnavailable("受管 OpenMAIC 服务未启用")


def _key(value: Optional[str]) -> str:
    text = (value or "").strip()
    if not text or len(text) > 200:
        raise FusionInvalidRequest("生成请求必须携带有效的 Idempotency-Key")
    return text


@router.post("/{course_id}/workspaces/{workspace_id}/generate", status_code=201)
async def generate_stage(
    course_id: str,
    workspace_id: str,
    body: GenerationIn,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> Dict[str, Any]:
    _require(container)
    assert_course_access(container, user, course_id)
    return await client.generate_stage(
        user_id=str(user.id), course_id=course_id, workspace_id=workspace_id,
        mode=body.mode, prompt=body.prompt, role_mode=body.role_mode,
        selected_role_ids=body.selected_role_ids,
        idempotency_key=_key(idempotency_key),
    )


@router.get("/{course_id}/jobs/{job_id}")
async def get_job(
    course_id: str,
    job_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
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
    client: OpenMAICFusionClient = Depends(_client),
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
    client: OpenMAICFusionClient = Depends(_client),
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
    client: OpenMAICFusionClient = Depends(_client),
) -> Dict[str, Any]:
    _require(container)
    assert_course_access(container, user, course_id)
    return await client.retry_job(user_id=str(user.id), course_id=course_id, job_id=job_id)


__all__ = ["router", "GenerationIn", "ARTIFACT_MEDIA_TYPES"]
