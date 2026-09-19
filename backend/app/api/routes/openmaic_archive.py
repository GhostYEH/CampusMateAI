"""CampusMate-facing `.maic.zip` export + import routes.

The gateway owns identity, course permission, retry safety and status translation,
exactly as it does for workspaces and materials. Two things are specific here:

- **Export answers bytes, not JSON.** A `.maic.zip` is a file the student saves, so
  the response is `application/zip` with a `Content-Disposition` filename and the
  digest in a header. The browser fetches it through the authenticated client (a
  plain link would not carry the JWT) and turns it into an object URL. The internal
  call still uses the service's one JSON envelope — the base64 is decoded here so
  the encoding never reaches the browser.
- **Import accepts a file, not base64.** The student picks a file, so the request
  is multipart. The size is checked before anything is sent upstream, and the
  archive is base64-encoded only for the internal hop.

Nothing in an archive decides ownership: the stage lands in the workspace named by
*this* request, owned by the JWT subject, regardless of what the manifest says.
"""

from __future__ import annotations

import base64
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Header, Response, UploadFile, status

from ...core.config import Settings
from ...models.multi_role import UserRow
from ...schemas.openmaic_fusion import StageOut
from ...services.container import ServiceContainer, get_container
from ...services.openmaic.course_context import assert_course_access
from ...services.openmaic.fusion_client import OpenMAICFusionClient
from ...services.openmaic.fusion_errors import FusionInvalidRequest, FusionUnavailable
from ..deps import current_user

router = APIRouter(prefix="/courses", tags=["openmaic-archive"])

#: Mirrors `openmaic-service/src/archive/manifest.ts`. The gateway refuses first
#: so the student gets a CampusMate-shaped message, and the service enforces the
#: same number so a direct caller cannot bypass it.
MAX_ARCHIVE_BYTES = int(2.5 * 1024 * 1024)
MAX_IDEMPOTENCY_KEY_LENGTH = 200


def _container() -> ServiceContainer:
    return get_container()


def _client(container: ServiceContainer = Depends(_container)) -> OpenMAICFusionClient:
    settings = container.settings
    return OpenMAICFusionClient(
        base_url=settings.openmaic_service_url,
        secret=settings.openmaic_internal_secret,
        timeout_seconds=settings.openmaic_service_timeout_seconds,
    )


def _require_fusion_enabled(settings: Settings) -> None:
    if not settings.openmaic_fusion_enabled:
        raise FusionUnavailable("受管 OpenMAIC 服务未启用")


def _require_idempotency_key(value: Optional[str]) -> str:
    key = (value or "").strip()
    if not key:
        raise FusionInvalidRequest("导入请求必须携带 Idempotency-Key")
    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise FusionInvalidRequest("Idempotency-Key 过长")
    return key


def _content_disposition(filename: str) -> str:
    """A download filename header that survives a non-ASCII title.

    HTTP header values are latin-1, so a Chinese filename cannot go in the quoted
    form at all. RFC 6266/5987 is the answer: an ASCII-only `filename` fallback for
    old clients plus `filename*=UTF-8''…` carrying the real name, percent-encoded.

    The name comes from the service, which derived it from a student-authored
    title, so both forms are stripped of anything that could terminate the header
    or start a new one.
    """
    cleaned = "".join(
        character
        for character in str(filename or "")
        if character.isprintable() and character not in '"\\\r\n'
    ).strip()
    # The fallback is what a client that ignores `filename*` will save. Deriving it
    # by dropping the non-ASCII characters yielded things like ".maic.zip", so a
    # name that is not already pure ASCII gets one clear, predictable stand-in.
    ascii_fallback = cleaned if cleaned and cleaned.isascii() else "archive.maic.zip"
    encoded = quote(cleaned or "学习内容.maic.zip", safe="")
    return f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded}\''


@router.get("/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/export")
async def export_stage(
    course_id: str,
    workspace_id: str,
    stage_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> Response:
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    payload = await client.export_stage(
        user_id=str(user.id),
        course_id=course_id,
        workspace_id=workspace_id,
        stage_id=stage_id,
    )
    encoded = payload.get("archive")
    if not isinstance(encoded, str) or not encoded:
        # The service answered without an archive. Treat it as a deployment drift
        # rather than handing the browser an empty download that looks like a
        # successful export.
        raise FusionUnavailable("受管服务未返回可用档案")
    try:
        archive = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise FusionUnavailable("受管服务返回的档案无法解码") from exc

    filename = str(payload.get("filename") or "学习内容.maic.zip")
    return Response(
        content=archive,
        media_type="application/zip",
        headers={
            "Content-Disposition": _content_disposition(filename),
            "Cache-Control": "no-store",
            "X-Archive-Sha256": str(payload.get("sha256") or ""),
            "X-Archive-Format-Version": str(payload.get("format_version") or ""),
        },
    )


@router.post("/{course_id}/workspaces/{workspace_id}/import", response_model=StageOut, status_code=status.HTTP_201_CREATED)
async def import_stage(
    course_id: str,
    workspace_id: str,
    file: UploadFile = File(...),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: OpenMAICFusionClient = Depends(_client),
) -> StageOut:
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    key = _require_idempotency_key(idempotency_key)

    # One byte past the limit so an oversize file is refused on the way in, rather
    # than uploaded and then rejected.
    content = await file.read(MAX_ARCHIVE_BYTES + 1)
    if len(content) > MAX_ARCHIVE_BYTES:
        raise FusionInvalidRequest(f"档案不能超过 {MAX_ARCHIVE_BYTES} 字节")
    if not content:
        raise FusionInvalidRequest("档案为空")

    payload = await client.import_stage(
        user_id=str(user.id),
        course_id=course_id,
        workspace_id=workspace_id,
        archive_b64=base64.b64encode(content).decode("ascii"),
        idempotency_key=key,
    )
    stage = payload.get("stage") if isinstance(payload, dict) else None
    if not isinstance(stage, dict):
        raise FusionUnavailable("受管服务未返回导入结果")
    return StageOut(**{name: stage[name] for name in StageOut.model_fields if name in stage})


__all__ = ["router", "MAX_ARCHIVE_BYTES"]
