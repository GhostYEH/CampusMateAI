"""多角色演示数据 seeding —— 仅在开发/演示环境使用。

明确标注为演示数据，不得冒充真实学校数据。
启动时幂等执行: 已存在的演示账号与课程不会重复创建。
"""
from __future__ import annotations

import logging
from typing import Optional

from ..core.config import Settings
from ..core.security import hash_password
from ..models.multi_role import UserRow
from ..repositories.multi_role_repository import (
    AnnouncementRepository,
    AssignmentRepository,
    ClassGroupRepository,
    CourseRepository,
    EnrollmentRepository,
    SubmissionRepository,
    UserRepository,
)
from ..services.container import ServiceContainer

logger = logging.getLogger(__name__)

DEMO_PASSWORD = "Demo123456"

# (username, role, display_name, student/teacher_number, college, major, grade)
DEMO_USERS = [
    ("teacher_demo", "teacher", "李老师(演示)", None, "T2024001", "信息工程学院", "计算机系", None),
    ("teacher_demo2", "teacher", "王老师(演示)", None, "T2024002", "外国语学院", "英语系", None),
    ("student_demo", "student", "陈同学(演示)", "S202401001", None, "信息工程学院", "计算机科学与技术", "2024"),
    ("admin_demo", "admin", "管理员(演示)", None, None, None, None, None),
]

# 30 名学生演示账号
def _demo_students() -> list[tuple[str, str, str, str, str, str, str, str]]:
    rows: list[tuple[str, str, str, str, str, str, str, str]] = []
    colleges_majors = [
        ("信息工程学院", "计算机科学与技术"),
        ("信息工程学院", "软件工程"),
        ("外国语学院", "英语"),
    ]
    for i in range(1, 31):
        college, major = colleges_majors[(i - 1) % 3]
        username = f"student_demo_{i:02d}"
        sn = f"S2024{1000 + i:04d}"
        display = f"学生{i:02d}(演示)"
        rows.append(
            (username, "student", display, sn, None, college, major, "2024")
        )
    return rows


def _ensure_user(
    user_repo: UserRepository,
    username: str,
    role: str,
    display_name: Optional[str],
    student_number: Optional[str],
    teacher_number: Optional[str],
    college: Optional[str],
    major: Optional[str],
    grade: Optional[str],
) -> UserRow:
    existing = user_repo.get_user_by_username(username)
    if existing is not None:
        return existing
    return user_repo.create_user(
        username=username,
        password_hash=hash_password(DEMO_PASSWORD),
        role=role,
        display_name=display_name,
        student_number=student_number,
        teacher_number=teacher_number,
        college=college,
        major=major,
        grade=grade,
    )


