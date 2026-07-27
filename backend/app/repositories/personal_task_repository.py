"""个人待办任务仓库 — 用户隔离 + 软删除 + 原文追溯。

设计要点:
- `user_id` 强制绑定: 所有读写都按 JWT 用户的 `user_id` 过滤,禁止跨用户读取。
- 软删除: `DELETE /tasks/{id}` 仅设置 `deleted_at`,不物理删除。
- 状态机:
    pending --complete--> completed (设置 completed_at)
    completed --restore--> pending (清空 completed_at)
    pending|completed --delete--> deleted (设置 deleted_at)
    deleted --restore--> pending (清空 deleted_at,保留 status='pending')
- 列表查询默认排除 `deleted` 状态(可通过 `include_deleted=true` 显式包含)。
- `materials` 以 JSON 数组字符串存储(如 '["申请表","证明材料"]')。

与 `AssignmentRepository`(教师发布的班级作业)严格分离:
- 仓库层不抛业务异常(留给 route 层),仅返回 Optional / row。
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from ..database.sqlite_db import Database
from ..models.personal_task import PersonalTaskRow


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return f"ptask_{uuid.uuid4().hex[:16]}"


def _dump_materials(materials: Optional[List[str]]) -> Optional[str]:
    if materials is None:
        return None
    return json.dumps(materials, ensure_ascii=False)


def _load_materials(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x) for x in data]
    except (ValueError, TypeError):
        pass
    return []


class PersonalTaskRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    # ===== 创建 =====

    def create_task(
        self,
        *,
        user_id: str,
        title: str,
        description: Optional[str] = None,
        target_students: Optional[str] = None,
        deadline: Optional[str] = None,
        materials: Optional[List[str]] = None,
        submission_method: Optional[str] = None,
        location: Optional[str] = None,
        source_name: Optional[str] = None,
        source_text: Optional[str] = None,
        source_notice_id: Optional[str] = None,
        priority: str = "medium",
        reminder_minutes: Optional[int] = None,
    ) -> PersonalTaskRow:
        tid = _new_id()
        now = _now_iso()
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO personal_tasks (
                    id, user_id, title, description, target_students,
                    deadline, materials, submission_method, location,
                    source_name, source_text, source_notice_id,
                    priority, status, reminder_minutes,
                    created_at, updated_at, completed_at, deleted_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, ?,?,NULL,NULL)""",
                (
                    tid, user_id, title, description, target_students,
                    deadline, _dump_materials(materials), submission_method, location,
                    source_name, source_text, source_notice_id,
                    priority, "pending", reminder_minutes,
                    now, now,
                ),
            )
        # 事务已提交,重新打开连接读取
        return self.get_task(tid, user_id=user_id)  # type: ignore[return-value]

    # ===== 查询 =====

    def get_task(
        self, task_id: str, *, user_id: str
    ) -> Optional[PersonalTaskRow]:
        with self._db.query() as conn:
            return self._get_task(conn, task_id, user_id)

    def _get_task(
        self, conn, task_id: str, user_id: str
    ) -> Optional[PersonalTaskRow]:
        cur = conn.execute(
            "SELECT * FROM personal_tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id),
        )
        row = cur.fetchone()
        return PersonalTaskRow.from_row(row) if row else None

    def list_tasks(
        self,
        user_id: str,
        *,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        deadline_before: Optional[str] = None,
        deadline_after: Optional[str] = None,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[PersonalTaskRow], int]:
        """列出当前用户的任务。

        - `status`: pending / completed / deleted(默认排除 deleted,除非 include_deleted=True)
        - `deadline_before` / `deadline_after`: ISO 8601,用于"即将截止"筛选
        - 返回按 `created_at DESC` 排序
        """
        conditions = ["user_id = ?"]
        params: list = [user_id]
        if status:
            conditions.append("status = ?")
            params.append(status)
        elif not include_deleted:
            conditions.append("status != 'deleted'")
        if priority:
            conditions.append("priority = ?")
            params.append(priority)
        if deadline_before:
            conditions.append("deadline <= ?")
            params.append(deadline_before)
        if deadline_after:
            conditions.append("deadline >= ?")
            params.append(deadline_after)
        where = " WHERE " + " AND ".join(conditions)
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            cur = conn.execute(
                f"SELECT COUNT(*) AS n FROM personal_tasks{where}", params
            )
            total = int(cur.fetchone()["n"])
            cur = conn.execute(
                f"""SELECT * FROM personal_tasks{where}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?""",
                params + [page_size, offset],
            )
            rows = cur.fetchall()
        return [PersonalTaskRow.from_row(r) for r in rows], total

    def list_recent_pending(
        self, user_id: str, *, limit: int = 5
    ) -> List[PersonalTaskRow]:
        """返回最近未完成且未删除的任务(按 deadline 升序,无 deadline 排在后面)。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT * FROM personal_tasks
                   WHERE user_id = ? AND status = 'pending'
                   ORDER BY
                       CASE WHEN deadline IS NULL THEN 1 ELSE 0 END,
                       deadline ASC,
                       created_at DESC
                   LIMIT ?""",
                (user_id, limit),
            )
            rows = cur.fetchall()
        return [PersonalTaskRow.from_row(r) for r in rows]

    def count_pending(self, user_id: str) -> int:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT COUNT(*) AS n FROM personal_tasks WHERE user_id = ? AND status = 'pending'",
                (user_id,),
            )
            return int(cur.fetchone()["n"])

    def count_overdue(self, user_id: str, *, now_iso: str) -> int:
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT COUNT(*) AS n FROM personal_tasks
                   WHERE user_id = ? AND status = 'pending'
                     AND deadline IS NOT NULL AND deadline < ?""",
                (user_id, now_iso),
            )
            return int(cur.fetchone()["n"])

    # ===== 更新 =====

    def update_task(
        self,
        task_id: str,
        *,
        user_id: str,
        fields: dict,
    ) -> Optional[PersonalTaskRow]:
        """部分更新。

        允许字段: title/description/target_students/deadline/materials/
                  submission_method/location/source_name/source_text/
                  source_notice_id/priority/reminder_minutes
        不允许通过此方法修改 status/completed_at/deleted_at/user_id。
        """
        if not fields:
            return self._get_task_with_open_conn(task_id, user_id)
        allowed = {
            "title", "description", "target_students", "deadline",
            "materials", "submission_method", "location", "source_name",
            "source_text", "source_notice_id", "priority", "reminder_minutes",
        }
        sets: List[str] = []
        values: List[Any] = []
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key == "materials":
                value = _dump_materials(value)
            sets.append(f"{key} = ?")
            values.append(value)
        if not sets:
            return self._get_task_with_open_conn(task_id, user_id)
        sets.append("updated_at = ?")
        values.append(_now_iso())
        values.append(task_id)
        with self._db.transaction() as conn:
            existing = self._get_task(conn, task_id, user_id)
            if existing is None:
                return None
            # 已删除任务禁止更新(需先 restore)
            if existing.status == "deleted":
                return None
            conn.execute(
                f"UPDATE personal_tasks SET {', '.join(sets)} WHERE id = ?",
                values,
            )
        return self.get_task(task_id, user_id=user_id)

    def _get_task_with_open_conn(
        self, task_id: str, user_id: str
    ) -> Optional[PersonalTaskRow]:
        with self._db.query() as conn:
            return self._get_task(conn, task_id, user_id)

    # ===== 状态机 =====

    def complete(
        self, task_id: str, *, user_id: str
    ) -> Optional[PersonalTaskRow]:
        """标记为已完成。仅 pending 可完成;已完成/已删除返回 None。"""
        now = _now_iso()
        with self._db.transaction() as conn:
            existing = self._get_task(conn, task_id, user_id)
            if existing is None:
                return None
            if existing.status != "pending":
                return None
            conn.execute(
                """UPDATE personal_tasks
                   SET status = 'completed', completed_at = ?, updated_at = ?
                   WHERE id = ?""",
                (now, now, task_id),
            )
        return self.get_task(task_id, user_id=user_id)

    def restore(
        self, task_id: str, *, user_id: str
    ) -> Optional[PersonalTaskRow]:
        """恢复为 pending(从 completed 或 deleted 状态)。"""
        now = _now_iso()
        with self._db.transaction() as conn:
            existing = self._get_task(conn, task_id, user_id)
            if existing is None:
                return None
            if existing.status == "pending":
                # 已是 pending,无需变更,但仍返回当前行
                return existing
            conn.execute(
                """UPDATE personal_tasks
                   SET status = 'pending', completed_at = NULL, deleted_at = NULL,
                       updated_at = ?
                   WHERE id = ?""",
                (now, task_id),
            )
        return self.get_task(task_id, user_id=user_id)

    def soft_delete(
        self, task_id: str, *, user_id: str
    ) -> Optional[PersonalTaskRow]:
        """软删除:设置 deleted_at 与 status='deleted'。"""
        now = _now_iso()
        with self._db.transaction() as conn:
            existing = self._get_task(conn, task_id, user_id)
            if existing is None:
                return None
            if existing.status == "deleted":
                # 已删除,幂等返回
                return existing
            conn.execute(
                """UPDATE personal_tasks
                   SET status = 'deleted', deleted_at = ?, updated_at = ?
                   WHERE id = ?""",
                (now, now, task_id),
            )
        return self.get_task(task_id, user_id=user_id)


__all__ = ["PersonalTaskRepository"]
