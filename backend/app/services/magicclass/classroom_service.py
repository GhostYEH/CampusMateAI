"""互动课堂服务 —— 编排 magicclass 客户端、课程上下文与结果持久化。

统一边界：
- 未启用(未配置 MAGICCLASS_ENABLED/BASE_URL)时，status 返回"关闭"状态，
  其余能力删除抛 magicclassNotEnabled(503)，不影响课程详情与 CPM 基础聊天。
- 所有生成操作绑定当前用户与课程权限(在路由层通过 assert_course_access 完成)。
- 客户端断开/并发请求不重复提交：同一 user_id+course_id 通过跨进程原子预占
  (result_store.acquire_reservation) 保证只有一个提交者，其余复用同一任务，
  且复用返回的是任务**真实 mode**。
- 不向 CampusMate 客户端返回任何 magicclass 凭据/Provider Key；访问码仅由后端
  magicclassClient 用于服务间认证。
"""
from __future__ import annotations

import time
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from .client import (
    GENERATION_STEPS,
    MagicClassClient,
    MagicClassProbeResult,
    normalize_step,
)
from .compatibility import (
    COMPATIBLE,
    INCOMPATIBLE,
    UNKNOWN,
    VERSION_SOURCE_UNKNOWN,
    effective_capabilities,
    is_degraded,
    resolve_compatibility,
    unavailable_capabilities,
    version_source,
)
from .composition import ClassroomComposition, parse_classroom_composition
from .errors import (
    MagicClassAuthError,
    MagicClassInvalidOrigin,
    MagicClassIncompatible,
    MagicClassNotEnabled,
    MagicClassProtocolError,
    MagicClassUnavailable,
)
from .requirement_builder import (
    GenerationRequestSnapshot,
    StudentBrief,
    build_input_payload,
    build_requirement,
    choose_adaptive_mode,
    mode_label,
    normalize_mode,
)
from .public_url import project_session_url, resolve_public_classroom_url
from .redaction import redact_public_text
from .result_store import (
    MagicClassReservation,
    MagicClassResultStore,
    MagicClassSession,
    new_session_id,
)
from ...core.config import Settings

if TYPE_CHECKING:  # 避免与 course_context 形成导入环
    from .course_context import LearningContext

# 目标部署的真实生成步骤(见 client.GENERATION_STEPS)。这里显式列出来做护栏，
# 保证任何新增步骤都被显式评审，而不是被静默透传。
PUBLIC_STEPS = ("queued", "failed", *GENERATION_STEPS)

# 探测失败时的缓存窗口(秒)：失败不长期缓存，服务恢复后能很快被重新识别
_FAILED_PROBE_TTL_SECONDS = 5.0


def _public_step(step: str, status: str = "") -> str:
    """归一化 step 到真实契约取值。"""
    normalized = normalize_step(step, status)
    return normalized if normalized in PUBLIC_STEPS else "initializing"


def _safe_mode_label(mode: Any) -> str:
    """历史数据里可能存在已下线的模式，一条旧记录不该让整个列表失败。"""
    try:
        return mode_label(mode)
    except ValueError:
        return str(mode or "").strip() or "互动课堂"


