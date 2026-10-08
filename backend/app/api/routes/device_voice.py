"""Device-scoped voice sessions reuse the user relay without granting user JWTs."""

from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket

from ...core.exceptions import AppException
from ...models.device import DesktopDevice
from ...schemas.focus_ai import (
    FocusRealtimeVoiceSessionResponse,
    FocusRealtimeVoiceStopResponse,
)
from ...services.container import get_container
from ...services.focus_realtime_voice_service import (
    get_focus_realtime_voice_service,
    RealtimeVoiceUnavailableError,
)
from .devices import current_device
from .focus_realtime_voice import relay_authorized

router = APIRouter(prefix="/devices/me", tags=["桌面设备语音"])


@dataclass
class VoiceLease:
    device_id: str
    focus_id: str
    key: str
    voice_id: str
    expires: float
    connected: bool = False


_leases: dict[str, VoiceLease] = {}
_lock = RLock()


def _owner(device_id: str) -> str:
    return "desktop_device:" + device_id


def _focus_valid(device: DesktopDevice, focus_id: str) -> bool:
    repository = get_container().desktop_device_service._repo
    session = repository.get_session_for_owner(
        session_id=focus_id, owner_user_id=device.owner_user_id
    )
    return bool(
        session
        and session["mode"] == "focus"
        and session["status"] in {"active", "paused"}
        and repository.device_owns_session(device_id=device.id, session_id=focus_id)
    )


def _cleanup() -> None:
    service = get_focus_realtime_voice_service()
    for voice_id, lease in list(_leases.items()):
        if monotonic() >= lease.expires or not service.owns(
            voice_id, _owner(lease.device_id)
        ):
            if service.owns(voice_id, _owner(lease.device_id)):
                service.stop(voice_id, _owner(lease.device_id))
            _leases.pop(voice_id, None)


@router.post(
    "/focus-sessions/{focus_id}/voice-sessions",
    status_code=201,
    response_model=FocusRealtimeVoiceSessionResponse,
    summary="为本设备专注会话创建实时语音连接",
)
def create_voice(
    focus_id: str,
    key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
    device: DesktopDevice = Depends(current_device),
):
    if not _focus_valid(device, focus_id):
        raise HTTPException(404, "专注会话不存在或已结束")
    with _lock:
        _cleanup()
        existing = next(
            (lease for lease in _leases.values() if lease.device_id == device.id), None
        )
        if existing:
            if existing.key != key or existing.focus_id != focus_id:
                raise AppException(
                    code="DEVICE_VOICE_ACTIVE",
                    http_status=409,
                    message="已有实时语音会话，请先停止",
                )
            voice_id = existing.voice_id
        else:
            try:
                voice_id = (
                    get_focus_realtime_voice_service()
                    .create(_owner(device.id))
                    .session_id
                )
            except RealtimeVoiceUnavailableError as exc:
                raise HTTPException(503, "实时语音尚未配置") from exc
            _leases[voice_id] = VoiceLease(
                device.id, focus_id, key, voice_id, monotonic() + 300
            )
    return FocusRealtimeVoiceSessionResponse(
        session_id=voice_id, websocket_path=f"devices/me/voice-sessions/{voice_id}/ws"
    )


@router.delete(
    "/voice-sessions/{voice_id}",
    response_model=FocusRealtimeVoiceStopResponse,
    summary="停止本设备实时语音会话",
)
def stop_voice(voice_id: str, device: DesktopDevice = Depends(current_device)):
    with _lock:
        _cleanup()
        lease = _leases.get(voice_id)
        if lease is None or lease.device_id != device.id:
            raise HTTPException(404, "实时语音会话不存在")
        service = get_focus_realtime_voice_service()
        if service.owns(voice_id, _owner(device.id)):
            service.stop(voice_id, _owner(device.id))
        _leases.pop(voice_id, None)
    return FocusRealtimeVoiceStopResponse(session_id=voice_id, stopped=True)


@router.websocket("/voice-sessions/{voice_id}/ws")
async def relay_device(voice_id: str, websocket: WebSocket):
    authorization = websocket.headers.get("authorization", "")
    credential = authorization[7:] if authorization.startswith("Bearer ") else ""
    try:
        device = get_container().desktop_device_service.authenticate(credential)
    except AppException:
        await websocket.close(code=1008)
        return
    with _lock:
        _cleanup()
        lease = _leases.get(voice_id)
        allowed = bool(
            lease
            and lease.device_id == device.id
            and not lease.connected
            and _focus_valid(device, lease.focus_id)
        )
        if allowed:
            lease.connected = True
            lease.expires = monotonic() + 4 * 3600
    if not allowed:
        await websocket.close(code=1008)
        return

    def authorized():
        try:
            current = get_container().desktop_device_service.authenticate(credential)
            with _lock:
                return bool(
                    _leases.get(voice_id) is lease
                    and monotonic() < lease.expires
                    and _focus_valid(current, lease.focus_id)
                )
        except AppException:
            return False

    try:
        await relay_authorized(voice_id, websocket, _owner(device.id), authorized)
    finally:
        with _lock:
            _leases.pop(voice_id, None)
