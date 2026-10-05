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

from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, File, Header, Query, UploadFile, status

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
from ..magicclass_gateway import build_fusion_client, require_idempotency_key, require_revision

router = APIRouter(prefix="/courses", tags=["课堂资料"])

DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 50
MAX_IDEMPOTENCY_KEY_LENGTH = 200


def _container() -> ServiceContainer:
    return get_container()


def _client(container: ServiceContainer = Depends(_container)) -> MagicClassFusionClient:
    """Build the internal client from the request container, not a module singleton."""
    return build_fusion_client(container, client_type=MagicClassFusionClient)


def _require_fusion_enabled(settings: Settings) -> None:
    if not settings.magicclass_fusion_enabled:
        raise FusionUnavailable("受管 magic class 服务未启用")


def _require_idempotency_key(value: Optional[str]) -> str:
    return require_idempotency_key(
        value,
        missing_message="上传请求必须携带 Idempotency-Key",
        max_length=MAX_IDEMPOTENCY_KEY_LENGTH,
    )


def _require_revision(value: Optional[str]) -> int:
    return require_revision(value)


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


@router.get(
    "/{course_id}/materials",
    response_model=MaterialListOut,
    summary="列出资料",
    responses={
        200: {
            "description": "资料列表（仅元数据，不含正文）",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "列出资料",
                            "value": {
                                "items": [
                                    {
                                        "id": "mat_001",
                                        "course_id": "course_001",
                                        "filename": "第三讲-操作系统.pdf",
                                        "media_type": "application/pdf",
                                        "byte_size": 1048576,
                                        "sha256": "3f786850e387550fdab836ed7e6dc881de23001b",
                                        "extraction_status": "extracted",
                                        "text_chars": 8421,
                                        "revision": 1,
                                        "created_at": "2026-09-20T08:00:00+00:00",
                                        "updated_at": "2026-09-20T08:00:00+00:00",
                                        "deduplicated": False,
                                    }
                                ],
                                "next_cursor": None,
                            },
                        }
                    }
                }
            },
        }
    },
)
async def list_materials(
    course_id: str,
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: Optional[str] = Query(None, max_length=512),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> MaterialListOut:
    """列出本课程中调用者可见的资料元数据（不含正文）。

    - 需要已登录且对该课程有访问权限。
    - 分页用 limit（默认 20，最大 50）与 cursor；next_cursor 为空表示没有下一页。
    - 受管服务未启用时返回 503，而不是空列表。
    """
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    payload = await client.list_materials(
        user_id=str(user.id), course_id=course_id, limit=_limit(limit), cursor=cursor
    )
    return MaterialListOut(
        items=[_material_out(item) for item in payload.get("items", [])],
        next_cursor=payload.get("next_cursor"),
    )


@router.post(
    "/{course_id}/materials",
    response_model=MaterialOut,
    status_code=status.HTTP_201_CREATED,
    summary="上传资料",
    responses={
        201: {
            "description": "上传成功，返回资料元数据（正文不回传）",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "上传资料",
                            "value": {
                                "id": "mat_001",
                                "course_id": "course_001",
                                "filename": "第三讲-操作系统.pdf",
                                "media_type": "application/pdf",
                                "byte_size": 1048576,
                                "sha256": "3f786850e387550fdab836ed7e6dc881de23001b",
                                "extraction_status": "extracted",
                                "text_chars": 8421,
                                "revision": 1,
                                "created_at": "2026-09-20T08:00:00+00:00",
                                "updated_at": "2026-09-20T08:00:00+00:00",
                                "deduplicated": False,
                            },
                        }
                    }
                }
            },
        }
    },
)
async def upload_material(
    course_id: str,
    file: UploadFile = File(...),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> MaterialOut:
    """上传一份课程资料，服务端在此提取文本并返回元数据。

    - multipart/form-data，字段为 `file`；必须携带 Idempotency-Key，重试不会创建副本。
    - 文件名仅按名称校验，媒体类型由扩展名推导；超限文件在此直接拒绝。
    - 需要已登录且对该课程有访问权限；受管服务未启用时返回 503。
    """
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


@router.post(
    "/{course_id}/materials/resolve",
    response_model=MaterialResolveOut,
    summary="解析资料引用",
    responses={
        200: {
            "description": "解析结果：可引用的资料与未解析到的 id",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "解析资料引用",
                            "value": {
                                "resolved": [
                                    {
                                        "id": "mat_001",
                                        "filename": "第三讲-操作系统.pdf",
                                        "media_type": "application/pdf",
                                        "extraction_status": "extracted",
                                        "text_chars": 8421,
                                        "updated_at": "2026-09-20T08:00:00+00:00",
                                    }
                                ],
                                "unresolved": ["mat_missing"],
                            },
                        }
                    }
                }
            },
        }
    },
)
async def resolve_materials(
    course_id: str,
    body: Annotated[
        MaterialResolveIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "解析两份资料引用",
                    "value": {"material_ids": ["mat_001", "mat_missing"]},
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> MaterialResolveOut:
    """批量解析资料引用，返回可被舞台引用的资料列表。

    - material_ids 最多 50 项，且只能包含非空字符串。
    - unresolved 只表示未解析到（异用户、异课程、已删除、不存在同义），不说明原因。
    - 需要已登录且对该课程有访问权限；受管服务未启用时返回 503。
    """
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


@router.get(
    "/{course_id}/materials/{material_id}",
    response_model=MaterialDetailOut,
    summary="读取资料",
    responses={
        200: {
            "description": "单份资料，含提取出的正文文本",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "读取资料",
                            "value": {
                                "id": "mat_001",
                                "course_id": "course_001",
                                "filename": "第三讲-操作系统.pdf",
                                "media_type": "application/pdf",
                                "byte_size": 1048576,
                                "sha256": "3f786850e387550fdab836ed7e6dc881de23001b",
                                "extraction_status": "extracted",
                                "text_chars": 8421,
                                "revision": 1,
                                "created_at": "2026-09-20T08:00:00+00:00",
                                "updated_at": "2026-09-20T08:00:00+00:00",
                                "deduplicated": False,
                                "text": "操作系统是管理计算机硬件与软件资源的系统软件……",
                            },
                        }
                    }
                }
            },
        }
    },
)
async def get_material(
    course_id: str,
    material_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> MaterialDetailOut:
    """读取单份资料，包含提取出的正文文本。

    - 这是唯一会返回正文的资料接口，列表接口只返回元数据。
    - 需要已登录且对该课程有访问权限；受管服务未启用时返回 503。
    """
    _require_fusion_enabled(container.settings)
    assert_course_access(container, user, course_id)
    return _material_detail(
        await client.get_material(
            user_id=str(user.id), course_id=course_id, material_id=material_id
        )
    )


@router.delete(
    "/{course_id}/materials/{material_id}",
    summary="删除资料",
    responses={
        200: {
            "description": "删除成功",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "删除资料",
                            "value": {"deleted": True},
                        }
                    }
                }
            },
        }
    },
)
async def delete_material(
    course_id: str,
    material_id: str,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Dict[str, Any]:
    """删除指定资料。

    - 必须携带 If-Match（当前 revision），不接受 `*`。
    - 需要已登录且对该课程有访问权限；受管服务未启用时返回 503。
    """
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
