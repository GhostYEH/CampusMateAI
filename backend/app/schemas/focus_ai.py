"""Focus AI 学习陪伴员的最小文本请求契约。"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class FocusAiAskRequest(BaseModel):
    """来自 Android ASR 的用户主动提问；当前版本没有视觉或会话上下文。"""

    text: str = Field(..., min_length=1, max_length=800)

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("问题不能为空")
        return normalized


class FocusAiAskResponse(BaseModel):
    answer: str


class FocusRealtimeVoiceSessionResponse(BaseModel):
    session_id: str
    app_id: str
    room_id: str
    user_id: str
    agent_user_id: str
    token: str
    token_expires_at: int


class FocusRealtimeVoiceStopResponse(BaseModel):
    session_id: str
    stopped: bool

__all__ = [
    "FocusAiAskRequest",
    "FocusAiAskResponse",
    "FocusRealtimeVoiceSessionResponse",
    "FocusRealtimeVoiceStopResponse",
]
