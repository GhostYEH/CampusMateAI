"""学生端扩展能力：个人考试安排。

这些数据均绑定 JWT 用户；课程/作业/通知仍复用各自业务仓库，避免在学生端复制权限逻辑。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException

from ...models.multi_role import UserRow
from ...schemas.student_exam import ExamIn
from ...services.container import ServiceContainer, get_container
from ..deps import require_role

router = APIRouter(tags=["考试安排"])


def _container() -> ServiceContainer:
    return get_container()


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
def list_exams(
    user: UserRow = Depends(require_role("student")),
    c: ServiceContainer = Depends(_container),
):
    """列出当前学生的全部考试安排，按考试日期与开始时间排序。"""
    return c.student_exam_repository.list_exams(user_id=user.id)


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
    return c.student_exam_repository.create_exam(
        user_id=user.id, fields=req.model_dump()
    )


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
    exam = c.student_exam_repository.update_exam(
        exam_id=exam_id, user_id=user.id, fields=req.model_dump()
    )
    if exam is None:
        raise HTTPException(status_code=404, detail="考试记录不存在")
    return exam


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
def delete_exam(
    exam_id: str,
    user: UserRow = Depends(require_role("student")),
    c: ServiceContainer = Depends(_container),
):
    """删除当前学生的指定考试安排，成功返回 ok 标记。"""
    c.student_exam_repository.delete_exam(exam_id=exam_id, user_id=user.id)
    return {"ok": True}


__all__ = ["router"]
