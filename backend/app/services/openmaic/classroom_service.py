"""互动课堂服务 —— 编排 OpenMAIC 客户端、课程上下文与结果持久化。

统一边界：
- 未启用(未配置 OPENMAIC_ENABLED/BASE_URL)时，get_status 返回"关闭"状态，
  其余能力删除抛 OpenMAICNotEnabled(503)，不影响课程详情与 CPM 基础聊天。
- 所有生成操作绑定当前用户与课程权限(在路由层通过 assert_course_access 完成)。
- 客户端断开不重复提交：同一课程存在进行中任务时，后续 generate 返回既有任务。
- 不向 OpenMAIC 发送任何服务端凭据/客户端 Key。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .client import OpenMAICClient
from .errors import OpenMAICNotEnabled
from .requirement_builder import (
    build_input_payload,
    build_requirement,
    validate_mode,
)
from .result_store import OpenMAICResultStore, OpenMAICSession, new_session_id
from ...core.config import Settings

# 把 OpenMAIC 的不同"进行中"状态统一为前端可用的 step 文案
_STEP_MAP = {
    "queued": "queued",
    "analyzing": "analyzing",
    "analyze": "analyzing",
    "outline": "outlining",
    "scenes": "generating",
    "media": "media",
    "voice": "voice",
    "save": "saving",
    "saving": "saving",
    "succeeded": "done",
    "failed": "failed",
}


def _public_step(step: str) -> str:
    return _STEP_MAP.get(step or "", step or "queued")


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
            )
        self._client = client

    @property
    def enabled(self) -> bool:
        return self._settings.openmaic_available and self._client is not None

    def _require_client(self) -> OpenMAICClient:
        if self._client is None or not self._settings.openmaic_available:
            raise OpenMAICNotEnabled()
        return self._client

    async def status(self) -> Dict[str, Any]:
        """safe 状态下返回 {enabled: False, capabilities:{}}，不抛异常。"""
        if not self.enabled:
            return {
                "enabled": False,
                "service": "openmaic",
                "version": "",
                "capabilities": {},
            }
        try:
            health = await self._require_client().health()
        except Exception:
            return {
                "enabled": True,
                "service": "openmaic",
                "version": "",
                "capabilities": {},
                "unreachable": True,
            }
        return {
            "enabled": True,
            "service": "openmaic",
            "version": health.version,
            "capabilities": health.capabilities,
        }

    # ===== 生成与轮询 =====

    async def _health_capabilities(self, client: OpenMAICClient) -> Dict[str, bool]:
        try:
            health = await client.health()
            return health.capabilities
        except Exception:
            return {}

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

        # 幂等：该课程已有进行中任务则复用
        existing = self._store.active_session(user_id=user_id, course_id=course_id)
        if existing is not None:
            return existing

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
        session = OpenMAICSession(
            session_id=new_session_id(),
            course_id=course_id,
            user_id=user_id,
            mode=mode,
            job_id=result.job_id,
            status="queued",
            step="queued",
            progress=0,
        )
        self._store.save(session)
        return session

    async def poll(
        self, session: OpenMAICSession
    ) -> OpenMAICSession:
        if session.status in ("succeeded", "failed"):
            return session
        client = self._require_client()
        if not session.job_id:
            session.status = "failed"
            session.step = "failed"
            session.error = "缺少 jobId，无法轮询"
            session.progress = 100
            self._store.save(session)
            return session
        result = await client.poll(session.job_id)
        session.progress = result.progress
        session.message = result.message or ""
        session.step = _public_step(result.step)
        if result.status in ("succeeded", "failed") or session.step == "done":
            session.status = result.status
            session.step = "done" if result.status == "succeeded" else "failed"
            if result.classroom_url:
                session.classroom_id = result.classroom_id
                session.classroom_url = result.classroom_url
                session.scenes_count = result.scenes_count
            if result.status == "succeeded":
                session.progress = 100
            session.updated_at = datetime.now(timezone.utc).isoformat()
        elif result.error:
            # 任务级失败信息透传(不含敏感内容)
            session.status = "failed"
            session.step = "failed"
            session.error = result.error
            session.progress = 100
        self._store.save(session)
        return session

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


__all__ = ["OpenMAICClassroomService"]