class MagicClassClassroomService:
    def __init__(
        self,
        settings: Settings,
        store: MagicClassResultStore,
        client: Optional[MagicClassClient] = None,
    ) -> None:
        self._settings = settings
        self._store = store
        if client is None and settings.magicclass_available:
            client = MagicClassClient(
                base_url=settings.magicclass_base_url,
                timeout_seconds=settings.magicclass_request_timeout_seconds,
                origin=settings.magicclass_origin,
                access_code=settings.magicclass_access_code,
                probe_timeout_seconds=settings.magicclass_health_timeout_seconds,
            )
        self._client = client
        # 契约指纹探测缓存：(过期时刻, 结果)。成功按 MAGICCLASS_PROBE_TTL_SECONDS
        # 缓存；失败只缓存很短时间，避免服务刚恢复仍被判不可用。
        self._probe_cache: Optional[tuple[float, MagicClassProbeResult]] = None

    @property
    def enabled(self) -> bool:
        return self._settings.magicclass_available and self._client is not None

    @property
    def _ttl(self) -> float:
        return float(self._settings.magicclass_reservation_ttl_seconds)

    def _require_client(self) -> MagicClassClient:
        if self._client is None or not self._settings.magicclass_available:
            raise MagicClassNotEnabled()
        return self._client

    async def _probe(self) -> MagicClassProbeResult:
        """带 TTL 缓存的契约指纹探测。"""
        ttl = float(self._settings.magicclass_probe_ttl_seconds)
        now = time.monotonic()
        cached = self._probe_cache
        if cached is not None and now < cached[0]:
            return cached[1]
        result = await self._require_client().probe()
        window = ttl if result.ok else min(ttl, _FAILED_PROBE_TTL_SECONDS)
        self._probe_cache = (now + window, result)
        return result

    def invalidate_probe_cache(self) -> None:
        self._probe_cache = None

    async def _require_compatible_client(self) -> MagicClassClient:
        """生成前的准入：未启用 / 不可达 / 访问码缺失 / 契约不兼容分别给出不同错误。"""
        client = self._require_client()
        probe = await self._probe()
        if probe.ok:
            return client
        if probe.unreachable:
            raise MagicClassUnavailable()
        if probe.access_code_required and not probe.authenticated:
            raise MagicClassAuthError()
        raise MagicClassIncompatible()

    # ===== 状态 =====

    async def status(self) -> Dict[str, Any]:
        """返回完整服务状态契约。

        契约：
        - configured: 后端是否配置了 magicclass（MAGICCLASS_ENABLED + BASE_URL）。
        - available:  目标服务**真实可达**且契约指纹通过（不因为配置非空就为真）。
        - enabled:    == configured and available，供客户端决定是否展示生成入口。
        - unavailable: 配置了但当前连不上（瞬时故障，可稍后重试）。
        - incompatible: 配置了、能连上，但接口契约/版本不匹配（部署问题，重试无用）。
        - degraded:   生成服务可用，但部分可选能力（图像/视频/TTS/搜索）不可用。
        - embed_origin: **浏览器公开 Origin**（独立子域），与内部 BASE_URL 分离；
          未配置时为 None —— 客户端 fail-closed，不渲染内嵌。
        - browser_embed_available: 学生浏览器能否安全内嵌课堂。
        """
        configured = self.enabled
        public_origin = self._settings.magicclass_public_origin or None
        base: Dict[str, Any] = {
            "enabled": False,
            "configured": configured,
            "available": False,
            "unavailable": False,
            "incompatible": False,
            "degraded": False,
            "compatibility": UNKNOWN,
            "compatibility_reason": None,
            "service": "magicclass",
            "version": "",
            "version_source": VERSION_SOURCE_UNKNOWN,
            "version_out_of_range": False,
            "capabilities": {},
            "unavailable_capabilities": [],
            "embed_origin": public_origin if configured else None,
            "browser_embed_available": False,
            "browser_embed_reason": None,
            "external_3d_available": bool(self._settings.magicclass_external_3d_available),
            "poll_interval_ms": self._settings.magicclass_poll_interval_ms,
            "poll_max_seconds": self._settings.magicclass_poll_max_seconds,
            "checked_at": _now_iso(),
            "reason": None,
        }
        if not configured:
            base["reason"] = "互动课堂服务未启用"
            return base
        try:
            probe = await self._probe()
        except Exception:  # noqa: BLE001 - status 必须安全降级，不能影响课程详情
            base["unavailable"] = True
            base["reason"] = "互动课堂服务暂不可用"
            return base

        base["version"] = probe.version
        base["version_source"] = version_source(probe.version)

        if probe.unreachable:
            base["unavailable"] = True
            base["reason"] = "互动课堂服务暂不可用"
            return base

        # 访问码问题必须在兼容性判定**之前**处理：它是部署/配置问题，
        # 不是契约不兼容，否则会把"需要访问码"误报成"版本不兼容"。
        if probe.access_code_required and not probe.authenticated:
            base["unavailable"] = True
            base["reason"] = "互动课堂服务需要访问码"
            return base

        verdict = resolve_compatibility(
            probes_ok=probe.ok,
            version=probe.version,
            allowed_versions=self._settings.magicclass_allowed_versions,
        )
        base["compatibility"] = verdict.state
        base["compatibility_reason"] = verdict.reason or None
        base["version_out_of_range"] = verdict.version_out_of_range
        if verdict.state == INCOMPATIBLE:
            base["incompatible"] = True
            base["reason"] = verdict.reason
            return base

        service_caps = probe.capabilities
        base.update(
            enabled=True,
            available=True,
            unavailable=False,
            capabilities=effective_capabilities(
                service_caps, self._settings.magicclass_capability_switches
            ),
            unavailable_capabilities=unavailable_capabilities(service_caps),
            degraded=is_degraded(service_caps),
            reason=None,
        )
        if not public_origin:
            base["browser_embed_reason"] = (
                "未配置浏览器公开 Origin(MAGICCLASS_EMBED_ORIGIN)，无法安全内嵌课堂"
            )
        elif not self._settings.magicclass_embed_enabled:
            base["browser_embed_reason"] = "已按配置关闭浏览器内嵌课堂"
        elif probe.access_code_required:
            # ACCESS_CODE cookie 只在后端 httpx 会话中；浏览器直连不会继承它。
            base["browser_embed_reason"] = (
                "目标互动课堂启用了独立访问保护，CampusMate 不会把访问码发送到浏览器。"
            )
        else:
            base["browser_embed_available"] = True
        return base

    # ===== 生成与轮询 =====

    async def _health_capabilities(self, client: MagicClassClient) -> Dict[str, bool]:
        """有效能力 = 服务端 health 声明 ∧ 运维开关（只能收紧，不能放开）。"""
        try:
            probe = await self._probe()
            return effective_capabilities(
                probe.capabilities, self._settings.magicclass_capability_switches
            )
        except Exception:  # noqa: BLE001 - 能力探测失败不阻断生成，退化为"全部关闭"
            return {}

    def _reserved_session(
        self, *, user_id: str, course_id: str, reservation: MagicClassReservation
    ) -> Optional[MagicClassSession]:
        """读取预占指向的会话；会话已终态或预占过期时返回 None(表示可以接管)。

        注意：这里不做任何阻塞等待。提交者拿到预占后会**先落盘 session 再提交**，
        因此在"预占已创建、session 尚未落盘"的极小窗口内，落败方会拿到一个
        由预占内容合成的 queued 占位会话 —— 这仍然是正确的语义(任务确实在排队)，
        且不会阻塞事件循环。
        """
        session = self._store.get_session(
            user_id=user_id, course_id=course_id, session_id=reservation.session_id
        )
        if session is not None:
            return None if session.is_terminal else session
        # 预占存在但会话文件缺失：租约未过期时视为"提交中"，返回占位会话
        if self._store.reservation_is_stale(reservation, self._ttl):
            return None
        return MagicClassSession(
            session_id=reservation.session_id,
            course_id=course_id,
            user_id=user_id,
            mode=reservation.mode,
            requested_mode=reservation.mode,
            job_id=reservation.job_id,
            status="queued",
            step="queued",
            progress=0,
            created_at=reservation.created_at,
            updated_at=reservation.updated_at,
        )

    def _acquire(self, *, user_id: str, course_id: str, mode: str) -> tuple[str, Optional[MagicClassSession]]:
        """原子预占。返回 (session_id, 需复用的会话)。

        复用会话非 None 时表示本次请求不是提交者，应直接返回该会话。
        """
        for _ in range(3):
            reservation = self._store.read_reservation(user_id=user_id, course_id=course_id)
            if reservation is not None:
                reusable = self._reserved_session(
                    user_id=user_id, course_id=course_id, reservation=reservation
                )
                if reusable is not None:
                    return reusable.session_id, reusable
                # 会话已终态 / 预占过期 —— 释放或接管
                if self._store.reservation_is_stale(reservation, self._ttl):
                    session_id = new_session_id()
                    if self._store.steal_reservation(
                        user_id=user_id,
                        course_id=course_id,
                        session_id=session_id,
                        mode=mode,
                        expected=reservation,
                    ):
                        return session_id, None
                else:
                    self._store.release_reservation(
                        user_id=user_id,
                        course_id=course_id,
                        session_id=reservation.session_id,
                    )
                continue
            session_id = new_session_id()
            if self._store.acquire_reservation(
                user_id=user_id, course_id=course_id, session_id=session_id, mode=mode
            ):
                return session_id, None
        raise MagicClassProtocolError("互动课堂任务正在启动，请稍后重试")

    async def generate(
        self,
        *,
        user_id: str,
        course_id: str,
        context: LearningContext,
        mode: str,
        brief: Optional[StudentBrief] = None,
        request_snapshot: Optional[GenerationRequestSnapshot] = None,
    ) -> MagicClassSession:
        client = await self._require_compatible_client()
        requested = normalize_mode(mode)

        # adaptive：依据**真实**上下文确定性选择形态，并保留可解释的理由
        resolved = requested
        adaptive_reason: Optional[str] = None
        if requested == "adaptive":
            signals = replace(
                context.signals,
                external_3d_available=bool(self._settings.magicclass_external_3d_available),
            )
            resolved, adaptive_reason = choose_adaptive_mode(signals)

        # 1) 跨进程原子预占：并发时只有一个请求成为提交者
        session_id, reusable = self._acquire(
            user_id=user_id, course_id=course_id, mode=resolved
        )
        if reusable is not None:
            # 复用已有任务 —— 必须返回任务真实 mode，而不是本次请求的 mode
            return reusable

        # 2) 先落盘(mode 为真实 mode)，让并发落败方能读到真实 mode
        session = MagicClassSession(
            session_id=session_id,
            course_id=course_id,
            user_id=user_id,
            mode=resolved,
            requested_mode=requested,
            adaptive_reason=adaptive_reason,
            status="queued",
            step="queued",
            progress=0,
            message="课堂生成任务已排队",
            # 快照与 session 同时落盘（且在提交上游**之前**），因此即使进程在
            # 提交过程中崩溃，retry 仍能读到完整的学生诉求。
            request_snapshot=(
                request_snapshot.to_dict() if request_snapshot is not None else None
            ),
        )
        self._store.save(session)

        try:
            capabilities = await self._health_capabilities(client)
            requirement = build_requirement(
                course_context=context.text,
                mode=resolved,
                brief=brief,
                enable_web_search=bool(capabilities.get("webSearch")),
                enable_image=bool(capabilities.get("imageGeneration")),
                enable_video=bool(capabilities.get("videoGeneration")),
                enable_tts=bool(capabilities.get("tts")),
                external_3d_available=bool(self._settings.magicclass_external_3d_available),
            )
            payload = build_input_payload(
                requirement=requirement,
                capabilities=capabilities,
                pdf_text=context.material_text or context.text,
            )
            result = await client.submit(payload)
        except Exception as exc:  # noqa: BLE001 - 提交失败必须释放预占，允许重试
            session.status = "failed"
            session.step = "failed"
            session.progress = 0
            session.error_code = _error_code_of(exc)
            session.error = f"提交课堂生成任务失败: {type(exc).__name__}"
            session.message = "提交失败，可重试"
            session.updated_at = _now_iso()
            self._store.save(session)
            self._store.release_reservation(
                user_id=user_id, course_id=course_id, session_id=session_id
            )
            raise

        session.job_id = result.job_id
        # 真实契约：提交后任务仍是 queued，step 也来自 202 响应，不臆测"已开始运行"
        session.status = result.status
        session.step = _public_step(result.step, result.status)
        session.message = "课堂生成任务已提交"
        self._store.update_reservation(
            user_id=user_id, course_id=course_id, session_id=session_id, job_id=result.job_id
        )
        self._store.save(session)
        return session

    async def poll(self, session: MagicClassSession) -> MagicClassSession:
        if session.is_terminal:
            return session
        client = self._require_client()
        if not session.job_id:
            session.status = "failed"
            session.step = "failed"
            session.error = "缺少 jobId，无法轮询"
            session.progress = 100
            session.updated_at = _now_iso()
            self._store.save(session)
            self._store.release_reservation(
                user_id=session.user_id, course_id=session.course_id, session_id=session.session_id
            )
            return session

        try:
            result = await client.poll(session.job_id)
        except (MagicClassInvalidOrigin, MagicClassProtocolError) as exc:
            # 上游返回了不可信的课堂地址（外域/端口不符/query/fragment/凭据/路径穿越）
            # 或成功响应缺少必要字段。这类结果**不能**使用，按失败收口，
            # 绝不下发地址，也不让轮询接口 502 掉。
            session.status = "failed"
            session.step = "failed"
            session.progress = 100
            session.partial = False
            session.error_code = _error_code_of(exc)
            session.error = "互动课堂返回了不可信的地址，已拒绝使用"
            session.updated_at = _now_iso()
            self._store.save(session)
            self._store.release_reservation(
                user_id=session.user_id,
                course_id=session.course_id,
                session_id=session.session_id,
            )
            return session

        before = (session.status, session.step, session.progress, session.message)
        session.progress = result.progress
        # 上游的 message / error 是**不可信自由文本**：可能包含内部地址或凭据，
        # 下发前必须脱敏。
        session.message = redact_public_text(result.message, self._settings) or session.message
        session.status = result.status
        session.step = _public_step(result.step, result.status)

        if result.status == "succeeded":
            session.progress = 100
            session.step = "completed"
            session.error = None
            session.error_code = None
            session.partial = result.partial
            # 只持久化**经过校验的 classroom_id**。公开地址是**派生值**：
            # 每次下发都由 public_url 按当前公开 Origin 现场投影，绝不落盘 ——
            # 否则公开 Origin 变更后历史记录会带着过期地址，且落盘文件会成为
            # 下一个"直接序列化原始 URL"的泄漏入口。
            # 上游返回的内部地址（result.upstream_classroom_url）同样绝不落盘。
            if result.classroom_id:
                session.classroom_id = result.classroom_id
                session.classroom_url = None
                session.scenes_count = result.scenes_count
        elif result.status == "failed":
            session.progress = 100
            session.step = "failed"
            session.partial = False
            session.error_code = "MAGICCLASS_GENERATION_FAILED"
            session.error = (
                redact_public_text(result.error, self._settings)
                or session.error
                or "课堂生成失败"
            )
        else:
            # 进行中：续租，避免长时间生成被误判为过期
            self._store.touch_reservation(
                user_id=session.user_id,
                course_id=session.course_id,
                session_id=session.session_id,
            )
            session.error = redact_public_text(result.error, self._settings) or None
            session.partial = False

        # updated_at 只在**真实进度发生变化**时前进（对应 job.updatedAt 语义），
        # 而不是每次轮询都无条件刷新 —— 否则 UI 无法用它判断"多久没有进展"。
        if (session.status, session.step, session.progress, session.message) != before:
            session.updated_at = _now_iso()

        self._store.save(session)
        if session.is_terminal:
            self._store.release_reservation(
                user_id=session.user_id,
                course_id=session.course_id,
                session_id=session.session_id,
            )
        return session

    # ===== 查询 =====

    async def composition(self, session: MagicClassSession) -> ClassroomComposition:
        """回读并统计**真实**课堂组成。

        读取失败**不**伪装成"空课堂"：返回带 `error` 的组成，由 UI 明确告知
        "内容读取失败"，而不是显示"这节课没有内容"。
        """
        external_3d = bool(self._settings.magicclass_external_3d_available)
        if not session.classroom_id:
            return ClassroomComposition(
                classroom_id="",
                external_3d_available=external_3d,
                read_at=_now_iso(),
                error="该任务还没有可读取的课堂",
            )
        try:
            payload = await self._require_client().fetch_classroom(session.classroom_id)
        except Exception as exc:  # noqa: BLE001 - 读取失败必须降级为可展示的状态
            return ClassroomComposition(
                classroom_id=session.classroom_id,
                external_3d_available=external_3d,
                read_at=_now_iso(),
                error=f"课堂内容读取失败({type(exc).__name__})",
            )
        return parse_classroom_composition(
            payload,
            classroom_id=session.classroom_id,
            external_3d_available=external_3d,
        )

    def get_session(self, *, user_id: str, course_id: str, session_id: str) -> Optional[MagicClassSession]:
        return self._store.get_session(user_id=user_id, course_id=course_id, session_id=session_id)

    def list_sessions(self, *, user_id: str, course_id: str) -> List[MagicClassSession]:
        return sorted(
            self._store.list_sessions(user_id=user_id, course_id=course_id),
            key=lambda s: s.created_at,
            reverse=True,
        )

    def list_recent(
        self,
        *,
        user_id: str,
        course_name_of: Callable[[str], Optional[str]],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """跨课程"最近内容"聚合。

        唯一职责：把**已经按权限解析过**的课程展平成一条按 `updated_at` 倒序的
        列表，让浏览器不必为每门课程各发一次历史请求。

        - `course_name_of(course_id)` 由调用方用统一课程可见性策略实现：返回
          课程名表示可见，返回 `None` 表示不可见 —— 不可见的课程**一律不出现**，
          因此不会跨课程/跨用户泄漏。
        - 只收终态成功的课堂（与 `list_classrooms` 同口径）：失败或进行中的
          任务不属于"最近内容"。
        - `limit` 由调用方夹紧上限后传入，这里再兜一次底。
        """
        if limit <= 0:
            return []
        rows: List[Dict[str, Any]] = []
        for session in self._store.list_user_sessions(user_id=user_id):
            if session.status != "succeeded":
                continue
            course_name = course_name_of(session.course_id)
            if course_name is None:
                continue
            url, reason = project_session_url(self._settings, session)
            rows.append({
                "kind": "classroom",
                "id": session.session_id,
                "course_id": session.course_id,
                "course_name": course_name,
                "title": _safe_mode_label(session.mode),
                "mode": session.mode,
                "status": session.status,
                "scenes_count": session.scenes_count,
                # 站内深链：回到课程详情的智能辅导栏目，并带上要打开的课堂。
                # 参数名与 Agent Runtime 的 `input_ref.deep_link` 保持一致。
                "href": f"/courses/{session.course_id}?tab=mentoring&session={session.session_id}",
                "classroom_url": url,
                "classroom_url_unavailable_reason": reason,
                "created_at": session.created_at,
                "updated_at": session.updated_at or session.created_at,
            })
        rows.sort(
            key=lambda row: (row["updated_at"], row["created_at"], row["id"]),
            reverse=True,
        )
        return rows[:limit]

    def list_classrooms(self, *, user_id: str, course_id: str) -> List[Dict[str, Any]]:
        """历史课堂列表。

        公开地址一律由可信 `classroom_id` **重新构造**：
        - 旧数据里存的是内部 URL → 读取时被替换成公开 URL（不做破坏性迁移）；
        - 没有可信 classroom_id → 不下发地址（但条目本身保留，便于运维排查）；
        - 未配置公开 Origin → 不下发地址，客户端显示"已生成但当前部署未开放浏览器访问"。
        """
        out: List[Dict[str, Any]] = []
        for s in self.list_sessions(user_id=user_id, course_id=course_id):
            if s.status != "succeeded":
                continue
            url, reason = project_session_url(self._settings, s)
            out.append({
                "session_id": s.session_id,
                "classroom_id": s.classroom_id,
                "url": url,
                "url_unavailable_reason": reason,
                "mode": s.mode,
                "scenes_count": s.scenes_count,
                "created_at": s.created_at,
            })
        return out


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _error_code_of(exc: BaseException) -> str:
    """把异常映射成稳定错误码，供客户端分支（不泄露内部细节）。"""
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code:
        return code
    return f"MAGICCLASS_{type(exc).__name__.upper()}"


__all__ = ["MagicClassClassroomService", "PUBLIC_STEPS", "ClassroomComposition"]
