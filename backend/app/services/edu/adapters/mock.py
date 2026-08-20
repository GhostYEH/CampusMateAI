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
    supported_features = ("profile", "schedule", "grade", "exam")
    implementation_status = "mock"
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

    async def login_with_cookies(
        self,
        *,
        cookies: dict,
        current_url: Optional[str] = None,
        user_agent: Optional[str] = None,
        config: Optional[dict] = None,
    ) -> dict:
        # Mock: 任何非空 cookies 视为登录成功
        if not cookies:
            raise PermissionError("Mock cookie 登录需要非空 cookies")
        # 用 cookie 数量的 hash 构造 mock id，不暴露原始 cookie 值
        import hashlib
        cookie_hash = hashlib.sha1(str(sorted(cookies.keys())).encode()).hexdigest()[:12]
        return {
            "mock": True,
            "via_cookies": True,
            "external_student_id": f"MOCK-COOKIE-{cookie_hash}",
            "cookies": dict(cookies),
        }

    async def verify_session(self, session: dict) -> bool:
        # Mock: 始终返回 True
        return True

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
        sem = semester or "2024-2025秋季(Mock)"
        return EduSchedule(
            semester=sem,
            items=[
                # A 普通课程：完整字段
                EduScheduleItem(
                    course_name="演示课程-高等数学(Mock)",
                    course_code="MOCK-MATH101",
                    teacher="张三",
                    teachers=["张三"],
                    location="逸夫楼-A101",
                    campus="主校区",
                    building="逸夫楼",
                    classroom="A101",
                    weekday=1,
                    start_section=1,
                    end_section=2,
                    start_time="08:00",
                    end_time="09:40",
                    weeks="1-16",
                    credit=4.0,
                    course_nature="专业必修",
                    course_category="学科基础课",
                    course_type="必修",
                    teaching_class="高等数学-01",
                    class_name="数学类-2401",
                    college="数学学院",
                    department="应用数学系",
                    assessment_method="考试",
                    exam_type="期末考试",
                    total_hours=64.0,
                    theory_hours=48.0,
                    practice_hours=16.0,
                    language="中文",
                    note="Mock 演示课程",
                    semester=sem,
                    semester_id="2024-2025-1",
                    extra_info={"开课学院": "数学学院", "授课语言": "中文"},
                ),
                # B 单周课程
                EduScheduleItem(
                    course_name="大学体育",
                    course_code="MOCK-PE201",
                    teacher="李老师",
                    teachers=["李老师"],
                    location="体育馆",
                    weekday=5,
                    start_section=3,
                    end_section=4,
                    start_time="14:00",
                    end_time="15:40",
                    weeks="1,3,5,7,9,11,13,15",
                    week_text="单周",
                    credit=1.0,
                    course_nature="公共必修",
                    teaching_class="体育-04",
                    college="体育教学部",
                    assessment_method="考查",
                    semester=sem,
                ),
                # C 非连续周
                EduScheduleItem(
                    course_name="实验心理学",
                    course_code="MOCK-PSY301",
                    teacher="王教授",
                    teachers=["王教授"],
                    location="心理楼-B205",
                    weekday=3,
                    start_section=3,
                    end_section=4,
                    weeks="1-8,10-16",
                    credit=3.0,
                    course_nature="专业必修",
                    teaching_class="实验心理学-01",
                    college="心理学院",
                    assessment_method="考试",
                    semester=sem,
                ),
                # D 多教师
                EduScheduleItem(
                    course_name="社会心理学",
                    course_code="MOCK-PSY203",
                    teacher="张三,李四",
                    teachers=["张三", "李四"],
                    location="逸夫楼-A302",
                    weekday=2,
                    start_section=3,
                    end_section=4,
                    start_time="10:00",
                    end_time="11:40",
                    weeks="1-8,10-16",
                    credit=2.0,
                    course_nature="专业必修",
                    course_category="专业基础课",
                    teaching_class="社会心理学-01",
                    college="社会学院",
                    assessment_method="考试",
                    semester=sem,
                ),
                # E 多地点（1-8周 A101，9-16周 B202，拆成两条 session）
                EduScheduleItem(
                    course_name="数据结构",
                    course_code="MOCK-CS201",
                    teacher="赵老师",
                    teachers=["赵老师"],
                    location="逸夫楼-A101",
                    weekday=4,
                    start_section=1,
                    end_section=2,
                    weeks="1-8",
                    credit=3.0,
                    course_nature="专业必修",
                    teaching_class="数据结构-01",
                    college="计算机学院",
                    assessment_method="考试",
                    semester=sem,
                ),
                EduScheduleItem(
                    course_name="数据结构",
                    course_code="MOCK-CS201",
                    teacher="赵老师",
                    teachers=["赵老师"],
                    location="逸夫楼-B202",
                    weekday=4,
                    start_section=1,
                    end_section=2,
                    weeks="9-16",
                    credit=3.0,
                    course_nature="专业必修",
                    teaching_class="数据结构-01",
                    college="计算机学院",
                    assessment_method="考试",
                    semester=sem,
                ),
                # F 超长课程名
                EduScheduleItem(
                    course_name="习近平新时代中国特色社会主义思想概论",
                    course_code="MOCK-POL101",
                    teacher="钱老师",
                    teachers=["钱老师"],
                    location="主楼-阶梯教室一",
                    weekday=1,
                    start_section=5,
                    end_section=6,
                    weeks="1-16",
                    credit=3.0,
                    course_nature="公共必修",
                    teaching_class="思政-01",
                    college="马克思主义学院",
                    assessment_method="考试",
                    semester=sem,
                ),
                # G 无地点
                EduScheduleItem(
                    course_name="在线慕课-创新创业基础",
                    course_code="MOCK-ONL101",
                    teacher="孙老师",
                    teachers=["孙老师"],
                    weekday=7,
                    start_section=1,
                    end_section=2,
                    weeks="1-8",
                    credit=1.0,
                    course_nature="公共选修",
                    teaching_class="慕课-01",
                    assessment_method="考查",
                    note="线上学习，无固定教室",
                    semester=sem,
                ),
                # H 无教师
                EduScheduleItem(
                    course_name="自习研讨课",
                    course_code="MOCK-SEM101",
                    location="研讨室-3",
                    weekday=6,
                    start_section=3,
                    end_section=4,
                    weeks="2-14",
                    credit=1.0,
                    course_nature="专业选修",
                    teaching_class="研讨-01",
                    assessment_method="考查",
                    semester=sem,
                ),
                # J 11-12节课程
                EduScheduleItem(
                    course_name="夜间选修-天文学导论",
                    course_code="MOCK-AST101",
                    teacher="周老师",
                    teachers=["周老师"],
                    location="天文楼-观测室",
                    weekday=3,
                    start_section=11,
                    end_section=12,
                    start_time="19:30",
                    end_time="21:10",
                    weeks="1-16",
                    credit=2.0,
                    course_nature="公共选修",
                    teaching_class="天文-01",
                    college="天文学院",
                    assessment_method="考查",
                    semester=sem,
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
