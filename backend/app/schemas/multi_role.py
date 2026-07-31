"""多角色协同平台请求/响应 schema (Pydantic v2)。

涵盖: 认证、用户、课程、班级、选课、通知、任务、提交、附件、工作台、分页。
所有时间字段以 ISO 8601 字符串(带时区)表示。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ===== 分页通用 =====


class PageMeta(BaseModel):
    total: int = 0
    page: int = 1
    page_size: int = 20
    has_more: bool = False


class Page(BaseModel):
    """统一分页响应。"""
    items: List[Any] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    has_more: bool = False

    @classmethod
    def from_rows(
        cls,
        items: List[Any],
        *,
        total: int,
        page: int,
        page_size: int,
    ) -> "Page":
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=(page * page_size) < total,
        )


# ===== 认证 =====


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


class UserPublic(BaseModel):
    id: str
    username: str
    role: str
    display_name: Optional[str] = None
    student_number: Optional[str] = None
    teacher_number: Optional[str] = None
    college: Optional[str] = None
    major: Optional[str] = None
    grade: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(..., description="access token 有效期(秒)")
    expires_at: str = Field(..., description="access token 到期时间(ISO 8601)")
    user: UserPublic


class UserCreate(BaseModel):
    """管理员创建用户请求(仅 admin 角色可调用)。

    约束:
    - username: 3-64 字符,仅字母/数字/下划线
    - password: 8-128 字符(由后端 PBKDF2 哈希后存储,不入日志)
    - role: student / teacher / admin
    - 学号/工号二选一,与角色一致(student→student_number,teacher→teacher_number)
    """

    username: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(..., pattern="^(student|teacher|admin)$")
    display_name: Optional[str] = Field(None, max_length=128)
    student_number: Optional[str] = Field(None, max_length=32)
    teacher_number: Optional[str] = Field(None, max_length=32)
    college: Optional[str] = Field(None, max_length=64)
    major: Optional[str] = Field(None, max_length=64)
    grade: Optional[str] = Field(None, max_length=32)


class UserAdminUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=128)
    role: Optional[str] = Field(None, pattern="^(student|teacher|admin)$")
    college: Optional[str] = Field(None, max_length=64)
    major: Optional[str] = Field(None, max_length=64)
    grade: Optional[str] = Field(None, max_length=32)
    is_active: Optional[bool] = None


class RegisterRequest(BaseModel):
    """公开注册请求(无需鉴权,仅限 student/teacher 自注册)。

    约束:
    - username: 3-64 字符,仅字母/数字/下划线
    - password: 8-128 字符
    - role: 仅允许 student / teacher(admin 必须由管理员创建)
    - display_name: 选填,≤128 字符
    - student_number / teacher_number: 选填,与 role 一致(后端校验)
    - college / major / grade: 选填,学生常用
    """

    username: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field("student", pattern="^(student|teacher)$")
    display_name: Optional[str] = Field(None, max_length=128)
    student_number: Optional[str] = Field(None, max_length=32)
    teacher_number: Optional[str] = Field(None, max_length=32)
    college: Optional[str] = Field(None, max_length=64)
    major: Optional[str] = Field(None, max_length=64)
    grade: Optional[str] = Field(None, max_length=32)


class AuthMeResponse(BaseModel):
    user: UserPublic
    access_token: Optional[str] = None
    expires_in: Optional[int] = None


# ===== 课程 =====


class CourseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    code: Optional[str] = Field(None, max_length=64)
    semester: Optional[str] = Field(None, max_length=32)
    description: Optional[str] = Field(None, max_length=2000)
    status: str = Field("draft", pattern="^(draft|active|archived)$")


class CourseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    code: Optional[str] = Field(None, max_length=64)
    semester: Optional[str] = Field(None, max_length=32)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[str] = Field(None, pattern="^(draft|active|archived)$")


class CourseOut(BaseModel):
    id: str
    name: str
    code: Optional[str] = None
    semester: Optional[str] = None
    description: Optional[str] = None
    teacher_id: str
    teacher_name: Optional[str] = None
    status: str
    created_at: str
    updated_at: str


# ===== 班级 =====


class ClassCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    class_code: Optional[str] = Field(None, max_length=64)
    description: Optional[str] = Field(None, max_length=2000)
    capacity: Optional[int] = Field(None, ge=1, le=1000)


class ClassUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    class_code: Optional[str] = Field(None, max_length=64)
    description: Optional[str] = Field(None, max_length=2000)
    capacity: Optional[int] = Field(None, ge=1, le=1000)


class ClassOut(BaseModel):
    id: str
    course_id: str
    name: str
    class_code: Optional[str] = None
    invite_code: str
    description: Optional[str] = None
    capacity: Optional[int] = None
    created_at: str
    updated_at: str


class ClassJoinRequest(BaseModel):
    invite_code: str = Field(..., min_length=1, max_length=32)


class ClassMemberOut(BaseModel):
    user_id: str
    username: str
    display_name: Optional[str] = None
    student_number: Optional[str] = None
    teacher_number: Optional[str] = None
    college: Optional[str] = None
    major: Optional[str] = None
    grade: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    enrollment_id: str
    member_role: str
    status: str
    joined_at: str


# ===== 通知 =====


class AnnouncementCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=20000)
    require_read: bool = False
    status: str = Field("draft", pattern="^(draft|published|archived)$")


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1, max_length=20000)
    require_read: Optional[bool] = None
    status: Optional[str] = Field(None, pattern="^(draft|published|archived)$")


class AnnouncementOut(BaseModel):
    id: str
    class_group_id: str
    author_id: str
    author_name: Optional[str] = None
    title: str
    content: str
    require_read: bool
    status: str
    published_at: Optional[str] = None
    created_at: str
    updated_at: str
    has_read: Optional[bool] = Field(None, description="当前学生视角是否已读(教师/管理员为 null)")


class ReadReceiptOut(BaseModel):
    user_id: str
    username: str
    display_name: Optional[str] = None
    student_number: Optional[str] = None
    read_at: str


class ReadStatusOut(BaseModel):
    announcement_id: str
    total_recipients: int
    read_count: int
    unread_count: int
    receipts: List[ReadReceiptOut] = Field(default_factory=list)


# ===== 全校活动 =====


class CampusActivityCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    summary: Optional[str] = Field(None, max_length=500)
    content: str = Field(..., min_length=1, max_length=20000)
    category: str = Field(
        "campus",
        pattern="^(campus|academic|volunteer|competition|lecture|sports)$",
    )
    location: Optional[str] = Field(None, max_length=200)
    registration_deadline: Optional[str] = None
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    capacity: Optional[int] = Field(None, ge=1, le=100000)
    status: str = Field("draft", pattern="^(draft|published)$")


class CampusActivityUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    summary: Optional[str] = Field(None, max_length=500)
    content: Optional[str] = Field(None, min_length=1, max_length=20000)
    category: Optional[str] = Field(
        None,
        pattern="^(campus|academic|volunteer|competition|lecture|sports)$",
    )
    location: Optional[str] = Field(None, max_length=200)
    registration_deadline: Optional[str] = None
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    capacity: Optional[int] = Field(None, ge=1, le=100000)
    status: Optional[str] = Field(
        None,
        pattern="^(draft|published|closed|archived)$",
    )


class CampusActivityOut(BaseModel):
    id: str
    author_id: str
    author_name: Optional[str] = None
    title: str
    summary: Optional[str] = None
    content: str
    category: str
    location: Optional[str] = None
    registration_deadline: Optional[str] = None
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    capacity: Optional[int] = None
    status: str
    published_at: Optional[str] = None
    created_at: str
    updated_at: str


# ===== 任务 =====


class AssignmentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=20000)
    deadline: Optional[str] = Field(None, description="ISO 8601 带时区")
    submission_types: List[str] = Field(default_factory=list, max_length=10)
    max_score: Optional[float] = Field(None, ge=0, le=1000)
    allow_resubmit: bool = True
    status: str = Field("draft", pattern="^(draft|published|closed|archived)$")


class AssignmentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=20000)
    deadline: Optional[str] = None
    submission_types: Optional[List[str]] = Field(None, max_length=10)
    max_score: Optional[float] = Field(None, ge=0, le=1000)
    allow_resubmit: Optional[bool] = None
    status: Optional[str] = Field(None, pattern="^(draft|published|closed|archived)$")


class AssignmentOut(BaseModel):
    id: str
    class_group_id: str
    author_id: str
    author_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    deadline: Optional[str] = None
    submission_types: List[str] = Field(default_factory=list)
    max_score: Optional[float] = None
    allow_resubmit: bool
    status: str
    published_at: Optional[str] = None
    created_at: str
    updated_at: str
    attachments: List["AssignmentAttachmentOut"] = Field(default_factory=list)


class AssignmentAttachmentOut(BaseModel):
    id: str
    assignment_id: str
    author_id: str
    original_filename: str
    stored_filename: str
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    created_at: str


class AssignmentStatsOut(BaseModel):
    assignment_id: str
    total_students: int
    submitted: int
    not_submitted: int
    draft: int
    late: int
    graded: int
    pending_grading: int
    avg_score: Optional[float] = None


class StudentStatusItem(BaseModel):
    student_id: str
    student_name: str
    student_number: Optional[str] = None
    submission_id: Optional[str] = None
    submission_status: str
    submitted_at: Optional[str] = None
    is_late: bool
    score: Optional[float] = None
    teacher_comment: Optional[str] = None
    read_status: str
    read_at: Optional[str] = None


# ===== 提交 =====


class SubmissionCreate(BaseModel):
    text_content: Optional[str] = Field(None, max_length=50000)
    submit: bool = False  # True=直接提交,False=保存草稿


class SubmissionUpdate(BaseModel):
    text_content: Optional[str] = Field(None, max_length=50000)


class SubmissionGrade(BaseModel):
    score: Optional[float] = Field(None, ge=0, le=1000)
    teacher_comment: Optional[str] = Field(None, max_length=5000)


class AttachmentOut(BaseModel):
    id: str
    submission_id: str
    original_filename: str
    stored_filename: str
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    created_at: str


class SubmissionOut(BaseModel):
    id: str
    assignment_id: str
    student_id: str
    student_name: Optional[str] = None
    student_number: Optional[str] = None
    college: Optional[str] = None
    major: Optional[str] = None
    grade: Optional[str] = None
    text_content: Optional[str] = None
    status: str
    submitted_at: Optional[str] = None
    updated_at: str
    score: Optional[float] = None
    teacher_comment: Optional[str] = None
    attachments: List[AttachmentOut] = Field(default_factory=list)


# ===== 工作台 =====


class TeacherDashboard(BaseModel):
    course_count: int
    class_count: int
    student_count: int
    active_assignment_count: int
    pending_submission_count: int
    unread_announcement_count: int
    overdue_student_count: int
    recent_assignments: List[dict] = Field(default_factory=list)
    recent_activity: List[dict] = Field(default_factory=list)


class StudentDashboard(BaseModel):
    enrolled_course_count: int
    unread_announcement_count: int
    pending_assignment_count: int
    overdue_assignment_count: int
    due_soon_assignments: List[dict] = Field(default_factory=list)
    recent_announcements: List[dict] = Field(default_factory=list)
    # 个人待办(学生从通知抽取,与教师发布的 assignments 严格分离)
    pending_personal_task_count: int = 0
    overdue_personal_task_count: int = 0
    due_soon_personal_tasks: List[dict] = Field(default_factory=list)


# ===== AI 上下文 =====


class CounselorContext(BaseModel):
    """AI 导员请求的可选教学上下文(权限校验由后端执行)。"""
    course_id: Optional[str] = None
    class_id: Optional[str] = None
    assignment_id: Optional[str] = None
    announcement_id: Optional[str] = None


# ===== 教师视角聚合(跨班级) =====


class TeacherAssignmentListItem(BaseModel):
    """教师视角的任务列表项(含班级/课程名 + 提交统计)。"""
    id: str
    class_group_id: str
    author_id: str
    title: str
    description: Optional[str] = None
    deadline: Optional[str] = None
    submission_types: List[str] = Field(default_factory=list)
    max_score: Optional[float] = None
    allow_resubmit: bool = True
    status: str
    published_at: Optional[str] = None
    created_at: str
    updated_at: str
    class_id: str
    class_name: str
    course_id: str
    course_name: str
    course_code: Optional[str] = None
    student_count: int = 0
    submitted_count: int = 0
    late_count: int = 0
    graded_count: int = 0
    avg_score: Optional[float] = None


class TeacherAnnouncementListItem(BaseModel):
    """教师视角的通知列表项(含班级/课程名 + 已读统计)。"""
    id: str
    class_group_id: str
    author_id: str
    title: str
    content: str
    require_read: bool = False
    status: str
    published_at: Optional[str] = None
    created_at: str
    updated_at: str
    class_id: str
    class_name: str
    course_id: str
    course_name: str
    total_recipients: int = 0
    read_count: int = 0
    unread_count: int = 0


class TeacherSubmissionListItem(BaseModel):
    """教师视角的提交列表项(含作业/班级/课程/学生信息)。"""
    id: str
    assignment_id: str
    assignment_title: str
    assignment_max_score: Optional[float] = None
    assignment_deadline: Optional[str] = None
    assignment_status: str
    student_id: str
    student_name: Optional[str] = None
    student_number: Optional[str] = None
    college: Optional[str] = None
    major: Optional[str] = None
    grade: Optional[str] = None
    class_id: str
    class_name: str
    course_id: str
    course_name: str
    text_content: Optional[str] = None
    status: str
    submitted_at: Optional[str] = None
    updated_at: str
    score: Optional[float] = None
    teacher_comment: Optional[str] = None
    is_late: bool = False


class TeacherAnalyticsAssignmentItem(BaseModel):
    assignment_id: str
    title: str
    deadline: Optional[str] = None
    status: str
    max_score: Optional[float] = None
    class_name: str
    course_name: str
    total_students: int
    submitted: int
    unsubmitted: int
    late: int
    graded: int
    avg_score: Optional[float] = None
    max_score_achieved: Optional[float] = None
    min_score_achieved: Optional[float] = None
    submission_rate: Optional[float] = None
    grading_rate: Optional[float] = None


class TeacherAnalyticsStudentItem(BaseModel):
    student_id: str
    student_name: Optional[str] = None
    student_number: Optional[str] = None
    class_name: str
    course_name: str
    total_assignments: int
    submitted_assignments: int
    unsubmitted_assignments: int
    graded_assignments: int
    avg_score: Optional[float] = None
    completion_rate: Optional[float] = None


class TeacherAnalyticsFrequentUnsubmitted(BaseModel):
    student_id: str
    student_name: Optional[str] = None
    student_number: Optional[str] = None
    class_name: str
    course_name: str
    unsubmitted_count: int
    total_assignments: int


class TeacherAnalyticsOut(BaseModel):
    total_assignments: int
    total_submitted: int
    total_expected_submissions: int
    total_unsubmitted: int
    total_late: int
    total_graded: int
    total_pending_grading: int
    overall_submission_rate: Optional[float] = None
    overall_grading_rate: Optional[float] = None
    overall_avg_score: Optional[float] = None
    overall_max_score: Optional[float] = None
    overall_min_score: Optional[float] = None
    score_distribution: Dict[str, int] = Field(default_factory=dict)
    assignments: List[TeacherAnalyticsAssignmentItem] = Field(default_factory=list)
    students: List[TeacherAnalyticsStudentItem] = Field(default_factory=list)
    frequent_unsubmitted_students: List[TeacherAnalyticsFrequentUnsubmitted] = Field(default_factory=list)


class TeacherTodayOut(BaseModel):
    """教师今日待处理聚合(待批改/临近截止/未提交/未读通知/草稿)。"""
    pending_grading_count: int = 0
    due_soon_assignment_count: int = 0
    unsubmitted_student_count: int = 0
    unread_announcement_count: int = 0
    draft_assignment_count: int = 0
    draft_announcement_count: int = 0
    pending_grading: List[dict] = Field(default_factory=list)
    due_soon_assignments: List[dict] = Field(default_factory=list)


__all__ = [
    "PageMeta",
    "Page",
    "LoginRequest",
    "RefreshRequest",
    "LogoutRequest",
    "TokenPair",
    "UserPublic",
    "UserCreate",
    "UserAdminUpdate",
    "RegisterRequest",
    "AuthMeResponse",
    "CourseCreate",
    "CourseUpdate",
    "CourseOut",
    "ClassCreate",
    "ClassUpdate",
    "ClassOut",
    "ClassJoinRequest",
    "ClassMemberOut",
    "AnnouncementCreate",
    "AnnouncementUpdate",
    "AnnouncementOut",
    "ReadReceiptOut",
    "ReadStatusOut",
    "CampusActivityCreate",
    "CampusActivityUpdate",
    "CampusActivityOut",
    "AssignmentCreate",
    "AssignmentUpdate",
    "AssignmentOut",
    "AssignmentStatsOut",
    "StudentStatusItem",
    "SubmissionCreate",
    "SubmissionUpdate",
    "SubmissionGrade",
    "AttachmentOut",
    "AssignmentAttachmentOut",
    "SubmissionOut",
    "TeacherDashboard",
    "StudentDashboard",
    "CounselorContext",
    "TeacherAssignmentListItem",
    "TeacherAnnouncementListItem",
    "TeacherSubmissionListItem",
    "TeacherAnalyticsAssignmentItem",
    "TeacherAnalyticsStudentItem",
    "TeacherAnalyticsFrequentUnsubmitted",
    "TeacherAnalyticsOut",
    "TeacherTodayOut",
]
