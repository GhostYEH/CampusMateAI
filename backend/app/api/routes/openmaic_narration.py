"""Course-bound per-scene narration gateway.

The teacher's voice for one slide. Two properties matter and are enforced here:

1. **No text crosses this boundary.** The client sends a scene id, never the
   words to speak. The managed service derives the script from the scene body,
   so "the audio for this page" is a function of "this page" and cannot drift
   from it. An endpoint that accepted text would let the browser synthesize a
   paragraph unrelated to any scene — which is exactly the defect this replaces.
2. **Audio is addressed by scene, not by artifact.** The browser asks about a
   scene and gets that scene's job, so switching pages or reloading cannot
   attach one page's audio to another.
"""

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

router = APIRouter(prefix="/courses", tags=["openmaic-narration"])


class NarrationIn(BaseModel):
    """Only identifiers: the script is derived server-side from the scene body."""

    scene_id: str = Field(..., min_length=1, max_length=192)
    stage_id: str = Field(..., min_length=1, max_length=192)


def _container() -> ServiceContainer:
    return get_container()


def _client(container: ServiceContainer = Depends(_container)) -> OpenMAICFusionClient:
    settings = container.settings
    return OpenMAICFusionClient(
        base_url=settings.openmaic_service_url,
        secret=settings.openmaic_internal_secret,
        timeout_seconds=settings.openmaic_service_timeout_seconds,
    )


def _require(container: ServiceContainer) -> None:
    if not container.settings.openmaic_fusion_enabled:
        raise FusionUnavailable("受管 OpenMAIC 服务未启用")


def _key(value: Optional[str]) -> str:
    text = (value or "").strip()
    if not text or len(text) > 200:
        raise FusionInvalidRequest("讲解生成请求必须携带有效的 Idempotency-Key")
    return text


@router.get(
    "/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}/narration"
)
async def get_scene_narration(
    course_id: str,
    workspace_id: str,
    stage_id: str,
    scene_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> Dict[str, Any]:
    """Report whether this scene already has narration, and which job owns it."""
    _require(container)
    assert_course_access(container, user, course_id)
    return await client.get_scene_narration(
        user_id=str(user.id), course_id=course_id, workspace_id=workspace_id,
        stage_id=stage_id, scene_id=scene_id,
    )


@router.post(
    "/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}/narration",
    status_code=202,
)
async def synthesize_scene_narration(
    course_id: str,
    workspace_id: str,
    stage_id: str,
    scene_id: str,
    body: NarrationIn,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> Dict[str, Any]:
    """Enqueue narration for one scene; the audio arrives as an artifact.

    Answers 202 with a job reference because synthesis is queued, not inline.
    Repeated calls for the same scene reuse the existing job rather than paying
    for a second synthesis.
    """
    _require(container)
    assert_course_access(container, user, course_id)
    # A body scene_id that disagrees with the path is a client bug worth
    # surfacing, not something to silently reconcile.
    if body.scene_id != scene_id or body.stage_id != stage_id:
        raise FusionInvalidRequest("请求体中的场景标识与路径不一致")
    return await client.synthesize_scene_narration(
        user_id=str(user.id), course_id=course_id, workspace_id=workspace_id,
        stage_id=stage_id, scene_id=scene_id,
        idempotency_key=_key(idempotency_key),
    )


__all__ = ["router", "NarrationIn"]
