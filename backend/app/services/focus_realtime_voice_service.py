"""Focus Seeduplex realtime session control plane.

The Android client never receives the upstream API key: it connects only to the
CampusMate relay WebSocket after an authenticated REST session creation.
"""
from __future__ import annotations

import logging
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


class FocusRealtimeVoiceService:
    """In-memory, per-process session ownership for the Seeduplex relay."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._sessions: dict[str, RealtimeVoiceSession] = {}

    def create(self, owner_user_id: str) -> RealtimeVoiceSession:
        if not self._settings.realtime_voice_available:
            raise RealtimeVoiceUnavailableError("实时语音尚未配置")
        session = RealtimeVoiceSession(
            session_id=f"focus_voice_{uuid.uuid4().hex}",
            owner_user_id=owner_user_id,
        )
        self._sessions[session.session_id] = session
        logger.info("seeduplex_session_create session=%s", session.session_id)
        return session

    def stop(self, session_id: str, owner_user_id: str) -> bool:
        if not self.owns(session_id, owner_user_id):
            raise RealtimeVoiceSessionNotFoundError()
        self._sessions.pop(session_id, None)
        return True

    def owns(self, session_id: str, owner_user_id: str) -> bool:
        session = self._sessions.get(session_id)
        return session is not None and session.owner_user_id == owner_user_id

    @property
    def seeduplex_url(self) -> str:
        return self._settings.volc_seeduplex_ws_url

    @property
    def seeduplex_api_key(self) -> str:
        return self._settings.volc_seeduplex_api_key

    @staticmethod
    def session_create_event() -> dict[str, Any]:
        """Request raw PCM output so the Android relay can play each binary frame directly."""
        return {
            "type": "session.create",
            "session": {
                "type": "realtime",
                "model": "1.2.6.1",
                "instructions": FOCUS_AI_SYSTEM_PROMPT,
                "audio": {
                    "input": {
                        "format": "pcm",
                        "sample_rate": 16000,
                        "channels": 1,
                        "bits": 16,
                    },
                    "output": {
                        "format": "pcm",
                        "sample_rate": 24000,
                        "channels": 1,
                        "bits": 16,
                    },
                },
            },
        }


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
