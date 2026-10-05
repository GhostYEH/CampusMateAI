"""SQLite data access for SubmissionRepository."""
from __future__ import annotations

import json
from typing import List, Optional
from ..database.sqlite_db import Database
from ..models.multi_role import SubmissionAttachmentRow, SubmissionRow
from ._multi_role_common import _new_id, _now_iso


class SubmissionRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    @staticmethod
    def _assert_student_write_allowed(conn, assignment_id: str, existing_status: Optional[str]) -> None:
        from ..core.exceptions import AssignmentClosed, AssignmentNotFound, ResubmitNotAllowed

        assignment = conn.execute(
            "SELECT status, allow_resubmit FROM assignments WHERE id = ?", (assignment_id,),
        ).fetchone()
        if not assignment or assignment["status"] not in ("published", "closed"):
            raise AssignmentNotFound()
        if assignment["status"] == "closed" and not assignment["allow_resubmit"]:
            raise AssignmentClosed()
        if existing_status and existing_status != "draft" and not assignment["allow_resubmit"]:
            raise ResubmitNotAllowed()

    def upsert_submission(
        self,
        *,
        assignment_id: str,
        student_id: str,
        text_content: Optional[str] = None,
        status: str = "draft",
        student_write: bool = False,
    ) -> SubmissionRow:
        """新建或更新提交(UNIQUE(assignment_id, student_id) 保证幂等)。"""
        now = _now_iso()
        submitted_at = now if status in ("submitted", "resubmitted", "late") else None
        # 学生写入需要在读改写前预占写锁，包括其他 Database 连接/进程，
        # 否则并发提交可以绕过截止校验。用 transaction(immediate=True)
        # 让最外层事务负责预占，不再在事务内手动 BEGIN。
        with self._db.transaction(immediate=student_write) as conn:
            cur = conn.execute(
                "SELECT id, status FROM submissions WHERE assignment_id = ? AND student_id = ?",
                (assignment_id, student_id),
            )
            existing = cur.fetchone()
            if student_write:
                self._assert_student_write_allowed(conn, assignment_id, existing["status"] if existing else None)
                if existing and existing["status"] != "draft":
                    if status in {"submitted", "graded"}:
                        status = "resubmitted"
                        submitted_at = now
            if existing:
                sid = existing["id"]
                conn.execute(
                    """UPDATE submissions
                       SET text_content = ?, status = ?, submitted_at = ?, updated_at = ?
                       WHERE id = ?""",
                    (text_content, status, submitted_at, now, sid),
                )
                if student_write:
                    # A grade belongs to the previous content, never to a new
                    # draft or resubmission.
                    conn.execute(
                        "UPDATE submissions SET score = NULL, teacher_comment = NULL WHERE id = ?",
                        (sid,),
                    )
            else:
                sid = _new_id("sub")
                conn.execute(
                    """INSERT INTO submissions
                       (id, assignment_id, student_id, text_content, status,
                        submitted_at, updated_at, score, teacher_comment)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (sid, assignment_id, student_id, text_content, status,
                     submitted_at, now, None, None),
                )
        return self.get_submission(sid)  # type: ignore[return-value]

    def get_submission(self, submission_id: str) -> Optional[SubmissionRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM submissions WHERE id = ?", (submission_id,)
            )
            row = cur.fetchone()
            return SubmissionRow.from_row(row) if row else None

    def get_submission_for_student(
        self, assignment_id: str, student_id: str
    ) -> Optional[SubmissionRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM submissions WHERE assignment_id = ? AND student_id = ?",
                (assignment_id, student_id),
            )
            row = cur.fetchone()
            return SubmissionRow.from_row(row) if row else None

    def get_submission_statuses_for_student(
        self, assignment_ids: List[str], student_id: str,
    ) -> dict[str, str]:
        """一次读取学生对一组作业的提交状态，供课程作业列表使用。"""
        ids = list(dict.fromkeys(assignment_ids))
        if not ids:
            return {}
        placeholders = ", ".join("?" for _ in ids)
        with self._db.query() as conn:
            cur = conn.execute(
                f"""SELECT assignment_id, status FROM submissions
                    WHERE student_id = ? AND assignment_id IN ({placeholders})""",
                [student_id, *ids],
            )
            return {row["assignment_id"]: row["status"] for row in cur.fetchall()}

    def list_submissions(
        self,
        assignment_id: str,
        *,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[dict], int]:
        conditions = ["submissions.assignment_id = ?"]
        params: list = [assignment_id]
        if status:
            conditions.append("submissions.status = ?")
            params.append(status)
        where = " WHERE " + " AND ".join(conditions)
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            cur = conn.execute(
                f"""SELECT COUNT(*) AS n FROM submissions{where}""", params
            )
            total = int(cur.fetchone()["n"])
            cur = conn.execute(
                f"""SELECT submissions.*, users.username, users.display_name,
                           users.student_number, users.college, users.major, users.grade
                    FROM submissions
                    JOIN users ON users.id = submissions.student_id
                    {where}
                    ORDER BY submissions.submitted_at DESC NULLS LAST
                    LIMIT ? OFFSET ?""",
                params + [page_size, offset],
            )
            rows = cur.fetchall()
        items = []
        for r in rows:
            items.append({
                "id": r["id"],
                "assignment_id": r["assignment_id"],
                "student_id": r["student_id"],
                "student_name": r["display_name"] or r["username"],
                "student_number": r["student_number"],
                "college": r["college"],
                "major": r["major"],
                "grade": r["grade"],
                "text_content": r["text_content"],
                "status": r["status"],
                "submitted_at": r["submitted_at"],
                "updated_at": r["updated_at"],
                "score": r["score"],
                "teacher_comment": r["teacher_comment"],
            })
        return items, total

    def grade(
        self,
        submission_id: str,
        *,
        score: Optional[float],
        teacher_comment: Optional[str],
    ) -> Optional[SubmissionRow]:
        now = _now_iso()
        with self._db.transaction() as conn:
            cur = conn.execute(
                """UPDATE submissions SET score = ?, teacher_comment = ?, updated_at = ?
                   WHERE id = ?""",
                (score, teacher_comment, now, submission_id),
            )
            if cur.rowcount == 0:
                return None
        return self.get_submission(submission_id)

    def count_pending_submissions(self, teacher_id: str) -> int:
        """教师所辖任务中已提交但未评分的数量。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT COUNT(*) AS n FROM submissions
                   JOIN assignments ON assignments.id = submissions.assignment_id
                   JOIN class_groups ON class_groups.id = assignments.class_group_id
                   JOIN courses ON courses.id = class_groups.course_id
                   WHERE courses.teacher_id = ?
                     AND submissions.status IN ('submitted','resubmitted','late')
                     AND submissions.score IS NULL""",
                (teacher_id,),
            )
            return int(cur.fetchone()["n"])

    # ===== 附件 =====

    def add_attachment(
        self,
        *,
        submission_id: str,
        original_filename: str,
        stored_filename: str,
        mime_type: Optional[str],
        size_bytes: int,
        storage_path: str,
        student_write: bool = False,
    ) -> SubmissionAttachmentRow:
        aid = _new_id("att")
        now = _now_iso()
        # 学生写入沿用与 upsert_submission 相同的 student_write 条件预占写锁。
        with self._db.transaction(immediate=student_write) as conn:
            if student_write:
                from ..core.exceptions import SubmissionNotFound

                submission = conn.execute(
                    "SELECT assignment_id, status FROM submissions WHERE id = ?", (submission_id,),
                ).fetchone()
                if not submission:
                    raise SubmissionNotFound()
                self._assert_student_write_allowed(conn, submission["assignment_id"], submission["status"])
                if submission["status"] != "draft":
                    conn.execute(
                        "UPDATE submissions SET score=NULL, teacher_comment=NULL, status=?, "
                        "submitted_at=?, updated_at=? WHERE id=?",
                        ("late" if submission["status"] == "late" else "resubmitted", now, now, submission_id),
                    )
            conn.execute(
                """INSERT INTO submission_attachments
                   (id, submission_id, original_filename, stored_filename,
                    mime_type, size_bytes, storage_path, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (aid, submission_id, original_filename, stored_filename,
                 mime_type, size_bytes, storage_path, now),
            )
        return self.get_attachment(aid)  # type: ignore[return-value]

    def get_attachment(self, attachment_id: str) -> Optional[SubmissionAttachmentRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM submission_attachments WHERE id = ?",
                (attachment_id,),
            )
            row = cur.fetchone()
            return SubmissionAttachmentRow.from_row(row) if row else None

    def list_attachments(self, submission_id: str) -> List[SubmissionAttachmentRow]:
        with self._db.query() as conn:
            cur = conn.execute(
                "SELECT * FROM submission_attachments WHERE submission_id = ? ORDER BY created_at ASC",
                (submission_id,),
            )
            return [SubmissionAttachmentRow.from_row(r) for r in cur.fetchall()]

    def delete_attachment(self, attachment_id: str) -> Optional[str]:
        """删除附件,返回其 storage_path(用于清理文件)。"""
        with self._db.transaction() as conn:
            cur = conn.execute(
                "SELECT storage_path FROM submission_attachments WHERE id = ?",
                (attachment_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            conn.execute(
                "DELETE FROM submission_attachments WHERE id = ?",
                (attachment_id,),
            )
            return row["storage_path"]

    # ===== 聚合统计 =====

    def assignment_stats(self, assignment_id: str, *, total_students: int) -> dict:
        """单任务的统计(单条聚合 SQL,避免 N+1)。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT
                       COUNT(*) AS total_submissions,
                       SUM(CASE WHEN status = 'submitted' THEN 1 ELSE 0 END) AS submitted,
                       SUM(CASE WHEN status = 'resubmitted' THEN 1 ELSE 0 END) AS resubmitted,
                       SUM(CASE WHEN status = 'late' THEN 1 ELSE 0 END) AS late,
                       SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END) AS draft,
                       SUM(CASE WHEN score IS NOT NULL THEN 1 ELSE 0 END) AS graded,
                       AVG(score) AS avg_score
                   FROM submissions
                   WHERE assignment_id = ?""",
                (assignment_id,),
            )
            row = cur.fetchone()
        submitted_total = int(row["submitted"] or 0) + int(row["resubmitted"] or 0) + int(row["late"] or 0)
        draft = int(row["draft"] or 0)
        graded = int(row["graded"] or 0)
        avg_score = float(row["avg_score"]) if row["avg_score"] is not None else None
        return {
            "assignment_id": assignment_id,
            "total_students": total_students,
            "submitted": submitted_total,
            "not_submitted": max(0, total_students - submitted_total - draft),
            "draft": draft,
            "late": int(row["late"] or 0),
            "graded": graded,
            "pending_grading": max(0, submitted_total - graded),
            "avg_score": avg_score,
        }

    def student_status(
        self,
        assignment_id: str,
        class_group_id: str,
        *,
        submission_status: Optional[str] = None,
        read_status: Optional[str] = None,
        query: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> tuple[List[dict], int]:
        """聚合查询每个学生的状态(提交状态/逾期/成绩)。

        read_status 字段对任务而言为 "not_required"(任务本身不要求已读回执,
        该字段保留用于前端兼容;若班级有同名通知可后续扩展关联)。
        使用 LEFT JOIN submissions,避免逐学生查询。
        """
        conditions = [
            "enrollments.class_group_id = ?",
            "enrollments.status = 'active'",
            "enrollments.member_role = 'student'",
        ]
        params: list = [class_group_id]
        if query:
            conditions.append(
                "(users.username LIKE ? OR users.display_name LIKE ? OR users.student_number LIKE ?)"
            )
            like = f"%{query}%"
            params.extend([like, like, like])
        if submission_status:
            if submission_status == "not_submitted":
                conditions.append("(submissions.status IS NULL OR submissions.status = 'draft')")
            else:
                conditions.append("submissions.status = ?")
                params.append(submission_status)
        # read_status 过滤对任务无意义(任务不要求已读回执),忽略以避免误导
        where = " WHERE " + " AND ".join(conditions)
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            cur = conn.execute(
                f"""SELECT COUNT(*) AS n FROM enrollments
                    JOIN users ON users.id = enrollments.user_id
                    LEFT JOIN submissions ON submissions.assignment_id = ?
                        AND submissions.student_id = enrollments.user_id
                    {where}""",
                [assignment_id] + params,
            )
            total = int(cur.fetchone()["n"])
            cur = conn.execute(
                f"""SELECT users.id AS student_id, users.username,
                           users.display_name AS student_name,
                           users.student_number,
                           submissions.id AS submission_id,
                           submissions.status AS submission_status,
                           submissions.submitted_at,
                           submissions.score,
                           submissions.teacher_comment,
                           assignments.deadline
                    FROM enrollments
                    JOIN users ON users.id = enrollments.user_id
                    LEFT JOIN submissions ON submissions.assignment_id = ?
                        AND submissions.student_id = enrollments.user_id
                    LEFT JOIN assignments ON assignments.id = ?
                    {where}
                    ORDER BY users.student_number ASC NULLS LAST, users.username ASC
                    LIMIT ? OFFSET ?""",
                [assignment_id, assignment_id] + params + [page_size, offset],
            )
            rows = cur.fetchall()
        items = []
        for r in rows:
            sub_status = r["submission_status"]
            submitted_at = r["submitted_at"]
            deadline = r["deadline"]
            is_late = False
            if sub_status in ("submitted", "resubmitted", "late"):
                if deadline and submitted_at and submitted_at > deadline:
                    is_late = True
                    sub_status_display = "late"
                else:
                    sub_status_display = sub_status
            else:
                sub_status_display = sub_status if sub_status else "not_submitted"
            items.append({
                "student_id": r["student_id"],
                "student_name": r["student_name"] or r["username"],
                "student_number": r["student_number"],
                "submission_id": r["submission_id"],
                "submission_status": sub_status_display,
                "submitted_at": submitted_at,
                "is_late": is_late,
                "score": r["score"],
                "teacher_comment": r["teacher_comment"],
                "read_status": "not_required",
                "read_at": None,
            })
        return items, total

    def count_student_pending_assignments(self, user_id: str, *, now_iso: str) -> int:
        """学生未提交且未过期的任务数。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT COUNT(*) AS n FROM assignments
                   JOIN class_groups ON class_groups.id = assignments.class_group_id
                   JOIN enrollments ON enrollments.class_group_id = class_groups.id
                   LEFT JOIN submissions ON submissions.assignment_id = assignments.id
                       AND submissions.student_id = enrollments.user_id
                   WHERE enrollments.user_id = ? AND enrollments.status = 'active'
                     AND assignments.status = 'published'
                     AND (submissions.status IS NULL OR submissions.status = 'draft')
                     AND (assignments.deadline IS NULL OR assignments.deadline >= ?)
                """,
                (user_id, now_iso),
            )
            return int(cur.fetchone()["n"])

    def count_student_overdue_assignments(self, user_id: str, *, now_iso: str) -> int:
        """学生已逾期的任务数(deadline < now 且未提交)。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT COUNT(*) AS n FROM assignments
                   JOIN class_groups ON class_groups.id = assignments.class_group_id
                   JOIN enrollments ON enrollments.user_id = ?
                       AND enrollments.class_group_id = class_groups.id
                       AND enrollments.status = 'active'
                   LEFT JOIN submissions ON submissions.assignment_id = assignments.id
                       AND submissions.student_id = enrollments.user_id
                   WHERE assignments.status = 'published'
                     AND assignments.deadline IS NOT NULL
                     AND assignments.deadline < ?
                     AND (submissions.status IS NULL
                          OR submissions.status NOT IN ('submitted','resubmitted','late'))
                """,
                (user_id, now_iso),
            )
            return int(cur.fetchone()["n"])

    def count_student_unread_announcements(self, user_id: str) -> int:
        """学生未读且 require_read=1 的已发布通知数。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT COUNT(*) AS n FROM announcements
                   JOIN class_groups ON class_groups.id = announcements.class_group_id
                   JOIN enrollments ON enrollments.user_id = ?
                       AND enrollments.class_group_id = class_groups.id
                       AND enrollments.status = 'active'
                   LEFT JOIN announcement_read_receipts receipt
                       ON receipt.announcement_id = announcements.id
                       AND receipt.student_id = enrollments.user_id
                   WHERE announcements.status = 'published'
                     AND announcements.require_read = 1
                     AND receipt.read_at IS NULL
                """,
                (user_id,),
            )
            return int(cur.fetchone()["n"])

    def count_student_enrolled_courses(self, user_id: str) -> int:
        """学生加入的不同课程数。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT COUNT(DISTINCT courses.id) AS n
                   FROM enrollments
                   JOIN class_groups ON class_groups.id = enrollments.class_group_id
                   JOIN courses ON courses.id = class_groups.course_id
                   WHERE enrollments.user_id = ? AND enrollments.status = 'active'
                """,
                (user_id,),
            )
            return int(cur.fetchone()["n"])

    def count_teacher_unread_announcements(self, teacher_id: str) -> int:
        """教师在自己班级中发布的、需已读但未全部已读的通知数(粗略口径)。

        口径: 每条 require_read=1 的已发布通知,
        若已读人数 < 班级学生数,则视为"有待跟进的未读"。
        """
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT COUNT(*) AS n FROM announcements ann
                   JOIN class_groups cg ON cg.id = ann.class_group_id
                   JOIN courses c ON c.id = cg.course_id
                   WHERE c.teacher_id = ?
                     AND ann.status = 'published'
                     AND ann.require_read = 1
                     AND (SELECT COUNT(*) FROM announcement_read_receipts r
                          WHERE r.announcement_id = ann.id)
                       < (SELECT COUNT(*) FROM enrollments e
                          WHERE e.class_group_id = cg.id AND e.status = 'active'
                            AND e.member_role = 'student')
                """,
                (teacher_id,),
            )
            return int(cur.fetchone()["n"])

    def count_teacher_overdue_students(self, teacher_id: str, *, now_iso: str) -> int:
        """教师所辖任务中已逾期且学生未提交的数量(人次数)。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT COUNT(*) AS n FROM assignments a
                   JOIN class_groups cg ON cg.id = a.class_group_id
                   JOIN courses c ON c.id = cg.course_id
                   JOIN enrollments e ON e.class_group_id = cg.id
                       AND e.status = 'active' AND e.member_role = 'student'
                   LEFT JOIN submissions s ON s.assignment_id = a.id
                       AND s.student_id = e.user_id
                   WHERE c.teacher_id = ?
                     AND a.status = 'published'
                     AND a.deadline IS NOT NULL
                     AND a.deadline < ?
                     AND (s.status IS NULL OR s.status NOT IN ('submitted','resubmitted','late'))
                """,
                (teacher_id, now_iso),
            )
            return int(cur.fetchone()["n"])

    def count_teacher_students(self, teacher_id: str) -> int:
        """教师所辖班级的不同学生数。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT COUNT(DISTINCT e.user_id) AS n
                   FROM enrollments e
                   JOIN class_groups cg ON cg.id = e.class_group_id
                   JOIN courses c ON c.id = cg.course_id
                   WHERE c.teacher_id = ? AND e.status = 'active'
                     AND e.member_role = 'student'
                """,
                (teacher_id,),
            )
            return int(cur.fetchone()["n"])

    def recent_teacher_assignments(self, teacher_id: str, *, limit: int = 5) -> List[dict]:
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT a.id, a.title, a.status, a.deadline, a.published_at,
                          cg.id AS class_id, cg.name AS class_name,
                          c.id AS course_id, c.name AS course_name
                   FROM assignments a
                   JOIN class_groups cg ON cg.id = a.class_group_id
                   JOIN courses c ON c.id = cg.course_id
                   WHERE c.teacher_id = ?
                   ORDER BY a.created_at DESC
                   LIMIT ?""",
                (teacher_id, limit),
            )
            rows = cur.fetchall()
        return [
            {
                "assignment_id": r["id"],
                "title": r["title"],
                "status": r["status"],
                "deadline": r["deadline"],
                "published_at": r["published_at"],
                "class_id": r["class_id"],
                "class_name": r["class_name"],
                "course_id": r["course_id"],
                "course_name": r["course_name"],
            }
            for r in rows
        ]

    def recent_student_announcements(self, user_id: str, *, limit: int = 5) -> List[dict]:
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT ann.id, ann.title, ann.published_at, ann.require_read,
                          cg.id AS class_id, cg.name AS class_name,
                          c.id AS course_id, c.name AS course_name,
                          receipt.read_at
                   FROM announcements ann
                   JOIN class_groups cg ON cg.id = ann.class_group_id
                   JOIN courses c ON c.id = cg.course_id
                   JOIN enrollments e ON e.class_group_id = cg.id AND e.user_id = ?
                       AND e.status = 'active'
                   LEFT JOIN announcement_read_receipts receipt
                       ON receipt.announcement_id = ann.id AND receipt.student_id = e.user_id
                   WHERE ann.status = 'published'
                   ORDER BY ann.published_at DESC NULLS LAST
                   LIMIT ?""",
                (user_id, limit),
            )
            rows = cur.fetchall()
        return [
            {
                "announcement_id": r["id"],
                "title": r["title"],
                "published_at": r["published_at"],
                "require_read": bool(r["require_read"]),
                "class_id": r["class_id"],
                "class_name": r["class_name"],
                "course_id": r["course_id"],
                "course_name": r["course_name"],
                "read_at": r["read_at"],
            }
            for r in rows
        ]

    def recent_student_assignments(
        self, user_id: str, *, due_within_days: int = 7, now_iso: str, limit: int = 5
    ) -> List[dict]:
        """列出学生最近 N 天内到期的任务。"""
        with self._db.query() as conn:
            cur = conn.execute(
                """SELECT a.id, a.title, a.deadline, a.status,
                          cg.id AS class_id, cg.name AS class_name,
                          c.id AS course_id, c.name AS course_name,
                          s.id AS submission_id, s.status AS submission_status
                   FROM assignments a
                   JOIN class_groups cg ON cg.id = a.class_group_id
                   JOIN courses c ON c.id = cg.course_id
                   JOIN enrollments e ON e.class_group_id = cg.id AND e.user_id = ?
                       AND e.status = 'active'
                   LEFT JOIN submissions s ON s.assignment_id = a.id AND s.student_id = e.user_id
                   WHERE a.status = 'published' AND a.deadline IS NOT NULL
                       AND a.deadline >= ?
                       AND a.deadline <= datetime(?, '+' || ? || ' days')
                   ORDER BY a.deadline ASC
                   LIMIT ?""",
                (user_id, now_iso, now_iso, due_within_days, limit),
            )
            rows = cur.fetchall()
        return [
            {
                "assignment_id": r["id"],
                "title": r["title"],
                "deadline": r["deadline"],
                "status": r["status"],
                "class_id": r["class_id"],
                "class_name": r["class_name"],
                "course_id": r["course_id"],
                "course_name": r["course_name"],
                "submission_id": r["submission_id"],
                "submission_status": r["submission_status"],
            }
            for r in rows
        ]

    # ===== 教师视角跨班级聚合查询(用于教师端列表/批改/学情) =====

    def list_assignments_for_teacher(
        self,
        teacher_id: str,
        *,
        status: Optional[str] = None,
        class_id: Optional[str] = None,
        course_id: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[dict], int]:
        """列出教师所辖课程下的所有任务(含班级/课程名 + 提交统计)。"""
        conditions = ["courses.teacher_id = ?"]
        params: list = [teacher_id]
        if status:
            conditions.append("assignments.status = ?")
            params.append(status)
        if class_id:
            conditions.append("assignments.class_group_id = ?")
            params.append(class_id)
        if course_id:
            conditions.append("class_groups.course_id = ?")
            params.append(course_id)
        if search:
            conditions.append("assignments.title LIKE ?")
            params.append(f"%{search}%")
        where = " WHERE " + " AND ".join(conditions)
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            cur = conn.execute(
                f"""SELECT COUNT(*) AS n FROM assignments
                    JOIN class_groups ON class_groups.id = assignments.class_group_id
                    JOIN courses ON courses.id = class_groups.course_id
                    {where}""",
                params,
            )
            total = int(cur.fetchone()["n"])
            cur = conn.execute(
                f"""SELECT assignments.id, assignments.class_group_id, assignments.author_id,
                           assignments.title, assignments.description, assignments.deadline,
                           assignments.submission_types, assignments.max_score,
                           assignments.allow_resubmit, assignments.status, assignments.published_at,
                           assignments.created_at, assignments.updated_at,
                           class_groups.id AS class_id, class_groups.name AS class_name,
                           class_groups.course_id, courses.name AS course_name, courses.code AS course_code,
                           (SELECT COUNT(*) FROM enrollments e
                            WHERE e.class_group_id = assignments.class_group_id
                              AND e.status = 'active' AND e.member_role = 'student') AS student_count,
                           (SELECT COUNT(*) FROM submissions s
                            WHERE s.assignment_id = assignments.id
                              AND s.status IN ('submitted','resubmitted','late')) AS submitted_count,
                           (SELECT COUNT(*) FROM submissions s
                            WHERE s.assignment_id = assignments.id
                              AND s.status = 'late') AS late_count,
                           (SELECT COUNT(*) FROM submissions s
                            WHERE s.assignment_id = assignments.id
                              AND s.score IS NOT NULL) AS graded_count,
                           (SELECT AVG(s.score) FROM submissions s
                            WHERE s.assignment_id = assignments.id
                              AND s.score IS NOT NULL) AS avg_score
                    FROM assignments
                    JOIN class_groups ON class_groups.id = assignments.class_group_id
                    JOIN courses ON courses.id = class_groups.course_id
                    {where}
                    ORDER BY assignments.deadline ASC NULLS LAST, assignments.created_at DESC
                    LIMIT ? OFFSET ?""",
                params + [page_size, offset],
            )
            rows = cur.fetchall()
        items = []
        for r in rows:
            types: list = []
            if r["submission_types"]:
                try:
                    parsed = json.loads(r["submission_types"])
                    if isinstance(parsed, list):
                        types = parsed
                except (ValueError, TypeError):
                    types = []
            items.append({
                "id": r["id"],
                "class_group_id": r["class_group_id"],
                "author_id": r["author_id"],
                "title": r["title"],
                "description": r["description"],
                "deadline": r["deadline"],
                "submission_types": types,
                "max_score": r["max_score"],
                "allow_resubmit": bool(r["allow_resubmit"]),
                "status": r["status"],
                "published_at": r["published_at"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "class_id": r["class_id"],
                "class_name": r["class_name"],
                "course_id": r["course_id"],
                "course_name": r["course_name"],
                "course_code": r["course_code"],
                "student_count": int(r["student_count"] or 0),
                "submitted_count": int(r["submitted_count"] or 0),
                "late_count": int(r["late_count"] or 0),
                "graded_count": int(r["graded_count"] or 0),
                "avg_score": float(r["avg_score"]) if r["avg_score"] is not None else None,
            })
        return items, total

    def list_announcements_for_teacher(
        self,
        teacher_id: str,
        *,
        status: Optional[str] = None,
        class_id: Optional[str] = None,
        course_id: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[dict], int]:
        """列出教师所辖课程下的所有通知(含班级/课程名 + 已读统计)。"""
        conditions = ["courses.teacher_id = ?"]
        params: list = [teacher_id]
        if status:
            conditions.append("announcements.status = ?")
            params.append(status)
        if class_id:
            conditions.append("announcements.class_group_id = ?")
            params.append(class_id)
        if course_id:
            conditions.append("class_groups.course_id = ?")
            params.append(course_id)
        if search:
            conditions.append("(announcements.title LIKE ? OR announcements.content LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like])
        where = " WHERE " + " AND ".join(conditions)
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            cur = conn.execute(
                f"""SELECT COUNT(*) AS n FROM announcements
                    JOIN class_groups ON class_groups.id = announcements.class_group_id
                    JOIN courses ON courses.id = class_groups.course_id
                    {where}""",
                params,
            )
            total = int(cur.fetchone()["n"])
            cur = conn.execute(
                f"""SELECT announcements.id, announcements.class_group_id, announcements.author_id,
                           announcements.title, announcements.content, announcements.require_read,
                           announcements.status, announcements.published_at,
                           announcements.created_at, announcements.updated_at,
                           class_groups.id AS class_id, class_groups.name AS class_name,
                           class_groups.course_id, courses.name AS course_name,
                           (SELECT COUNT(*) FROM enrollments e
                            WHERE e.class_group_id = announcements.class_group_id
                              AND e.status = 'active' AND e.member_role = 'student') AS total_recipients,
                           (SELECT COUNT(*) FROM announcement_read_receipts r
                            WHERE r.announcement_id = announcements.id) AS read_count
                    FROM announcements
                    JOIN class_groups ON class_groups.id = announcements.class_group_id
                    JOIN courses ON courses.id = class_groups.course_id
                    {where}
                    ORDER BY announcements.published_at DESC NULLS LAST,
                             announcements.created_at DESC
                    LIMIT ? OFFSET ?""",
                params + [page_size, offset],
            )
            rows = cur.fetchall()
        items = []
        for r in rows:
            total_recipients = int(r["total_recipients"] or 0)
            read_count = int(r["read_count"] or 0)
            items.append({
                "id": r["id"],
                "class_group_id": r["class_group_id"],
                "author_id": r["author_id"],
                "title": r["title"],
                "content": r["content"],
                "require_read": bool(r["require_read"]),
                "status": r["status"],
                "published_at": r["published_at"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "class_id": r["class_id"],
                "class_name": r["class_name"],
                "course_id": r["course_id"],
                "course_name": r["course_name"],
                "total_recipients": total_recipients,
                "read_count": read_count,
                "unread_count": max(0, total_recipients - read_count),
            })
        return items, total

    def list_submissions_for_teacher(
        self,
        teacher_id: str,
        *,
        assignment_id: Optional[str] = None,
        class_id: Optional[str] = None,
        course_id: Optional[str] = None,
        status: Optional[str] = None,
        graded: Optional[bool] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[dict], int]:
        """列出教师所辖课程下的所有提交(含作业/班级/课程/学生信息)。"""
        conditions = ["courses.teacher_id = ?"]
        params: list = [teacher_id]
        if assignment_id:
            conditions.append("submissions.assignment_id = ?")
            params.append(assignment_id)
        if class_id:
            conditions.append("assignments.class_group_id = ?")
            params.append(class_id)
        if course_id:
            conditions.append("class_groups.course_id = ?")
            params.append(course_id)
        if status:
            conditions.append("submissions.status = ?")
            params.append(status)
        if graded is True:
            conditions.append("submissions.score IS NOT NULL")
        elif graded is False:
            conditions.append("submissions.score IS NULL")
        if search:
            conditions.append(
                "(users.username LIKE ? OR users.display_name LIKE ? OR users.student_number LIKE ?)"
            )
            like = f"%{search}%"
            params.extend([like, like, like])
        where = " WHERE " + " AND ".join(conditions)
        offset = (page - 1) * page_size
        with self._db.query() as conn:
            cur = conn.execute(
                f"""SELECT COUNT(*) AS n FROM submissions
                    JOIN assignments ON assignments.id = submissions.assignment_id
                    JOIN class_groups ON class_groups.id = assignments.class_group_id
                    JOIN courses ON courses.id = class_groups.course_id
                    JOIN users ON users.id = submissions.student_id
                    {where}""",
                params,
            )
            total = int(cur.fetchone()["n"])
            cur = conn.execute(
                f"""SELECT submissions.id, submissions.assignment_id, submissions.student_id,
                           submissions.text_content, submissions.status, submissions.submitted_at,
                           submissions.updated_at, submissions.score, submissions.teacher_comment,
                           assignments.title AS assignment_title, assignments.max_score,
                           assignments.deadline AS assignment_deadline, assignments.status AS assignment_status,
                           assignments.class_group_id AS class_id, class_groups.name AS class_name,
                           class_groups.course_id, courses.name AS course_name,
                           users.username, users.display_name AS student_name,
                           users.student_number, users.college, users.major, users.grade
                    FROM submissions
                    JOIN assignments ON assignments.id = submissions.assignment_id
                    JOIN class_groups ON class_groups.id = assignments.class_group_id
                    JOIN courses ON courses.id = class_groups.course_id
                    JOIN users ON users.id = submissions.student_id
                    {where}
                    ORDER BY submissions.submitted_at DESC NULLS LAST
                    LIMIT ? OFFSET ?""",
                params + [page_size, offset],
            )
            rows = cur.fetchall()
        items = []
        for r in rows:
            is_late = r["status"] == "late" or (
                r["assignment_deadline"] is not None
                and r["submitted_at"] is not None
                and r["submitted_at"] > r["assignment_deadline"]
            )
            items.append({
                "id": r["id"],
                "assignment_id": r["assignment_id"],
                "assignment_title": r["assignment_title"],
                "assignment_max_score": r["max_score"],
                "assignment_deadline": r["assignment_deadline"],
                "assignment_status": r["assignment_status"],
                "student_id": r["student_id"],
                "student_name": r["student_name"] or r["username"],
                "student_number": r["student_number"],
                "college": r["college"],
                "major": r["major"],
                "grade": r["grade"],
                "class_id": r["class_id"],
                "class_name": r["class_name"],
                "course_id": r["course_id"],
                "course_name": r["course_name"],
                "text_content": r["text_content"],
                "status": r["status"],
                "submitted_at": r["submitted_at"],
                "updated_at": r["updated_at"],
                "score": r["score"],
                "teacher_comment": r["teacher_comment"],
                "is_late": bool(is_late),
            })
        return items, total

    def teacher_analytics(
        self,
        teacher_id: str,
        *,
        class_id: Optional[str] = None,
        course_id: Optional[str] = None,
    ) -> dict:
        """教师学情聚合: 提交率/批改率/分数分布/各作业完成情况/学生完成率。

        所有数字均来自真实 SQL 聚合,不写死。
        """
        conditions = ["courses.teacher_id = ?"]
        params: list = [teacher_id]
        if class_id:
            conditions.append("assignments.class_group_id = ?")
            params.append(class_id)
        if course_id:
            conditions.append("class_groups.course_id = ?")
            params.append(course_id)
        where = " WHERE " + " AND ".join(conditions)
        with self._db.query() as conn:
            # 各作业完成情况
            cur = conn.execute(
                f"""SELECT assignments.id, assignments.title, assignments.deadline, assignments.status,
                           assignments.max_score, assignments.class_group_id,
                           class_groups.name AS class_name, courses.name AS course_name,
                           (SELECT COUNT(*) FROM enrollments e
                            WHERE e.class_group_id = assignments.class_group_id
                              AND e.status = 'active' AND e.member_role = 'student') AS total_students,
                           (SELECT COUNT(*) FROM submissions s
                            WHERE s.assignment_id = assignments.id
                              AND s.status IN ('submitted','resubmitted','late')) AS submitted,
                           (SELECT COUNT(*) FROM submissions s
                            WHERE s.assignment_id = assignments.id
                              AND s.status = 'late') AS late,
                           (SELECT COUNT(*) FROM submissions s
                            WHERE s.assignment_id = assignments.id
                              AND s.score IS NOT NULL) AS graded,
                           (SELECT AVG(s.score) FROM submissions s
                            WHERE s.assignment_id = assignments.id
                              AND s.score IS NOT NULL) AS avg_score,
                           (SELECT MAX(s.score) FROM submissions s
                            WHERE s.assignment_id = assignments.id
                              AND s.score IS NOT NULL) AS max_score,
                           (SELECT MIN(s.score) FROM submissions s
                            WHERE s.assignment_id = assignments.id
                              AND s.score IS NOT NULL) AS min_score
                    FROM assignments
                    JOIN class_groups ON class_groups.id = assignments.class_group_id
                    JOIN courses ON courses.id = class_groups.course_id
                    {where}
                    ORDER BY assignments.deadline ASC NULLS LAST""",
                params,
            )
            assignment_rows = cur.fetchall()

            # 学生课程完成率(按学生聚合)
            cur = conn.execute(
                f"""SELECT users.id AS student_id, users.username, users.display_name AS student_name,
                           users.student_number,
                           class_groups.name AS class_name, courses.name AS course_name,
                           COUNT(DISTINCT assignments.id) AS total_assignments,
                           COUNT(DISTINCT CASE WHEN submissions.status IN ('submitted','resubmitted','late')
                                THEN assignments.id END) AS submitted_assignments,
                           COUNT(DISTINCT CASE WHEN submissions.score IS NOT NULL
                                THEN assignments.id END) AS graded_assignments,
                           AVG(submissions.score) AS avg_score
                    FROM enrollments
                    JOIN users ON users.id = enrollments.user_id
                    JOIN class_groups ON class_groups.id = enrollments.class_group_id
                    JOIN courses ON courses.id = class_groups.course_id
                    LEFT JOIN assignments ON assignments.class_group_id = class_groups.id
                        AND assignments.status IN ('published','closed')
                    LEFT JOIN submissions ON submissions.assignment_id = assignments.id
                        AND submissions.student_id = users.id
                    WHERE enrollments.status = 'active' AND enrollments.member_role = 'student'
                      AND courses.teacher_id = ?
                      {('AND class_groups.id = ?' if class_id else '')}
                      {('AND class_groups.course_id = ?' if course_id else '')}
                    GROUP BY users.id, class_groups.id
                    ORDER BY users.student_number ASC, users.username ASC""",
                [teacher_id] + ([class_id] if class_id else []) + ([course_id] if course_id else []),
            )
            student_rows = cur.fetchall()

            # 一次加载全部已评分提交，避免每份作业重新连接并逐项查找满分。
            score_rows = conn.execute(
                f"""SELECT submissions.score, assignments.max_score
                    FROM submissions
                    JOIN assignments ON assignments.id = submissions.assignment_id
                    JOIN class_groups ON class_groups.id = assignments.class_group_id
                    JOIN courses ON courses.id = class_groups.course_id
                    {where} AND submissions.score IS NOT NULL""",
                params,
            ).fetchall()
            unscored = int(conn.execute(
                f"""SELECT COUNT(*) AS n FROM submissions
                    JOIN assignments ON assignments.id = submissions.assignment_id
                    JOIN class_groups ON class_groups.id = assignments.class_group_id
                    JOIN courses ON courses.id = class_groups.course_id
                    {where} AND submissions.score IS NULL
                      AND submissions.status IN ('submitted','resubmitted','late')""",
                params,
            ).fetchone()["n"])

        # 聚合总览
        total_assignments = len(assignment_rows)
        total_submitted = sum(int(r["submitted"] or 0) for r in assignment_rows)
        total_expected = sum(int(r["total_students"] or 0) for r in assignment_rows)
        total_graded = sum(int(r["graded"] or 0) for r in assignment_rows)
        total_late = sum(int(r["late"] or 0) for r in assignment_rows)
        score_distribution = {"excellent": 0, "good": 0, "pass": 0, "fail": 0, "unscored": 0}
        assignment_summaries = []
        for r in assignment_rows:
            total_students = int(r["total_students"] or 0)
            submitted = int(r["submitted"] or 0)
            graded = int(r["graded"] or 0)
            late = int(r["late"] or 0)
            avg_score = float(r["avg_score"]) if r["avg_score"] is not None else None
            max_score = float(r["max_score"]) if r["max_score"] is not None else None
            min_score = float(r["min_score"]) if r["min_score"] is not None else None
            submission_rate = round(submitted / total_students, 4) if total_students else None
            grading_rate = round(graded / submitted, 4) if submitted else None
            assignment_summaries.append({
                "assignment_id": r["id"],
                "title": r["title"],
                "deadline": r["deadline"],
                "status": r["status"],
                "max_score": r["max_score"],
                "class_name": r["class_name"],
                "course_name": r["course_name"],
                "total_students": total_students,
                "submitted": submitted,
                "unsubmitted": max(0, total_students - submitted),
                "late": late,
                "graded": graded,
                "avg_score": avg_score,
                "max_score_achieved": max_score,
                "min_score_achieved": min_score,
                "submission_rate": submission_rate,
                "grading_rate": grading_rate,
            })
        # 分数分布(基于 100 分制归一化)
        cur2_scores: list = []
        for row in score_rows:
            score = float(row["score"])
            cur2_scores.append(score)
            asg_max = row["max_score"]
            normalized = (score / asg_max * 100) if asg_max else score
            if normalized >= 90:
                score_distribution["excellent"] += 1
            elif normalized >= 75:
                score_distribution["good"] += 1
            elif normalized >= 60:
                score_distribution["pass"] += 1
            else:
                score_distribution["fail"] += 1
        # 未评分提交数
        score_distribution["unscored"] = unscored

        # 学生完成率
        student_summaries = []
        consecutive_unsubmitted_students = []
        for r in student_rows:
            total_a = int(r["total_assignments"] or 0)
            submitted_a = int(r["submitted_assignments"] or 0)
            graded_a = int(r["graded_assignments"] or 0)
            avg_s = float(r["avg_score"]) if r["avg_score"] is not None else None
            completion_rate = round(submitted_a / total_a, 4) if total_a else None
            student_summaries.append({
                "student_id": r["student_id"],
                "student_name": r["student_name"] or r["username"],
                "student_number": r["student_number"],
                "class_name": r["class_name"],
                "course_name": r["course_name"],
                "total_assignments": total_a,
                "submitted_assignments": submitted_a,
                "unsubmitted_assignments": max(0, total_a - submitted_a),
                "graded_assignments": graded_a,
                "avg_score": avg_s,
                "completion_rate": completion_rate,
            })
            # 连续多次未提交(>=2 次未提交)
            if total_a >= 2 and (total_a - submitted_a) >= 2:
                consecutive_unsubmitted_students.append({
                    "student_id": r["student_id"],
                    "student_name": r["student_name"] or r["username"],
                    "student_number": r["student_number"],
                    "class_name": r["class_name"],
                    "course_name": r["course_name"],
                    "unsubmitted_count": total_a - submitted_a,
                    "total_assignments": total_a,
                })

        overall_submission_rate = round(total_submitted / total_expected, 4) if total_expected else None
        overall_grading_rate = round(total_graded / total_submitted, 4) if total_submitted else None
        overall_avg_score = (
            sum(cur2_scores) / len(cur2_scores) if cur2_scores else None
        )
        overall_max_score = max(cur2_scores) if cur2_scores else None
        overall_min_score = min(cur2_scores) if cur2_scores else None

        return {
            "total_assignments": total_assignments,
            "total_submitted": total_submitted,
            "total_expected_submissions": total_expected,
            "total_unsubmitted": max(0, total_expected - total_submitted),
            "total_late": total_late,
            "total_graded": total_graded,
            "total_pending_grading": max(0, total_submitted - total_graded),
            "overall_submission_rate": overall_submission_rate,
            "overall_grading_rate": overall_grading_rate,
            "overall_avg_score": overall_avg_score,
            "overall_max_score": overall_max_score,
            "overall_min_score": overall_min_score,
            "score_distribution": score_distribution,
            "assignments": assignment_summaries,
            "students": student_summaries,
            "frequent_unsubmitted_students": consecutive_unsubmitted_students,
        }
