"""Speech recognition response schemas."""

from typing import Any

from pydantic import BaseModel, Field


class AsrResponse(BaseModel):
    """本地语音识别结果。

    `text` 为空字符串表示"没听清"（静音、噪声或只剩标点），
    属于正常成功响应，客户端应提示用户重说而不是当错误处理。
    """

    text: str = Field(description="识别文本；空字符串表示没听清")
    duration_seconds: float = Field(
        ge=0, description="服务端实际送入识别的音频时长(秒)"
    )


class AsrErrorResponse(BaseModel):
    """ASR 失败时的统一错误信封，与全局异常处理保持一致。"""

    code: str = Field(description="稳定错误码，例如 ASR_BUSY / ASR_AUDIO_INVALID")
    message: str = Field(description="可直接展示的中文提示")
    details: Any | None = Field(default=None, description="可选的结构化细节")
    request_id: str | None = Field(default=None, description="请求追踪 ID")


__all__ = ["AsrErrorResponse", "AsrResponse"]
