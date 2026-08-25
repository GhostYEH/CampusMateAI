"""EduDataRepository — 教务同步数据持久化仓库。

管理 edu_courses / edu_schedule_items / edu_grades 三张表。
支持幂等同步：基于唯一键 upsert，未在本次 batch 出现的旧数据标记 is_stale=1（软删除）。
返回 inserted / updated / unchanged / removed 统计。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ..database.sqlite_db import Database
from ..models.edu import EduBindingRow
from ..schemas.edu import EduExam, EduExamItem, EduGrade, EduGradeItem, EduSchedule, EduScheduleItem


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_id(prefix: str, *parts: str) -> str:
    raw = ":".join(str(p) for p in parts)
    return f"{prefix}_{hashlib.md5(raw.encode('utf-8')).hexdigest()[:24]}"


def _source_hash(**fields) -> str:
    raw = "|".join(f"{k}={fields.get(k)}" for k in sorted(fields.keys()))
    return hashlib.md5(raw.encode('utf-8')).hexdigest()


@dataclass
class SyncStats:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    removed: int = 0
    failed: int = 0

    @property
    def total(self) -> int:
        return self.inserted + self.updated + self.unchanged + self.removed + self.failed

    def to_dict(self) -> dict:
        return {
            "inserted": self.inserted,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "removed": self.removed,
            "failed": self.failed,
        }


@dataclass
class PersistedScheduleItem:
    id: str
    user_id: str
    semester: Optional[str]
    course_code: Optional[str]
    course_name: str
    teacher: Optional[str]
    teachers: Optional[list] = None
    location: Optional[str] = None
    campus: Optional[str] = None
    building: Optional[str] = None
    classroom: Optional[str] = None
    weekday: Optional[int] = None
    start_section: Optional[int] = None
    end_section: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    weeks: Optional[str] = None
    week_text: Optional[str] = None
    credit: Optional[float] = None
    course_nature: Optional[str] = None
    course_category: Optional[str] = None
    course_type: Optional[str] = None
    teaching_class: Optional[str] = None
    class_name: Optional[str] = None
    college: Optional[str] = None
    department: Optional[str] = None
    assessment_method: Optional[str] = None
    exam_type: Optional[str] = None
    total_hours: Optional[float] = None
    theory_hours: Optional[float] = None
    practice_hours: Optional[float] = None
    language: Optional[str] = None
    note: Optional[str] = None
    semester_id: Optional[str] = None
    extra_info: Optional[dict] = None
    is_stale: bool = False
    last_seen_at: Optional[str] = None


@dataclass
class PersistedGradeItem:
    id: str
    user_id: str
    semester: Optional[str]
    course_code: Optional[str]
    course_name: str
    credit: Optional[float]
    score: Optional[str]
    grade_point: Optional[float]
    category: Optional[str]
    status: Optional[str]
    is_stale: bool
    last_seen_at: Optional[str]


@dataclass
class PersistedExamItem:
    id: str
    user_id: str
    semester: Optional[str]
    course_code: Optional[str]
    course_name: str
    exam_type: Optional[str]
    location: Optional[str]
    seat: Optional[str]
    starts_at: Optional[str]
    ends_at: Optional[str]
    notes: Optional[str]
    is_stale: bool
    last_seen_at: Optional[str]


class EduDataRepository:
    """教务同步数据仓库。"""

    def __init__(self, db: Database) -> None:
        self._db = db

    # ===== 课表 =====

    def sync_schedule_items(
        self,
        *,
        binding: EduBindingRow,
        schedule: EduSchedule,
        sync_batch_id: str,
    ) -> SyncStats:
        stats = SyncStats()
        now = _now_iso()
        seen_ids: list[str] = []
        edu_system_id = binding.edu_system_id
        user_id = binding.user_id
        university_id = binding.university_id
        semester = schedule.semester

        with self._db.transaction() as conn:
            for item in schedule.items:
                if not item.course_name:
                    stats.failed += 1
                    continue
                item_semester = item.semester or semester
                teachers_json = json.dumps(item.teachers, ensure_ascii=False) if item.teachers else None
                extra_info_json = json.dumps(item.extra_info, ensure_ascii=False) if item.extra_info else None
                source_hash = _source_hash(
                    course_code=item.course_code or "",
                    course_name=item.course_name,
                    teacher=item.teacher or "",
                    teachers=teachers_json or "",
                    location=item.location or "",
                    weekday=item.weekday,
                    start_section=item.start_section,
                    end_section=item.end_section,
                    weeks=item.weeks or "",
                    credit=item.credit,
                    course_nature=item.course_nature or "",
                    teaching_class=item.teaching_class or "",
                    assessment_method=item.assessment_method or "",
                    extra_info=extra_info_json or "",
                )
                item_id = _short_id(
                    "edu_sch",
                    user_id,
                    edu_system_id or "",
                    item_semester or "",
                    item.course_code or "",
                    str(item.weekday or ""),
                    str(item.start_section or ""),
                    item.weeks or "",
                    item.teaching_class or "",
                )
                seen_ids.append(item_id)
                existing = conn.execute(
                    "SELECT id, source_hash, is_stale FROM edu_schedule_items WHERE id = ?",
                    (item_id,),
                ).fetchone()
                if existing is None:
                    conn.execute(
                        """
                        INSERT INTO edu_schedule_items (
                            id, user_id, edu_system_id, university_id, semester,
                            course_code, course_name, teacher, teachers, location,
                            campus, building, classroom,
                            weekday, start_section, end_section, start_time, end_time,
                            weeks, week_text, credit,
                            course_nature, course_category, course_type,
                            teaching_class, class_name, college, department,
                            assessment_method, exam_type,
                            total_hours, theory_hours, practice_hours,
                            language, note, semester_id, extra_info,
                            provider, source, source_hash, last_seen_at, sync_batch_id,
                            is_stale, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item_id, user_id, edu_system_id, university_id, item_semester,
                            item.course_code, item.course_name, item.teacher, teachers_json, item.location,
                            item.campus, item.building, item.classroom,
                            item.weekday, item.start_section, item.end_section,
                            item.start_time, item.end_time,
                            item.weeks, item.week_text, item.credit,
                            item.course_nature, item.course_category, item.course_type,
                            item.teaching_class, item.class_name, item.college, item.department,
                            item.assessment_method, item.exam_type,
                            item.total_hours, item.theory_hours, item.practice_hours,
                            item.language, item.note, item.semester_id, extra_info_json,
                            binding.provider, "edu_connector", source_hash, now, sync_batch_id,
                            0, now, now,
                        ),
                    )
                    stats.inserted += 1
                else:
                    if existing["is_stale"] == 1 or existing["source_hash"] != source_hash:
                        conn.execute(
                            """
                            UPDATE edu_schedule_items SET
                                course_name = ?, teacher = ?, teachers = ?, location = ?,
                                campus = ?, building = ?, classroom = ?,
                                weekday = ?, start_section = ?, end_section = ?,
                                start_time = ?, end_time = ?,
                                weeks = ?, week_text = ?, credit = ?,
                                course_nature = ?, course_category = ?, course_type = ?,
                                teaching_class = ?, class_name = ?, college = ?, department = ?,
                                assessment_method = ?, exam_type = ?,
                                total_hours = ?, theory_hours = ?, practice_hours = ?,
                                language = ?, note = ?, semester_id = ?, extra_info = ?,
                                semester = COALESCE(?, semester),
                                source_hash = ?, last_seen_at = ?, sync_batch_id = ?,
                                is_stale = 0, updated_at = ?
                            WHERE id = ?
                            """,
                            (
                                item.course_name, item.teacher, teachers_json, item.location,
                                item.campus, item.building, item.classroom,
                                item.weekday, item.start_section, item.end_section,
                                item.start_time, item.end_time,
                                item.weeks, item.week_text, item.credit,
                                item.course_nature, item.course_category, item.course_type,
                                item.teaching_class, item.class_name, item.college, item.department,
                                item.assessment_method, item.exam_type,
                                item.total_hours, item.theory_hours, item.practice_hours,
                                item.language, item.note, item.semester_id, extra_info_json,
                                item_semester, source_hash, now, sync_batch_id, now, item_id,
                            ),
                        )
                        stats.updated += 1
                    else:
                        conn.execute(
                            "UPDATE edu_schedule_items SET last_seen_at = ?, sync_batch_id = ?, updated_at = ? WHERE id = ?",
                            (now, sync_batch_id, now, item_id),
                        )
                        stats.unchanged += 1

            if seen_ids and edu_system_id:
                seen_semesters = {it.semester or semester for it in schedule.items if it.course_name}
                if seen_semesters:
                    sem_placeholders = ",".join("?" for _ in seen_semesters)
                    id_placeholders = ",".join("?" for _ in seen_ids)
                    cur = conn.execute(
                        f"""
                        UPDATE edu_schedule_items SET is_stale = 1, updated_at = ?
                        WHERE user_id = ? AND edu_system_id = ?
                          AND semester IN ({sem_placeholders})
                          AND id NOT IN ({id_placeholders})
                          AND is_stale = 0
                        """,
                        (now, user_id, edu_system_id, *seen_semesters, *seen_ids),
                    )
                    stats.removed = cur.rowcount or 0

        return stats

    def list_schedule_items(
        self,
        *,
        user_id: str,
        semester: Optional[str] = None,
        include_stale: bool = False,
    ) -> list[PersistedScheduleItem]:
        with self._db.query() as conn:
            if semester:
                sql = """
                    SELECT * FROM edu_schedule_items
                    WHERE user_id = ? AND semester = ? AND is_stale <= ?
                    ORDER BY weekday ASC, start_section ASC
                """
                rows = conn.execute(sql, (user_id, semester, 1 if include_stale else 0)).fetchall()
            else:
                sql = """
                    SELECT * FROM edu_schedule_items
                    WHERE user_id = ? AND is_stale <= ?
                    ORDER BY semester DESC, weekday ASC, start_section ASC
                """
                rows = conn.execute(sql, (user_id, 1 if include_stale else 0)).fetchall()
        return [self._row_to_schedule_item(r) for r in rows]

    def list_semesters_with_schedule(self, user_id: str) -> list[str]:
        with self._db.query() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT semester FROM edu_schedule_items
                WHERE user_id = ? AND semester IS NOT NULL AND is_stale = 0
                ORDER BY semester DESC
                """,
                (user_id,),
            ).fetchall()
        return [r["semester"] for r in rows if r["semester"]]

    @staticmethod
    def _row_to_schedule_item(row) -> PersistedScheduleItem:
        teachers_raw = row["teachers"] if "teachers" in row.keys() else None
        teachers_list: Optional[list] = None
        if teachers_raw:
            try:
                teachers_list = json.loads(teachers_raw)
                if not isinstance(teachers_list, list):
                    teachers_list = None
            except (TypeError, ValueError):
                teachers_list = None
        extra_raw = row["extra_info"] if "extra_info" in row.keys() else None
        extra_dict: Optional[dict] = None
        if extra_raw:
            try:
                extra_dict = json.loads(extra_raw)
                if not isinstance(extra_dict, dict):
                    extra_dict = None
            except (TypeError, ValueError):
                extra_dict = None
        def _g(key: str) -> Any:
            return row[key] if key in row.keys() else None
        return PersistedScheduleItem(
            id=row["id"],
            user_id=row["user_id"],
            semester=row["semester"],
            course_code=row["course_code"],
            course_name=row["course_name"],
            teacher=row["teacher"],
            teachers=teachers_list,
            location=row["location"],
            campus=_g("campus"),
            building=_g("building"),
            classroom=_g("classroom"),
            weekday=row["weekday"],
            start_section=row["start_section"],
            end_section=row["end_section"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            weeks=row["weeks"],
            week_text=_g("week_text"),
            credit=_g("credit"),
            course_nature=_g("course_nature"),
            course_category=_g("course_category"),
            course_type=_g("course_type"),
            teaching_class=_g("teaching_class"),
            class_name=_g("class_name"),
            college=_g("college"),
            department=_g("department"),
            assessment_method=_g("assessment_method"),
            exam_type=_g("exam_type"),
            total_hours=_g("total_hours"),
            theory_hours=_g("theory_hours"),
            practice_hours=_g("practice_hours"),
            language=_g("language"),
            note=_g("note"),
            semester_id=_g("semester_id"),
            extra_info=extra_dict,
            is_stale=bool(row["is_stale"]),
            last_seen_at=row["last_seen_at"],
        )

    # ===== 成绩 =====

    def sync_grade_items(
        self,
        *,
        binding: EduBindingRow,
        grade: EduGrade,
        sync_batch_id: str,
    ) -> SyncStats:
        stats = SyncStats()
        now = _now_iso()
        seen_ids: list[str] = []
        edu_system_id = binding.edu_system_id
        user_id = binding.user_id
        university_id = binding.university_id
        semester = grade.semester

        with self._db.transaction() as conn:
            for item in grade.items:
                if not item.course_name:
                    stats.failed += 1
                    continue
                item_semester = item.semester or semester
                source_hash = _source_hash(
                    course_code=item.course_code or "",
                    course_name=item.course_name,
                    credit=item.credit,
                    score=item.score or "",
                    grade_point=item.grade_point,
                    category=item.category or "",
                    status=item.status or "",
                )
                item_id = _short_id(
                    "edu_grd",
                    user_id,
                    edu_system_id or "",
                    item_semester or "",
                    item.course_code or "",
                    item.course_name,
                )
                seen_ids.append(item_id)
                existing = conn.execute(
                    "SELECT id, source_hash, is_stale FROM edu_grades WHERE id = ?",
                    (item_id,),
                ).fetchone()
                if existing is None:
                    conn.execute(
                        """
                        INSERT INTO edu_grades (
                            id, user_id, edu_system_id, university_id, semester,
                            course_code, course_name, credit, score, grade_point,
                            category, status, provider, source, source_hash,
                            last_seen_at, sync_batch_id, is_stale, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                        """,
                        (
                            item_id, user_id, edu_system_id, university_id, item_semester,
                            item.course_code, item.course_name, item.credit, item.score, item.grade_point,
                            item.category, item.status, binding.provider, "edu_connector", source_hash,
                            now, sync_batch_id, now, now,
                        ),
                    )
                    stats.inserted += 1
                else:
                    if existing["is_stale"] == 1 or existing["source_hash"] != source_hash:
                        conn.execute(
                            """
                            UPDATE edu_grades SET
                                course_name = ?, credit = ?, score = ?, grade_point = ?,
                                category = ?, status = ?,
                                semester = COALESCE(?, semester),
                                source_hash = ?, last_seen_at = ?, sync_batch_id = ?,
                                is_stale = 0, updated_at = ?
                            WHERE id = ?
                            """,
                            (
                                item.course_name, item.credit, item.score, item.grade_point,
                                item.category, item.status, item_semester,
                                source_hash, now, sync_batch_id, now, item_id,
                            ),
                        )
                        stats.updated += 1
                    else:
                        conn.execute(
                            "UPDATE edu_grades SET last_seen_at = ?, sync_batch_id = ?, updated_at = ? WHERE id = ?",
                            (now, sync_batch_id, now, item_id),
                        )
                        stats.unchanged += 1

            if seen_ids and edu_system_id:
                seen_semesters = {it.semester or semester for it in grade.items if it.course_name}
                if seen_semesters:
                    sem_placeholders = ",".join("?" for _ in seen_semesters)
                    id_placeholders = ",".join("?" for _ in seen_ids)
                    cur = conn.execute(
                        f"""
                        UPDATE edu_grades SET is_stale = 1, updated_at = ?
                        WHERE user_id = ? AND edu_system_id = ?
                          AND semester IN ({sem_placeholders})
                          AND id NOT IN ({id_placeholders})
                          AND is_stale = 0
                        """,
                        (now, user_id, edu_system_id, *seen_semesters, *seen_ids),
                    )
                    stats.removed = cur.rowcount or 0

        return stats

    def list_grade_items(
        self,
        *,
        user_id: str,
        semester: Optional[str] = None,
        include_stale: bool = False,
    ) -> list[PersistedGradeItem]:
        with self._db.query() as conn:
            if semester:
                sql = """
                    SELECT * FROM edu_grades
                    WHERE user_id = ? AND semester = ? AND is_stale <= ?
                    ORDER BY course_name ASC
                """
                rows = conn.execute(sql, (user_id, semester, 1 if include_stale else 0)).fetchall()
            else:
                sql = """
                    SELECT * FROM edu_grades
                    WHERE user_id = ? AND is_stale <= ?
                    ORDER BY semester DESC, course_name ASC
                """
                rows = conn.execute(sql, (user_id, 1 if include_stale else 0)).fetchall()
        return [self._row_to_grade_item(r) for r in rows]

    def list_semesters_with_grades(self, user_id: str) -> list[str]:
        with self._db.query() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT semester FROM edu_grades
                WHERE user_id = ? AND semester IS NOT NULL AND is_stale = 0
                ORDER BY semester DESC
                """,
                (user_id,),
            ).fetchall()
        return [r["semester"] for r in rows if r["semester"]]

    @staticmethod
    def _row_to_grade_item(row) -> PersistedGradeItem:
        return PersistedGradeItem(
            id=row["id"],
            user_id=row["user_id"],
            semester=row["semester"],
            course_code=row["course_code"],
            course_name=row["course_name"],
            credit=row["credit"],
            score=row["score"],
            grade_point=row["grade_point"],
            category=row["category"],
            status=row["status"],
            is_stale=bool(row["is_stale"]),
            last_seen_at=row["last_seen_at"],
        )

    # ===== 考试 =====

    def sync_exam_items(
        self,
        *,
        binding: EduBindingRow,
        exam: EduExam,
        sync_batch_id: str,
    ) -> SyncStats:
        stats = SyncStats()
        now = _now_iso()
        seen_ids: list[str] = []
        edu_system_id = binding.edu_system_id
        user_id = binding.user_id
        university_id = binding.university_id
        semester = exam.semester

        with self._db.transaction() as conn:
            for item in exam.items:
                if not item.course_name:
                    stats.failed += 1
                    continue
                item_semester = item.semester or semester
                source_hash = _source_hash(
                    course_code=item.course_code or "",
                    course_name=item.course_name,
                    exam_type=item.exam_type or "",
                    location=item.location or "",
                    seat=item.seat or "",
                    starts_at=item.starts_at or "",
                    ends_at=item.ends_at or "",
                    notes=item.notes or "",
                )
                item_id = _short_id(
                    "edu_exm",
                    user_id,
                    edu_system_id or "",
                    item_semester or "",
                    item.course_code or "",
                    item.course_name,
                    item.exam_type or "",
                    item.starts_at or "",
                )
                seen_ids.append(item_id)
                existing = conn.execute(
                    "SELECT id, source_hash, is_stale FROM edu_exam_items WHERE id = ?",
                    (item_id,),
                ).fetchone()
                if existing is None:
                    conn.execute(
                        """
                        INSERT INTO edu_exam_items (
                            id, user_id, edu_system_id, university_id, semester,
                            course_code, course_name, exam_type, location, seat,
                            starts_at, ends_at, notes, provider, source, source_hash,
                            last_seen_at, sync_batch_id, is_stale, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                        """,
                        (
                            item_id, user_id, edu_system_id, university_id, item_semester,
                            item.course_code, item.course_name, item.exam_type, item.location,
                            item.seat, item.starts_at, item.ends_at, item.notes,
                            binding.provider, "edu_connector", source_hash,
                            now, sync_batch_id, now, now,
                        ),
                    )
                    stats.inserted += 1
                elif existing["is_stale"] == 1 or existing["source_hash"] != source_hash:
                    conn.execute(
                        """
                        UPDATE edu_exam_items SET
                            course_name = ?, exam_type = ?, location = ?, seat = ?,
                            starts_at = ?, ends_at = ?, notes = ?, semester = COALESCE(?, semester),
                            source_hash = ?, last_seen_at = ?, sync_batch_id = ?,
                            is_stale = 0, updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            item.course_name, item.exam_type, item.location, item.seat,
                            item.starts_at, item.ends_at, item.notes, item_semester,
                            source_hash, now, sync_batch_id, now, item_id,
                        ),
                    )
                    stats.updated += 1
                else:
                    conn.execute(
                        "UPDATE edu_exam_items SET last_seen_at = ?, sync_batch_id = ?, updated_at = ? WHERE id = ?",
                        (now, sync_batch_id, now, item_id),
                    )
                    stats.unchanged += 1

            if seen_ids and edu_system_id:
                seen_semesters = {it.semester or semester for it in exam.items if it.course_name}
                if seen_semesters:
                    sem_placeholders = ",".join("?" for _ in seen_semesters)
                    id_placeholders = ",".join("?" for _ in seen_ids)
                    cur = conn.execute(
                        f"""
                        UPDATE edu_exam_items SET is_stale = 1, updated_at = ?
                        WHERE user_id = ? AND edu_system_id = ?
                          AND semester IN ({sem_placeholders})
                          AND id NOT IN ({id_placeholders})
                          AND is_stale = 0
                        """,
                        (now, user_id, edu_system_id, *seen_semesters, *seen_ids),
                    )
                    stats.removed = cur.rowcount or 0
        return stats

    def list_exam_items(
        self,
        *,
        user_id: str,
        semester: Optional[str] = None,
        include_stale: bool = False,
    ) -> list[PersistedExamItem]:
        with self._db.query() as conn:
            stale_limit = 1 if include_stale else 0
            if semester:
                rows = conn.execute(
                    """
                    SELECT * FROM edu_exam_items
                    WHERE user_id = ? AND semester = ? AND is_stale <= ?
                    ORDER BY starts_at ASC, course_name ASC
                    """,
                    (user_id, semester, stale_limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM edu_exam_items
                    WHERE user_id = ? AND is_stale <= ?
                    ORDER BY semester DESC, starts_at ASC, course_name ASC
                    """,
                    (user_id, stale_limit),
                ).fetchall()
        return [self._row_to_exam_item(row) for row in rows]

    def list_semesters_with_exams(self, user_id: str) -> list[str]:
        with self._db.query() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT semester FROM edu_exam_items
                WHERE user_id = ? AND semester IS NOT NULL AND is_stale = 0
                ORDER BY semester DESC
                """,
                (user_id,),
            ).fetchall()
        return [row["semester"] for row in rows if row["semester"]]

    @staticmethod
    def _row_to_exam_item(row) -> PersistedExamItem:
        return PersistedExamItem(
            id=row["id"],
            user_id=row["user_id"],
            semester=row["semester"],
            course_code=row["course_code"],
            course_name=row["course_name"],
            exam_type=row["exam_type"],
            location=row["location"],
            seat=row["seat"],
            starts_at=row["starts_at"],
            ends_at=row["ends_at"],
            notes=row["notes"],
            is_stale=bool(row["is_stale"]),
            last_seen_at=row["last_seen_at"],
        )

    # ===== 清理 =====

    def clear_user_data(self, user_id: str) -> None:
        with self._db.transaction() as conn:
            conn.execute("DELETE FROM edu_schedule_items WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM edu_grades WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM edu_exam_items WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM edu_courses WHERE user_id = ?", (user_id,))


__all__ = [
    "SyncStats",
    "PersistedScheduleItem",
    "PersistedGradeItem",
    "PersistedExamItem",
    "EduDataRepository",
]
