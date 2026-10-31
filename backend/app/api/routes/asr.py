"""Authenticated on-device speech recognition endpoint.

浏览器把按住说话录到的音频转成 WAV/PCM16LE/16kHz/单声道后上传；后端用
本地 SenseVoice 模型离线转写，不发任何外部请求。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from starlette.concurrency import run_in_threadpool

from ...core.exceptions import AppException
from ...models.multi_role import UserRow
from ...schemas.asr import AsrResponse
from ...services.asr import (
    AsrAudioTooLongError,
    AsrError,
    AsrInvalidAudioError,
    AsrUnavailableError,
    decode_wav_pcm16_mono,
)
from ...services.container import ServiceContainer, get_container
from ..deps import current_user

router = APIRouter(tags=["语音识别"])


def _transcribe(
    container: ServiceContainer,
    data: bytes,
) -> AsrResponse:
    """同步执行"解析 WAV → 能量门控 → 模型推理"，由线程池承载。

    这里全部是 CPU/同步阻塞工作（实测 60 秒音频约 1.85 秒），不能放在事件循环上。
    """
    engine = container.asr
    if engine is None:  # 路由已判过，这里防御容器被并发替换
        raise AsrUnavailableError("本地语音识别未就绪")

    settings = container.settings
    try:
        samples, sample_rate = decode_wav_pcm16_mono(
            data, max_seconds=settings.asr_max_audio_seconds
        )
    except AsrAudioTooLongError as exc:
        raise AppException(
            str(exc), code="ASR_AUDIO_TOO_LONG", http_status=413
        ) from exc
    except AsrInvalidAudioError as exc:
        raise AppException(
            str(exc), code="ASR_AUDIO_INVALID", http_status=422
        ) from exc

    duration_seconds = len(samples) / sample_rate if sample_rate else 0.0
    try:
        text = engine.transcribe(samples, sample_rate)
    except AsrUnavailableError as exc:
        raise AppException(
            str(exc), code="ASR_UNAVAILABLE", http_status=503
        ) from exc
    except AsrError as exc:
        # 引擎内部错误只给出通用中文提示，绝不把堆栈或模型路径返回客户端。
        raise AppException(
            "语音识别失败，请重试", code="ASR_FAILED", http_status=500
        ) from exc
    return AsrResponse(text=text, duration_seconds=round(duration_seconds, 3))


@router.post(
    "/assistant/asr",
    response_model=AsrResponse,
    summary="识别语音输入",
    responses={
        200: {
            "description": "识别完成；text 可能为空字符串，表示没听清",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "正常识别",
                            "value": {
                                "text": "开饭时间早上9点至下午5点。",
                                "duration_seconds": 5.59,
                            },
                        },
                        "没听清": {
                            "summary": "静音或噪声，没有可用语音",
                            "value": {"text": "", "duration_seconds": 1.2},
                        },
                    }
                }
            },
        }
    },
)
async def recognize_speech(
    audio: Annotated[UploadFile, File(description="WAV/PCM16LE/16kHz/单声道 音频")],
    _: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> AsrResponse:
    """把学生按住说话录到的音频转成文本，供 AI 助手输入框回填。

    - 请求为 `multipart/form-data`，字段名 `audio`。
    - 音频约定 WAV / PCM16LE / 16000Hz / 单声道（由客户端录制后就地转换）。
    - 成功一律 200；`text` 为空字符串表示没听清（静音、噪声或只剩标点）。
    - 音频非法或超时长返回 422/413，本地识别未就绪返回 503。
    """
    if container.asr is None:
        raise AppException(
            "本地语音识别未就绪", code="ASR_UNAVAILABLE", http_status=503
        )

    settings = container.settings
    max_bytes = settings.asr_max_upload_mb * 1024 * 1024
    # 多读一个字节即可判定超限，避免把超大文件全量读进内存。
    try:
        data = await audio.read(max_bytes + 1)
    finally:
        await audio.close()
    if len(data) > max_bytes:
        raise AppException(
            f"录音文件不能超过 {settings.asr_max_upload_mb} MB",
            code="ASR_AUDIO_TOO_LARGE",
            http_status=413,
        )
    if not data:
        raise AppException("录音文件为空", code="ASR_AUDIO_INVALID", http_status=422)

    return await run_in_threadpool(_transcribe, container, data)


__all__ = ["router"]
