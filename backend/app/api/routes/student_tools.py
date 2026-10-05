"""学生端扩展能力：个人考试安排。

这些数据均绑定 JWT 用户；课程/作业/通知仍复用各自业务仓库，避免在学生端复制权限逻辑。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from ...models.multi_role import UserRow
from ...services.container import ServiceContainer, get_container
from ..deps import require_role

router = APIRouter(tags=["考试安排"])


def _container() -> ServiceContainer:
    return get_container()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


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


@router.get(
    "/student/exams",
    summary="列出考试安排",
    responses={
        200: {
            "description": "返回当前学生的考试安排列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "考试安排列表",
                            "value": [
                                {
                                    "id": "exam_math_final_2026",
                                    "user_id": "u_demo",
                                    "course_name": "高等数学",
                                    "exam_date": "2026-12-30",
                                    "start_time": "09:00",
                                    "end_time": "11:00",
                                    "location": "第三教学楼 201",
                                    "seat_number": "A-018",
                                    "exam_type": "期末考试",
                                    "reminder_enabled": True,
                                    "notes": "可携带计算器",
                                    "created_at": "2026-10-06T10:00:00+08:00",
                                    "updated_at": "2026-10-06T10:00:00+08:00",
                                }
                            ],
                        }
                    }
                }
            },
        },
    },
)
def list_exams(user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)):
    """列出当前学生的全部考试安排，按考试日期与开始时间排序。"""
    with c.db.query() as conn:
        rows = conn.execute("SELECT * FROM student_exams WHERE user_id = ? ORDER BY exam_date, start_time", (user.id,)).fetchall()
    return [dict(row) for row in rows]


@router.post(
    "/student/exams",
    status_code=201,
    summary="创建考试安排",
    responses={
        201: {
            "description": "创建成功，返回新建的考试安排",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "新建的考试安排",
                            "value": {
                                "id": "exam_math_final_2026",
                                "user_id": "u_demo",
                                "course_name": "高等数学",
                                "exam_date": "2026-12-30",
                                "start_time": "09:00",
                                "end_time": "11:00",
                                "location": "第三教学楼 201",
                                "seat_number": "A-018",
                                "exam_type": "期末考试",
                                "reminder_enabled": True,
                                "notes": "可携带计算器",
                                "created_at": "2026-10-06T10:00:00+08:00",
                                "updated_at": "2026-10-06T10:00:00+08:00",
                            },
                        }
                    }
                }
            },
        },
    },
)
def create_exam(
    req: Annotated[
        ExamIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "创建高等数学期末考试",
                    "value": {
                        "course_name": "高等数学",
                        "exam_date": "2026-12-30",
                        "start_time": "09:00",
                        "end_time": "11:00",
                        "location": "第三教学楼 201",
                        "seat_number": "A-018",
                        "exam_type": "期末考试",
                        "reminder_enabled": True,
                        "notes": "可携带计算器",
                    },
                }
            }
        ),
    ],
    user: UserRow = Depends(require_role("student")),
    c: ServiceContainer = Depends(_container),
):
    """为当前学生创建一条考试安排并返回创建结果。"""
    now = _now(); exam_id = _id("exam")
    with c.db.transaction() as conn:
        conn.execute("INSERT INTO student_exams (id,user_id,course_name,exam_date,start_time,end_time,location,seat_number,exam_type,reminder_enabled,notes,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (exam_id,user.id,req.course_name,req.exam_date,req.start_time,req.end_time,req.location,req.seat_number,req.exam_type,int(req.reminder_enabled),req.notes,now,now))
        row = conn.execute("SELECT * FROM student_exams WHERE id = ?", (exam_id,)).fetchone()
    return dict(row)


@router.patch(
    "/student/exams/{exam_id}",
    summary="更新考试安排",
    responses={
        200: {
            "description": "更新成功，返回最新的考试安排",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "更新后的考试安排",
                            "value": {
                                "id": "exam_math_final_2026",
                                "user_id": "u_demo",
                                "course_name": "高等数学",
                                "exam_date": "2026-12-31",
                                "start_time": "14:00",
                                "end_time": "16:00",
                                "location": "第三教学楼 305",
                                "seat_number": "A-018",
                                "exam_type": "期末考试",
                                "reminder_enabled": True,
                                "notes": "可携带计算器",
                                "created_at": "2026-10-06T10:00:00+08:00",
                                "updated_at": "2026-10-06T11:30:00+08:00",
                            },
                        }
                    }
                }
            },
        },
    },
)
def update_exam(
    exam_id: str,
    req: Annotated[
        ExamIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "调整考试时间地点",
                    "value": {
                        "course_name": "高等数学",
                        "exam_date": "2026-12-31",
                        "start_time": "14:00",
                        "end_time": "16:00",
                        "location": "第三教学楼 305",
                        "seat_number": "A-018",
                        "exam_type": "期末考试",
                        "reminder_enabled": True,
                        "notes": "可携带计算器",
                    },
                }
            }
        ),
    ],
    user: UserRow = Depends(require_role("student")),
    c: ServiceContainer = Depends(_container),
):
    """更新指定考试安排（course_name 与 exam_date 必填）；记录不存在或不属于当前学生返回 404。"""
    with c.db.transaction() as conn:
        result = conn.execute("UPDATE student_exams SET course_name=?,exam_date=?,start_time=?,end_time=?,location=?,seat_number=?,exam_type=?,reminder_enabled=?,notes=?,updated_at=? WHERE id=? AND user_id=?", (req.course_name,req.exam_date,req.start_time,req.end_time,req.location,req.seat_number,req.exam_type,int(req.reminder_enabled),req.notes,_now(),exam_id,user.id))
        if result.rowcount == 0: raise HTTPException(status_code=404, detail="考试记录不存在")
        return dict(conn.execute("SELECT * FROM student_exams WHERE id = ?", (exam_id,)).fetchone())


@router.delete(
    "/student/exams/{exam_id}",
    summary="删除考试安排",
    responses={
        200: {
            "description": "删除成功",
            "content": {
                "application/json": {
                    "examples": {"成功": {"summary": "删除成功", "value": {"ok": True}}}
                }
            },
        },
    },
)
def delete_exam(exam_id: str, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)):
    """删除当前学生的指定考试安排，成功返回 ok 标记。"""
    with c.db.transaction() as conn:
        conn.execute("DELETE FROM student_exams WHERE id = ? AND user_id = ?", (exam_id, user.id))
    return {"ok": True}


__all__ = ["router"]
