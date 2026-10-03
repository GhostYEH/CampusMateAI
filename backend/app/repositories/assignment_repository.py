"""SQLite data access for AssignmentRepository."""
from __future__ import annotations

import json
from typing import List, Optional
from ..database.sqlite_db import Database
from ..models.multi_role import AssignmentAttachmentRow, AssignmentRow
from ._multi_role_common import _new_id, _now_iso


class AssignmentRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create_assignment(
        self,
        *,
        class_group_id: str,
        author_id: str,
        title: str,
        description: Optional[str] = None,
        deadline: Optional[str] = None,
        submission_types: Optional[List[str]] = None,
        max_score: Optional[float] = None,
        allow_resubmit: bool = True,
        status: str = "draft",
    ) -> AssignmentRow:
        aid = _new_id("asg")
        now = _now_iso()
        types_json = json.dumps(submission_types, ensure_ascii=False) if submission_types else None
        published_at = now if status == "published" else None
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO assignments
                   (id, class_group_id, author_id, title, description, deadline,
                    submission_types, max_score, allow_resubmit, status, published_at,
                    created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (aid, class_group_id, author_id, title, description, deadline,
                 types_json, max_score, int(allow_resubmit), status, published_at,
                 now, now),
            )
        return self.get_assignment(aid)  # type: ignore[return-value]

    def get_assignment(self, assignment_id: str) -> Optional[AssignmentRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM assignments WHERE id = ?", (assignment_id,)
            )
            row = cur.fetchone()
            return AssignmentRow.from_row(row) if row else None

    def update_assignment(
        self, assignment_id: str, *, fields: dict
    ) -> Optional[AssignmentRow]:
        if not fields:
            return self.get_assignment(assignment_id)
        allowed = {
            "title", "description", "deadline", "submission_types",
            "max_score", "allow_resubmit", "status",
        }
        sets = []
        values: list = []
        for k, v in fields.items():
            if k not in allowed:
                continue
            if k == "status" and v not in ("draft", "published", "closed", "archived"):
                continue
            if k == "allow_resubmit":
                v = int(bool(v))
            if k == "submission_types" and isinstance(v, list):
                v = json.dumps(v, ensure_ascii=False)
            sets.append(f"{k} = ?")
            values.append(v)
        if not sets:
            return self.get_assignment(assignment_id)
        sets.append("updated_at = ?")
        values.append(_now_iso())
        values.append(assignment_id)
        with self._db.transaction() as conn:
            conn.execute(
                f"UPDATE assignments SET {', '.join(sets)} WHERE id = ?",
                values,
            )
        return self.get_assignment(assignment_id)

    def publish(self, assignment_id: str) -> Optional[AssignmentRow]:
        now = _now_iso()
        with self._db.transaction() as conn:
            cur = conn.execute(
                """UPDATE assignments SET status = 'published', published_at = ?, updated_at = ?
                   WHERE id = ? AND status = 'draft'""",
                (now, now, assignment_id),
            )
            if cur.rowcount == 0:
                return None
        return self.get_assignment(assignment_id)

    def close(self, assignment_id: str) -> Optional[AssignmentRow]:
        now = _now_iso()
        with self._db.transaction() as conn:
            cur = conn.execute(
                """UPDATE assignments SET status = 'closed', updated_at = ?
                   WHERE id = ? AND status = 'published'""",
                (now, assignment_id),
            )
            if cur.rowcount == 0:
                return None
        return self.get_assignment(assignment_id)

    def list_assignments(
        self,
        class_group_id: str,
        *,
        status: Optional[str] = "published",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[AssignmentRow], int]:
        conditions = ["class_group_id = ?"]
        params: list = [class_group_id]
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = " WHERE " + " AND ".join(conditions)
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            cur = conn.execute(
                f"SELECT COUNT(*) AS n FROM assignments{where}", params
            )
            total = int(cur.fetchone()["n"])
            cur = conn.execute(
                f"""SELECT * FROM assignments{where}
                    ORDER BY deadline ASC NULLS LAST, created_at DESC
                    LIMIT ? OFFSET ?""",
                params + [page_size, offset],
            )
            rows = cur.fetchall()
        return [AssignmentRow.from_row(r) for r in rows], total

    def list_assignments_for_student(
        self,
        user_id: str,
        *,
        due_within_days: Optional[int] = None,
        submission_status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "deadline",
        sort_desc: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[dict], int]:
        """列出学生所在班级的所有已发布任务(含班级/课程信息)。"""
        conditions = [
            "assignments.status IN ('published','closed')",
            "enrollments.user_id = ?",
            "enrollments.status = 'active'",
        ]
        params: list = [user_id]
        now = _now_iso()
        if due_within_days is not None:
            conditions.append(
                "assignments.deadline IS NOT NULL AND assignments.deadline >= ?"
            )
            params.append(now)
        if search:
            conditions.append("assignments.title LIKE ?")
            params.append(f"%{search}%")
        if submission_status == "submitted":
            conditions.append(
                "submissions.status IN ('submitted','resubmitted','late')"
            )
        elif submission_status == "graded":
            conditions.append("submissions.score IS NOT NULL")
        elif submission_status == "pending":
            conditions.append(
                "(submissions.status IS NULL OR submissions.status = 'draft') "
                "AND (assignments.deadline IS NULL OR assignments.deadline >= ?)"
            )
            params.append(now)
        elif submission_status == "overdue":
            conditions.append(
                "(submissions.status IS NULL OR submissions.status = 'draft') "
                "AND assignments.deadline IS NOT NULL AND assignments.deadline < ?"
            )
            params.append(now)
        where = " WHERE " + " AND ".join(conditions)
        sort_columns = {
            "deadline": "assignments.deadline",
            "created_at": "assignments.created_at",
            "title": "assignments.title",
        }
        order_column = sort_columns.get(sort_by, "assignments.deadline")
        order_direction = "DESC" if sort_desc else "ASC"
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            cur = conn.execute(
                f"""SELECT COUNT(*) AS n FROM assignments
                    JOIN class_groups ON class_groups.id = assignments.class_group_id
                    JOIN enrollments ON enrollments.class_group_id = class_groups.id
                    LEFT JOIN submissions ON submissions.assignment_id = assignments.id
                        AND submissions.student_id = enrollments.user_id
                    {where}""",
                params,
            )
            total = int(cur.fetchone()["n"])
            cur = conn.execute(
                f"""SELECT assignments.id AS assignment_id, assignments.class_group_id,
                           assignments.title, assignments.description, assignments.deadline,
                           assignments.submission_types, assignments.max_score,
                           assignments.allow_resubmit, assignments.status, assignments.published_at,
                           assignments.created_at, assignments.author_id,
                           class_groups.name AS class_name, class_groups.course_id,
                           courses.name AS course_name, courses.code AS course_code,
                           courses.teacher_id AS teacher_id,
                           submissions.status AS submission_status,
                           submissions.score AS submission_score
                    FROM assignments
                    JOIN class_groups ON class_groups.id = assignments.class_group_id
                    JOIN courses ON courses.id = class_groups.course_id
                    JOIN enrollments ON enrollments.class_group_id = class_groups.id
                    LEFT JOIN submissions ON submissions.assignment_id = assignments.id
                        AND submissions.student_id = enrollments.user_id
                    {where}
                    ORDER BY {order_column} {order_direction} NULLS LAST
                    LIMIT ? OFFSET ?""",
                params + [page_size, offset],
            )
            rows = cur.fetchall()
        items = []
        for r in rows:
            submission_types = (
                json.loads(r["submission_types"])
                if r["submission_types"]
                else []
            )
            items.append({
                "id": r["assignment_id"],
                "assignment_id": r["assignment_id"],
                "class_id": r["class_group_id"],
                "class_group_id": r["class_group_id"],
                "title": r["title"],
                "description": r["description"],
                "deadline": r["deadline"],
                "submission_types": submission_types,
                "submission_type": (
                    "both" if len(submission_types) > 1
                    else submission_types[0] if submission_types
                    else "text"
                ),
                "max_score": r["max_score"],
                "allow_resubmit": bool(r["allow_resubmit"]),
                "status": r["status"],
                "submission_status": r["submission_status"] or "not_submitted",
                "submission_score": r["submission_score"],
                "published_at": r["published_at"],
                "created_at": r["created_at"],
                "author_id": r["author_id"],
                "class_name": r["class_name"],
                "course_id": r["course_id"],
                "course_name": r["course_name"],
                "course_code": r["course_code"],
                "teacher_id": r["teacher_id"],
            })
        return items, total

    def count_active_assignments(self, teacher_id: str) -> int:
        """教师所辖班级中已发布且未关闭的任务数。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT COUNT(*) AS n FROM assignments
                   JOIN class_groups ON class_groups.id = assignments.class_group_id
                   JOIN courses ON courses.id = class_groups.course_id
                   WHERE courses.teacher_id = ? AND assignments.status = 'published'""",
                (teacher_id,),
            )
            return int(cur.fetchone()["n"])

    # ===== 任务附件 =====

    def add_attachment(
        self,
        *,
        assignment_id: str,
        author_id: str,
        original_filename: str,
        stored_filename: str,
        mime_type: Optional[str],
        size_bytes: int,
        storage_path: str,
    ) -> AssignmentAttachmentRow:
        aid = _new_id("aatt")
        now = _now_iso()
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO assignment_attachments
                   (id, assignment_id, author_id, original_filename, stored_filename,
                    mime_type, size_bytes, storage_path, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (aid, assignment_id, author_id, original_filename, stored_filename,
                 mime_type, size_bytes, storage_path, now),
            )
        return self.get_attachment(aid)  # type: ignore[return-value]

    def get_attachment(self, attachment_id: str) -> Optional[AssignmentAttachmentRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM assignment_attachments WHERE id = ?",
                (attachment_id,),
            )
            row = cur.fetchone()
            return AssignmentAttachmentRow.from_row(row) if row else None

    def list_attachments(self, assignment_id: str) -> List[AssignmentAttachmentRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM assignment_attachments WHERE assignment_id = ? ORDER BY created_at ASC",
                (assignment_id,),
            )
            return [AssignmentAttachmentRow.from_row(r) for r in cur.fetchall()]

    def list_attachments_for_assignments(self, assignment_ids: List[str]) -> dict[str, List[AssignmentAttachmentRow]]:
        ids = list(dict.fromkeys(assignment_ids))
        if not ids:
            return {}
        placeholders = ",".join("?" for _ in ids)
        with self._db.query() as conn:
            rows = conn.execute(
                f"SELECT * FROM assignment_attachments WHERE assignment_id IN ({placeholders}) ORDER BY created_at ASC",
                ids,
            ).fetchall()
        grouped: dict[str, List[AssignmentAttachmentRow]] = {}
        for row in rows:
            attachment = AssignmentAttachmentRow.from_row(row)
            grouped.setdefault(attachment.assignment_id, []).append(attachment)
        return grouped

    def delete_attachment(self, attachment_id: str) -> Optional[str]:
        """Delete attachment and return its storage_path for file cleanup."""
        with self._db.transaction() as conn:
            cur = conn.execute(
                "SELECT storage_path FROM assignment_attachments WHERE id = ?",
                (attachment_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            conn.execute(
                "DELETE FROM assignment_attachments WHERE id = ?",
                (attachment_id,),
            )
            return row["storage_path"]
