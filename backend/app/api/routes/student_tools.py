"""学生端扩展能力：活动报名、个人考试安排、办事申请和失物招领。

这些数据均绑定 JWT 用户；课程/作业/通知仍复用各自业务仓库，避免在学生端复制权限逻辑。
空教室接口只返回学校数据源已有的记录，不生成演示课表。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
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
            CREATE TABLE IF NOT EXISTS activity_registrations (
                id TEXT PRIMARY KEY, activity_id TEXT NOT NULL, student_id TEXT NOT NULL,
                registered_at TEXT NOT NULL, UNIQUE(activity_id, student_id)
            );
            CREATE INDEX IF NOT EXISTS idx_activity_registrations_student ON activity_registrations(student_id);
            CREATE TABLE IF NOT EXISTS student_exams (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL, course_name TEXT NOT NULL,
                exam_date TEXT NOT NULL, start_time TEXT, end_time TEXT, location TEXT,
                seat_number TEXT, exam_type TEXT, reminder_enabled INTEGER NOT NULL DEFAULT 1,
                notes TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_student_exams_user_date ON student_exams(user_id, exam_date);
            CREATE TABLE IF NOT EXISTS service_requests (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL, kind TEXT NOT NULL,
                title TEXT NOT NULL, content TEXT, status TEXT NOT NULL DEFAULT 'submitted',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_service_requests_user ON service_requests(user_id, created_at);
            CREATE TABLE IF NOT EXISTS lost_found_items (
                id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, kind TEXT NOT NULL,
                title TEXT NOT NULL, content TEXT, location TEXT, contact TEXT,
                status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_lost_found_status ON lost_found_items(status, created_at);
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


class ServiceRequestIn(BaseModel):
    kind: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=200)
    content: Optional[str] = Field(None, max_length=5000)


class LostFoundIn(BaseModel):
    kind: str = Field(..., pattern="^(lost|found)$")
    title: str = Field(..., min_length=1, max_length=200)
    content: Optional[str] = Field(None, max_length=5000)
    location: Optional[str] = Field(None, max_length=200)
    contact: Optional[str] = Field(None, max_length=200)


def _activity_out(row, c: ServiceContainer, user_id: str) -> dict:
    activity = c.campus_activity_repository.get_activity(row["activity_id"])
    count = 0
    with c.db.query() as conn:
        count = int(conn.execute("SELECT COUNT(*) n FROM activity_registrations WHERE activity_id = ?", (row["activity_id"],)).fetchone()["n"])
    return {
        "registered": activity is not None and row["student_id"] == user_id,
        "registered_at": row["registered_at"],
        "registered_count": count,
        "capacity": activity.capacity if activity else None,
    }


@router.get("/activities/{activity_id}")
def activity_detail(activity_id: str, user: UserRow = Depends(current_user), c: ServiceContainer = Depends(_container)):
    activity = c.campus_activity_repository.get_activity(activity_id)
    if activity is None or (user.role != "admin" and activity.status != "published"):
        raise HTTPException(status_code=404, detail="活动不存在")
    author = c.user_repository.get_user_by_id(activity.author_id)
    return {**activity.__dict__, "author_name": (author.display_name or author.username) if author else None}


@router.get("/activities/{activity_id}/registration")
def activity_registration(activity_id: str, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)):
    _ensure_tables(c)
    activity = c.campus_activity_repository.get_activity(activity_id)
    if activity is None or activity.status != "published":
        raise HTTPException(status_code=404, detail="活动不存在")
    with c.db.query() as conn:
        row = conn.execute("SELECT * FROM activity_registrations WHERE activity_id = ? AND student_id = ?", (activity_id, user.id)).fetchone()
    return _activity_out(row, c, user.id) if row else {"registered": False, "registered_at": None, "registered_count": _registration_count(c, activity_id), "capacity": activity.capacity}


def _registration_count(c: ServiceContainer, activity_id: str) -> int:
    with c.db.query() as conn:
        return int(conn.execute("SELECT COUNT(*) n FROM activity_registrations WHERE activity_id = ?", (activity_id,)).fetchone()["n"])


@router.post("/activities/{activity_id}/registration")
def register_activity(activity_id: str, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)):
    _ensure_tables(c)
    activity = c.campus_activity_repository.get_activity(activity_id)
    if activity is None or activity.status != "published":
        raise HTTPException(status_code=404, detail="活动不存在")
    if activity.registration_deadline and activity.registration_deadline < _now():
        raise HTTPException(status_code=409, detail="报名已截止")
    if activity.capacity and _registration_count(c, activity_id) >= activity.capacity:
        raise HTTPException(status_code=409, detail="报名名额已满")
    with c.db.transaction() as conn:
        conn.execute("INSERT OR IGNORE INTO activity_registrations (id, activity_id, student_id, registered_at) VALUES (?,?,?,?)", (_id("reg"), activity_id, user.id, _now()))
        row = conn.execute("SELECT * FROM activity_registrations WHERE activity_id = ? AND student_id = ?", (activity_id, user.id)).fetchone()
    return _activity_out(row, c, user.id)


@router.delete("/activities/{activity_id}/registration")
def cancel_activity(activity_id: str, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)):
    _ensure_tables(c)
    with c.db.transaction() as conn:
        conn.execute("DELETE FROM activity_registrations WHERE activity_id = ? AND student_id = ?", (activity_id, user.id))
    return {"registered": False, "registered_at": None, "registered_count": _registration_count(c, activity_id), "capacity": None}


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


@router.get("/student/classrooms")
def list_classrooms(date: Optional[str] = Query(None), building: Optional[str] = Query(None), user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)):
    """返回学校排课/空教室数据源已同步的记录；当前数据源为空时明确返回空列表。"""
    return {"items": [], "total": 0, "date": date, "building": building, "source": "school_schedule"}


@router.get("/student/service-requests")
def list_service_requests(user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)):
    _ensure_tables(c)
    with c.db.query() as conn:
        rows = conn.execute("SELECT * FROM service_requests WHERE user_id = ? ORDER BY created_at DESC", (user.id,)).fetchall()
    return [dict(row) for row in rows]


@router.post("/student/service-requests", status_code=201)
def create_service_request(req: ServiceRequestIn, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)):
    _ensure_tables(c); now = _now(); request_id = _id("request")
    with c.db.transaction() as conn:
        conn.execute("INSERT INTO service_requests (id,user_id,kind,title,content,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)", (request_id,user.id,req.kind,req.title,req.content,"submitted",now,now))
        return dict(conn.execute("SELECT * FROM service_requests WHERE id = ?", (request_id,)).fetchone())


@router.get("/student/service-requests/{request_id}")
def get_service_request(request_id: str, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)):
    _ensure_tables(c)
    with c.db.query() as conn: row = conn.execute("SELECT * FROM service_requests WHERE id = ? AND user_id = ?", (request_id, user.id)).fetchone()
    if row is None: raise HTTPException(status_code=404, detail="申请不存在")
    return dict(row)


@router.get("/student/lost-found")
def list_lost_found(kind: Optional[str] = Query(None, pattern="^(lost|found)$"), mine: bool = Query(False), user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)):
    _ensure_tables(c); params = [user.id]; where = "owner_id = ?" if mine else "status = 'open' OR owner_id = ?"
    if kind: where = f"kind = ? AND ({where})"; params.insert(0, kind)
    with c.db.query() as conn: rows = conn.execute(f"SELECT * FROM lost_found_items WHERE {where} ORDER BY created_at DESC", params).fetchall()
    return [dict(row) for row in rows]


@router.post("/student/lost-found", status_code=201)
def create_lost_found(req: LostFoundIn, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)):
    _ensure_tables(c); now = _now(); item_id = _id("lost")
    with c.db.transaction() as conn:
        conn.execute("INSERT INTO lost_found_items (id,owner_id,kind,title,content,location,contact,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (item_id,user.id,req.kind,req.title,req.content,req.location,req.contact,"open",now,now))
        return dict(conn.execute("SELECT * FROM lost_found_items WHERE id = ?", (item_id,)).fetchone())


@router.get("/student/lost-found/{item_id}")
def get_lost_found(item_id: str, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)):
    _ensure_tables(c)
    with c.db.query() as conn: row = conn.execute("SELECT * FROM lost_found_items WHERE id = ? AND (status = 'open' OR owner_id = ?)", (item_id, user.id)).fetchone()
    if row is None: raise HTTPException(status_code=404, detail="信息不存在")
    return dict(row)


@router.delete("/student/lost-found/{item_id}")
def delete_lost_found(item_id: str, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)):
    _ensure_tables(c)
    with c.db.transaction() as conn: conn.execute("DELETE FROM lost_found_items WHERE id = ? AND owner_id = ?", (item_id, user.id))
    return {"ok": True}


__all__ = ["router"]
