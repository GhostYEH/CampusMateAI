"""Authenticated speech synthesis endpoint for the digital human."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ...models.multi_role import UserRow
from ...schemas.tts import TtsRequest
from ...services.container import ServiceContainer, get_container
from ...services.tts.mimo import strip_speech_markdown
from ..deps import current_user

router = APIRouter(tags=["语音合成"])


@router.post("/assistant/tts", summary="合成数字人语音")
async def synthesize_speech(
    req: Annotated[
        TtsRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "合成一段助手回复语音",
                    "value": {
                        "text": "同学你好，我把今天的学习任务整理好了。",
                        "style": "温和亲切",
                    },
                }
            }
        ),
    ],
    _: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> StreamingResponse:
    """将 AI 助手回复文本合成为数字人语音。

    - 成功返回 PCM16LE 二进制流，采样率见响应头 X-Audio-Sample-Rate，单声道。
    - 朗读文本为空或超长返回 422，语音服务未配置返回 503。
    """
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
