"""Speech synthesis request schemas."""

from pydantic import BaseModel, Field


class TtsRequest(BaseModel):
    text: str = Field(min_length=1)
    style: str | None = Field(default=None, max_length=500)


__all__ = ["TtsRequest"]
