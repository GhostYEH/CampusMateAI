"""CampusMate-facing material routes.

A material is a course-scoped document a student brought in. The gateway owns
the same things it owns for workspaces and discovery, plus the one decision that
is specific to this surface:

- **identity** — the acting user is the CampusMate JWT subject and the course is
  the one in the path, re-checked against the unified course-visibility policy
  before anything is sent upstream;
- **intake policy** — the file is size-checked, its filename is validated as a
  *name* (never a path) and its text is extracted here, in
  :mod:`...services.magicclass.material_extraction`. The browser never chooses the
  media type: it is derived from the extension, so a mislabelled upload cannot
  talk the extractor into decoding binary bytes as text;
- **retry safety** — an upload must carry an `Idempotency-Key` and a delete must
  carry `If-Match`;
- **status translation** — the service's 412 becomes a 409 for the browser;
- **the fusion switch** — when the runtime is off these routes answer 503 rather
  than an empty list, which would read as "you have no materials".

The file bytes are read for extraction and are **not** retained by this slice;
what the managed service stores is the metadata plus the extracted text. Asset
storage is a later slice, and the capability stays "partially complete" until
then.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Header, Query, UploadFile, status

from ...core.config import Settings
from ...models.multi_role import UserRow
from ...schemas.magicclass_fusion import (
    MaterialDetailOut,
    MaterialListOut,
    MaterialOut,
    MaterialResolveIn,
    MaterialResolveOut,
    MaterialReferenceOut,
)
from ...services.container import ServiceContainer, get_container
from ...services.magicclass.course_context import assert_course_access
from ...services.magicclass.fusion_client import MagicClassFusionClient
from ...services.magicclass.fusion_errors import FusionInvalidRequest, FusionUnavailable
from ...services.magicclass.material_extraction import (
    MAX_MATERIAL_BYTES,
    MAX_REFERENCE_COUNT,
    extract_material,
)
from ..deps import current_user

router = APIRouter(prefix="/courses", tags=["magicclass-materials"])

DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 50
MAX_IDEMPOTENCY_KEY_LENGTH = 200


def _container() -> ServiceContainer:
    return get_container()


def _client(container: ServiceContainer = Depends(_container)) -> MagicClassFusionClient:
    """Build the internal client from the request container, not a module singleton."""
    settings = container.settings
    return MagicClassFusionClient(
        base_url=settings.magicclass_service_url,
        secret=settings.magicclass_internal_secret,
        timeout_seconds=settings.magicclass_service_timeout_seconds,
    )


def _require_fusion_enabled(settings: Settings) -> None:
    if not settings.magicclass_fusion_enabled:
        raise FusionUnavailable("受管 magic class 服务未启用")


def _require_idempotency_key(value: Optional[str]) -> str:
    key = (value or "").strip()
    if not key:
        raise FusionInvalidRequest("上传请求必须携带 Idempotency-Key")
    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise FusionInvalidRequest("Idempotency-Key 过长")
    return key


def _require_revision(value: Optional[str]) -> int:
    raw = (value or "").strip().replace("W/", "").replace('"', "")
    if not raw:
        raise FusionInvalidRequest("写入请求必须携带 If-Match（当前 revision）")
    if raw == "*":
        raise FusionInvalidRequest("If-Match 不接受 *，请传回你读到的 revision")
    try:
        revision = int(raw)
    except ValueError as exc:
        raise FusionInvalidRequest("If-Match 必须是正整数 revision") from exc
    if revision < 1:
        raise FusionInvalidRequest("If-Match 必须是正整数 revision")
    return revision


def _limit(value: int) -> int:
    return max(1, min(int(value), MAX_PAGE_LIMIT))


def _material_out(payload: Dict[str, Any]) -> MaterialOut:
    return MaterialOut(**{k: payload[k] for k in MaterialOut.model_fields if k in payload})


def _material_detail(payload: Dict[str, Any]) -> MaterialDetailOut:
    return MaterialDetailOut(
        **{k: payload[k] for k in MaterialDetailOut.model_fields if k in payload}
    )


def _reference_out(payload: Dict[str, Any]) -> MaterialReferenceOut:
    return MaterialReferenceOut(
        **{k: payload[k] for k in MaterialReferenceOut.model_fields if k in payload}
    )


@router.get("/{course_id}/materials", response_model=MaterialListOut)
async def list_materials(
    course_id: str,
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: Optional[str] = Query(None, max_length=512),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> MaterialListOut:
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    payload = await client.list_materials(
        user_id=str(user.id), course_id=course_id, limit=_limit(limit), cursor=cursor
    )
    return MaterialListOut(
        items=[_material_out(item) for item in payload.get("items", [])],
        next_cursor=payload.get("next_cursor"),
    )


@router.post("/{course_id}/materials", response_model=MaterialOut, status_code=status.HTTP_201_CREATED)
async def upload_material(
    course_id: str,
    file: UploadFile = File(...),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> MaterialOut:
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    key = _require_idempotency_key(idempotency_key)

    # Read one byte past the limit so an oversized file is rejected on the way
    # in, rather than parsed and then rejected on the way out.
    content = await file.read(MAX_MATERIAL_BYTES + 1)
    extracted = extract_material(filename=file.filename or "", content=content)
    created = await client.create_material(
        user_id=str(user.id),
        course_id=course_id,
        filename=extracted.filename,
        media_type=extracted.media_type,
        byte_size=extracted.byte_size,
        sha256=extracted.sha256,
        extraction_status=extracted.extraction_status,
        text=extracted.text,
        content_base64=extracted.content_base64,
        idempotency_key=key,
    )
    return _material_out(created)


@router.post("/{course_id}/materials/resolve", response_model=MaterialResolveOut)
async def resolve_materials(
    course_id: str,
    body: MaterialResolveIn,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> MaterialResolveOut:
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    ids = [str(item).strip() for item in body.material_ids]
    if any(not item for item in ids):
        raise FusionInvalidRequest("material_ids 只能包含非空字符串")
    if len(ids) > MAX_REFERENCE_COUNT:
        raise FusionInvalidRequest(f"material_ids 最多 {MAX_REFERENCE_COUNT} 项")
    payload = await client.resolve_materials(
        user_id=str(user.id), course_id=course_id, material_ids=ids
    )
    return MaterialResolveOut(
        resolved=[_reference_out(item) for item in payload.get("resolved", [])],
        unresolved=[str(item) for item in payload.get("unresolved", [])],
    )


@router.get("/{course_id}/materials/{material_id}", response_model=MaterialDetailOut)
async def get_material(
    course_id: str,
    material_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> MaterialDetailOut:
    """The one material route that returns the extracted text."""
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    return _material_detail(
        await client.get_material(
            user_id=str(user.id), course_id=course_id, material_id=material_id
        )
    )


@router.delete("/{course_id}/materials/{material_id}")
async def delete_material(
    course_id: str,
    material_id: str,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Dict[str, Any]:
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    await client.delete_material(
        user_id=str(user.id),
        course_id=course_id,
        material_id=material_id,
        revision=_require_revision(if_match),
    )
    return {"deleted": True}


__all__ = ["router", "DEFAULT_PAGE_LIMIT", "MAX_PAGE_LIMIT", "MAX_MATERIAL_BYTES"]
