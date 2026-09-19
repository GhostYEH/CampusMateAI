"""Course-bound generation and job recovery gateway."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from ...models.multi_role import UserRow
from ...services.container import ServiceContainer, get_container
from ...services.openmaic.course_context import assert_course_access
from ...services.openmaic.fusion_client import OpenMAICFusionClient
from ...services.openmaic.fusion_errors import FusionInvalidRequest, FusionUnavailable
from ..deps import current_user

router = APIRouter(prefix="/courses", tags=["openmaic-generation"])


class GenerationIn(BaseModel):
    mode: str = Field(..., min_length=1, max_length=80)
    prompt: str = Field(..., min_length=1, max_length=2000)


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
    return await client.generate_stage(user_id=str(user.id), course_id=course_id, workspace_id=workspace_id, mode=body.mode, prompt=body.prompt, idempotency_key=_key(idempotency_key))


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


__all__ = ["router", "GenerationIn"]
