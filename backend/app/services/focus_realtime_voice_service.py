"""Focus 实时语音会话：后端生成 RTC Token 并控制 VoiceChat 生命周期。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import struct
import time
import uuid
from dataclasses import dataclass
from typing import Any

from ..core.config import Settings
from .focus_ai_service import FOCUS_AI_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class RealtimeVoiceUnavailableError(Exception):
    pass


class RealtimeVoiceProviderError(Exception):
    pass


class RealtimeVoiceSessionNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class RealtimeVoiceSession:
    session_id: str
    owner_user_id: str
    app_id: str
    room_id: str
    user_id: str
    agent_user_id: str
    token: str
    token_expires_at: int


class VolcRtcTokenIssuer:
    """官方 RTC AccessToken v001 的小型后端实现；AppKey 永不返回客户端。"""

    _VERSION = "001"
    _PUBLISH_STREAM = 0
    _PUBLISH_AUDIO = 1
    _PUBLISH_VIDEO = 2
    _PUBLISH_DATA = 3
    _SUBSCRIBE_STREAM = 4

    @staticmethod
    def _string(value: str) -> bytes:
        encoded = value.encode("utf-8")
        return struct.pack("<H", len(encoded)) + encoded

    def issue(self, *, app_id: str, app_key: str, room_id: str, user_id: str, expires_at: int) -> str:
        if len(app_id) != 24:
            raise RealtimeVoiceUnavailableError("RTC AppId 配置无效")
        privileges = {
            self._PUBLISH_STREAM: expires_at,
            self._PUBLISH_AUDIO: expires_at,
            self._PUBLISH_VIDEO: expires_at,
            self._PUBLISH_DATA: expires_at,
            self._SUBSCRIBE_STREAM: expires_at,
        }
        message = b"".join(
            (
                struct.pack("<I", secrets.randbits(32)),
                struct.pack("<I", int(time.time())),
                struct.pack("<I", expires_at),
                self._string(room_id),
                self._string(user_id),
                struct.pack("<H", len(privileges)),
                b"".join(struct.pack("<HI", key, value) for key, value in sorted(privileges.items())),
            )
        )
        signature = hmac.new(app_key.encode("utf-8"), message, hashlib.sha256).digest()
        packed = struct.pack("<H", len(message)) + message + struct.pack("<H", len(signature)) + signature
        return f"{self._VERSION}{app_id}{base64.b64encode(packed).decode('ascii')}"


class VolcengineVoiceChatClient:
    """通过官方 volcengine Python SDK 调用 RTC OpenAPI，便于在测试中替换。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _call(self, action: str, body: dict[str, Any]) -> None:
        try:
            from volcengine.ApiInfo import ApiInfo
            from volcengine.Credentials import Credentials
            from volcengine.ServiceInfo import ServiceInfo
            from volcengine.base.Service import Service
        except ImportError as exc:
            raise RealtimeVoiceUnavailableError("缺少火山引擎服务端 SDK") from exc
        credentials = Credentials(
            self._settings.volc_access_key_id,
            self._settings.volc_secret_access_key,
            "rtc",
            "cn-north-1",
        )
        service = Service(
            ServiceInfo("rtc.volcengineapi.com", {}, credentials, 5, 15, scheme="https"),
            {action: ApiInfo("POST", "/", {"Action": action, "Version": "2025-06-01"}, {}, {})},
        )
        try:
            raw = service.json(action, {}, json.dumps(body, ensure_ascii=False, separators=(",", ":")))
            response = json.loads(raw)
        except Exception as exc:  # SDK only exposes provider text; never send it to Android.
            raise RealtimeVoiceProviderError() from exc
        if response.get("ResponseMetadata", {}).get("Error"):
            raise RealtimeVoiceProviderError()

    def start(self, body: dict[str, Any]) -> None:
        self._call("StartVoiceChat", body)

    def stop(self, body: dict[str, Any]) -> None:
        self._call("StopVoiceChat", body)


class FocusRealtimeVoiceService:
    def __init__(self, settings: Settings, voice_chat: VolcengineVoiceChatClient | None = None) -> None:
        self._settings = settings
        self._voice_chat = voice_chat or VolcengineVoiceChatClient(settings)
        self._token_issuer = VolcRtcTokenIssuer()
        self._sessions: dict[str, RealtimeVoiceSession] = {}

    def _voice_chat_body(self, session: RealtimeVoiceSession) -> dict[str, Any]:
        try:
            config = json.loads(self._settings.volc_rtc_voicechat_config_json)
        except json.JSONDecodeError as exc:
            raise RealtimeVoiceUnavailableError("VoiceChat 配置不是有效 JSON") from exc
        if not isinstance(config, dict):
            raise RealtimeVoiceUnavailableError("VoiceChat 配置格式无效")
        config = json.loads(json.dumps(config))
        config.setdefault("AgentConfig", {})
        config["AgentConfig"].setdefault("UserId", session.agent_user_id)
        config["AgentConfig"]["TargetUserId"] = [session.user_id]
        config.setdefault("Config", {})
        config["Config"].setdefault("InterruptMode", 0)
        config["Config"].setdefault("LLMConfig", {})
        config["Config"]["LLMConfig"].setdefault("SystemPrompt", FOCUS_AI_SYSTEM_PROMPT)
        config.update({"AppId": session.app_id, "RoomId": session.room_id, "TaskId": session.session_id})
        return config

    def create(self, owner_user_id: str) -> RealtimeVoiceSession:
        if not self._settings.realtime_voice_available:
            raise RealtimeVoiceUnavailableError("实时语音尚未配置")
        now = int(time.time())
        expires_at = now + max(300, self._settings.volc_rtc_token_ttl_seconds)
        session_id = f"focus_voice_{uuid.uuid4().hex}"
        room_id = f"focus_{uuid.uuid4().hex}"
        user_id = f"u_{owner_user_id.replace('-', '')[:48]}"
        session = RealtimeVoiceSession(
            session_id=session_id,
            owner_user_id=owner_user_id,
            app_id=self._settings.volc_rtc_app_id,
            room_id=room_id,
            user_id=user_id,
            agent_user_id=self._settings.volc_rtc_agent_user_id,
            token=self._token_issuer.issue(
                app_id=self._settings.volc_rtc_app_id,
                app_key=self._settings.volc_rtc_app_key,
                room_id=room_id,
                user_id=user_id,
                expires_at=expires_at,
            ),
            token_expires_at=expires_at,
        )
        self._voice_chat.start(self._voice_chat_body(session))
        self._sessions[session.session_id] = session
        return session

    def stop(self, session_id: str, owner_user_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None or session.owner_user_id != owner_user_id:
            raise RealtimeVoiceSessionNotFoundError()
        try:
            self._voice_chat.stop({"AppId": session.app_id, "RoomId": session.room_id, "TaskId": session.session_id})
        finally:
            self._sessions.pop(session_id, None)
        return True


_service: FocusRealtimeVoiceService | None = None


def get_focus_realtime_voice_service() -> FocusRealtimeVoiceService:
    global _service
    if _service is None:
        from ..core.config import get_settings
        _service = FocusRealtimeVoiceService(get_settings())
    return _service


def reset_focus_realtime_voice_service_for_tests(service: FocusRealtimeVoiceService | None = None) -> None:
    global _service
    _service = service
