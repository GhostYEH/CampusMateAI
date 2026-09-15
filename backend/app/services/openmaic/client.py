"""OpenMAIC HTTP 客户端。

职责边界:
- 仅负责与 OpenMAIC 服务通信(access-code 探测与校验 / health / 提交 / 轮询)。
- 所有服务端凭据只存在于后端配置,逻辑上绝不发送 OpenMAIC Provider Key。
- 对 OpenMAIC 返回的 jobId / pollUrl / classroomId / 课堂 URL 做校验,
  只有与已配置 OPENMAIC_BASE_URL Origin 完全一致的课堂 URL 才会被接受。
- 统一把超时、连接失败、401、429、5xx、无效 JSON、生成失败映射为稳定异常。

ACCESS_CODE 支持(对齐真实部署的 middleware 契约):
- `GET /api/access-code/status` 与 `POST /api/access-code/verify` 是目标部署的
  白名单接口;`ACCESS_CODE` 未配置时 status 返回 `{enabled:false}`。
- 若目标启用了 ACCESS_CODE,本客户端用后端配置的 `OPENMAIC_ACCESS_CODE`
  调 verify 换取 `openmaic_access` cookie,并在后续请求携带。
- 访问码只存在于后端配置,绝不进入任何响应体、日志或客户端。

本客户端通过注入 transport 以便在测试中用 httpx.MockTransport 模拟真实联调。
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx

from .errors import (
    OpenMAICAuthError,
    OpenMAICInvalidOrigin,
    OpenMAICProtocolError,
    OpenMAICRateLimited,
    OpenMAICServerError,
    OpenMAICUnavailable,
)

_JOB_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")
_CLASSROOM_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,192}$")

ACCESS_COOKIE_NAME = "openmaic_access"

# 目标部署 generate-classroom 真实步骤(见 lib/server/classroom-generation.ts)
GENERATION_STEPS = (
    "initializing",
    "researching",
    "generating_outlines",
    "generating_scenes",
    "generating_media",
    "generating_tts",
    "persisting",
    "completed",
)
# job 级别的 step 还可能是 queued / failed
JOB_STEP_VALUES = ("queued", "failed", *GENERATION_STEPS)
JOB_STATUS_VALUES = ("queued", "running", "succeeded", "failed")


def normalize_step(raw: Any, status: str = "") -> str:
    """把 OpenMAIC 的 step 归一化到真实契约取值。

    未知 step 不伪造:回落到与 status 一致的稳定取值。
    """
    step = str(raw or "").strip()
    if step in JOB_STEP_VALUES:
        return step
    if status == "failed":
        return "failed"
    if status == "succeeded":
        return "completed"
    if status == "queued":
        return "queued"
    return "initializing"


def normalize_status(raw: Any) -> str:
    status = str(raw or "").strip()
    return status if status in JOB_STATUS_VALUES else "running"


# ===== 结果结构(扁平 { success: true, ... } OpenMAIC 契约) =====


@dataclass
class OpenMAICHealth:
    ok: bool
    version: str = ""
    capabilities: Dict[str, bool] = field(default_factory=dict)
    # 目标部署是否启用了 ACCESS_CODE 保护
    access_code_required: bool = False
    # 我方是否已被目标部署认可(未启用 ACCESS_CODE 时恒为 True)
    authenticated: bool = True


@dataclass
class OpenMAICSubmitResult:
    job_id: str
    # 真实契约：202 响应里带 job.status / job.step，新建任务时为 queued。
    status: str = "queued"
    step: str = "queued"


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
        access_code: str = "",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._origin = origin or self._origin_from(base_url)
        self._transport = transport
        self._access_code = (access_code or "").strip()
        # 运行期状态:是否已探测过 access-code、拿到的 cookie、目标是否要求访问码
        self._access_ready = False
        self._access_cookie: Optional[str] = None
        self._access_code_required = False
        self._access_lock = asyncio.Lock()

    @staticmethod
    def _origin_from(base_url: str) -> str:
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _client(self) -> httpx.AsyncClient:
        kwargs: Dict[str, Any] = {
            "timeout": self._timeout,
            "base_url": self._base_url,
            "follow_redirects": False,
        }
        if self._access_cookie:
            kwargs["cookies"] = {ACCESS_COOKIE_NAME: self._access_cookie}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.AsyncClient(**kwargs)

    # ===== ACCESS_CODE =====

    async def _ensure_access(self, client: httpx.AsyncClient) -> None:
        """按目标部署的真实契约完成 access-code 探测/校验。

        未启用 ACCESS_CODE 的目标:status 返回 enabled=false,直接放行。
        启用但后端未配置访问码:抛 OpenMAICAuthError(不泄露任何凭据)。
        """
        if self._access_ready:
            return
        async with self._access_lock:
            if self._access_ready:
                return
            try:
                probe = await client.get("/api/access-code/status")
            except httpx.HTTPError as exc:
                raise OpenMAICUnavailable(
                    f"OpenMAIC 访问码探测失败: {type(exc).__name__}"
                ) from exc
            data: Dict[str, Any] = {}
            if probe.status_code == 200:
                try:
                    payload = probe.json()
                except (json.JSONDecodeError, ValueError):
                    payload = None
                if isinstance(payload, dict):
                    data = payload
            self._access_code_required = data.get("enabled") is True
            if not self._access_code_required:
                self._access_ready = True
                return
            if not self._access_code:
                raise OpenMAICAuthError(
                    "OpenMAIC 目标部署启用了访问码，但后端未配置 OPENMAIC_ACCESS_CODE"
                )
            try:
                verified = await client.post(
                    "/api/access-code/verify", json={"code": self._access_code}
                )
            except httpx.HTTPError as exc:
                raise OpenMAICUnavailable(
                    f"OpenMAIC 访问码校验失败: {type(exc).__name__}"
                ) from exc
            if verified.status_code != 200:
                raise OpenMAICAuthError("OpenMAIC 访问码校验未通过")
            token = verified.cookies.get(ACCESS_COOKIE_NAME)
            if token:
                self._access_cookie = token
            self._access_ready = True

    def _reset_access(self) -> None:
        """401 后作废本地 access 状态,允许重新校验一次。"""
        self._access_ready = False
        self._access_cookie = None

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
        """只接受与已配置 OpenMAIC Origin(含端口)一致、路径为 /classroom/{id} 的 URL。

        按 urlparse 比较 scheme+netloc，而不是字符串前缀，避免
        `http://host:3000` 与 `http://host:30001` 之类的前缀混淆。
        拒绝任意 Origin / javascript: / data: / file: 等，防止恶意跳转。
        """
        if raw is None:
            return None
        if not isinstance(raw, str):
            raise OpenMAICInvalidOrigin("互动课堂返回 URL 格式非法")
        parsed = urlparse(raw)
        expected = urlparse(self._origin)
        if parsed.scheme != expected.scheme or parsed.netloc != expected.netloc:
            raise OpenMAICInvalidOrigin("互动课堂返回 URL 不属于已配置服务")
        if parsed.query or parsed.fragment or parsed.params:
            raise OpenMAICInvalidOrigin("互动课堂返回 URL 携带非法参数")
        prefix = "/classroom/"
        if not parsed.path.startswith(prefix):
            raise OpenMAICInvalidOrigin("互动课堂返回 URL 路径非法")
        tail = parsed.path[len(prefix):]
        if not tail or "/" in tail or "\\" in tail or ".." in tail:
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
        response = await self._send(method, path, params=params, json_body=json_body)
        # cookie 过期时重新校验一次访问码,只重试一次,避免请求风暴。
        if response.status_code == 401 and self._access_cookie:
            self._reset_access()
            async with self._client() as client:
                await self._ensure_access(client)
            response = await self._send(method, path, params=params, json_body=json_body)

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

    async def _send(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
    ) -> httpx.Response:
        try:
            async with self._client() as client:
                await self._ensure_access(client)
                return await client.request(
                    method, path, params=params, json=json_body
                )
        except httpx.TimeoutException as exc:
            raise OpenMAICUnavailable(f"OpenMAIC 请求超时: {type(exc).__name__}") from exc
        except httpx.HTTPError as exc:
            raise OpenMAICUnavailable(f"OpenMAIC 连接失败: {type(exc).__name__}") from exc

    # ===== 对外能力 =====

    async def health(self) -> OpenMAICHealth:
        payload = await self._request("GET", "/api/health")
        capabilities = payload.get("capabilities") or {}
        if not isinstance(capabilities, dict):
            capabilities = {}
        required = self._access_code_required
        return OpenMAICHealth(
            ok=True,
            version=str(payload.get("version") or ""),
            capabilities={
                str(key): bool(value)
                for key, value in capabilities.items()
                if isinstance(value, bool)
            },
            access_code_required=required,
            authenticated=(not required) or self._access_cookie is not None,
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
        status = normalize_status(payload.get("status"))
        step = normalize_step(payload.get("step"), status)
        try:
            progress = int(payload.get("progress") or 0)
        except (TypeError, ValueError):
            progress = 0
        progress = max(0, min(100, progress))
        # 真实契约: done = status === 'succeeded' || status === 'failed'
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
        if status == "failed":
            step = "failed"
        elif status == "succeeded":
            step = "completed"
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
    "ACCESS_COOKIE_NAME",
    "GENERATION_STEPS",
    "JOB_STEP_VALUES",
    "JOB_STATUS_VALUES",
    "normalize_step",
    "normalize_status",
]
