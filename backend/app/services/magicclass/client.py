"""magicclass HTTP 客户端。

职责边界:
- 仅负责与 magicclass 服务通信(access-code 探测与校验 / health / 提交 / 轮询)。
- 所有服务端凭据只存在于后端配置,逻辑上绝不发送 magicclass Provider Key。
- 对 magicclass 返回的 jobId / pollUrl / classroomId / 课堂 URL 做校验,
  只有与已配置 MAGICCLASS_BASE_URL Origin 完全一致的课堂 URL 才会被接受。
- 统一把超时、连接失败、401、429、5xx、无效 JSON、生成失败映射为稳定异常。

ACCESS_CODE 支持(对齐真实部署的 middleware 契约):
- `GET /api/access-code/status` 与 `POST /api/access-code/verify` 是目标部署的
  白名单接口;`ACCESS_CODE` 未配置时 status 返回 `{enabled:false}`。
- 若目标启用了 ACCESS_CODE,本客户端用后端配置的 `MAGICCLASS_ACCESS_CODE`
  调 verify 换取 `magicclass_access` cookie,并在后续请求携带。
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
    MagicClassAuthError,
    MagicClassInvalidOrigin,
    MagicClassProtocolError,
    MagicClassRateLimited,
    MagicClassServerError,
    MagicClassUnavailable,
)

_JOB_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")
_CLASSROOM_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,192}$")

ACCESS_COOKIE_NAME = "magicclass_access"

# 契约指纹探针使用的 jobId：格式合法(isValidClassroomJobId = /^[a-zA-Z0-9_-]+$/)
# 但必然不存在，因此目标服务会走"job not found"分支返回 404 —— 这是在不创建
# 任何生成任务、不产生任何成本的前提下证明作业族存在与语义稳定的最稳办法。
PROBE_JOB_ID = "__probe__"

# 契约指纹包含的三个只读探针
PROBE_CHECKS = ("health", "access_code", "generate_classroom")

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
    """把 magic class 的 step 归一化到真实契约取值。

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


def _optional_int(raw: Any) -> Optional[int]:
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


# ===== 结果结构(扁平 { success: true, ... } magic class 契约) =====


@dataclass
class MagicClassHealth:
    ok: bool
    version: str = ""
    capabilities: Dict[str, bool] = field(default_factory=dict)
    # 目标部署是否启用了 ACCESS_CODE 保护
    access_code_required: bool = False
    # 我方是否已被目标部署认可(未启用 ACCESS_CODE 时恒为 True)
    authenticated: bool = True


@dataclass
class MagicClassSubmitResult:
    job_id: str
    # 真实契约：202 响应里带 job.status / job.step，新建任务时为 queued。
    status: str = "queued"
    step: str = "queued"


@dataclass
class MagicClassPollResult:
    status: str
    step: str = "queued"
    progress: int = 0
    message: str = ""
    done: bool = False
    error: Optional[str] = None
    classroom_id: Optional[str] = None
    # **仅内部**：上游返回并已通过内部 Origin 校验的地址。
    # 绝不允许持久化或下发给客户端 —— 公开地址由 public_url 模块按公开 Origin 现场构造。
    upstream_classroom_url: Optional[str] = None
    scenes_count: Optional[int] = None
    # 真实进度计数（用于判断"部分完成"：succeeded 但产出少于预期）
    scenes_generated: Optional[int] = None
    total_scenes: Optional[int] = None

    @property
    def partial(self) -> bool:
        return bool(
            self.status == "succeeded"
            and self.total_scenes is not None
            and self.scenes_generated is not None
            and self.scenes_generated < self.total_scenes
        )


@dataclass
class MagicClassProbeResult:
    """契约指纹探测结果。**不抛异常**：探测失败也要能安全降级为状态。"""

    ok: bool
    version: str = ""
    capabilities: Dict[str, bool] = field(default_factory=dict)
    access_code_required: bool = False
    authenticated: bool = True
    checks: Dict[str, bool] = field(default_factory=dict)
    failed_check: Optional[str] = None
    # 服务不可达（连接失败/超时），与"契约不兼容"是两回事
    unreachable: bool = False
    reason: str = ""


