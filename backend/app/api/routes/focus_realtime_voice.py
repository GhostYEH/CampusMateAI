"""已认证的 Focus RTC 实时语音会话接口。"""
from fastapi import APIRouter, Depends, HTTPException, status

from ...models.multi_role import UserRow
from ...schemas.focus_ai import FocusRealtimeVoiceSessionResponse, FocusRealtimeVoiceStopResponse
from ...services.focus_realtime_voice_service import (
    FocusRealtimeVoiceService,
    RealtimeVoiceProviderError,
    RealtimeVoiceSessionNotFoundError,
    RealtimeVoiceUnavailableError,
    get_focus_realtime_voice_service,
)
from ..deps import current_user

router = APIRouter(prefix="/focus/realtime-voice")


@router.post("/sessions", response_model=FocusRealtimeVoiceSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(user: UserRow = Depends(current_user)) -> FocusRealtimeVoiceSessionResponse:
    try:
        session = get_focus_realtime_voice_service().create(user.id)
    except RealtimeVoiceUnavailableError:
        raise HTTPException(status_code=503, detail="实时语音服务尚未配置，请稍后再试。")
    except RealtimeVoiceProviderError:
        raise HTTPException(status_code=502, detail="实时语音服务暂时不可用，请稍后再试。")
    return FocusRealtimeVoiceSessionResponse(**session.__dict__)


@router.delete("/sessions/{session_id}", response_model=FocusRealtimeVoiceStopResponse)
def stop_session(session_id: str, user: UserRow = Depends(current_user)) -> FocusRealtimeVoiceStopResponse:
    try:
        stopped = get_focus_realtime_voice_service().stop(session_id, user.id)
    except RealtimeVoiceSessionNotFoundError:
        raise HTTPException(status_code=404, detail="实时语音会话不存在。")
    except RealtimeVoiceProviderError:
        raise HTTPException(status_code=502, detail="实时语音会话关闭失败，请稍后重试。")
    return FocusRealtimeVoiceStopResponse(session_id=session_id, stopped=stopped)
