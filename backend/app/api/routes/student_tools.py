"""学生端扩展能力：个人考试安排。

这些数据均绑定 JWT 用户；课程/作业/通知仍复用各自业务仓库，避免在学生端复制权限逻辑。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...models.multi_role import UserRow
from ...services.container import ServiceContainer, get_container
from ..deps import current_user, require_role

router = APIRouter(tags=["student-tools"])


def _container() -> ServiceContainer:
    return get_container()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _ensure_tables(c: ServiceContainer) -> None:
    with c.db.transaction() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS student_exams (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL, course_name TEXT NOT NULL,
                exam_date TEXT NOT NULL, start_time TEXT, end_time TEXT, location TEXT,
                seat_number TEXT, exam_type TEXT, reminder_enabled INTEGER NOT NULL DEFAULT 1,
                notes TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_student_exams_user_date ON student_exams(user_id, exam_date);
            """
        )


def _student(user: UserRow) -> UserRow:
    if user.role != "student":
        raise HTTPException(status_code=403, detail="仅学生可访问此功能")
    return user


class ExamIn(BaseModel):
    course_name: str = Field(..., min_length=1, max_length=200)
    exam_date: str = Field(..., min_length=1, max_length=32)
    start_time: Optional[str] = Field(None, max_length=16)
    end_time: Optional[str] = Field(None, max_length=16)
    location: Optional[str] = Field(None, max_length=200)
    seat_number: Optional[str] = Field(None, max_length=32)
    exam_type: Optional[str] = Field(None, max_length=64)
    reminder_enabled: bool = True
    notes: Optional[str] = Field(None, max_length=2000)


@router.get("/student/exams")
def list_exams(user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)):
    _ensure_tables(c)
    with c.db.query() as conn:
        rows = conn.execute("SELECT * FROM student_exams WHERE user_id = ? ORDER BY exam_date, start_time", (user.id,)).fetchall()
    return [dict(row) for row in rows]


@router.post("/student/exams", status_code=201)
def create_exam(req: ExamIn, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)):
    _ensure_tables(c); now = _now(); exam_id = _id("exam")
    with c.db.transaction() as conn:
        conn.execute("INSERT INTO student_exams (id,user_id,course_name,exam_date,start_time,end_time,location,seat_number,exam_type,reminder_enabled,notes,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (exam_id,user.id,req.course_name,req.exam_date,req.start_time,req.end_time,req.location,req.seat_number,req.exam_type,int(req.reminder_enabled),req.notes,now,now))
        row = conn.execute("SELECT * FROM student_exams WHERE id = ?", (exam_id,)).fetchone()
    return dict(row)


@router.patch("/student/exams/{exam_id}")
def update_exam(exam_id: str, req: ExamIn, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)):
    _ensure_tables(c)
    with c.db.transaction() as conn:
        result = conn.execute("UPDATE student_exams SET course_name=?,exam_date=?,start_time=?,end_time=?,location=?,seat_number=?,exam_type=?,reminder_enabled=?,notes=?,updated_at=? WHERE id=? AND user_id=?", (req.course_name,req.exam_date,req.start_time,req.end_time,req.location,req.seat_number,req.exam_type,int(req.reminder_enabled),req.notes,_now(),exam_id,user.id))
        if result.rowcount == 0: raise HTTPException(status_code=404, detail="考试记录不存在")
        return dict(conn.execute("SELECT * FROM student_exams WHERE id = ?", (exam_id,)).fetchone())


@router.delete("/student/exams/{exam_id}")
def delete_exam(exam_id: str, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)):
    _ensure_tables(c)
    with c.db.transaction() as conn:
        conn.execute("DELETE FROM student_exams WHERE id = ? AND user_id = ?", (exam_id, user.id))
    return {"ok": True}


__all__ = ["router"]
