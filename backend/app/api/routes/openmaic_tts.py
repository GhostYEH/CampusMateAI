"""Course-bound speech synthesis gateway.

The upstream call never happens in the request path: the managed service runs
providers through a queued job worker because its route handlers are synchronous
by design (identity consumption and writes share one SQLite transaction). So
this route answers 202 with a job reference, the service synthesizes offline,
and the audio is fetched afterwards through the artifact download route.
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

router = APIRouter(prefix="/courses", tags=["openmaic-tts"])


class TtsIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)
    instruction: Optional[str] = Field(None, min_length=1, max_length=2000)
    voice: Optional[str] = Field(None, min_length=1, max_length=80)


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
        raise FusionInvalidRequest("语音合成请求必须携带有效的 Idempotency-Key")
    return text


@router.post("/{course_id}/tts", status_code=202)
async def synthesize_speech(
    course_id: str,
    body: TtsIn,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> Dict[str, Any]:
    _require(container)
    assert_course_access(container, user, course_id)
    return await client.synthesize_speech(
        user_id=str(user.id),
        course_id=course_id,
        text=body.text,
        instruction=body.instruction,
        voice=body.voice,
        idempotency_key=_key(idempotency_key),
    )


__all__ = ["router", "TtsIn"]