def seed_demo_data(container: ServiceContainer, *, force: bool = False) -> dict:
    """幂等 seed 演示数据。

    Args:
        container: 已就绪的 ServiceContainer
        force: True=即使已 seed 过也继续补齐(不删除已有数据,仅插入缺失)

    Returns:
        统计字典 {users_added, courses_added, ...}
    """
    if not container.settings.auto_seed_demo_users and not force:
        return {"skipped": True}

    stats = {
        "users_added": 0,
        "courses_added": 0,
        "classes_added": 0,
        "enrollments_added": 0,
        "announcements_added": 0,
        "assignments_added": 0,
        "submissions_added": 0,
    }

    user_repo = container.user_repository
    course_repo = container.course_repository
    class_repo = container.class_group_repository
    enr_repo = container.enrollment_repository
    ann_repo = container.announcement_repository
    asg_repo = container.assignment_repository
    sub_repo = container.submission_repository

    # === 用户 ===
    created_users: dict[str, UserRow] = {}
    for row in DEMO_USERS + _demo_students():
        # row = (username, role, display_name, student_number, teacher_number,
        #        college, major, grade)
        # 上面 DEMO_USERS 的列对齐为:
        #   (username, role, display_name, student_number, teacher_number,
        #    college, major, grade)
        username, role, display, sn, tn, college, major, grade = row
        existing = user_repo.get_user_by_username(username)
        if existing is None:
            user = _ensure_user(
                user_repo, username, role, display, sn, tn, college, major, grade
            )
            stats["users_added"] += 1
        else:
            user = existing
        created_users[username] = user

    teacher1 = created_users["teacher_demo"]
    teacher2 = created_users["teacher_demo2"]
    admin = created_users["admin_demo"]
    student_demo = created_users["student_demo"]

    # === 课程 ===
    existing_courses, _ = course_repo.list_courses(page=1, page_size=200)
    existing_course_codes = {c.code for c in existing_courses if c.code}
    course_defs = [
        ("演示课程-高等数学(上)", "DEMO-MATH101-2024", "2024-2025秋季", "高等数学基础", teacher1.id),
        ("演示课程-程序设计基础", "DEMO-CS101-2024", "2024-2025秋季", "Python 入门", teacher1.id),
        ("演示课程-大学英语", "DEMO-ENG101-2024", "2024-2025秋季", "学术英语", teacher2.id),
    ]
    course_ids: dict[str, str] = {}
    for name, code, sem, desc, tid in course_defs:
        if code in existing_course_codes:
            # 找到已存在的课程
            for c in existing_courses:
                if c.code == code:
                    course_ids[code] = c.id
                    break
            continue
        course = course_repo.create_course(
            name=name, code=code, semester=sem, description=desc,
            teacher_id=tid, status="active",
        )
        course_ids[code] = course.id
        stats["courses_added"] += 1

    # === 班级 ===
    class_defs = [
        ("演示-计科1班", course_ids["DEMO-MATH101-2024"], "DEMO-MATH101-CLS1", 40),
        ("演示-计科2班", course_ids["DEMO-CS101-2024"], "DEMO-CS101-CLS1", 50),
        ("演示-软件1班", course_ids["DEMO-CS101-2024"], "DEMO-CS101-CLS2", 50),
        ("演示-英语1班", course_ids["DEMO-ENG101-2024"], "DEMO-ENG101-CLS1", 30),
    ]
    existing_classes, _ = class_repo.list_classes(page=1, page_size=200)
    existing_class_codes = {c.class_code for c in existing_classes if c.class_code}
    class_ids: dict[str, str] = {}
    for name, course_id, class_code, capacity in class_defs:
        if class_code in existing_class_codes:
            for c in existing_classes:
                if c.class_code == class_code:
                    class_ids[class_code] = c.id
                    break
            continue
        cls = class_repo.create_class(
            course_id=course_id, name=name, class_code=class_code,
            description=f"演示班级-{name}", capacity=capacity,
        )
        class_ids[class_code] = cls.id
        stats["classes_added"] += 1

    # === 选课(把 30 名演示学生 + student_demo 全部加入 4 个班级) ===
    student_usernames = ["student_demo"] + [f"student_demo_{i:02d}" for i in range(1, 31)]
    for class_code, cid in class_ids.items():
        for username in student_usernames:
            user = created_users.get(username)
            if user is None:
                continue
            existing_enr = enr_repo.get_enrollment(cid, user.id)
            if existing_enr is not None:
                continue
            try:
                enr_repo.enroll(
                    class_group_id=cid, user_id=user.id, member_role="student"
                )
                stats["enrollments_added"] += 1
            except Exception:
                # 重复插入忽略(UNIQUE 约束)
                pass

    # === 通知 ===
    # 按(班级, 标题)逐条补,已存在则跳过(避免重复 seed)
    announcement_defs = [
        ("DEMO-MATH101-CLS1", "开学第一周课程安排", "请同学们注意第一周课程安排,周三 1-2 节在 A301 教室上课,周五 3-4 节为习题课。", True, "published"),
        ("DEMO-MATH101-CLS1", "第一次作业提交说明", "请于 9 月 20 日前上传第一章习题的扫描件,要求字迹清晰。", True, "published"),
        ("DEMO-CS101-CLS1", "Python 环境准备", "请同学们在第一节课前完成 Python 3.11+ 与 VS Code 安装。", False, "published"),
        ("DEMO-CS101-CLS2", "软件工程导论", "本课程将介绍软件工程的基本概念与开发流程。", False, "published"),
        ("DEMO-ENG101-CLS1", "英语晨读活动", "请同学们每周二、四早晨 7:30 到图书馆北广场参加英语晨读。", True, "published"),
        ("DEMO-MATH101-CLS1", "(草稿-未发布)期中考试安排", "草稿,学生不可见。", True, "draft"),
    ]
    for class_code, title, content, require_read, status in announcement_defs:
        cid = class_ids.get(class_code)
        if cid is None:
            continue
        # 检查是否已存在同名通知
        existing_list, _ = ann_repo.list_announcements(cid, status=None, page=1, page_size=200)
        if any(a.title == title for a in existing_list):
            continue
        ann_repo.create_announcement(
            class_group_id=cid, author_id=teacher1.id,
            title=title, content=content,
            require_read=require_read, status=status,
        )
        stats["announcements_added"] += 1

    # === 任务 ===
    assignment_defs = [
        ("DEMO-MATH101-CLS1", "第一章习题", "完成课本 P15-P18 第 1-5 题。", "2026-09-20T23:59:59+08:00", 100, True, "published"),
        ("DEMO-MATH101-CLS1", "第二章习题", "完成课本 P30-P35 第 1-8 题。", "2026-09-27T23:59:59+08:00", 100, True, "published"),
        ("DEMO-CS101-CLS1", "实验一:Hello World", "编写 Python 程序输出 Hello World 并截图。", "2026-09-15T23:59:59+08:00", 50, True, "published"),
        ("DEMO-CS101-CLS1", "实验二:数据类型", "完成数据类型转换练习。", "2026-09-22T23:59:59+08:00", 50, False, "published"),
        ("DEMO-CS101-CLS2", "项目一:简单计算器", "实现一个支持加减乘除的命令行计算器。", "2026-09-30T23:59:59+08:00", 100, True, "published"),
        ("DEMO-ENG101-CLS1", "听力练习 1", "完成课本 Unit 1 的听力练习。", "2026-09-18T23:59:59+08:00", 50, True, "published"),
        ("DEMO-ENG101-CLS1", "口语展示", "准备 3 分钟自我介绍口语展示。", "2026-09-25T23:59:59+08:00", 50, True, "published"),
        ("DEMO-MATH101-CLS1", "(草稿-未发布)期中考试", "草稿任务,学生不可见。", None, 100, False, "draft"),
    ]
    created_assignments: dict[tuple[str, str], str] = {}  # (class_code, title) -> id
    for class_code, title, desc, deadline, max_score, allow_resubmit, status in assignment_defs:
        cid = class_ids.get(class_code)
        if cid is None:
            continue
        existing_list, _ = asg_repo.list_assignments(cid, status=None, page=1, page_size=200)
        if any(a.title == title for a in existing_list):
            for a in existing_list:
                if a.title == title:
                    created_assignments[(class_code, title)] = a.id
                    break
            continue
        asg = asg_repo.create_assignment(
            class_group_id=cid, author_id=teacher1.id,
            title=title, description=desc, deadline=deadline,
            submission_types=["text", "file"], max_score=float(max_score),
            allow_resubmit=allow_resubmit, status=status,
        )
        created_assignments[(class_code, title)] = asg.id
        stats["assignments_added"] += 1

    # === 提交 + 评分 ===
    asg1_id = created_assignments.get(("DEMO-MATH101-CLS1", "第一章习题"))
    if asg1_id is not None:
        # student_demo 已提交
        existing_sub = sub_repo.get_submission_for_student(asg1_id, student_demo.id)
        if existing_sub is None:
            sub_repo.upsert_submission(
                assignment_id=asg1_id, student_id=student_demo.id,
                text_content="答案见附件。", status="submitted",
            )
            stats["submissions_added"] += 1
        # student_demo_01 已提交并被评分
        s01 = created_users.get("student_demo_01")
        if s01 is not None:
            existing_sub = sub_repo.get_submission_for_student(asg1_id, s01.id)
            if existing_sub is None:
                sub_repo.upsert_submission(
                    assignment_id=asg1_id, student_id=s01.id,
                    text_content="作业已完成。", status="submitted",
                )
                stats["submissions_added"] += 1
            existing_sub = sub_repo.get_submission_for_student(asg1_id, s01.id)
            if existing_sub is not None and existing_sub.score is None:
                sub_repo.grade(
                    existing_sub.id, score=95.0,
                    teacher_comment="思路清晰,大部分正确。第 3 题注意符号问题。",
                )

    logger.info("演示数据 seed 完成: %s", stats)
    return stats


__all__ = ["seed_demo_data", "DEMO_PASSWORD"]
