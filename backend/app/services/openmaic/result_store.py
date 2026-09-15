"""OpenMAIC 课堂会话持久化 —— 小型专用文件存储。

不修改数据库结构：agent_artifacts 的 run_id 通过外键关联 agent_runs，
复用它会迫使创建语义上的假 Agent 运行记录，干扰 Agent Runtime 契约。
因此按需求"实现小型专用适配层"，把每个课堂会话状态写成 JSON 文件，
原子写入(temp+rename)，并按 {user_id}/{course_id} 目录天然做用户/课程隔离，
读取时强制校验用户与课程归属。

跨请求/跨进程预占：
- 每个 {user_id}/{course_id} 目录下有一个 `.active.json` 预占文件，
  用 `os.open(..., O_CREAT | O_EXCL)` 原子创建 —— 该原语在 POSIX 与 Windows
  上都是原子的，因此多进程(多 uvicorn worker)并发时只有一个请求能成为
  "提交者"，其余请求复用同一任务，避免重复提交到 OpenMAIC。
- 预占带租约(`ttl_seconds`)：提交者崩溃且不再轮询时，租约到期后可被接管；
  客户端每次轮询都会续租(touch)，正常生成不会因超时被抢占。
- 任务进入终态(succeeded/failed)时释放预占。

历史裁剪：
- 每用户每课程最多保留 `max_results` 条记录；超出时只裁剪**最早的终态记录**，
  进行中的记录永不删除。
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

# 预占文件名以 "." 开头，与历史会话文件区分；list_sessions 显式跳过隐藏文件。
RESERVATION_FILENAME = ".active.json"

TERMINAL_STATUSES = ("succeeded", "failed")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


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

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES


@dataclass
class OpenMAICReservation:
    """user_id + course_id 级别的生成预占(租约)。"""

    session_id: str
    mode: str
    job_id: Optional[str] = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "mode": self.mode,
            "job_id": self.job_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional["OpenMAICReservation"]:
        session_id = data.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            return None
        return cls(
            session_id=session_id,
            mode=str(data.get("mode") or "adaptive"),
            job_id=data.get("job_id"),
            created_at=str(data.get("created_at") or _now()),
            updated_at=str(data.get("updated_at") or data.get("created_at") or _now()),
        )


class OpenMAICResultStore:
    """课堂会话的 JSON 文件存储 + 原子预占 + 历史裁剪。"""

    def __init__(self, storage_dir: Path, *, max_results: int = 20) -> None:
        self._root = storage_dir
        self._root.mkdir(parents=True, exist_ok=True)
        self._max_results = max(1, int(max_results))

    # ===== 路径 =====

    @staticmethod
    def _safe(part: str) -> str:
        return re.sub(r"[^0-9a-zA-Z_\-.]", "_", part)

    def _course_dir(self, user_id: str, course_id: str) -> Path:
        return self._root / self._safe(user_id) / self._safe(course_id)

    def _session_path(self, user_id: str, course_id: str, session_id: str) -> Path:
        return self._course_dir(user_id, course_id) / f"{self._safe(session_id)}.json"

    def _reservation_path(self, user_id: str, course_id: str) -> Path:
        return self._course_dir(user_id, course_id) / RESERVATION_FILENAME

    @staticmethod
    def _valid_session_id(session_id: Optional[str]) -> bool:
        return bool(session_id) and bool(_SESSION_ID_RE.match(session_id or ""))

    @staticmethod
    def _write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # ===== 会话读写 =====

    def save(self, session: OpenMAICSession) -> None:
        session.updated_at = session.updated_at or _now()
        self._write_json_atomic(
            self._session_path(session.user_id, session.course_id, session.session_id),
            session.to_dict(),
        )
        self._prune(session.user_id, session.course_id)

    def _read_session_file(self, path: Path, *, user_id: str, course_id: str) -> Optional[OpenMAICSession]:
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

    def get_session(
        self, *, user_id: str, course_id: str, session_id: str
    ) -> Optional[OpenMAICSession]:
        if not self._valid_session_id(session_id):
            return None
        path = self._session_path(user_id, course_id, session_id)
        if not path.exists():
            return None
        return self._read_session_file(path, user_id=user_id, course_id=course_id)

    def list_sessions(self, *, user_id: str, course_id: str) -> List[OpenMAICSession]:
        directory = self._course_dir(user_id, course_id)
        sessions: List[OpenMAICSession] = []
        if not directory.exists():
            return sessions
        for path in directory.glob("*.json"):
            # 预占文件是隐藏文件，不属于历史记录
            if path.name.startswith("."):
                continue
            session = self._read_session_file(path, user_id=user_id, course_id=course_id)
            if session is not None:
                sessions.append(session)
        sessions.sort(key=lambda s: s.created_at)
        return sessions

    def active_session(self, *, user_id: str, course_id: str) -> Optional[OpenMAICSession]:
        for session in self.list_sessions(user_id=user_id, course_id=course_id):
            if not session.is_terminal:
                return session
        return None

    def _prune(self, user_id: str, course_id: str) -> None:
        """把每用户每课程的历史记录裁剪到 max_results，只删最早的终态记录。"""
        sessions = self.list_sessions(user_id=user_id, course_id=course_id)
        overflow = len(sessions) - self._max_results
        if overflow <= 0:
            return
        # 只裁剪终态记录，且从最早开始；进行中的记录永不删除。
        removable = sorted(
            (s for s in sessions if s.is_terminal), key=lambda s: s.created_at
        )
        for session in removable[:overflow]:
            path = self._session_path(user_id, course_id, session.session_id)
            try:
                os.unlink(path)
            except OSError:
                pass

    # ===== 预占(跨进程原子) =====

    def read_reservation(
        self, *, user_id: str, course_id: str
    ) -> Optional[OpenMAICReservation]:
        path = self._reservation_path(user_id, course_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(data, dict):
            return None
        return OpenMAICReservation.from_dict(data)

    def acquire_reservation(
        self,
        *,
        user_id: str,
        course_id: str,
        session_id: str,
        mode: str,
    ) -> bool:
        """尝试原子抢占预占。已被占用返回 False。

        `O_CREAT | O_EXCL` 在 POSIX 与 Windows 上都是原子的：并发/多进程下
        只有一个调用能创建成功，其余收到 FileExistsError。
        """
        path = self._reservation_path(user_id, course_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        reservation = OpenMAICReservation(session_id=session_id, mode=mode)
        payload = json.dumps(reservation.to_dict(), ensure_ascii=False).encode("utf-8")
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            return False
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        return True

    def steal_reservation(
        self,
        *,
        user_id: str,
        course_id: str,
        session_id: str,
        mode: str,
    ) -> bool:
        """接管过期预占。先删再原子创建；创建失败说明被别人抢先，返回 False。"""
        path = self._reservation_path(user_id, course_id)
        try:
            os.unlink(path)
        except OSError:
            pass
        return self.acquire_reservation(
            user_id=user_id, course_id=course_id, session_id=session_id, mode=mode
        )

    def update_reservation(
        self,
        *,
        user_id: str,
        course_id: str,
        session_id: str,
        job_id: Optional[str] = None,
    ) -> None:
        """提交成功/续租时刷新预占。只更新仍属于该 session 的预占。"""
        path = self._reservation_path(user_id, course_id)
        current = self.read_reservation(user_id=user_id, course_id=course_id)
        if current is None or current.session_id != session_id:
            return
        current.job_id = job_id if job_id is not None else current.job_id
        current.updated_at = _now()
        self._write_json_atomic(path, current.to_dict())

    def touch_reservation(self, *, user_id: str, course_id: str, session_id: str) -> None:
        self.update_reservation(
            user_id=user_id, course_id=course_id, session_id=session_id, job_id=None
        )

    def release_reservation(
        self, *, user_id: str, course_id: str, session_id: Optional[str] = None
    ) -> None:
        """释放预占。给定 session_id 时只释放仍指向它的预占，避免误删他人的。"""
        path = self._reservation_path(user_id, course_id)
        if session_id is not None:
            current = self.read_reservation(user_id=user_id, course_id=course_id)
            if current is not None and current.session_id != session_id:
                return
        try:
            os.unlink(path)
        except OSError:
            pass

    @staticmethod
    def reservation_is_stale(reservation: OpenMAICReservation, ttl_seconds: float) -> bool:
        updated = _parse_iso(reservation.updated_at) or _parse_iso(reservation.created_at)
        if updated is None:
            return True
        return (datetime.now(timezone.utc) - updated).total_seconds() > float(ttl_seconds)


__all__ = [
    "OpenMAICResultStore",
    "OpenMAICSession",
    "OpenMAICReservation",
    "RESERVATION_FILENAME",
    "TERMINAL_STATUSES",
    "new_session_id",
]
