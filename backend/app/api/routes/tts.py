"""Authenticated speech synthesis endpoint for the digital human."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ...models.multi_role import UserRow
from ...schemas.tts import TtsRequest
from ...services.container import ServiceContainer, get_container
from ...services.tts.mimo import strip_speech_markdown
from ..deps import current_user

router = APIRouter()


@router.post("/assistant/tts")
async def synthesize_speech(
    req: TtsRequest,
    _: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> StreamingResponse:
    text = strip_speech_markdown(req.text)
    if not text:
        raise HTTPException(status_code=422, detail="朗读文本不能为空")
    if len(text) > container.settings.mimo_tts_max_chars:
        raise HTTPException(status_code=422, detail="朗读文本过长")
    if container.tts is None:
        raise HTTPException(status_code=503, detail="语音服务未配置")

    return StreamingResponse(
        container.tts.stream_pcm(text, (req.style or "").strip()),
        media_type="application/octet-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
            "X-Audio-Format": "pcm16le",
            "X-Audio-Sample-Rate": str(container.settings.mimo_tts_sample_rate),
            "X-Audio-Channels": "1",
        },
    )


__all__ = ["router"]
