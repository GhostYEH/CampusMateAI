"""OpenMAIC HTTP 客户端。

职责边界:
- 仅负责与 OpenMAIC 服务通信(health / 提交 / 轮询)。
- 所有服务端凭据只存在于后端配置,逻辑上绝不发送 OpenMAIC Provider Key。
- 对 OpenMAIC 返回的 jobId / pollUrl / classroomId / 课堂 URL 做校验,
  只有与已配置 OPENMAIC_BASE_URL Origin 完全一致的课堂 URL 才会被接受。
- 统一把超时、连接失败、401、429、5xx、无效 JSON、生成失败映射为稳定异常。

本客户端通过注入 transport 以便在测试中用 httpx.MockTransport 模拟真实联调。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from .errors import (
    OpenMAICAuthError,
    OpenMAICGenerationFailed,
    OpenMAICInvalidOrigin,
    OpenMAICProtocolError,
    OpenMAICRateLimited,
    OpenMAICServerError,
    OpenMAICUnavailable,
)

_JOB_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")
_CLASSROOM_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,192}$")


# ===== 结果结构(扁平 { success: true, ... } OpenMAIC 契约) =====


@dataclass
class OpenMAICHealth:
    ok: bool
    version: str = ""
    capabilities: Dict[str, bool] = None  # type: ignore[assignment]


@dataclass
class OpenMAICSubmitResult:
    job_id: str


@dataclass
class OpenMAICPollResult:
    status: str
    step: str = "queued"
    progress: int = 0
    message: str = ""
    done: bool = False
    error: Optional[str] = None
    classroom_id: Optional[str] = None
    classroom_url: Optional[str] = None
    scenes_count: Optional[int] = None


class OpenMAICClient:
    """OpenMAIC /api 客户端。非启用状态下不应调用(由上层拦截)。"""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 30.0,
        origin: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._origin = origin or self._origin_from(base_url)
        self._transport = transport

    @staticmethod
    def _origin_from(base_url: str) -> str:
        from urllib.parse import urlparse

        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _client(self) -> httpx.AsyncClient:
        kwargs: Dict[str, Any] = {
            "timeout": self._timeout,
            "base_url": self._base_url,
            "follow_redirects": False,
        }
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.AsyncClient(**kwargs)

    # ===== 校验辅助 =====

    @staticmethod
    def _validate_openmaic_job_id(raw: Any) -> str:
        if not isinstance(raw, str) or not _JOB_ID_RE.match(raw):
            raise OpenMAICProtocolError("OpenMAIC 返回的 jobId 无效")
        return raw

    @staticmethod
    def _validate_classroom_id(raw: Any) -> Optional[str]:
        if raw is None:
            return None
        if not isinstance(raw, str) or not _CLASSROOM_ID_RE.match(raw):
            raise OpenMAICProtocolError("OpenMAIC 返回的 classroomId 无效")
        return raw

    def _validate_classroom_url(
        self, raw: Any, classroom_id: Optional[str]
    ) -> Optional[str]:
        """只接受与已配置 OpenMAIC Origin 一致、且路径为 /classroom/{id} 的 URL。

        拒绝任意 Origin / javascript: / data: / file: 等，防止恶意跳转。
        """
        if raw is None:
            return None
        if not isinstance(raw, str):
            raise OpenMAICInvalidOrigin("互动课堂返回 URL 格式非法")
        prefix = f"{self._origin}/classroom/"
        if not raw.startswith(prefix):
            raise OpenMAICInvalidOrigin("互动课堂返回 URL 不属于已配置服务")
        tail = raw[len(prefix):]
        if not tail or any(ch in tail for ch in ("?", "#", "/", "..", "\\")):
            raise OpenMAICInvalidOrigin("互动课堂返回 URL 路径非法")
        if classroom_id is not None and tail != classroom_id:
            raise OpenMAICInvalidOrigin("互动课堂返回 URL 与课堂 ID 不一致")
        return raw

    # ===== 请求执行 =====

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
    ) -> Dict[str, Any]:
        try:
            async with self._client() as client:
                response = await client.request(
                    method, path, params=params, json=json_body
                )
        except httpx.TimeoutException as exc:
            raise OpenMAICUnavailable(f"OpenMAIC 请求超时: {type(exc).__name__}") from exc
        except httpx.HTTPError as exc:
            raise OpenMAICUnavailable(f"OpenMAIC 连接失败: {type(exc).__name__}") from exc

        if response.status_code == 401:
            raise OpenMAICAuthError("OpenMAIC 鉴权失败")
        if response.status_code == 403:
            raise OpenMAICAuthError("OpenMAIC 拒绝访问")
        if response.status_code == 429:
            raise OpenMAICRateLimited()
        if response.status_code >= 500:
            raise OpenMAICServerError(f"OpenMAIC 返回 HTTP {response.status_code}")
        if response.status_code not in (200, 201, 202):
            raise OpenMAICProtocolError(f"OpenMAIC 返回意外 HTTP {response.status_code}")

        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise OpenMAICProtocolError("OpenMAIC 返回了无效 JSON") from exc
        if not isinstance(payload, dict):
            raise OpenMAICProtocolError("OpenMAIC 返回结构异常")
        if payload.get("success") is not True:
            err = payload.get("error") or payload.get("errorCode") or "未知错误"
            raise OpenMAICProtocolError(f"OpenMAIC 返回失败: {str(err)[:200]}")
        return payload

    # ===== 对外能力 =====

    async def health(self) -> OpenMAICHealth:
        payload = await self._request("GET", "/api/health")
        capabilities = payload.get("capabilities") or {}
        if not isinstance(capabilities, dict):
            capabilities = {}
        return OpenMAICHealth(
            ok=True,
            version=str(payload.get("version") or ""),
            capabilities={
                str(key): bool(value)
                for key, value in capabilities.items()
                if isinstance(value, bool)
            },
        )

    async def submit(self, input_payload: dict) -> OpenMAICSubmitResult:
        payload = await self._request(
            "POST",
            "/api/generate-classroom",
            json_body=input_payload,
        )
        job_id = self._validate_openmaic_job_id(payload.get("jobId"))
        return OpenMAICSubmitResult(job_id=job_id)

    async def poll(self, job_id: str) -> OpenMAICPollResult:
        validated = self._validate_openmaic_job_id(job_id)
        payload = await self._request("GET", f"/api/generate-classroom/{validated}")
        status = str(payload.get("status") or "running")
        step = str(payload.get("step") or "running")
        try:
            progress = int(payload.get("progress") or 0)
        except (TypeError, ValueError):
            progress = 0
        done = bool(payload.get("done")) or status in ("succeeded", "failed")
        result = payload.get("result")
        classroom_id: Optional[str] = None
        classroom_url: Optional[str] = None
        scenes_count: Optional[int] = None
        if status == "succeeded" and isinstance(result, dict):
            classroom_id = self._validate_classroom_id(result.get("classroomId"))
            classroom_url = self._validate_classroom_url(
                result.get("url"), classroom_id
            )
            try:
                scenes_count = (
                    int(result.get("scenesCount"))
                    if result.get("scenesCount") is not None
                    else None
                )
            except (TypeError, ValueError):
                scenes_count = None
        error = payload.get("error")
        if isinstance(error, dict):
            error = str(error.get("message") or error.get("error") or error)
        elif error is not None:
            error = str(error)
        return OpenMAICPollResult(
            status=status,
            step=step,
            progress=progress,
            message=str(payload.get("message") or ""),
            done=done,
            error=error,
            classroom_id=classroom_id,
            classroom_url=classroom_url,
            scenes_count=scenes_count,
        )


__all__ = [
    "OpenMAICClient",
    "OpenMAICHealth",
    "OpenMAICSubmitResult",
    "OpenMAICPollResult",
]