"""OpenMAIC 课堂会话持久化 —— 小型专用文件存储。

不修改数据库结构：agent_artifacts 的 run_id 通过外键关联 agent_runs，
复用它会迫使创建语义上的假 Agent 运行记录，干扰 Agent Runtime 契约。
因此按需求"实现小型专用适配层"，把每个课堂会话状态写成 JSON 文件，
原子写入(temp+rename)，并按 {user_id}/{course_id} 目录天然做用户/课程隔离，
读取时强制校验用户与课程归属。

指导原则：
- 客户端断开不重复提交：generate 幂等由 classroom_service 通过"该 course 已有
  进行中任务"去重保证，本层只负责存取。
- 日志/异常不包含附件全文与学生隐私，仅存结构化状态字段。
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_session_id() -> str:
    return f"om_{uuid.uuid4().hex}"


@dataclass
class OpenMAICSession:
    session_id: str
    course_id: str
    user_id: str
    mode: str = "adaptive"
    job_id: Optional[str] = None
    status: str = "queued"
    step: str = "queued"
    progress: int = 0
    message: str = ""
    error: Optional[str] = None
    classroom_id: Optional[str] = None
    classroom_url: Optional[str] = None
    scenes_count: Optional[int] = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "course_id": self.course_id,
            "user_id": self.user_id,
            "mode": self.mode,
            "job_id": self.job_id,
            "status": self.status,
            "step": self.step,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "classroom_id": self.classroom_id,
            "classroom_url": self.classroom_url,
            "scenes_count": self.scenes_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OpenMAICSession":
        allowed = {f for f in cls.__dataclass_fields__ if f in data}
        return cls(**{f: data[f] for f in allowed})


class OpenMAICResultStore:
    """课堂会话的 JSON 文件存储。"""

    def __init__(self, storage_dir: Path) -> None:
        self._root = storage_dir
        self._root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe(part: str) -> str:
        return re.sub(r"[^0-9a-zA-Z_\-.]", "_", part)

    def _course_dir(self, user_id: str, course_id: str) -> Path:
        return self._root / self._safe(user_id) / self._safe(course_id)

    def _session_path(self, user_id: str, course_id: str, session_id: str) -> Path:
        return self._course_dir(user_id, course_id) / f"{self._safe(session_id)}.json"

    @staticmethod
    def _valid_session_id(session_id: Optional[str]) -> bool:
        return bool(session_id) and bool(_SESSION_ID_RE.match(session_id or ""))

    def save(self, session: OpenMAICSession) -> None:
        path = self._session_path(session.user_id, session.course_id, session.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def get_session(
        self, *, user_id: str, course_id: str, session_id: str
    ) -> Optional[OpenMAICSession]:
        if not self._valid_session_id(session_id):
            return None
        path = self._session_path(user_id, course_id, session_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(data, dict):
            return None
        # 归属校验
        if data.get("user_id") != user_id or data.get("course_id") != course_id:
            return None
        return OpenMAICSession.from_dict(data)

    def list_sessions(self, *, user_id: str, course_id: str) -> List[OpenMAICSession]:
        directory = self._course_dir(user_id, course_id)
        sessions: List[OpenMAICSession] = []
        if not directory.exists():
            return sessions
        for path in directory.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(data, dict):
                continue
            if data.get("user_id") != user_id or data.get("course_id") != course_id:
                continue
            sessions.append(OpenMAICSession.from_dict(data))
        return sessions

    def active_session(self, *, user_id: str, course_id: str) -> Optional[OpenMAICSession]:
        for session in self.list_sessions(user_id=user_id, course_id=course_id):
            if session.status in ("queued", "running", "generating"):
                return session
        return None


__all__ = [
    "OpenMAICResultStore",
    "OpenMAICSession",
    "new_session_id",
]