class MagicClassClient:
    """magicclass /api 客户端。非启用状态下不应调用(由上层拦截)。"""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 30.0,
        origin: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        access_code: str = "",
        probe_timeout_seconds: Optional[float] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        # 探测用更短的超时：健康检查不能拖慢课程详情页
        self._probe_timeout = (
            timeout_seconds if probe_timeout_seconds is None else probe_timeout_seconds
        )
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

    def _client(self, timeout: Optional[float] = None) -> httpx.AsyncClient:
        kwargs: Dict[str, Any] = {
            "timeout": self._timeout if timeout is None else timeout,
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
        启用但后端未配置访问码:抛 magicclassAuthError(不泄露任何凭据)。
        """
        if self._access_ready:
            return
        async with self._access_lock:
            if self._access_ready:
                return
            try:
                probe = await client.get("/api/access-code/status")
            except httpx.HTTPError as exc:
                raise MagicClassUnavailable(
                    f"magic class 访问码探测失败: {type(exc).__name__}"
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
                raise MagicClassAuthError(
                    "magic class 目标部署启用了访问码，但后端未配置 MAGICCLASS_ACCESS_CODE"
                )
            try:
                verified = await client.post(
                    "/api/access-code/verify", json={"code": self._access_code}
                )
            except httpx.HTTPError as exc:
                raise MagicClassUnavailable(
                    f"magic class 访问码校验失败: {type(exc).__name__}"
                ) from exc
            if verified.status_code != 200:
                raise MagicClassAuthError("magic class 访问码校验未通过")
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
    def _validate_magicclass_job_id(raw: Any) -> str:
        if not isinstance(raw, str) or not _JOB_ID_RE.match(raw):
            raise MagicClassProtocolError("magic class 返回的 jobId 无效")
        return raw

    @staticmethod
    def _validate_classroom_id(raw: Any) -> Optional[str]:
        if raw is None:
            return None
        if not isinstance(raw, str) or not _CLASSROOM_ID_RE.match(raw):
            raise MagicClassProtocolError("magic class 返回的 classroomId 无效")
        return raw

    def _validate_classroom_url(
        self, raw: Any, classroom_id: Optional[str]
    ) -> Optional[str]:
        """只接受与已配置 magicclass Origin(含端口)一致、路径为 /classroom/{id} 的 URL。

        按 urlparse 比较 scheme+netloc，而不是字符串前缀，避免
        `http://host:3000` 与 `http://host:30001` 之类的前缀混淆。
        拒绝任意 Origin / javascript: / data: / file: 等，防止恶意跳转。
        """
        if raw is None:
            return None
        if not isinstance(raw, str):
            raise MagicClassInvalidOrigin("互动课堂返回 URL 格式非法")
        parsed = urlparse(raw)
        expected = urlparse(self._origin)
        if parsed.scheme != expected.scheme or parsed.netloc != expected.netloc:
            raise MagicClassInvalidOrigin("互动课堂返回 URL 不属于已配置服务")
        if parsed.query or parsed.fragment or parsed.params:
            raise MagicClassInvalidOrigin("互动课堂返回 URL 携带非法参数")
        prefix = "/classroom/"
        if not parsed.path.startswith(prefix):
            raise MagicClassInvalidOrigin("互动课堂返回 URL 路径非法")
        tail = parsed.path[len(prefix):]
        if not tail or "/" in tail or "\\" in tail or ".." in tail:
            raise MagicClassInvalidOrigin("互动课堂返回 URL 路径非法")
        if classroom_id is not None and tail != classroom_id:
            raise MagicClassInvalidOrigin("互动课堂返回 URL 与课堂 ID 不一致")
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
            raise MagicClassAuthError("magic class 鉴权失败")
        if response.status_code == 403:
            raise MagicClassAuthError("magic class 拒绝访问")
        if response.status_code == 429:
            raise MagicClassRateLimited()
        if response.status_code >= 500:
            raise MagicClassServerError(f"magic class 返回 HTTP {response.status_code}")
        if response.status_code not in (200, 201, 202):
            raise MagicClassProtocolError(f"magic class 返回意外 HTTP {response.status_code}")

        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise MagicClassProtocolError("magic class 返回了无效 JSON") from exc
        if not isinstance(payload, dict):
            raise MagicClassProtocolError("magic class 返回结构异常")
        if payload.get("success") is not True:
            err = payload.get("error") or payload.get("errorCode") or "未知错误"
            raise MagicClassProtocolError(f"magic class 返回失败: {str(err)[:200]}")
        return payload

    async def _send(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
        timeout: Optional[float] = None,
    ) -> httpx.Response:
        try:
            async with self._client(timeout=timeout) as client:
                await self._ensure_access(client)
                return await client.request(
                    method, path, params=params, json=json_body
                )
        except httpx.TimeoutException as exc:
            raise MagicClassUnavailable(f"magic class 请求超时: {type(exc).__name__}") from exc
        except httpx.HTTPError as exc:
            raise MagicClassUnavailable(f"magic class 连接失败: {type(exc).__name__}") from exc

    # ===== 契约指纹（只读、零成本、无副作用）=====

    async def _raw_get(self, path: str, *, timeout: Optional[float] = None) -> httpx.Response:
        """不做状态码判定的 GET —— 探针需要区分 404/400/200，不能复用 `_request`。"""
        try:
            async with self._client(timeout=timeout) as client:
                await self._ensure_access(client)
                return await client.get(path)
        except httpx.TimeoutException as exc:
            raise MagicClassUnavailable(f"magic class 请求超时: {type(exc).__name__}") from exc
        except httpx.HTTPError as exc:
            raise MagicClassUnavailable(f"magic class 连接失败: {type(exc).__name__}") from exc

    @staticmethod
    def _json_dict(response: httpx.Response) -> Optional[Dict[str, Any]]:
        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError):
            return None
        return payload if isinstance(payload, dict) else None

    async def probe(self) -> MagicClassProbeResult:
        """用三个只读探针判断目标部署的契约是否与预期一致。

        依据（对参考实现源码核对）：
        - P1 `GET /api/health`：`apiSuccess({status:'ok', version, capabilities})`
          → 必须 200 且带 `success:true`、`status:'ok'`、`capabilities` 为对象。
        - P2 `GET /api/access-code/status`：`apiSuccess({enabled, authenticated})`
          → 必须 200 且 `enabled` 是布尔。
        - P3 `GET /api/generate-classroom/{不存在的合法 id}`：作业族存在时返回
          404 `INVALID_REQUEST` + "Classroom generation job not found"。
          **不会创建任何任务**，是本设计里唯一能零成本验证作业族的办法。

        绝不抛异常：不可达 → `unreachable=True`；契约不符 → `failed_check` 指出哪一项。
        """
        result = MagicClassProbeResult(ok=False, checks={name: False for name in PROBE_CHECKS})
        try:
            health_response = await self._raw_get("/api/health", timeout=self._probe_timeout)
        except MagicClassAuthError:
            result.failed_check = "access_code"
            result.access_code_required = True
            result.authenticated = False
            result.reason = "目标服务启用了访问码，但后端未配置 MAGICCLASS_ACCESS_CODE"
            return result
        except MagicClassUnavailable as exc:
            result.unreachable = True
            result.reason = f"互动课堂服务不可达: {type(exc).__name__}"
            return result
        result.checks["health"] = self._check_health(health_response, result)

        try:
            access_response = await self._raw_get(
                "/api/access-code/status", timeout=self._probe_timeout
            )
        except MagicClassUnavailable as exc:
            result.unreachable = True
            result.reason = f"互动课堂服务不可达: {type(exc).__name__}"
            return result
        result.checks["access_code"] = self._check_access_code(access_response, result)

        if result.access_code_required and not result.authenticated:
            result.failed_check = "access_code"
            result.reason = "目标服务启用了访问码，但后端未配置 MAGICCLASS_ACCESS_CODE"
            return result

        try:
            job_response = await self._raw_get(
                f"/api/generate-classroom/{PROBE_JOB_ID}", timeout=self._probe_timeout
            )
        except MagicClassUnavailable as exc:
            result.unreachable = True
            result.reason = f"互动课堂服务不可达: {type(exc).__name__}"
            return result
        result.checks["generate_classroom"] = self._check_generate_family(job_response)

        for name in PROBE_CHECKS:
            if not result.checks[name]:
                result.failed_check = name
                result.reason = result.reason or f"契约探针 {name} 不通过"
                return result
        result.ok = True
        return result

    @staticmethod
    def _check_health(response: httpx.Response, result: "MagicClassProbeResult") -> bool:
        if response.status_code != 200:
            return False
        payload = MagicClassClient._json_dict(response)
        if payload is None or payload.get("success") is not True:
            return False
        if payload.get("status") != "ok":
            return False
        capabilities = payload.get("capabilities")
        if not isinstance(capabilities, dict):
            return False
        result.version = str(payload.get("version") or "")
        result.capabilities = {
            str(key): bool(value)
            for key, value in capabilities.items()
            if isinstance(value, bool)
        }
        return True

    @staticmethod
    def _check_access_code(response: httpx.Response, result: "MagicClassProbeResult") -> bool:
        if response.status_code != 200:
            return False
        payload = MagicClassClient._json_dict(response)
        if payload is None or payload.get("success") is not True:
            return False
        enabled = payload.get("enabled")
        if not isinstance(enabled, bool):
            return False
        result.access_code_required = enabled
        if enabled:
            result.authenticated = bool(payload.get("authenticated"))
        else:
            result.authenticated = True
        return True

    @staticmethod
    def _check_generate_family(response: httpx.Response) -> bool:
        """作业族存在性：未知但格式合法的 jobId 必须返回 404 + INVALID_REQUEST。"""
        if response.status_code != 404:
            return False
        payload = MagicClassClient._json_dict(response)
        if payload is None or payload.get("success") is not False:
            return False
        if payload.get("errorCode") != "INVALID_REQUEST":
            return False
        return "not found" in str(payload.get("error") or "").lower()

    # ===== 对外能力 =====

    async def health(self) -> MagicClassHealth:
        payload = await self._request("GET", "/api/health")
        capabilities = payload.get("capabilities") or {}
        if not isinstance(capabilities, dict):
            capabilities = {}
        required = self._access_code_required
        return MagicClassHealth(
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

    async def submit(self, input_payload: dict) -> MagicClassSubmitResult:
        payload = await self._request(
            "POST",
            "/api/generate-classroom",
            json_body=input_payload,
        )
        job_id = self._validate_magicclass_job_id(payload.get("jobId"))
        # 真实契约：202 响应里带 status / step，新建任务时为 queued。
        # 字段**缺失**时按真实契约的取值 queued 处理，而不是走 normalize_status 的
        # "running" 兜底 —— 新建任务不可能是 running，那是臆测。
        raw_status = payload.get("status")
        raw_step = payload.get("step")
        status = normalize_status(raw_status) if raw_status is not None else "queued"
        step = normalize_step(raw_step, status) if raw_step is not None else "queued"
        return MagicClassSubmitResult(job_id=job_id, status=status, step=step)

    async def fetch_classroom(self, classroom_id: str) -> Dict[str, Any]:
        """只读回读课堂文档（用于如实统计真实组成）。

        端点：`GET /api/classroom?id={classroomId}`，返回
        `{success:true, classroom:{id, stage, scenes[], createdAt}}`。
        """
        validated = self._validate_classroom_id(classroom_id)
        if validated is None:
            raise MagicClassProtocolError("课堂 ID 无效")
        return await self._request("GET", "/api/classroom", params={"id": validated})

    async def poll(self, job_id: str) -> MagicClassPollResult:
        validated = self._validate_magicclass_job_id(job_id)
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
        if status == "succeeded":
            if not isinstance(result, dict):
                raise MagicClassProtocolError("magic class 成功响应缺少课堂结果")
            classroom_id = self._validate_classroom_id(result.get("classroomId"))
            classroom_url = self._validate_classroom_url(
                result.get("url"), classroom_id
            )
            if classroom_id is None or classroom_url is None:
                raise MagicClassProtocolError("magic class 成功响应缺少课堂 ID 或地址")
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
        return MagicClassPollResult(
            status=status,
            step=step,
            progress=progress,
            message=str(payload.get("message") or ""),
            done=done,
            error=error,
            classroom_id=classroom_id,
            upstream_classroom_url=classroom_url,
            scenes_count=scenes_count,
            scenes_generated=_optional_int(payload.get("scenesGenerated")),
            total_scenes=_optional_int(payload.get("totalScenes")),
        )


__all__ = [
    "MagicClassClient",
    "MagicClassHealth",
    "MagicClassProbeResult",
    "MagicClassSubmitResult",
    "MagicClassPollResult",
    "ACCESS_COOKIE_NAME",
    "PROBE_JOB_ID",
    "PROBE_CHECKS",
    "GENERATION_STEPS",
    "JOB_STEP_VALUES",
    "JOB_STATUS_VALUES",
    "normalize_step",
    "normalize_status",
]
