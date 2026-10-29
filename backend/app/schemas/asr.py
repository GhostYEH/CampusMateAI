"""Speech recognition response schemas."""

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


__all__ = ["AsrResponse"]
