"""Small JSON-backed store for learner quiz attempts."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from threading import Lock, RLock
from weakref import WeakValueDictionary

from ...core.exceptions import AppException

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
    _locks = WeakValueDictionary()
    _locks_guard = Lock()

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        with self._locks_guard:
            key = str(root.resolve())
            self._lock = self._locks.setdefault(key, RLock())

    @contextmanager
    def _locked(self):
        # Serialize the entire read/check/write, including retry allocation.
        # The file lock also protects separate backend worker processes.
        with self._lock, (self._root / ".attempts.lock").open("a+b") as handle:
            if os.name == "nt":
                import msvcrt
                if handle.seek(0, os.SEEK_END) == 0:
                    handle.write(b"\0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def latest(self, root_id: str, *, user_id: str) -> Optional[QuizAttempt]:
        with self._locked():
            current = self.get(root_id, user_id=user_id)
            index = 1
            while (retry := self.get(f"{root_id}:retry:{index}", user_id=user_id)) is not None:
                current = retry
                index += 1
            return current

    def update(
        self, *, attempt_id: str, user_id: str, course_id: str, workspace_id: str,
        stage_id: str, scene_id: str, phase: str, answers: dict[str, Any],
        results: list[dict[str, Any]], start_new_attempt: bool = False,
    ) -> QuizAttempt:
        with self._locked():
            root = root_attempt_id(user_id, stage_id, scene_id)
            prior = self.get(attempt_id, user_id=user_id)
            if start_new_attempt:
                attempt_id = self.next_retry_id(root, user_id=user_id)
                prior = None
            elif prior is None:
                # Normalize a client placeholder to the server-owned root.
                attempt_id = root
                prior = self.get(root, user_id=user_id)
            if prior and (
                (prior.course_id, prior.workspace_id, prior.stage_id, prior.scene_id)
                != (course_id, workspace_id, stage_id, scene_id)
                or PHASE_ORDER[phase] < PHASE_ORDER[prior.phase]
            ):
                raise AppException("测验状态不能回退或更改所属课堂", code="QUIZ_ATTEMPT_CONFLICT", http_status=409)
            attempt = QuizAttempt(
                attempt_id=attempt_id, user_id=user_id, course_id=course_id,
                workspace_id=workspace_id, stage_id=stage_id, scene_id=scene_id,
                phase=phase, answers=answers, results=results,
            )
            self.save(attempt)
            return attempt

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
