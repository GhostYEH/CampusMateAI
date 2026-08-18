"""学生端扩展能力：个人考试安排、办事申请和失物招领。

这些数据均绑定 JWT 用户；课程/作业/通知仍复用各自业务仓库，避免在学生端复制权限逻辑。
空教室接口只返回学校数据源已有的记录，不生成演示课表。
"""
from __future__ import annotations

import json
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
                university_id TEXT, title TEXT NOT NULL, content TEXT, location TEXT, contact TEXT,
                contact_visibility TEXT NOT NULL DEFAULT 'private',
                status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_lost_found_status ON lost_found_items(status, created_at);
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(lost_found_items)")}
        if "university_id" not in columns:
            conn.execute("ALTER TABLE lost_found_items ADD COLUMN university_id TEXT")
        if "contact_visibility" not in columns:
            conn.execute("ALTER TABLE lost_found_items ADD COLUMN contact_visibility TEXT NOT NULL DEFAULT 'private'")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_lost_found_university ON lost_found_items(university_id,status,created_at)")


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
    contact_visibility: str = Field("private", pattern="^(private|public)$")


def _university_id(user: UserRow) -> str:
    if not user.university_id:
        from .community import UniversityRequired
        raise UniversityRequired()
    return user.university_id


def _lost_found_out(row, viewer_id: str) -> dict:
    result = dict(row)
    if result.get("owner_id") != viewer_id and result.get("contact_visibility") != "public":
        result["contact"] = None
    return result


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
    _ensure_tables(c); university_id = _university_id(user)
    rows, _ = c.community_repository.list_posts(university_id, q=None, page=1, page_size=200, category="lostfound", sort="time")
    items = []
    for post in rows:
        extra = json.loads(post.get("extra_json", "{}") or "{}")
        if kind and extra.get("kind") != kind:
            continue
        if mine and post["author_id"] != user.id:
            continue
        items.append(_lost_found_from_post(post, user.id))
    return items


@router.post("/student/lost-found", status_code=201)
def create_lost_found(req: LostFoundIn, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)):
    _ensure_tables(c); university_id = _university_id(user)
    extra = {"kind": req.kind, "contact_visibility": req.contact_visibility}
    if req.location:
        extra["location"] = req.location
    if req.contact:
        extra["contact"] = req.contact
    post = c.community_repository.create_post(
        university_id=university_id, author_id=user.id, title=req.title,
        content=req.content or "", category="lostfound", images=[], is_anonymous=False, extra=extra,
    )
    return _lost_found_from_post(post, user.id)


@router.get("/student/lost-found/{item_id}")
def get_lost_found(item_id: str, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)):
    _ensure_tables(c); _university_id(user)
    post = c.community_repository.get_post(item_id)
    if post is None or post["category"] != "lostfound" or post["university_id"] != user.university_id:
        raise HTTPException(status_code=404, detail="信息不存在")
    if post["status"] != "published" and post["author_id"] != user.id:
        raise HTTPException(status_code=404, detail="信息不存在")
    return _lost_found_from_post(post, user.id)


@router.delete("/student/lost-found/{item_id}")
def delete_lost_found(item_id: str, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)):
    _ensure_tables(c)
    post = c.community_repository.get_post(item_id)
    if post is not None and post["author_id"] == user.id:
        c.community_repository.set_post_status(item_id, "deleted")
    return {"ok": True}


def _lost_found_from_post(post: dict, viewer_id: str) -> dict:
    extra = json.loads(post.get("extra_json", "{}") or "{}")
    is_owner = post["author_id"] == viewer_id
    contact = extra.get("contact")
    if not is_owner and extra.get("contact_visibility", "private") != "public":
        contact = None
    return {
        "id": post["id"], "owner_id": post["author_id"], "kind": extra.get("kind", "lost"),
        "university_id": post["university_id"], "title": post["title"], "content": post["content"],
        "location": extra.get("location"), "contact": contact,
        "contact_visibility": extra.get("contact_visibility", "private"),
        "status": post["status"], "created_at": post["created_at"], "updated_at": post["updated_at"],
    }


__all__ = ["router"]
