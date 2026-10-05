"""Course-bound generation and job recovery gateway."""

from __future__ import annotations

import base64
import hashlib
from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, Header, Response
from pydantic import BaseModel, Field

from ...models.multi_role import UserRow
from ...services.container import ServiceContainer, get_container
from ...services.magicclass.course_context import assert_course_access, build_course_context
from ...services.magicclass.fusion_client import MagicClassFusionClient
from ...services.magicclass.fusion_errors import FusionInvalidRequest, FusionUnavailable
from ..deps import current_user
from ..magicclass_gateway import build_fusion_client
from .magicclass_archive import content_disposition

router = APIRouter(prefix="/courses", tags=["课堂生成"])

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
    return build_fusion_client(container, client_type=MagicClassFusionClient)


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


@router.post(
    "/{course_id}/workspaces/{workspace_id}/generate",
    status_code=201,
    summary="生成舞台内容",
    responses={
        201: {
            "description": "已生成舞台内容，返回舞台、任务与来源",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "生成一节函数极限讲解课堂",
                            "value": {
                                "stage_id": "stg_1a2b3c",
                                "stage": {
                                    "id": "stg_1a2b3c",
                                    "workspace_id": "ws_1",
                                    "course_id": "course_db_2025",
                                    "title": "函数极限",
                                    "revision": 1,
                                    "dsl_version": "0.3.0",
                                    "document": {"dslVersion": "0.3.0", "scenes": []},
                                },
                                "job": {
                                    "id": "job_5b7e21",
                                    "status": "queued",
                                    "progress": 0,
                                    "artifact_id": None,
                                    "mode": "slide",
                                    "error_code": None,
                                },
                                "source": "provider",
                            },
                        }
                    }
                }
            },
        }
    },
)
async def generate_stage(
    course_id: str,
    workspace_id: str,
    body: Annotated[
        GenerationIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "生成函数极限讲解舞台",
                    "value": {
                        "mode": "slide",
                        "prompt": "讲解函数极限的直观含义与典型例题",
                        "role_mode": "preset",
                        "selected_role_ids": ["role_teacher"],
                    },
                }
            }
        ),
    ],
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Dict[str, Any]:
    """生成一节绑定课程与工作台的舞台内容。

    - 必须携带有效 Idempotency-Key；重复提交同一键不会重复生成。
    - 生成模型不可用（返回 local-template）时返回 503，而不是假的课堂。
    - 需要已登录且对该课程有访问权限；受管服务未启用时返回 503。
    """
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


@router.post(
    "/{course_id}/home-generate",
    status_code=201,
    summary="生成首页内容",
    responses={
        201: {
            "description": "已生成课程首页内容，返回工作台、任务与来源",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "由课程首页主题生成学习课堂",
                            "value": {
                                "workspace_id": "ws_home",
                                "source": "provider",
                                "stage_id": "stg_home",
                                "job": {
                                    "id": "job_home",
                                    "status": "queued",
                                    "progress": 0,
                                    "artifact_id": None,
                                    "mode": "slide",
                                    "error_code": None,
                                },
                            },
                        }
                    }
                }
            },
        }
    },
)
async def generate_home(
    course_id: str,
    body: Annotated[
        HomeGenerationIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "由主题生成课程首页",
                    "value": {"mode": "slide", "prompt": "函数极限"},
                }
            }
        ),
    ],
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Dict[str, Any]:
    """把一次课程首页提交收敛成一个工作台/任务对。

    - 工作台按学习者与课程稳定复用，同一主题重试不会创建重复工作台。
    - 课程上下文由服务端按 course_id 重建，浏览器只提交自己的主题。
    - 生成模型不可用或未返回工作台标识时返回 503。
    """
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


@router.get(
    "/{course_id}/jobs/{job_id}",
    summary="读取生成任务",
    responses={
        200: {
            "description": "生成任务的当前状态与进度",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "读取生成任务",
                            "value": {
                                "id": "job_5b7e21",
                                "course_id": "course_db_2025",
                                "kind": "generation",
                                "mode": "slide",
                                "status": "running",
                                "progress": 60,
                                "attempts": 1,
                                "error_code": None,
                                "artifact_id": None,
                                "scene_id": None,
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "updated_at": "2026-10-06T08:00:30+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
async def get_job(
    course_id: str,
    job_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Dict[str, Any]:
    """读取生成任务的状态与进度。

    - 任务不存在返回 404（NOT_FOUND）。
    - 需要已登录且对该课程有访问权限；受管服务未启用时返回 503。
    """
    _require(container)
    assert_course_access(container, user, course_id)
    return await client.get_job(user_id=str(user.id), course_id=course_id, job_id=job_id)


@router.get(
    "/{course_id}/artifacts/{artifact_id}",
    summary="读取生成产物",
)
async def get_artifact(
    course_id: str,
    artifact_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Response:
    """读取一次生成产物的原始字节（按产物媒体类型返回文件）。

    - 响应为二进制文件流，不是 JSON；带 X-Artifact-Sha256 头。
    - 受管服务未返回可用或类型不受支持的产物时返回 503。
    - 需要已登录且对该课程有访问权限；受管服务未启用时返回 503。
    """
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


@router.post(
    "/{course_id}/jobs/{job_id}/cancel",
    summary="取消生成任务",
    responses={
        200: {
            "description": "已取消，返回更新后的任务状态",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "取消生成任务",
                            "value": {
                                "id": "job_5b7e21",
                                "course_id": "course_db_2025",
                                "kind": "generation",
                                "mode": "slide",
                                "status": "cancelled",
                                "progress": 60,
                                "attempts": 1,
                                "error_code": None,
                                "artifact_id": None,
                                "scene_id": None,
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "updated_at": "2026-10-06T08:01:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
async def cancel_job(
    course_id: str,
    job_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Dict[str, Any]:
    """取消一个进行中的生成任务。

    - 已完成的任务不可取消；重复取消返回当前状态。
    - 需要已登录且对该课程有访问权限；受管服务未启用时返回 503。
    """
    _require(container)
    assert_course_access(container, user, course_id)
    return await client.cancel_job(user_id=str(user.id), course_id=course_id, job_id=job_id)


@router.post(
    "/{course_id}/jobs/{job_id}/retry",
    summary="重试生成任务",
    responses={
        200: {
            "description": "已重新入队，返回更新后的任务状态",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "重试生成任务",
                            "value": {
                                "id": "job_5b7e21",
                                "course_id": "course_db_2025",
                                "kind": "generation",
                                "mode": "slide",
                                "status": "queued",
                                "progress": 0,
                                "attempts": 2,
                                "error_code": None,
                                "artifact_id": None,
                                "scene_id": None,
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "updated_at": "2026-10-06T08:02:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
async def retry_job(
    course_id: str,
    job_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    client: MagicClassFusionClient = Depends(_client),
) -> Dict[str, Any]:
    """重试一个失败或已取消的生成任务。

    - 只有失败或已取消的任务可以重试；其他状态返回 400。
    - 需要已登录且对该课程有访问权限；受管服务未启用时返回 503。
    """
    _require(container)
    assert_course_access(container, user, course_id)
    return await client.retry_job(user_id=str(user.id), course_id=course_id, job_id=job_id)


__all__ = ["router", "GenerationIn", "HomeGenerationIn", "ARTIFACT_MEDIA_TYPES"]
