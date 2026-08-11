"""学习会话仓库 — 状态机 + 用户隔离 + 休息记录 + 个人待办关联校验。

状态机:
  active --pause--> paused --resume--> active
  active --finish--> completed
  paused --finish--> completed (关闭未结束的休息)

禁止:
  - 已结束会话再次暂停/恢复/结束
  - 未暂停会话直接恢复
  - 结束时间早于开始时间(由 finish 时服务端计算,不接受客户端传入)

related_task_id 校验(若非空):
  - 必须解析为当前 JWT 用户的 PersonalTask
  - 必须未软删除(status != 'deleted')
  - 不得使用教师 Assignment ID(严格区分两类实体)

duration_seconds = (ended_at - started_at) - pause_seconds (服务端在 finish 时计算)
pause_seconds 由每次 resume 时累加该次休息时长。
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from ..core.exceptions import (
    InvalidTransition,
    PersonalTaskNotFound,
    StudySessionNotFound,
)
from ..database.sqlite_db import Database
from ..models.study import StudyBreakRow, StudySessionRow


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _parse_iso(s: str) -> datetime:
    """解析 ISO 8601(带时区),失败抛 ValueError。"""
    return datetime.fromisoformat(s)


def _seconds_between(start_iso: str, end_iso: str) -> int:
    """计算两个 ISO 时间戳之间的秒数(向下取整,负值返回 0)。"""
    try:
        start = _parse_iso(start_iso)
        end = _parse_iso(end_iso)
    except ValueError:
        return 0
    delta = (end - start).total_seconds()
    if delta < 0:
        return 0
    return int(delta)


class StudySessionRepository:
    def __init__(self, db: Database, personal_task_repo: Optional[Any] = None) -> None:
        self._db = db
        # PersonalTaskRepository 注入(用于校验 related_task_id)。
        # 类型设为 Any 以避免循环导入;实际为 PersonalTaskRepository。
        self._personal_task_repo = personal_task_repo

    def _validate_related_task_id(
        self, conn, task_id: str, user_id: str
    ) -> None:
        """校验 related_task_id 属于当前用户且未软删除。

        - 空: 跳过校验
        - 不属于当前用户: 抛 PersonalTaskNotFound(404,统一不泄露存在性)
        - 已软删除: 抛 PersonalTaskNotFound(404)
        - 教师 Assignment ID: PersonalTaskRepository 查不到,同样 404

        在已打开的 transaction 连接中执行,避免连接复用问题。
        """
        if not task_id:
            return
        if self._personal_task_repo is None:
            return  # 容器未注入(理论上不会发生),由上层兜底
        cur = conn.execute(
            "SELECT status FROM personal_tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id),
        )
        row = cur.fetchone()
        if row is None:
            raise PersonalTaskNotFound(
                f"关联任务 {task_id} 不存在或不属于当前用户"
            )
        if row["status"] == "deleted":
            raise PersonalTaskNotFound(
                f"关联任务 {task_id} 已删除,不能关联学习会话"
            )

    # ===== 创建 =====

    def create_session(
        self,
        *,
        user_id: str,
        mode: str = "focus",
        goal: Optional[str] = None,
        related_task_id: Optional[str] = None,
    ) -> StudySessionRow:
        sid = _new_id("stdy")
        now = _now_iso()
        with self._db.transaction() as conn:
            # 校验 related_task_id 必须属于当前用户且未软删除
            self._validate_related_task_id(conn, related_task_id or "", user_id)
            conn.execute(
                """INSERT INTO study_sessions
                   (id, user_id, mode, goal, related_task_id, started_at, paused_at, ended_at,
                    duration_seconds, pause_seconds, status, self_report, self_report_tags,
                    expression_signal, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,0,0,'active',NULL,NULL,NULL,?,?)""",
                (sid, user_id, mode, goal, related_task_id, now, None, None, now, now),
            )
        # 重新读取(transaction 已关闭,需用 get_session 自带 query 连接)
        result = self.get_session(sid, user_id=user_id)
        if result is None:  # pragma: no cover - 理论上不会发生
            raise RuntimeError("刚创建的会话读取失败")
        return result

    # ===== 查询 =====

    def get_session(
        self, session_id: str, *, user_id: str
    ) -> Optional[StudySessionRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM study_sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            )
            row = cur.fetchone()
            return StudySessionRow.from_row(row) if row else None

    def _get_session(
        self, conn, session_id: str, user_id: str
    ) -> Optional[StudySessionRow]:
        cur = conn.execute(
            "SELECT * FROM study_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        )
        row = cur.fetchone()
        return StudySessionRow.from_row(row) if row else None

    def get_active_session(
        self, user_id: str
    ) -> Optional[StudySessionRow]:
        """返回当前未结束的会话(active 或 paused),至多一条。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT * FROM study_sessions
                   WHERE user_id = ? AND status IN ('active','paused')
                   ORDER BY started_at DESC LIMIT 1""",
                (user_id,),
            )
            row = cur.fetchone()
            return StudySessionRow.from_row(row) if row else None

    def list_sessions(
        self,
        user_id: str,
        *,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[StudySessionRow], int]:
        conditions = ["user_id = ?"]
        params: list = [user_id]
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = " WHERE " + " AND ".join(conditions)
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            cur = conn.execute(
                f"SELECT COUNT(*) AS n FROM study_sessions{where}", params
            )
            total = int(cur.fetchone()["n"])
            cur = conn.execute(
                f"""SELECT * FROM study_sessions{where}
                    ORDER BY started_at DESC
                    LIMIT ? OFFSET ?""",
                params + [page_size, offset],
            )
            rows = cur.fetchall()
        return [StudySessionRow.from_row(r) for r in rows], total

    def list_breaks(self, session_id: str, *, user_id: str) -> List[StudyBreakRow]:
        with self._db.query() as conn:
            # 先校验会话归属
            cur = conn.execute(
                "SELECT 1 FROM study_sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            )
            if cur.fetchone() is None:
                raise StudySessionNotFound()
            cur = conn.execute(
                """SELECT * FROM study_breaks
                   WHERE session_id = ? ORDER BY started_at ASC""",
                (session_id,),
            )
            rows = cur.fetchall()
        return [StudyBreakRow.from_row(r) for r in rows]

    # ===== 状态机 =====

    def pause(
        self, session_id: str, *, user_id: str, reason: Optional[str] = None
    ) -> StudySessionRow:
        now = _now_iso()
        with self._db.transaction() as conn:
            session = self._get_session(conn, session_id, user_id)
            if session is None:
                raise StudySessionNotFound()
            if session.status != "active":
                raise InvalidTransition(
                    f"当前状态({session.status})不允许暂停,仅 active 会话可暂停"
                )
            conn.execute(
                "UPDATE study_sessions SET status='paused', paused_at=?, updated_at=? WHERE id=?",
                (now, now, session_id),
            )
            # 开启一条休息记录
            conn.execute(
                """INSERT INTO study_breaks (id, session_id, started_at, ended_at, reason, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (_new_id("brk"), session_id, now, None, reason, now),
            )
        return self.get_session(session_id, user_id=user_id)  # type: ignore[return-value]

    def resume(
        self, session_id: str, *, user_id: str
    ) -> StudySessionRow:
        now = _now_iso()
        with self._db.transaction() as conn:
            session = self._get_session(conn, session_id, user_id)
            if session is None:
                raise StudySessionNotFound()
            if session.status != "paused":
                raise InvalidTransition(
                    f"当前状态({session.status})不允许恢复,仅 paused 会话可恢复"
                )
            # 关闭最近一条未结束的休息记录,累加 pause_seconds
            cur = conn.execute(
                """SELECT id, started_at FROM study_breaks
                   WHERE session_id = ? AND ended_at IS NULL
                   ORDER BY started_at DESC LIMIT 1""",
                (session_id,),
            )
            open_break = cur.fetchone()
            added_pause = 0
            if open_break:
                added_pause = _seconds_between(open_break["started_at"], now)
                conn.execute(
                    "UPDATE study_breaks SET ended_at=? WHERE id=?",
                    (now, open_break["id"]),
                )
            conn.execute(
                """UPDATE study_sessions
                   SET status='active', paused_at=NULL,
                       pause_seconds = pause_seconds + ?,
                       updated_at = ?
                   WHERE id = ?""",
                (added_pause, now, session_id),
            )
        return self.get_session(session_id, user_id=user_id)  # type: ignore[return-value]

    def finish(
        self,
        session_id: str,
        *,
        user_id: str,
        self_report: Optional[str] = None,
        self_report_tags: Optional[List[str]] = None,
    ) -> StudySessionRow:
        now = _now_iso()
        with self._db.transaction() as conn:
            session = self._get_session(conn, session_id, user_id)
            if session is None:
                raise StudySessionNotFound()
            if session.status == "completed":
                raise InvalidTransition("会话已结束,不能再次结束")
            if session.status not in ("active", "paused"):
                raise InvalidTransition(
                    f"当前状态({session.status})不允许结束"
                )
            # 关闭未结束的休息记录,累加 pause_seconds
            cur = conn.execute(
                """SELECT id, started_at FROM study_breaks
                   WHERE session_id = ? AND ended_at IS NULL""",
                (session_id,),
            )
            open_breaks = cur.fetchall()
            extra_pause = 0
            for b in open_breaks:
                extra_pause += _seconds_between(b["started_at"], now)
                conn.execute(
                    "UPDATE study_breaks SET ended_at=? WHERE id=?",
                    (now, b["id"]),
                )
            total_pause = session.pause_seconds + extra_pause
            duration = _seconds_between(session.started_at, now) - total_pause
            if duration < 0:
                duration = 0
            tags_json = (
                json.dumps(self_report_tags, ensure_ascii=False)
                if self_report_tags
                else None
            )
            conn.execute(
                """UPDATE study_sessions
                   SET status='completed', ended_at=?, duration_seconds=?,
                       pause_seconds=?, self_report=?,
                       self_report_tags=?, paused_at=NULL, updated_at=?
                   WHERE id = ?""",
                (
                    now,
                    duration,
                    total_pause,
                    self_report,
                    tags_json,
                    now,
                    session_id,
                ),
            )
        return self.get_session(session_id, user_id=user_id)  # type: ignore[return-value]

    # ===== 更新(仅未结束会话) =====

    def update_session(
        self,
        session_id: str,
        *,
        user_id: str,
        goal: Optional[str] = None,
        related_task_id: Optional[str] = None,
        self_report: Optional[str] = None,
        self_report_tags: Optional[List[str]] = None,
        expression_signal: Optional[Any] = None,
    ) -> StudySessionRow:
        """部分更新。仅未结束会话可更新 goal/related_task_id;
        self_report/self_report_tags/expression_signal 可在任意状态下更新
        (结束时的 self_report 由 finish 写入)。
        """
        now = _now_iso()
        with self._db.transaction() as conn:
            session = self._get_session(conn, session_id, user_id)
            if session is None:
                raise StudySessionNotFound()
            sets: List[str] = []
            values: list = []
            # goal / related_task_id 仅未结束时可改
            if session.status != "completed":
                if goal is not None:
                    sets.append("goal = ?")
                    values.append(goal)
                if related_task_id is not None:
                    # 校验新关联的任务属于当前用户且未软删除
                    self._validate_related_task_id(
                        conn, related_task_id or "", user_id
                    )
                    sets.append("related_task_id = ?")
                    values.append(related_task_id)
            # self_report / tags / signal 任意状态可改
            if self_report is not None:
                sets.append("self_report = ?")
                values.append(self_report)
            if self_report_tags is not None:
                sets.append("self_report_tags = ?")
                values.append(
                    json.dumps(self_report_tags, ensure_ascii=False)
                )
            if expression_signal is not None:
                sets.append("expression_signal = ?")
                # expression_signal 可能是 dict/list/str,统一序列化为 JSON 字符串
                if isinstance(expression_signal, str):
                    values.append(expression_signal)
                else:
                    values.append(
                        json.dumps(expression_signal, ensure_ascii=False)
                    )
            if not sets:
                return session
            sets.append("updated_at = ?")
            values.append(now)
            values.append(session_id)
            conn.execute(
                f"UPDATE study_sessions SET {', '.join(sets)} WHERE id = ?",
                values,
            )
        return self.get_session(session_id, user_id=user_id)  # type: ignore[return-value]

    def delete_session(self, session_id: str, *, user_id: str) -> bool:
        with self._db.transaction() as conn:
            cur = conn.execute(
                "SELECT 1 FROM study_sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            )
            if cur.fetchone() is None:
                raise StudySessionNotFound()
            conn.execute(
                "DELETE FROM study_sessions WHERE id = ?", (session_id,)
            )
            return True


__all__ = ["StudySessionRepository"]
