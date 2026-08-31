"""Authenticated CampusMate WebSocket relay for Seeduplex full-duplex voice."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
import uuid

import websockets
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status

from ...core.config import get_settings
from ...core.security import JWTError, decode_jwt
from ...models.multi_role import UserRow
from ...repositories.multi_role_repository import UserRepository
from ...schemas.focus_ai import FocusRealtimeVoiceSessionResponse, FocusRealtimeVoiceStopResponse
from ...services.container import get_container
from ...services.focus_realtime_voice_service import (
    RealtimeVoiceSessionNotFoundError,
    RealtimeVoiceUnavailableError,
    get_focus_realtime_voice_service,
)
from ..deps import current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/focus/realtime-voice")


@router.post("/sessions", response_model=FocusRealtimeVoiceSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(user: UserRow = Depends(current_user)) -> FocusRealtimeVoiceSessionResponse:
    try:
        session = get_focus_realtime_voice_service().create(user.id)
    except RealtimeVoiceUnavailableError:
        raise HTTPException(status_code=503, detail="实时语音服务尚未配置，请稍后再试。")
    return FocusRealtimeVoiceSessionResponse(
        session_id=session.session_id,
        websocket_path=f"focus/realtime-voice/ws/{session.session_id}",
    )


@router.delete("/sessions/{session_id}", response_model=FocusRealtimeVoiceStopResponse)
def stop_session(session_id: str, user: UserRow = Depends(current_user)) -> FocusRealtimeVoiceStopResponse:
    try:
        stopped = get_focus_realtime_voice_service().stop(session_id, user.id)
    except RealtimeVoiceSessionNotFoundError:
        raise HTTPException(status_code=404, detail="实时语音会话不存在。")
    return FocusRealtimeVoiceStopResponse(session_id=session_id, stopped=stopped)


def _websocket_user(websocket: WebSocket) -> UserRow | None:
    token = websocket.query_params.get("access_token")
    if not token:
        return None
    try:
        payload = decode_jwt(token, get_settings().jwt_secret)
    except JWTError:
        return None
    if payload.type != "access":
        return None
    user = get_container().user_repository.get_user_by_id(payload.sub)
    return user if user is not None and user.is_active else None


async def _send_json(websocket: WebSocket, payload: dict) -> None:
    await websocket.send_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _redact_for_log(value: object) -> object:
    """Keep protocol diagnostics useful without writing credentials to logs."""
    sensitive_keys = {"api_key", "apikey", "authorization", "token", "secret", "password"}
    if isinstance(value, dict):
        return {
            key: "***" if key.lower() in sensitive_keys else _redact_for_log(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_for_log(item) for item in value]
    return value


@router.websocket("/ws/{session_id}")
async def relay(session_id: str, websocket: WebSocket) -> None:
    """Relay only: Android PCM binary frames become upstream Base64 JSON events."""
    user = _websocket_user(websocket)
    service = get_focus_realtime_voice_service()
    if user is None or not service.owns(session_id, user.id):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    first_audio_at: float | None = None
    commit_sent = False
    response_create_sent = False
    vad_turn_event_seen = False
    vad_turn_number = 0
    audio_append_count = 0
    # Some Seeduplex output events omit one or more identifiers after the first
    # event of a response. Retain the latest upstream values only for forwarding
    # that same response's metadata to the Android transport.
    active_response_id: str | None = None
    active_item_id: str | None = None
    try:
        async with websockets.connect(
            service.seeduplex_url,
            additional_headers={"X-Api-Key": service.seeduplex_api_key},
            ping_interval=20,
            ping_timeout=20,
            max_size=2**20,
        ) as upstream:
            started = time.monotonic()
            await upstream.send(json.dumps(service.session_create_event(), ensure_ascii=False))
            logger.info("seeduplex_session_create_sent session=%s", session_id)
            logger.info(
                "realtime_turn_boundary_config session=%s explicit_commit_sent=%s response_create_sent=%s vad_turn_event_seen=%s",
                session_id,
                commit_sent,
                response_create_sent,
                vad_turn_event_seen,
            )
            await _send_json(websocket, {"type": "state", "state": "connecting"})

            async def android_to_upstream() -> None:
                nonlocal first_audio_at, commit_sent, audio_append_count
                while True:
                    message = await websocket.receive()
                    if message["type"] == "websocket.disconnect":
                        return
                    data = message.get("bytes")
                    if data is not None:
                        if not data:
                            continue
                        if first_audio_at is None:
                            first_audio_at = time.monotonic()
                            logger.info("first_audio_frame_sent session=%s", session_id)
                        event = {"type": "input_audio_buffer.append", "event_id": uuid.uuid4().hex, "audio": base64.b64encode(data).decode("ascii")}
                        await upstream.send(json.dumps(event, separators=(",", ":")))
                        audio_append_count += 1
                        if audio_append_count == 1:
                            logger.info(
                                "realtime_turn_event session=%s turn=%s event=audio_append_first event_id=%s bytes=%d",
                                session_id,
                                vad_turn_number or "pending_vad",
                                event["event_id"],
                                len(data),
                            )
                        continue
                    raw = message.get("text")
                    if not raw:
                        continue
                    command = json.loads(raw)
                    kind = command.get("type")
                    logger.info("realtime_client_control_received session=%s type=%s", session_id, kind)
                    if kind in {"response.cancel", "interrupt"}:
                        # CampusMate accepts the legacy local command during migration, but sends
                        # the exact Seeduplex cancel event upstream. Do not close the session or
                        # stop microphone relay: Seeduplex remains full-duplex after cancellation.
                        await upstream.send(json.dumps({"type": "response.cancel"}))
                        logger.info("response_cancel_sent session=%s", session_id)
                    elif kind == "commit":
                        await upstream.send(json.dumps({"type": "input_audio_buffer.commit", "event_id": uuid.uuid4().hex}))
                        commit_sent = True
                        logger.info("realtime_input_audio_commit_sent session=%s", session_id)
                    elif kind == "stop":
                        await upstream.send(json.dumps({"type": "session.close", "event_id": uuid.uuid4().hex}))
                        logger.info("session_close_sent session=%s", session_id)
                        return

            async def upstream_to_android() -> None:
                nonlocal vad_turn_event_seen, active_response_id, active_item_id, vad_turn_number, audio_append_count
                while True:
                    raw = await upstream.recv()
                    if isinstance(raw, bytes):
                        continue
                    event = json.loads(raw)
                    kind = event.get("type", "")
                    response = event.get("response") if isinstance(event.get("response"), dict) else {}
                    item = event.get("item") if isinstance(event.get("item"), dict) else {}
                    direct_response_id = event.get("response_id") or response.get("id")
                    direct_item_id = event.get("item_id") or item.get("id")
                    event_id = event.get("event_id") or event.get("id")
                    if isinstance(direct_response_id, str) and direct_response_id:
                        active_response_id = direct_response_id
                    if isinstance(direct_item_id, str) and direct_item_id:
                        active_item_id = direct_item_id
                    response_id = direct_response_id or active_response_id
                    item_id = direct_item_id or active_item_id
                    logger.info(
                        "realtime_upstream_event session=%s type=%s event_id=%s response_id=%s item_id=%s",
                        session_id,
                        kind,
                        event_id or "-",
                        response_id or "-",
                        item_id or "-",
                    )
                    if kind in {"session.created", "session.updated"}:
                        logger.info(
                            "seeduplex_session_event session=%s type=%s payload=%s",
                            session_id,
                            kind,
                            json.dumps(_redact_for_log(event), ensure_ascii=False, separators=(",", ":")),
                        )
                    if "vad" in kind or "speech_started" in kind or "speech_stopped" in kind:
                        vad_turn_event_seen = True
                        if kind == "input_audio_buffer.speech_started":
                            vad_turn_number += 1
                            audio_append_count = 0
                        logger.info(
                            "realtime_turn_event session=%s turn=%s event=%s event_id=%s audio_start_ms=%s audio_end_ms=%s",
                            session_id,
                            vad_turn_number or "pending_vad",
                            kind,
                            event_id or "-",
                            event.get("audio_start_ms", "-"),
                            event.get("audio_end_ms", "-"),
                        )
                    if kind == "input_audio_buffer.speech_started":
                        # Barge-in is deliberately relayed as its own Android event.  The
                        # phone can stop already-buffered/local playback immediately, while
                        # this relay cancels an upstream response only when one is still live.
                        interrupted_response_id = active_response_id
                        if interrupted_response_id:
                            await upstream.send(json.dumps({"type": "response.cancel"}))
                            logger.info(
                                "realtime_barge_in_cancel_sent session=%s response_id=%s",
                                session_id,
                                interrupted_response_id,
                            )
                            active_response_id = None
                            active_item_id = None
                            await _send_json(websocket, {
                                "type": "user_speech_started",
                                "response_id": interrupted_response_id,
                            })
                        else:
                            # Seeduplex Ogg playback may already be locally buffered after the
                            # upstream response has completed.  Do not forward its acoustic
                            # echo as a fresh barge-in; the next genuine user turn is handled by
                            # normal VAD/transcription.
                            logger.debug("realtime_speech_start_without_live_response session=%s", session_id)
                    if kind == "session.created":
                        logger.info("seeduplex_session_created session=%s connect_ms=%d", session_id, (time.monotonic() - started) * 1000)
                        audio_output = event.get("session", {}).get("audio", {}).get("output", {})
                        logger.info(
                            "seeduplex_audio_output_config session=%s format=%s sample_rate=%s channels=%s bits=%s",
                            session_id,
                            audio_output.get("format", "-"),
                            audio_output.get("sample_rate", "-"),
                            audio_output.get("channels", "-"),
                            audio_output.get("bits", "-"),
                        )
                        await _send_json(websocket, {"type": "state", "state": "listening"})
                    elif kind == "input_audio_buffer.committed":
                        logger.info(
                            "realtime_turn_event session=%s turn=%s event=audio_committed event_id=%s",
                            session_id,
                            vad_turn_number or "pending_vad",
                            event_id or "-",
                        )
                    elif kind == "response.created":
                        logger.info(
                            "realtime_turn_event session=%s turn=%s event=response_created event_id=%s response_id=%s item_id=%s",
                            session_id,
                            vad_turn_number or "pending_vad",
                            event_id or "-",
                            response_id or "-",
                            item_id or "-",
                        )
                    elif kind == "response.output_audio.delta":
                        audio = event.get("delta") or event.get("audio")
                        if isinstance(audio, str):
                            logger.info(
                                "seeduplex_output_audio_delta session=%s bytes=%d header_hex=%s",
                                session_id,
                                len(base64.b64decode(audio)),
                                base64.b64decode(audio)[:8].hex(" "),
                            )
                            # Binary CampusMate frame avoids another Base64 hop to Android.
                            await websocket.send_bytes(base64.b64decode(audio))
                            logger.info("first_ai_audio_received session=%s", session_id)
                    elif kind in {"conversation.item.input_audio_transcription.delta", "conversation.item.input_audio_transcription.completed"}:
                        text = event.get("delta") or event.get("transcript", "")
                        logger.info("realtime_transcript_forwarded session=%s completed=%s length=%d event_id=%s item_id=%s", session_id, kind.endswith("completed"), len(text), event_id or "-", item_id or "-")
                        await _send_json(websocket, {
                            "type": "user_transcript_done" if kind.endswith("completed") else "user_transcript_delta",
                            "text": text,
                            "event_id": event_id or "",
                            "item_id": item_id or "",
                        })
                    elif kind in {"response.output_text.delta", "response.output_text.done"}:
                        text = event.get("delta") or event.get("text", "")
                        logger.info("realtime_answer_forwarded session=%s completed=%s length=%d event_id=%s response_id=%s item_id=%s", session_id, kind.endswith("done"), len(text), event_id or "-", response_id or "-", item_id or "-")
                        await _send_json(websocket, {
                            "type": "ai_text_done" if kind.endswith("done") else "ai_text_delta",
                            "text": text,
                            "response_id": response_id or "",
                            "item_id": item_id or "",
                            "event_id": event_id or "",
                        })
                    elif kind == "response.output_audio.started":
                        logger.info("ai_response_started session=%s", session_id)
                        await _send_json(websocket, {"type": "state", "state": "speaking"})
                    elif kind in {"response.output_audio.done", "response.done"}:
                        logger.info("ai_response_done session=%s", session_id)
                        await _send_json(websocket, {"type": "state", "state": "listening"})
                        active_response_id = None
                        active_item_id = None
                    elif kind == "session.closed":
                        logger.info("session_closed session=%s", session_id)
                        await _send_json(websocket, {"type": "session_closed"})
                        return
                    elif kind == "error":
                        logger.warning("seeduplex_error session=%s code=%s", session_id, event.get("code"))
                        await _send_json(websocket, {"type": "error", "message": "实时语音服务暂时不可用"})
                        return
                    else:
                        # Forward only non-sensitive protocol events for future capability expansion.
                        await _send_json(websocket, {"type": "provider_event", "event": kind})

            left = asyncio.create_task(android_to_upstream())
            right = asyncio.create_task(upstream_to_android())
            done, pending = await asyncio.wait({left, right}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("seeduplex_relay_failed session=%s type=%s", session_id, type(exc).__name__)
        try:
            await _send_json(websocket, {"type": "error", "message": "实时语音连接失败，请稍后重试"})
        except Exception:
            pass
    finally:
        logger.info(
            "realtime_turn_boundary_summary session=%s explicit_commit_sent=%s response_create_sent=%s vad_turn_event_seen=%s",
            session_id,
            commit_sent,
            response_create_sent,
            vad_turn_event_seen,
        )
        if service.owns(session_id, user.id):
            service.stop(session_id, user.id)
        try:
            await websocket.close()
        except Exception:
            pass
