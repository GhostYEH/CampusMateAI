"""FastAPI client for the repository-managed magic class service.

Two rules shape this module:

- **The gateway is the only identity.** Every call mints a short-lived assertion
  from the *server-side* user and course; nothing the browser sends is forwarded
  as an identity, and the internal address plus the assertion never appear in a
  response.
- **The service's answers are translated, not relayed.** Status codes, bodies and
  failure codes are mapped into CampusMate's vocabulary
  ({@link .fusion_errors}) so no internal detail leaks and the browser sees a
  status it can act on.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from ...schemas.magicclass_fusion import FusionState, FusionStatus
from .capabilities import filter_capabilities
from .fusion_errors import FusionUnavailable, raise_for_service_error
from .service_assertion import issue_service_assertion

# Health/status is not course-scoped, so the assertion carries a sentinel that is
# obviously not a CampusMate course id rather than borrowing a real one.
SERVICE_SCOPE_SENTINEL = "__service__"

ASSERTION_HEADER = "X-CampusMate-Service-Assertion"
IDEMPOTENCY_HEADER = "Idempotency-Key"
IF_MATCH_HEADER = "If-Match"


class _Unset:
    """Sentinel for "the caller did not pass this argument".

    Optional body fields need three states (absent, present-with-value,
    present-with-null); `None` alone collapses two of them.
    """

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return "UNSET"


UNSET = _Unset()

READ_SCOPES = ("workspace:read",)
WRITE_SCOPES = ("workspace:read", "workspace:write")

# Discovery is a navigation surface over the same rows, so it keeps its own
# narrow scopes: a token minted to browse folders cannot be replayed to write a
# stage, and a search token is read-only by construction.
FOLDER_READ_SCOPES = ("folder:read",)
FOLDER_WRITE_SCOPES = ("folder:read", "folder:write")
SEARCH_READ_SCOPES = ("search:read",)
# Editing a stage is a distinct capability from owning the workspace: reading is
# enough to render an outline, writing additionally allows commands.
STAGE_READ_SCOPES = ("stage:read",)
STAGE_WRITE_SCOPES = ("stage:read", "stage:write")
# A material is course-scoped source content: reading is enough to cite it, and
# writing additionally allows uploading or deleting one.
MATERIAL_READ_SCOPES = ("material:read",)
MATERIAL_WRITE_SCOPES = ("material:read", "material:write")
# `.maic.zip` moves one stage in or out of a workspace. Export is a read of that
# stage; import writes a new one, so the two get separate grants.
ARCHIVE_READ_SCOPES = ("archive:read",)
ARCHIVE_WRITE_SCOPES = ("archive:write",)
VIDEO_EXPORT_SCOPES = ("archive:read", "job:write")
GENERATION_WRITE_SCOPES = ("generation:write", "workspace:write", "job:write")
TTS_WRITE_SCOPES = ("tts:write",)
# Scene narration is the same capability as TTS, addressed per scene: reading is
# enough to ask "does this page have audio", writing additionally synthesizes.
# They stay separate so a read-only view can poll without holding a write grant.
NARRATION_READ_SCOPES = ("tts:read",)
NARRATION_WRITE_SCOPES = ("tts:write",)
DISCUSSION_WRITE_SCOPES = ("multi-agent:write",)
# Artifacts are the finished products of jobs (stage JSON, WAV audio); reading
# one is a job-level capability, so it reuses the job read scope.
ARTIFACT_READ_SCOPES = ("job:read",)
JOB_READ_SCOPES = ("job:read",)
JOB_CANCEL_SCOPES = ("job:cancel",)
PROVIDER_STATUS_SCOPES = ("service:status",)
WHITEBOARD_WRITE_SCOPES = ("stage:write",)


def _status(
    state: FusionState,
    *,
    reason: str,
    capabilities: Optional[list[str]] = None,
) -> FusionStatus:
    """构造对外状态。

    只有 ``ready`` 才带 capability —— 依赖没就绪时声称能力可用，会让浏览器
    打开一个必然失败的功能入口。
    """
    return FusionStatus(
        enabled=state is not FusionState.DISABLED,
        available=state is FusionState.READY,
        state=state,
        capabilities=capabilities if state is FusionState.READY else [],
        reason=reason,
    )


class MagicClassFusionClient:
    def __init__(
        self,
        *,
        base_url: str,
        secret: str,
        timeout_seconds: float = 5.0,
        transport: Optional[Any] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.secret = secret
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    # ===== transport =====

    def _assertion(self, user_id: str, course_id: str, scopes: tuple[str, ...]) -> str:
        try:
            return issue_service_assertion(
                user_id=user_id,
                course_id=course_id,
                scopes=list(scopes),
                secret=self.secret,
            )
        except Exception as exc:  # pragma: no cover - only reachable on misconfiguration
            raise FusionUnavailable() from exc

    async def _request(
        self,
        method: str,
        path: str,
        *,
        user_id: str,
        course_id: str,
        scopes: tuple[str, ...],
        params: Optional[dict[str, Any]] = None,
        json_body: Optional[dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        if_match: Optional[int] = None,
    ) -> Any:
        if not self.base_url or not self.secret:
            raise FusionUnavailable(details={"reason": "service_unconfigured"})
        headers = {ASSERTION_HEADER: self._assertion(user_id, course_id, scopes)}
        if idempotency_key:
            headers[IDEMPOTENCY_HEADER] = idempotency_key
        if if_match is not None:
            headers[IF_MATCH_HEADER] = str(int(if_match))
        url = f"{self.base_url}{path}"

        try:
            response = await self._dispatch(
                method, url, headers=headers, params=params, json_body=json_body
            )
        except Exception as exc:
            # The internal address and the assertion are deliberately absent.
            raise FusionUnavailable(details={"reason": "service_unreachable"}) from exc

        if response.status_code >= 400:
            raise_for_service_error(response.status_code, _safe_json(response))
        return _safe_json(response)

    async def _dispatch(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        params: Optional[dict[str, Any]],
        json_body: Optional[dict[str, Any]],
    ):
        if self.transport is not None:
            # The test double only implements `get`, so GET stays on that path.
            if method == "GET":
                if params:
                    return await self.transport.get(url, headers=headers, timeout=self.timeout_seconds, params=params)
                return await self.transport.get(url, headers=headers, timeout=self.timeout_seconds)
            return await self.transport.request(
                method, url, headers=headers, timeout=self.timeout_seconds, json=json_body
            )
        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=False) as client:
            return await client.request(
                method, url, headers=headers, params=params, json=json_body
            )

    # ===== status =====

    async def status(self, *, user_id: str) -> FusionStatus:
        if not self.base_url or not self.secret:
            # 开关开着但没配地址/密钥：网关自己就是没就绪的那一环。
            return _status(FusionState.UNAVAILABLE, reason="service_unconfigured")
        try:
            assertion = issue_service_assertion(
                user_id=user_id,
                course_id=SERVICE_SCOPE_SENTINEL,
                scopes=["service:status"],
                secret=self.secret,
            )
        except Exception:
            return _status(FusionState.UNAVAILABLE, reason="assertion_unsupported")

        try:
            headers = {ASSERTION_HEADER: assertion}
            response = await self._dispatch(
                "GET",
                f"{self.base_url}/internal/health/ready",
                headers=headers,
                params=None,
                json_body=None,
            )
        except Exception:
            return _status(FusionState.UNAVAILABLE, reason="service_unreachable")

        if response.status_code in (401, 403):
            # 受管服务在线但拒绝我们：部署问题，重试无用。
            return _status(FusionState.UNAVAILABLE, reason="assertion_rejected")
        if response.status_code == 503:
            # 服务在线、依赖未就绪 —— 这是 degraded，不是 unavailable。
            return _status(FusionState.DEGRADED, reason="dependency_unavailable")
        if response.status_code != 200:
            return _status(FusionState.UNAVAILABLE, reason="service_unreachable")

        payload = _safe_json(response)
        if not isinstance(payload, dict):
            return _status(FusionState.UNAVAILABLE, reason="service_unreachable")
        if payload.get("status") != "ready":
            # 200 但自称未就绪：以服务自己的判断为准。
            return _status(FusionState.DEGRADED, reason="dependency_unavailable")
        raw = payload.get("capabilities")
        capabilities = filter_capabilities(raw if isinstance(raw, list) else [])
        return _status(FusionState.READY, reason="ready", capabilities=capabilities)

    # ===== workspaces =====

    async def list_workspaces(
        self,
        *,
        user_id: str,
        course_id: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = int(limit)
        if cursor:
            params["cursor"] = cursor
        return await self._request(
            "GET",
            f"/internal/courses/{course_id}/workspaces",
            user_id=user_id,
            course_id=course_id,
            scopes=READ_SCOPES,
            params=params or None,
        )

    async def create_workspace(
        self,
        *,
        user_id: str,
        course_id: str,
        name: str,
        description: str = "",
        folder_id: Optional[str] = None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"name": name, "description": description}
        if folder_id is not None:
            body["folder_id"] = folder_id
        return await self._request(
            "POST",
            f"/internal/courses/{course_id}/workspaces",
            user_id=user_id,
            course_id=course_id,
            scopes=WRITE_SCOPES,
            json_body=body,
            idempotency_key=idempotency_key,
        )

    async def get_workspace(
        self, *, user_id: str, course_id: str, workspace_id: str
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/internal/courses/{course_id}/workspaces/{workspace_id}",
            user_id=user_id,
            course_id=course_id,
            scopes=READ_SCOPES,
        )

    async def update_workspace(
        self,
        *,
        user_id: str,
        course_id: str,
        workspace_id: str,
        revision: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        folder_id: Any = UNSET,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if folder_id is not UNSET:
            # An explicit `null` moves the workspace back to the unfiled list, so
            # "not provided" must stay distinguishable from "clear it".
            body["folder_id"] = folder_id
        return await self._request(
            "PATCH",
            f"/internal/courses/{course_id}/workspaces/{workspace_id}",
            user_id=user_id,
            course_id=course_id,
            scopes=WRITE_SCOPES,
            json_body=body,
            if_match=revision,
        )

    async def delete_workspace(
        self, *, user_id: str, course_id: str, workspace_id: str, revision: int
    ) -> dict[str, Any]:
        return await self._request(
            "DELETE",
            f"/internal/courses/{course_id}/workspaces/{workspace_id}",
            user_id=user_id,
            course_id=course_id,
            scopes=WRITE_SCOPES,
            if_match=revision,
        )

    # ===== stages =====

    async def list_stages(
        self,
        *,
        user_id: str,
        course_id: str,
        workspace_id: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = int(limit)
        if cursor:
            params["cursor"] = cursor
        return await self._request(
            "GET",
            f"/internal/courses/{course_id}/workspaces/{workspace_id}/stages",
            user_id=user_id,
            course_id=course_id,
            scopes=READ_SCOPES,
            params=params or None,
        )

    async def create_stage(
        self,
        *,
        user_id: str,
        course_id: str,
        workspace_id: str,
        title: str,
        document: Optional[dict[str, Any]],
        idempotency_key: str,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"title": title}
        if document is not None:
            body["document"] = document
        return await self._request(
            "POST",
            f"/internal/courses/{course_id}/workspaces/{workspace_id}/stages",
            user_id=user_id,
            course_id=course_id,
            scopes=WRITE_SCOPES,
            json_body=body,
            idempotency_key=idempotency_key,
        )

    async def get_stage(
        self, *, user_id: str, course_id: str, workspace_id: str, stage_id: str
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/internal/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}",
            user_id=user_id,
            course_id=course_id,
            scopes=READ_SCOPES,
        )

    async def replace_stage(
        self,
        *,
        user_id: str,
        course_id: str,
        workspace_id: str,
        stage_id: str,
        revision: int,
        document: dict[str, Any],
        title: Optional[str] = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"document": document}
        if title is not None:
            body["title"] = title
        return await self._request(
            "PUT",
            f"/internal/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}",
            user_id=user_id,
            course_id=course_id,
            scopes=WRITE_SCOPES,
            json_body=body,
            if_match=revision,
        )

    async def delete_stage(
        self,
        *,
        user_id: str,
        course_id: str,
        workspace_id: str,
        stage_id: str,
        revision: int,
    ) -> dict[str, Any]:
        return await self._request(
            "DELETE",
            f"/internal/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}",
            user_id=user_id,
            course_id=course_id,
            scopes=WRITE_SCOPES,
            if_match=revision,
        )

    # ===== folders =====

    async def list_folders(
        self,
        *,
        user_id: str,
        course_id: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = int(limit)
        if cursor:
            params["cursor"] = cursor
        return await self._request(
            "GET",
            f"/internal/courses/{course_id}/folders",
            user_id=user_id,
            course_id=course_id,
            scopes=FOLDER_READ_SCOPES,
            params=params or None,
        )

    async def create_folder(
        self,
        *,
        user_id: str,
        course_id: str,
        name: str,
        parent_id: Optional[str] = None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"name": name}
        if parent_id is not None:
            body["parent_id"] = parent_id
        return await self._request(
            "POST",
            f"/internal/courses/{course_id}/folders",
            user_id=user_id,
            course_id=course_id,
            scopes=FOLDER_WRITE_SCOPES,
            json_body=body,
            idempotency_key=idempotency_key,
        )

    async def get_folder(
        self, *, user_id: str, course_id: str, folder_id: str
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/internal/courses/{course_id}/folders/{folder_id}",
            user_id=user_id,
            course_id=course_id,
            scopes=FOLDER_READ_SCOPES,
        )

    async def update_folder(
        self,
        *,
        user_id: str,
        course_id: str,
        folder_id: str,
        revision: int,
        name: Optional[str] = None,
        parent_id: Any = UNSET,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if parent_id is not UNSET:
            body["parent_id"] = parent_id
        return await self._request(
            "PATCH",
            f"/internal/courses/{course_id}/folders/{folder_id}",
            user_id=user_id,
            course_id=course_id,
            scopes=FOLDER_WRITE_SCOPES,
            json_body=body,
            if_match=revision,
        )

    async def delete_folder(
        self, *, user_id: str, course_id: str, folder_id: str, revision: int
    ) -> dict[str, Any]:
        return await self._request(
            "DELETE",
            f"/internal/courses/{course_id}/folders/{folder_id}",
            user_id=user_id,
            course_id=course_id,
            scopes=FOLDER_WRITE_SCOPES,
            if_match=revision,
        )

    # ===== search =====

    async def search(
        self,
        *,
        user_id: str,
        course_id: str,
        query: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"q": query}
        if limit is not None:
            params["limit"] = int(limit)
        if cursor:
            params["cursor"] = cursor
        return await self._request(
            "GET",
            f"/internal/courses/{course_id}/search",
            user_id=user_id,
            course_id=course_id,
            scopes=SEARCH_READ_SCOPES,
            params=params,
        )


    # ===== editor =====

    async def apply_stage_commands(
        self,
        *,
        user_id: str,
        course_id: str,
        workspace_id: str,
        stage_id: str,
        commands: list[dict[str, Any]],
        revision: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Apply an editor command list to one stage.

        The command list (not a document) is what travels: the service applies it
        to the row it reads inside the request transaction, so an author who never
        saw a concurrent change cannot revert it. `If-Match` carries the revision
        this list was composed against.
        """
        return await self._request(
            "POST",
            f"/internal/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/commands",
            user_id=user_id,
            course_id=course_id,
            scopes=STAGE_WRITE_SCOPES,
            json_body={"commands": commands},
            idempotency_key=idempotency_key,
            if_match=revision,
        )

    async def get_stage_outline(
        self, *, user_id: str, course_id: str, workspace_id: str, stage_id: str
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/internal/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/outline",
            user_id=user_id,
            course_id=course_id,
            scopes=STAGE_READ_SCOPES,
        )

    async def get_stage_playback(
        self,
        *,
        user_id: str,
        course_id: str,
        workspace_id: str,
        stage_id: str,
        scene_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """The playable plan (renderer decisions + resume position) for one stage."""
        params = {"scene_id": scene_id} if scene_id else None
        return await self._request(
            "GET",
            f"/internal/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/playback",
            user_id=user_id,
            course_id=course_id,
            scopes=STAGE_READ_SCOPES,
            params=params,
        )

    async def get_stage_scene(
        self,
        *,
        user_id: str,
        course_id: str,
        workspace_id: str,
        stage_id: str,
        scene_id: str,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/internal/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}",
            user_id=user_id,
            course_id=course_id,
            scopes=STAGE_READ_SCOPES,
        )


    # ===== materials =====

    async def list_materials(
        self,
        *,
        user_id: str,
        course_id: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = int(limit)
        if cursor:
            params["cursor"] = cursor
        return await self._request(
            "GET",
            f"/internal/courses/{course_id}/materials",
            user_id=user_id,
            course_id=course_id,
            scopes=MATERIAL_READ_SCOPES,
            params=params or None,
        )

    async def create_material(
        self,
        *,
        user_id: str,
        course_id: str,
        filename: str,
        media_type: str,
        byte_size: int,
        sha256: str,
        extraction_status: str,
        text: str,
        content_base64: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Record one bounded intake decision, including its original bytes."""
        return await self._request(
            "POST",
            f"/internal/courses/{course_id}/materials",
            user_id=user_id,
            course_id=course_id,
            scopes=MATERIAL_WRITE_SCOPES,
            json_body={
                "filename": filename,
                "media_type": media_type,
                "byte_size": int(byte_size),
                "sha256": sha256,
                "extraction_status": extraction_status,
                "text": text,
                "content_base64": content_base64,
            },
            idempotency_key=idempotency_key,
        )

    async def get_material(
        self, *, user_id: str, course_id: str, material_id: str
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/internal/courses/{course_id}/materials/{material_id}",
            user_id=user_id,
            course_id=course_id,
            scopes=MATERIAL_READ_SCOPES,
        )

    async def delete_material(
        self, *, user_id: str, course_id: str, material_id: str, revision: int
    ) -> dict[str, Any]:
        return await self._request(
            "DELETE",
            f"/internal/courses/{course_id}/materials/{material_id}",
            user_id=user_id,
            course_id=course_id,
            scopes=MATERIAL_WRITE_SCOPES,
            if_match=revision,
        )

    async def resolve_materials(
        self, *, user_id: str, course_id: str, material_ids: list[str]
    ) -> dict[str, Any]:
        """Turn ids into authorized references, reporting the ones that did not resolve."""
        return await self._request(
            "POST",
            f"/internal/courses/{course_id}/materials/resolve",
            user_id=user_id,
            course_id=course_id,
            scopes=MATERIAL_READ_SCOPES,
            json_body={"material_ids": list(material_ids)},
        )


    # ===== `.maic.zip` 导出 / 导入 =====

    async def export_stage(
        self,
        *,
        user_id: str,
        course_id: str,
        workspace_id: str,
        stage_id: str,
    ) -> dict[str, Any]:
        """把一份 stage 导出为 `.maic.zip`（服务端以 base64 放在 JSON 信封里）。"""
        return await self._request(
            "GET",
            f"/internal/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/export",
            user_id=user_id,
            course_id=course_id,
            scopes=ARCHIVE_READ_SCOPES,
        )

    async def export_stage_format(
        self,
        *,
        user_id: str,
        course_id: str,
        workspace_id: str,
        stage_id: str,
        format: str,
    ) -> dict[str, Any]:
        """导出一个受限格式文件，内部仍使用 JSON + base64 信封。"""
        return await self._request(
            "GET",
            f"/internal/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/export/{format}",
            user_id=user_id,
            course_id=course_id,
            scopes=ARCHIVE_READ_SCOPES,
        )

    async def import_pptx(
        self,
        *,
        user_id: str,
        course_id: str,
        workspace_id: str,
        pptx_b64: str,
        title: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """把 PPTX 的结构化子集导入当前工作台。"""
        return await self._request(
            "POST",
            f"/internal/courses/{course_id}/workspaces/{workspace_id}/import/pptx",
            user_id=user_id,
            course_id=course_id,
            scopes=ARCHIVE_WRITE_SCOPES,
            json_body={"pptx": pptx_b64, "title": title},
            idempotency_key=idempotency_key,
        )

    async def import_stage(
        self,
        *,
        user_id: str,
        course_id: str,
        workspace_id: str,
        archive_b64: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """把 `.maic.zip` 导入为当前工作台里的一份新 stage。

        档案里的 workspace/course/user 只是说明文字，落点始终由本次请求的路径与
        断言决定。
        """
        return await self._request(
            "POST",
            f"/internal/courses/{course_id}/workspaces/{workspace_id}/import",
            user_id=user_id,
            course_id=course_id,
            scopes=ARCHIVE_WRITE_SCOPES,
            json_body={"archive": archive_b64},
            idempotency_key=idempotency_key,
        )

    async def export_stage_video(
        self,
        *,
        user_id: str,
        course_id: str,
        workspace_id: str,
        stage_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/internal/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/export/video",
            user_id=user_id,
            course_id=course_id,
            scopes=VIDEO_EXPORT_SCOPES,
            json_body={},
            idempotency_key=idempotency_key,
        )

    # ===== generation / jobs / provider-safe settings =====

    async def generate_stage(
        self,
        *,
        user_id: str,
        course_id: str,
        workspace_id: str,
        mode: str,
        prompt: str,
        idempotency_key: str,
        role_mode: str = "preset",
        selected_role_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/internal/courses/{course_id}/workspaces/{workspace_id}/generate",
            user_id=user_id,
            course_id=course_id,
            scopes=GENERATION_WRITE_SCOPES,
            json_body={
                "mode": mode,
                "prompt": prompt,
                "role_mode": role_mode,
                "selected_role_ids": selected_role_ids or [],
            },
            idempotency_key=idempotency_key,
        )

    async def get_job(self, *, user_id: str, course_id: str, job_id: str) -> dict[str, Any]:
        return await self._request(
            "GET", f"/internal/courses/{course_id}/jobs/{job_id}",
            user_id=user_id, course_id=course_id, scopes=JOB_READ_SCOPES,
        )

    async def cancel_job(self, *, user_id: str, course_id: str, job_id: str) -> dict[str, Any]:
        return await self._request(
            "POST", f"/internal/courses/{course_id}/jobs/{job_id}/cancel",
            user_id=user_id, course_id=course_id, scopes=JOB_CANCEL_SCOPES,
        )

    async def retry_job(self, *, user_id: str, course_id: str, job_id: str) -> dict[str, Any]:
        return await self._request(
            "POST", f"/internal/courses/{course_id}/jobs/{job_id}/retry",
            user_id=user_id, course_id=course_id, scopes=("job:write",),
        )

    async def synthesize_speech(
        self,
        *,
        user_id: str,
        course_id: str,
        text: str,
        instruction: Optional[str] = None,
        voice: Optional[str] = None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Enqueue one speech-synthesis job; the audio arrives via an artifact."""
        body: dict[str, Any] = {"text": text}
        if instruction is not None:
            body["instruction"] = instruction
        if voice is not None:
            body["voice"] = voice
        return await self._request(
            "POST", f"/internal/courses/{course_id}/tts",
            user_id=user_id, course_id=course_id, scopes=TTS_WRITE_SCOPES,
            json_body=body, idempotency_key=idempotency_key,
        )

    async def run_discussion(
        self, *, user_id: str, course_id: str, prompt: str, idempotency_key: str
    ) -> dict[str, Any]:
        """Enqueue one multi-agent round-table job; the transcript arrives via an artifact."""
        return await self._request(
            "POST", f"/internal/courses/{course_id}/discussion",
            user_id=user_id, course_id=course_id, scopes=DISCUSSION_WRITE_SCOPES,
            json_body={"prompt": prompt}, idempotency_key=idempotency_key,
        )

    async def get_scene_narration(
        self,
        *,
        user_id: str,
        course_id: str,
        workspace_id: str,
        stage_id: str,
        scene_id: str,
    ) -> dict[str, Any]:
        """Read whether one scene already has narration audio.

        The scene is addressed by id, so the answer is bound to that page: the
        service derives the script from the scene body and reports the job that
        belongs to it (or nothing). The browser therefore never has to remember
        a job/artifact id to keep audio attached to the right scene.
        """
        return await self._request(
            "GET", self._narration_path(course_id, workspace_id, stage_id, scene_id),
            user_id=user_id, course_id=course_id, scopes=NARRATION_READ_SCOPES,
        )

    async def synthesize_scene_narration(
        self,
        *,
        user_id: str,
        course_id: str,
        workspace_id: str,
        stage_id: str,
        scene_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Enqueue narration for exactly one scene.

        No text crosses this boundary: the service derives the script from the
        scene body, so the audio cannot describe something other than the page
        it is attached to.
        """
        return await self._request(
            "POST", self._narration_path(course_id, workspace_id, stage_id, scene_id),
            user_id=user_id, course_id=course_id, scopes=NARRATION_WRITE_SCOPES,
            json_body={"scene_id": scene_id, "stage_id": stage_id},
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def _narration_path(course_id: str, workspace_id: str, stage_id: str, scene_id: str) -> str:
        return (
            f"/internal/courses/{course_id}/workspaces/{workspace_id}"
            f"/stages/{stage_id}/scenes/{scene_id}/narration"
        )

    async def get_artifact(
        self, *, user_id: str, course_id: str, artifact_id: str
    ) -> dict[str, Any]:
        return await self._request(
            "GET", f"/internal/courses/{course_id}/artifacts/{artifact_id}",
            user_id=user_id, course_id=course_id, scopes=ARTIFACT_READ_SCOPES,
        )

    async def provider_status(self, *, user_id: str) -> dict[str, Any]:
        return await self._request(
            "GET", "/internal/settings/providers", user_id=user_id,
            course_id=SERVICE_SCOPE_SENTINEL, scopes=PROVIDER_STATUS_SCOPES,
        )

    async def add_whiteboard(
        self,
        *,
        user_id: str,
        course_id: str,
        workspace_id: str,
        stage_id: str,
        board: dict[str, Any],
        revision: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/internal/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/whiteboard",
            user_id=user_id, course_id=course_id, scopes=WHITEBOARD_WRITE_SCOPES,
            json_body={"board": board}, idempotency_key=idempotency_key, if_match=revision,
        )


def _safe_json(response: Any) -> Any:
    """Never let a malformed body become an exception the caller cannot classify."""
    try:
        return response.json()
    except Exception:
        return None


__all__ = [
    "MagicClassFusionClient",
    "SERVICE_SCOPE_SENTINEL",
    "ASSERTION_HEADER",
    "IDEMPOTENCY_HEADER",
    "IF_MATCH_HEADER",
    "READ_SCOPES",
    "WRITE_SCOPES",
    "FOLDER_READ_SCOPES",
    "FOLDER_WRITE_SCOPES",
    "SEARCH_READ_SCOPES",
    "STAGE_READ_SCOPES",
    "STAGE_WRITE_SCOPES",
    "MATERIAL_READ_SCOPES",
    "MATERIAL_WRITE_SCOPES",
    "ARCHIVE_READ_SCOPES",
    "ARCHIVE_WRITE_SCOPES",
    "VIDEO_EXPORT_SCOPES",
    "GENERATION_WRITE_SCOPES",
    "TTS_WRITE_SCOPES",
    "NARRATION_READ_SCOPES",
    "NARRATION_WRITE_SCOPES",
    "DISCUSSION_WRITE_SCOPES",
    "ARTIFACT_READ_SCOPES",
    "JOB_READ_SCOPES",
    "JOB_CANCEL_SCOPES",
    "PROVIDER_STATUS_SCOPES",
    "WHITEBOARD_WRITE_SCOPES",
    "UNSET",
]
