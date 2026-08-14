"""MockEduAdapter — 教务系统 Mock 适配器。

提供完整 Mock 数据，让整个 EduConnector 在无真实教务系统时也能跑通。
明确标注为 Mock 数据，不冒充真实学校数据。

仅用于：
- 开发/演示环境
- 测试
- 真实 Adapter 未实现时的降级

production 环境下 EduConnectorService 会拒绝使用 MockAdapter（除非显式开启）。
"""
from __future__ import annotations

from typing import Optional

from ....models.edu import (
    EDU_PROVIDER_MOCK,
    EDU_PROVIDER_UNSUPPORTED,
    LOGIN_EXEC_BACKEND_HTTP,
    LOGIN_EXEC_CLIENT_WEBVIEW,
)
from ....schemas.edu import (
    EduExam,
    EduExamItem,
    EduGrade,
    EduGradeItem,
    EduProfile,
    EduSchedule,
    EduScheduleItem,
)
from .base import EduAdapter


class MockEduAdapter(EduAdapter):
    """教务系统 Mock 适配器。

    明确标记 is_mock=True, provider=mock。
    仅用于开发/测试/演示/CI。Production 默认禁止自动 fallback 到 Mock。
    """

    provider = EDU_PROVIDER_MOCK
    is_mock = True
    supported_login_modes = (LOGIN_EXEC_BACKEND_HTTP, LOGIN_EXEC_CLIENT_WEBVIEW)

    async def login(
        self,
        *,
        username: str,
        password: str,
        config: Optional[dict] = None,
    ) -> dict:
        # Mock 登录：任何非空 username/password 都成功
        if not username or not password:
            raise PermissionError("Mock 登录需要非空 username/password")
        return {
            "mock": True,
            "username": username,
            "external_student_id": f"MOCK-{username}",
        }

    async def fetch_profile(self, session: dict) -> EduProfile:
        return EduProfile(
            external_student_id=session.get("external_student_id") or "MOCK-S000000001",
            name="演示同学(Mock)",
            gender="unknown",
            college="演示学院(Mock)",
            major="演示专业(Mock)",
            grade="2024",
            class_name="演示班级(Mock-1)",
            enrollment_year="2024",
            schooling_length="4",
        )

    async def fetch_schedule(self, session: dict, *, semester: Optional[str] = None) -> EduSchedule:
        return EduSchedule(
            semester=semester or "2024-2025秋季(Mock)",
            items=[
                EduScheduleItem(
                    course_name="演示课程-高等数学(Mock)",
                    course_code="MOCK-MATH101",
                    teacher="演示教师(Mock)",
                    location="演示楼-A101(Mock)",
                    weekday=1,
                    start_section=1,
                    end_section=2,
                    start_time="08:00",
                    end_time="09:40",
                    weeks="1-16",
                    semester=semester or "2024-2025秋季(Mock)",
                ),
                EduScheduleItem(
                    course_name="演示课程-程序设计基础(Mock)",
                    course_code="MOCK-CS101",
                    teacher="演示教师(Mock)",
                    location="演示楼-B202(Mock)",
                    weekday=3,
                    start_section=3,
                    end_section=4,
                    start_time="10:00",
                    end_time="11:40",
                    weeks="1-16",
                    semester=semester or "2024-2025秋季(Mock)",
                ),
            ],
        )

    async def fetch_grade(self, session: dict, *, semester: Optional[str] = None) -> EduGrade:
        return EduGrade(
            semester=semester or "2024-2025秋季(Mock)",
            gpa=3.75,
            items=[
                EduGradeItem(
                    course_name="演示课程-高等数学(Mock)",
                    course_code="MOCK-MATH101",
                    credit=4.0,
                    score="88",
                    grade_point=3.7,
                    semester=semester or "2024-2025秋季(Mock)",
                    category="必修",
                    status="已通过",
                ),
                EduGradeItem(
                    course_name="演示课程-程序设计基础(Mock)",
                    course_code="MOCK-CS101",
                    credit=3.0,
                    score="92",
                    grade_point=4.0,
                    semester=semester or "2024-2025秋季(Mock)",
                    category="必修",
                    status="已通过",
                ),
            ],
        )

    async def fetch_exam(self, session: dict, *, semester: Optional[str] = None) -> EduExam:
        return EduExam(
            semester=semester or "2024-2025秋季(Mock)",
            items=[
                EduExamItem(
                    course_name="演示课程-高等数学(Mock)",
                    course_code="MOCK-MATH101",
                    exam_type="期末考试",
                    location="演示楼-A101(Mock)",
                    seat="MOCK-001",
                    starts_at="2025-01-10T08:00:00",
                    ends_at="2025-01-10T10:00:00",
                    semester=semester or "2024-2025秋季(Mock)",
                    notes="Mock 演示考试安排",
                ),
            ],
        )


__all__ = ["MockEduAdapter"]