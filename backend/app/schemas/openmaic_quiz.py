from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


QuizPhase = Literal["draft", "submitted", "reviewed"]


class QuizAttemptIn(BaseModel):
    attempt_id: str = Field(min_length=1, max_length=128)
    phase: QuizPhase
    answers: dict[str, str | list[str]] = Field(default_factory=dict)
    results: list[dict[str, Any]] = Field(default_factory=list)
    start_new_attempt: bool = False


class QuizAttemptStateOut(BaseModel):
    attempt_id: str
    state: dict[str, Any] | None = None
