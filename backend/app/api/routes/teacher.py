"""教师视角聚合路由 — 跨班级的任務/通知/提交列表 + 學情分析 + 今日待處理。

權限:
- 所有接口僅限教師與管理員(管理員視角為空或全量,此處僅返回教師本人數據)。
- 教師只能看到自己所轄課程下的數據,後端按 teacher_id 嚴格隔離。
- 學生禁止訪問。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ...core.exceptions import Forbidden
from ...models.multi_role import UserRow
from ...schemas.multi_role import (
    Page,
    TeacherAnalyticsOut,
    TeacherAnnouncementListItem,
    TeacherAssignmentListItem,
    TeacherSubmissionListItem,
    TeacherTodayOut,
)
from ...services.container import ServiceContainer, get_container
from ..deps import current_user

router = APIRouter(prefix="/teacher", tags=["teacher"])


def _container() -> ServiceContainer:
    return get_container()


def _assert_teacher_or_admin(user: UserRow) -> None:
    if user.role == "student":
        raise Forbidden("学生无权访问教师聚合接口")


@router.get("/assignments", response_model=Page)
def list_teacher_assignments(
    status: Optional[str] = Query(
        None, pattern="^(draft|published|closed|archived)$"
    ),
    class_id: Optional[str] = Query(None),
    course_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> Page:
    """列出教师所轄課程下的所有任務(含班級/課程名 + 提交統計)。"""
    _assert_teacher_or_admin(user)
    if user.role == "admin":
        # 管理員不返回個人教師數據(避免誤用);如需全量請走各業務路由
        return Page(items=[], total=0, page=page, page_size=page_size, has_more=False)
    items, total = container.submission_repository.list_assignments_for_teacher(
        user.id,
        status=status,
        class_id=class_id,
        course_id=course_id,
        search=search,
        page=page,
        page_size=page_size,
    )
    typed = [TeacherAssignmentListItem(**item) for item in items]
    return Page.from_rows(typed, total=total, page=page, page_size=page_size)


@router.get("/announcements", response_model=Page)
def list_teacher_announcements(
    status: Optional[str] = Query(
        None, pattern="^(draft|published|archived)$"
    ),
    class_id: Optional[str] = Query(None),
    course_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> Page:
    """列出教师所轄課程下的所有通知(含班級/課程名 + 已讀統計)。"""
    _assert_teacher_or_admin(user)
    if user.role == "admin":
        return Page(items=[], total=0, page=page, page_size=page_size, has_more=False)
    items, total = container.submission_repository.list_announcements_for_teacher(
        user.id,
        status=status,
        class_id=class_id,
        course_id=course_id,
        search=search,
        page=page,
        page_size=page_size,
    )
    typed = [TeacherAnnouncementListItem(**item) for item in items]
    return Page.from_rows(typed, total=total, page=page, page_size=page_size)


@router.get("/submissions", response_model=Page)
def list_teacher_submissions(
    assignment_id: Optional[str] = Query(None),
    class_id: Optional[str] = Query(None),
    course_id: Optional[str] = Query(None),
    status: Optional[str] = Query(
        None, pattern="^(draft|submitted|resubmitted|late)$"
    ),
    graded: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> Page:
    """列出教师所轄課程下的所有提交(含作業/班級/課程/學生信息)。"""
    _assert_teacher_or_admin(user)
    if user.role == "admin":
        return Page(items=[], total=0, page=page, page_size=page_size, has_more=False)
    items, total = container.submission_repository.list_submissions_for_teacher(
        user.id,
        assignment_id=assignment_id,
        class_id=class_id,
        course_id=course_id,
        status=status,
        graded=graded,
        search=search,
        page=page,
        page_size=page_size,
    )
    typed = [TeacherSubmissionListItem(**item) for item in items]
    return Page.from_rows(typed, total=total, page=page, page_size=page_size)


@router.get("/analytics", response_model=TeacherAnalyticsOut)
def teacher_analytics(
    class_id: Optional[str] = Query(None),
    course_id: Optional[str] = Query(None),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> TeacherAnalyticsOut:
    """教师學情聚合(所有數字來自真實 SQL 聚合,不寫死)。"""
    _assert_teacher_or_admin(user)
    if user.role == "admin":
        return TeacherAnalyticsOut(
            total_assignments=0,
            total_submitted=0,
            total_expected_submissions=0,
            total_unsubmitted=0,
            total_late=0,
            total_graded=0,
            total_pending_grading=0,
        )
    data = container.submission_repository.teacher_analytics(
        user.id, class_id=class_id, course_id=course_id,
    )
    return TeacherAnalyticsOut(**data)


@router.get("/today", response_model=TeacherTodayOut)
def teacher_today(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> TeacherTodayOut:
    """教师今日待處理聚合: 待批改/臨近截止/未提交/未讀通知/草稿。

    所有數字來自真實 SQL,不寫死。
    """
    _assert_teacher_or_admin(user)
    if user.role == "admin":
        return TeacherTodayOut()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    soon_iso = (now + timedelta(days=3)).isoformat()
    sub_repo = container.submission_repository
    asg_repo = container.assignment_repository
    ann_repo = container.announcement_repository

    # 待批改(已提交未評分,最近 10 條)
    pending_items, pending_count = sub_repo.list_submissions_for_teacher(
        user.id, graded=False, page=1, page_size=10,
    )
    # 臨近截止(3 天內未截止的已發佈作業)
    all_asg, _ = sub_repo.list_assignments_for_teacher(
        user.id, status="published", page=1, page_size=200,
    )
    due_soon = []
    unsubmitted_total = 0
    for a in all_asg:
        if a["deadline"]:
            try:
                dl = datetime.fromisoformat(a["deadline"].replace("Z", "+00:00"))
            except ValueError:
                continue
            if now <= dl <= (now + timedelta(days=3)):
                due_soon.append({
                    "assignment_id": a["id"],
                    "title": a["title"],
                    "deadline": a["deadline"],
                    "class_name": a["class_name"],
                    "course_name": a["course_name"],
                    "unsubmitted_count": max(
                        0, a["student_count"] - a["submitted_count"]
                    ),
                })
        unsubmitted_total += max(0, a["student_count"] - a["submitted_count"])

    # 草稿數量
    draft_asg, draft_asg_count = sub_repo.list_assignments_for_teacher(
        user.id, status="draft", page=1, page_size=200,
    )
    draft_ann, draft_ann_count = sub_repo.list_announcements_for_teacher(
        user.id, status="draft", page=1, page_size=200,
    )

    unread_announcements = sub_repo.count_teacher_unread_announcements(teacher_id=user.id)

    return TeacherTodayOut(
        pending_grading_count=pending_count,
        due_soon_assignment_count=len(due_soon),
        unsubmitted_student_count=unsubmitted_total,
        unread_announcement_count=unread_announcements,
        draft_assignment_count=draft_asg_count,
        draft_announcement_count=draft_ann_count,
        pending_grading=pending_items,
        due_soon_assignments=due_soon,
    )


__all__ = ["router"]
