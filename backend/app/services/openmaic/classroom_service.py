"""互动课堂服务 —— 编排 OpenMAIC 客户端、课程上下文与结果持久化。

统一边界：
- 未启用(未配置 OPENMAIC_ENABLED/BASE_URL)时，status 返回"关闭"状态，
  其余能力删除抛 OpenMAICNotEnabled(503)，不影响课程详情与 CPM 基础聊天。
- 所有生成操作绑定当前用户与课程权限(在路由层通过 assert_course_access 完成)。
- 客户端断开/并发请求不重复提交：同一 user_id+course_id 通过跨进程原子预占
  (result_store.acquire_reservation) 保证只有一个提交者，其余复用同一任务，
  且复用返回的是任务**真实 mode**。
- 不向 OpenMAIC 发送任何服务端凭据/客户端 Key；访问码只在客户端内部使用。
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .client import GENERATION_STEPS, OpenMAICClient, normalize_step
from .errors import OpenMAICNotEnabled, OpenMAICProtocolError
from .requirement_builder import (
    build_input_payload,
    build_requirement,
    validate_mode,
)
from .result_store import (
    OpenMAICReservation,
    OpenMAICResultStore,
    OpenMAICSession,
    new_session_id,
)
from ...core.config import Settings

# 目标部署的真实生成步骤(见 client.GENERATION_STEPS)。这里显式列出来做护栏，
# 保证任何新增步骤都被显式评审，而不是被静默透传。
PUBLIC_STEPS = ("queued", "failed", *GENERATION_STEPS)


def _public_step(step: str, status: str = "") -> str:
    """归一化 step 到真实契约取值。"""
    normalized = normalize_step(step, status)
    return normalized if normalized in PUBLIC_STEPS else "initializing"


class OpenMAICClassroomService:
    def __init__(
        self,
        settings: Settings,
        store: OpenMAICResultStore,
        client: Optional[OpenMAICClient] = None,
    ) -> None:
        self._settings = settings
        self._store = store
        if client is None and settings.openmaic_available:
            client = OpenMAICClient(
                base_url=settings.openmaic_base_url,
                timeout_seconds=settings.openmaic_request_timeout_seconds,
                origin=settings.openmaic_origin,
                access_code=settings.openmaic_access_code,
            )
        self._client = client

    @property
    def enabled(self) -> bool:
        return self._settings.openmaic_available and self._client is not None

    @property
    def _ttl(self) -> float:
        return float(self._settings.openmaic_reservation_ttl_seconds)

    def _require_client(self) -> OpenMAICClient:
        if self._client is None or not self._settings.openmaic_available:
            raise OpenMAICNotEnabled()
        return self._client

    # ===== 状态 =====

    async def status(self) -> Dict[str, Any]:
        """返回 enabled/unavailable 契约。

        契约：
        - configured: 后端是否配置了 OpenMAIC（OPENMAIC_ENABLED + BASE_URL）。
        - available:  当前是否可用（health 可达 且 目标部署的 ACCESS_CODE 已通过）。
        - enabled:    == configured and available，供客户端决定是否展示生成入口。
        - unavailable: configured and not available（配置了但当前不可用）。
        - embed_origin: 可信的 OpenMAIC Origin（含端口），仅在 configured 时返回，
          供客户端按完整 URL.origin 精确校验课堂地址；未配置时为 null(fail-closed)。
        """
        configured = self.enabled
        origin = (self._settings.openmaic_origin or None) if configured else None
        base: Dict[str, Any] = {
            "enabled": False,
            "configured": configured,
            "available": False,
            "unavailable": False,
            "service": "openmaic",
            "version": "",
            "capabilities": {},
            "embed_origin": origin,
            "reason": None,
        }
        if not configured:
            base["reason"] = "互动课堂服务未启用"
            return base
        try:
            health = await self._require_client().health()
        except Exception:  # noqa: BLE001 - health 失败必须降级，不能影响课程详情
            base["unavailable"] = True
            base["reason"] = "互动课堂服务暂不可用"
            return base
        if health.access_code_required and not health.authenticated:
            base["unavailable"] = True
            base["reason"] = "互动课堂服务需要访问码"
            return base
        base.update(
            enabled=True,
            available=True,
            unavailable=False,
            version=health.version,
            capabilities=health.capabilities,
            reason=None,
        )
        return base

    # ===== 生成与轮询 =====

    async def _health_capabilities(self, client: OpenMAICClient) -> Dict[str, bool]:
        try:
            health = await client.health()
            return health.capabilities
        except Exception:  # noqa: BLE001
            return {}

    def _reserved_session(
        self, *, user_id: str, course_id: str, reservation: OpenMAICReservation
    ) -> Optional[OpenMAICSession]:
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
        return OpenMAICSession(
            session_id=reservation.session_id,
            course_id=course_id,
            user_id=user_id,
            mode=reservation.mode,
            job_id=reservation.job_id,
            status="queued",
            step="queued",
            progress=0,
            created_at=reservation.created_at,
            updated_at=reservation.updated_at,
        )

    def _acquire(self, *, user_id: str, course_id: str, mode: str) -> tuple[str, Optional[OpenMAICSession]]:
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
        raise OpenMAICProtocolError("互动课堂任务正在启动，请稍后重试")

    async def generate(
        self,
        *,
        user_id: str,
        course_id: str,
        course_context: str,
        mode: str,
        learning_objective: Optional[str] = None,
    ) -> OpenMAICSession:
        client = self._require_client()
        mode = validate_mode(mode)

        # 1) 跨进程原子预占：并发时只有一个请求成为提交者
        session_id, reusable = self._acquire(
            user_id=user_id, course_id=course_id, mode=mode
        )
        if reusable is not None:
            # 复用已有任务 —— 必须返回任务真实 mode，而不是本次请求的 mode
            return reusable

        # 2) 先落盘(mode 为真实 mode)，让并发落败方能读到真实 mode
        session = OpenMAICSession(
            session_id=session_id,
            course_id=course_id,
            user_id=user_id,
            mode=mode,
            status="queued",
            step="queued",
            progress=0,
            message="课堂生成任务已排队",
        )
        self._store.save(session)

        try:
            capabilities = await self._health_capabilities(client)
            requirement = build_requirement(
                course_context=course_context,
                mode=mode,
                learning_objective=learning_objective,
                enable_web_search=bool(capabilities.get("webSearch")),
                enable_image=bool(capabilities.get("imageGeneration")),
                enable_video=bool(capabilities.get("videoGeneration")),
                enable_tts=bool(capabilities.get("tts")),
            )
            payload = build_input_payload(
                requirement=requirement,
                capabilities=capabilities,
                pdf_text=course_context,
            )
            result = await client.submit(payload)
        except Exception as exc:  # noqa: BLE001 - 提交失败必须释放预占，允许重试
            session.status = "failed"
            session.step = "failed"
            session.progress = 0
            session.error = f"提交课堂生成任务失败: {type(exc).__name__}"
            session.message = "提交失败，可重试"
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

    async def poll(self, session: OpenMAICSession) -> OpenMAICSession:
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

        result = await client.poll(session.job_id)

        session.progress = result.progress
        session.message = result.message or session.message
        session.status = result.status
        session.step = _public_step(result.step, result.status)
        # 每次成功轮询都刷新 updated_at（真实契约里的 job.updatedAt 语义）
        session.updated_at = _now_iso()

        if result.status == "succeeded":
            session.progress = 100
            session.step = "completed"
            session.error = None
            if result.classroom_url:
                session.classroom_id = result.classroom_id
                session.classroom_url = result.classroom_url
                session.scenes_count = result.scenes_count
        elif result.status == "failed":
            session.progress = 100
            session.step = "failed"
            session.error = result.error or session.error or "课堂生成失败"
        else:
            # 进行中：续租，避免长时间生成被误判为过期
            self._store.touch_reservation(
                user_id=session.user_id,
                course_id=session.course_id,
                session_id=session.session_id,
            )
            session.error = result.error or None

        self._store.save(session)
        if session.is_terminal:
            self._store.release_reservation(
                user_id=session.user_id,
                course_id=session.course_id,
                session_id=session.session_id,
            )
        return session

    # ===== 查询 =====

    def get_session(self, *, user_id: str, course_id: str, session_id: str) -> Optional[OpenMAICSession]:
        return self._store.get_session(user_id=user_id, course_id=course_id, session_id=session_id)

    def list_sessions(self, *, user_id: str, course_id: str) -> List[OpenMAICSession]:
        return sorted(
            self._store.list_sessions(user_id=user_id, course_id=course_id),
            key=lambda s: s.created_at,
            reverse=True,
        )

    def list_classrooms(self, *, user_id: str, course_id: str) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for s in self.list_sessions(user_id=user_id, course_id=course_id):
            if s.status != "succeeded" or not s.classroom_url:
                continue
            out.append({
                "session_id": s.session_id,
                "classroom_id": s.classroom_id,
                "url": s.classroom_url,
                "mode": s.mode,
                "scenes_count": s.scenes_count,
                "created_at": s.created_at,
            })
        return out


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


__all__ = ["OpenMAICClassroomService", "PUBLIC_STEPS"]
