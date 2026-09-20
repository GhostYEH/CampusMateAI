"""Small JSON-backed store for learner quiz attempts."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

PHASE_ORDER = {"draft": 0, "submitted": 1, "reviewed": 2}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def root_attempt_id(user_id: str, stage_id: str, scene_id: str) -> str:
    raw = f"{user_id}\0{stage_id}\0{scene_id}".encode()
    return "quiz-attempt-" + hashlib.sha256(raw).hexdigest()[:32]


@dataclass
class QuizAttempt:
    attempt_id: str
    user_id: str
    course_id: str
    workspace_id: str
    stage_id: str
    scene_id: str
    phase: str = "draft"
    answers: dict[str, Any] = field(default_factory=dict)
    results: list[dict[str, Any]] = field(default_factory=list)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QuizAttempt":
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


class QuizAttemptStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe(value: str) -> str:
        return "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in value)

    def _path(self, attempt_id: str) -> Path:
        return self._root / f"{self._safe(attempt_id)}.json"

    def get(self, attempt_id: str, *, user_id: str) -> Optional[QuizAttempt]:
        path = self._path(attempt_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict) or data.get("user_id") != user_id:
            return None
        return QuizAttempt.from_dict(data)

    def save(self, attempt: QuizAttempt) -> None:
        attempt.updated_at = _now()
        self._root.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=self._root, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(attempt.to_dict(), handle, ensure_ascii=False)
            os.replace(name, self._path(attempt.attempt_id))
        finally:
            try:
                os.unlink(name)
            except OSError:
                pass

    def next_retry_id(self, root_id: str, *, user_id: str) -> str:
        index = 1
        while self.get(f"{root_id}:retry:{index}", user_id=user_id) is not None:
            index += 1
        return f"{root_id}:retry:{index}"


__all__ = ["PHASE_ORDER", "QuizAttempt", "QuizAttemptStore", "root_attempt_id"]
