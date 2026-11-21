"""Course-bound stage whiteboard gateway.

The whiteboard is part of the authorized stage document, not a free-form
scratchpad. The browser therefore sends the board snapshot with the current
stage revision; the managed service remains the only writer and rejects a
stale revision. Keeping `If-Match` mandatory here prevents two learners (or a
retry and an edit) from overwriting each other silently.
"""

from __future__ import annotations

from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, Header
from pydantic import BaseModel, Field

from ...models.multi_role import UserRow
from ...services.container import ServiceContainer, get_container
from ...services.magicclass.course_context import assert_course_access
from ...services.magicclass.fusion_client import MagicClassFusionClient
from ...services.magicclass.fusion_errors import FusionInvalidRequest, FusionUnavailable
from ..deps import current_user
from ..magicclass_gateway import build_fusion_client, require_idempotency_key, require_revision

router = APIRouter(prefix="/courses", tags=["课堂白板"])

MAX_BOARD_ELEMENTS = 2000


def _container() -> ServiceContainer:
    return get_container()


def _client(container: ServiceContainer = Depends(_container)) -> MagicClassFusionClient:
    return build_fusion_client(container, client_type=MagicClassFusionClient)


def _require_idempotency_key(value: Optional[str]) -> str:
    return require_idempotency_key(
        value,
        missing_message="白板保存请求必须携带 Idempotency-Key",
        max_length=200,
    )


def _require_revision(value: Optional[str]) -> int:
    return require_revision(value, missing_message="白板保存请求必须携带 If-Match（当前 revision）")


class WhiteboardIn(BaseModel):
    """A complete board snapshot; partial element edits are not accepted.

    The managed service validates the element schema. This gateway only rejects
    structurally impossible snapshots early, so malformed input never reaches
    the service and a stale revision cannot be hidden inside a large payload.
    """

    board: Dict[str, Any] = Field(..., description="完整白板快照（id/viewport/elements）")


def _validate_board(board: Dict[str, Any]) -> None:
    board_id = board.get("id")
    if not isinstance(board_id, str) or not board_id.strip() or len(board_id) > 192:
        raise FusionInvalidRequest("白板必须包含合法的 id")
    viewport_size = board.get("viewportSize")
    if not isinstance(viewport_size, (int, float)) or not viewport_size or viewport_size <= 0:
        raise FusionInvalidRequest("白板 viewportSize 必须是正数")
    viewport_ratio = board.get("viewportRatio")
    if not isinstance(viewport_ratio, (int, float)) or viewport_ratio <= 0:
        raise FusionInvalidRequest("白板 viewportRatio 必须是正数")
    elements = board.get("elements")
    if not isinstance(elements, list):
        raise FusionInvalidRequest("白板 elements 必须是数组")
    if len(elements) > MAX_BOARD_ELEMENTS:
        raise FusionInvalidRequest("白板元素过多")


@router.post(
    "/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/whiteboard",
    summary="保存舞台白板",
    responses={
        200: {
            "description": "白板已按当前 revision 保存，返回最新 revision 与白板快照",
            "content": {
                "application/json": {
                    "example": {
                        "revision": 8,
                        "board": {
                            "id": "whiteboard_1",
                            "viewportSize": 1000,
                            "viewportRatio": 0.5625,
                            "elements": [],
                        },
                    }
                }
            },
        },
        409: {"description": "revision 已过期，客户端应重新读取舞台后再保存"},
    },
)
async def save_stage_whiteboard(
    course_id: str,
    workspace_id: str,
    stage_id: str,
    body: Annotated[
        WhiteboardIn,
        Body(
            openapi_examples={
                "添加一张文字卡": {
                    "summary": "保存完整白板快照",
                    "value": {
                        "board": {
                            "id": "whiteboard_1",
                            "viewportSize": 1000,
                            "viewportRatio": 0.5625,
                            "elements": [
                                {
                                    "id": "wb-text-1",
                                    "type": "text",
                                    "left": 80,
                                    "top": 80,
                                    "width": 360,
                                    "height": 80,
                                    "rotate": 0,
                                    "content": "极限存在的条件",
                                    "defaultFontName": "PingFang SC",
                                    "defaultColor": "#153B34",
                                }
                            ],
                        }
                    },
                }
            }
        ),
    ],
    if_match: Optional[str] = Header(None, alias="If-Match"),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Dict[str, Any]:
    """Persist the complete board against the stage revision.

    - Course access is re-checked before the internal call.
    - A stale `If-Match` becomes a 409 through the shared fusion error mapping.
    - The response is the managed service's canonical board/revision, so the
      browser can keep editing without guessing a new revision.
    """
    if not container.settings.magicclass_fusion_enabled:
        raise FusionUnavailable("受管 magic class 服务未启用")
    assert_course_access(container, user, course_id)
    _validate_board(body.board)
    revision = _require_revision(if_match)
    key = _require_idempotency_key(idempotency_key)
    return await client.add_whiteboard(
        user_id=str(user.id),
        course_id=course_id,
        workspace_id=workspace_id,
        stage_id=stage_id,
        board=body.board,
        revision=revision,
        idempotency_key=key,
    )


__all__ = ["router", "WhiteboardIn"]
