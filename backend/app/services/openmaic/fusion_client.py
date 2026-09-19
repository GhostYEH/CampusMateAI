"""FastAPI client for the repository-managed OpenMAIC service.

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

from ...schemas.openmaic_fusion import FusionState, FusionStatus
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


class OpenMAICFusionClient:
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
            raise FusionUnavailable()
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
            raise FusionUnavailable() from exc

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


def _safe_json(response: Any) -> Any:
    """Never let a malformed body become an exception the caller cannot classify."""
    try:
        return response.json()
    except Exception:
        return None


__all__ = [
    "OpenMAICFusionClient",
    "SERVICE_SCOPE_SENTINEL",
    "ASSERTION_HEADER",
    "IDEMPOTENCY_HEADER",
    "IF_MATCH_HEADER",
    "READ_SCOPES",
    "WRITE_SCOPES",
    "FOLDER_READ_SCOPES",
    "FOLDER_WRITE_SCOPES",
    "SEARCH_READ_SCOPES",
    "UNSET",
]
