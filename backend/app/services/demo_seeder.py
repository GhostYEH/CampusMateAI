"""多角色演示数据 seeding —— 仅在开发/演示环境使用。

明确标注为演示数据，不得冒充真实学校数据。
启动时幂等执行: 已存在的演示账号与课程不会重复创建。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
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

# (username, role, display_name, student_number, teacher_number, college, major, grade)
# CampusMate AI 只存在 student / admin 两类系统角色。
# 历史演示中的 teacher 账号已改为 admin(管理员负责系统内容维护)。
DEMO_USERS = [
    ("admin_demo2", "admin", "李管理员(演示)", None, None, "信息工程学院", "计算机系", None),
    ("admin_demo3", "admin", "王管理员(演示)", None, None, "外国语学院", "英语系", None),
    ("student_demo", "student", "陈同学(演示)", "S202401001", None, "信息工程学院", "计算机科学与技术", "2024"),
    ("agent_demo", "student", "智能体演示用户", "SAGENTDEMO", None, "信息工程学院", "计算机科学与技术", "2024"),
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
        "personal_tasks_added": 0,
        "community_posts_added": 0,
    }

    user_repo = container.user_repository
    course_repo = container.course_repository
    class_repo = container.class_group_repository
    enr_repo = container.enrollment_repository
    ann_repo = container.announcement_repository
    asg_repo = container.assignment_repository
    sub_repo = container.submission_repository
    personal_task_repo = container.personal_task_repository
    community_repo = container.community_repository

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

    teacher1 = created_users["admin_demo2"]
    teacher2 = created_users["admin_demo3"]
    admin = created_users["admin_demo"]
    student_demo = created_users["student_demo"]
    agent_demo = created_users["agent_demo"]
    demo_university = container.university_repository.ensure_demo_university()
    if student_demo.university_id != demo_university.id:
        student_demo = user_repo.update_university(student_demo.id, demo_university.id)
    if agent_demo.university_id != demo_university.id:
        agent_demo = user_repo.update_university(agent_demo.id, demo_university.id)

    # === 校园社区热帖 ===
    # 首页按热度读取社区数据。使用真实的帖子、评论和点赞记录，让演示环境
    # 与用户发布后的正常页面保持同一条数据链路。
    hot_post_defs = [
        (
            "图书馆自习室座位怎么选？这份避坑清单请收好",
            "整理了早中晚三个时段的空位情况，也欢迎大家补充常用楼层和插座位置。",
            "campus",
            7,
            ["北区三楼靠窗位置上午光线很好。", "期末周建议提前在小程序里预约。", "一楼研讨区可以小组讨论。", "谢谢分享，已收藏。"],
        ),
        (
            "新学期选课互助：这些公共课还有空位吗？",
            "想整理一份选课互助表，已经选到课程的同学可以分享上课时间和老师风格。",
            "question",
            5,
            ["体育课还有两个时段可以选。", "通识课《电影鉴赏》周四下午还有名额。", "建议先关注教务系统的补退选通知。"],
        ),
        (
            "求推荐：校内适合小组讨论的安静地点",
            "我们四个人要准备课程展示，希望找一个有白板、插座方便、不会影响别人的地方。",
            "study",
            3,
            ["图书馆一层研讨间需要提前预约。", "教学楼 B 座的公共讨论区晚上人不多。"],
        ),
        (
            "周末校园骑行路线分享，沿途景色很棒",
            "从东门出发绕湖一圈，大约四十分钟，适合傍晚放松。",
            "life",
            1,
            ["收藏了，周末去试试。"],
        ),
    ]
    existing_posts, _ = community_repo.list_posts(
        demo_university.id, q=None, page=1, page_size=200, sort="time"
    )
    posts_by_title = {post["title"]: post for post in existing_posts}
    engagement_users = [
        created_users[f"student_demo_{index:02d}"] for index in range(1, 31)
    ]
    for title, content, category, like_target, comments in hot_post_defs:
        post = posts_by_title.get(title)
        if post is None:
            post = community_repo.create_post(
                university_id=demo_university.id,
                author_id=student_demo.id,
                title=title,
                content=content,
                category=category,
                images=[],
                is_anonymous=False,
            )
            stats["community_posts_added"] += 1
        for user in engagement_users[:like_target]:
            community_repo.toggle("forum_likes", "like_count", post["id"], user.id, True)
        existing_comments = community_repo.list_comments(post["id"])
        existing_comment_texts = {comment["content"] for comment in existing_comments}
        for index, comment in enumerate(comments):
            if comment not in existing_comment_texts:
                community_repo.create_comment(
                    post=post,
                    author_id=engagement_users[like_target + index].id,
                    content=comment,
                    parent_comment_id=None,
                    is_anonymous=False,
                )

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

    # === 学生个人待办 ===
    # 用一条无截止时间的真实学习计划补齐首页的个人安排区域；无 deadline
    # 的任务会在“即将截止”列表数量不足时作为最近待办展示。
    demo_personal_task_title = "整理本周学习任务"
    existing_personal_tasks, _ = personal_task_repo.list_tasks(
        student_demo.id, include_deleted=True, page=1, page_size=200
    )
    if not any(task.title == demo_personal_task_title for task in existing_personal_tasks):
        personal_task_repo.create_task(
            user_id=student_demo.id,
            title=demo_personal_task_title,
            description="完成高等数学第一章习题复习，并按优先级整理本周课程与作业。",
            source_name="个人安排",
            priority="high",
        )
        stats["personal_tasks_added"] += 1

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

    # === Agent runtime demo 数据(§14 隔离 demo) ===
    agent_stats = _seed_agent_demo_data(container, agent_demo)
    stats.update(agent_stats)

    logger.info("演示数据 seed 完成: %s", stats)
    return stats


# ===== Agent runtime demo 数据(§14) =====
# 确定性 demo 数据:三领域场景,全部绑定 demo user,不使用真实学生数据。
# 固定 ID 前缀保证幂等;reset_agent_demo.py 只删除这些 demo-owned 记录。

AGENT_DEMO_EXAM_IDS = [
    "demo_exam_math_final",
    "demo_exam_cs_final",
    "demo_exam_eng_final",
]
AGENT_DEMO_CAMPAIGN_ID = "demo_fr_campaign_001"
AGENT_DEMO_JOB_ID = "demo_agent_job_001"
AGENT_DEMO_RUN_ID = "demo_agent_run_001"


def _seed_agent_demo_data(container: ServiceContainer, demo_user: UserRow) -> dict:
    """seed agent runtime demo 数据(三领域场景)。

    全部绑定 demo_user,确定性 ID,幂等。不使用真实学生数据。
    """
    stats = {
        "agent_exams_added": 0,
        "agent_notices_added": 0,
        "agent_campaign_added": 0,
        "agent_job_added": 0,
        "agent_run_added": 0,
        "agent_model_calls_added": 0,
        "agent_research_session_added": 0,
        "agent_research_sources_added": 0,
    }
    db = container.db
    now = datetime.now(timezone.utc).isoformat()
    uid = demo_user.id

    conn = db._connect()
    try:
        # student_exams 表(与 student_tools 路由一致)
        conn.executescript(
            "CREATE TABLE IF NOT EXISTS student_exams ("
            "id TEXT PRIMARY KEY, user_id TEXT NOT NULL, course_name TEXT NOT NULL, "
            "exam_date TEXT NOT NULL, start_time TEXT, end_time TEXT, location TEXT, "
            "seat_number TEXT, exam_type TEXT, reminder_enabled INTEGER NOT NULL DEFAULT 1, "
            "notes TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);"
            "CREATE INDEX IF NOT EXISTS idx_student_exams_user_date "
            "ON student_exams(user_id, exam_date);"
        )
        # final_review 表
        from ..repositories.final_review_migration import (
            apply_final_review_migration,
        )
        apply_final_review_migration(conn)
        # notice_workflow 表
        from ..repositories.notice_workflow_repository import _SCHEMA_SQL as _NWF_SQL
        conn.executescript(_NWF_SQL)
        # course_research 表
        from ..repositories.course_research_repository import (
            _SCHEMA_SQL as _CRS_SQL,
        )
        conn.executescript(_CRS_SQL)

        # --- 三个考试(字符串 exam_id) ---
        exam_defs = [
            ("demo_exam_math_final", "高等数学(演示)", "2026-12-30"),
            ("demo_exam_cs_final", "程序设计基础(演示)", "2027-01-06"),
            ("demo_exam_eng_final", "大学英语(演示)", "2027-01-10"),
        ]
        for exam_id, course_name, exam_date in exam_defs:
            exists = conn.execute(
                "SELECT 1 FROM student_exams WHERE id = ?", (exam_id,)
            ).fetchone()
            if exists:
                continue
            conn.execute(
                "INSERT INTO student_exams (id,user_id,course_name,exam_date,"
                "reminder_enabled,created_at,updated_at) VALUES (?,?,?,?,1,?,?)",
                (exam_id, uid, course_name, exam_date, now, now),
            )
            stats["agent_exams_added"] += 1

        # --- Chaoxing-like 通知 ---
        # 使用独立 demo source，避免被真实超星回填任务扫描。
        chaoxing_exists = conn.execute(
            "SELECT 1 FROM notices WHERE user_id = ? AND source = 'agent_demo' "
            "AND external_id = 'demo_chaoxing_001'",
            (uid,),
        ).fetchone()
        if not chaoxing_exists:
            conn.execute(
                "INSERT INTO notices (id,user_id,source,external_id,title,content,"
                "published_at,created_at,updated_at) VALUES (?,?,'agent_demo',"
                "'demo_chaoxing_001',?,?,?,?,?)",
                (
                    "demo_notice_chaoxing_001",
                    uid,
                    "【超星学习通】高等数学作业截止提醒(演示)",
                    "请于 12 月 25 日前完成第五章习题提交,逾期不计分。",
                    now,
                    now,
                    now,
                ),
            )
            stats["agent_notices_added"] += 1

        # --- final-review campaign(草稿,未激活) ---
        campaign_exists = conn.execute(
            "SELECT 1 FROM final_review_campaigns WHERE campaign_id = ?",
            (AGENT_DEMO_CAMPAIGN_ID,),
        ).fetchone()
        if not campaign_exists:
            conn.execute(
                "INSERT INTO final_review_campaigns (campaign_id,user_id,"
                "exam_ids_json,daily_capacity_minutes,status,idempotency_key,"
                "created_at,updated_at) VALUES (?,?,?,120,'draft',"
                "'demo_fr_campaign_idem',?,?)",
                (
                    AGENT_DEMO_CAMPAIGN_ID,
                    uid,
                    json.dumps(AGENT_DEMO_EXAM_IDS),
                    now,
                    now,
                ),
            )
            stats["agent_campaign_added"] += 1

        # --- agent_job + agent_run(QUEUED,演示运行) ---
        job_exists = conn.execute(
            "SELECT 1 FROM agent_jobs WHERE job_id = ?", (AGENT_DEMO_JOB_ID,)
        ).fetchone()
        if not job_exists:
            conn.execute(
                "INSERT INTO agent_jobs (job_id,user_id,job_kind,status,"
                "idempotency_key,input_ref_json,created_at,updated_at) "
                "VALUES (?,?,'final_review','QUEUED','demo_job_idem','{}',?,?)",
                (AGENT_DEMO_JOB_ID, uid, now, now),
            )
            stats["agent_job_added"] += 1

        run_exists = conn.execute(
            "SELECT 1 FROM agent_runs WHERE run_id = ?", (AGENT_DEMO_RUN_ID,)
        ).fetchone()
        if not run_exists:
            conn.execute(
                "INSERT INTO agent_runs (run_id,job_id,user_id,status,phase,"
                "created_at,updated_at) VALUES (?,?,?,'QUEUED','IDLE',?,?)",
                (AGENT_DEMO_RUN_ID, AGENT_DEMO_JOB_ID, uid, now, now),
            )
            stats["agent_run_added"] += 1

        # --- fake-provider outcome(agent_model_calls) ---
        model_call_exists = conn.execute(
            "SELECT 1 FROM agent_model_calls WHERE call_id = 'demo_mc_001'"
        ).fetchone()
        if not model_call_exists:
            conn.execute(
                "INSERT INTO agent_model_calls (call_id,run_id,provider,"
                "route_policy,model,status,latency_ms,started_at,finished_at) "
                "VALUES ('demo_mc_001',?,'fake','reasoning_primary','fake-model',"
                "'completed',120,?,?)",
                (AGENT_DEMO_RUN_ID, now, now),
            )
            stats["agent_model_calls_added"] += 1

        # --- course_research session + sources(含一个受控冲突) ---
        crs_exists = conn.execute(
            "SELECT 1 FROM course_research_sessions WHERE session_id = "
            "'demo_crs_001'"
        ).fetchone()
        if not crs_exists:
            conn.execute(
                "INSERT INTO course_research_sessions (session_id,run_id,job_id,"
                "user_id,question,assistance_mode,academic_policy,"
                "source_policy_json,status,created_at,updated_at) "
                "VALUES ('demo_crs_001',?,?,?,'解释极限的定义(演示)','EXPLAIN',"
                "'ALLOWED','{\"course_material_priority\":true,\"allow_web\":true,"
                "\"allow_user_upload\":false}','QUEUED',?,?)",
                (AGENT_DEMO_RUN_ID, AGENT_DEMO_JOB_ID, uid, now, now),
            )
            stats["agent_research_session_added"] += 1

        # 两个课程来源(含受控冲突:同一论断不同结论)
        for src_id, title, supports, note in [
            (
                "demo_crs_src_001",
                "课本定义(演示)",
                1,
                "与课本一致",
            ),
            (
                "demo_crs_src_002",
                "课件补充(演示)",
                0,
                "课件使用了不同表述,与课本存在冲突",
            ),
        ]:
            src_exists = conn.execute(
                "SELECT 1 FROM course_research_sources WHERE source_id = ?",
                (src_id,),
            ).fetchone()
            if src_exists:
                continue
            conn.execute(
                "INSERT INTO course_research_sources (source_id,session_id,"
                "user_id,source_type,title,accessed_at,is_verified,"
                "verification_note,supports_claim,created_at) "
                "VALUES (?,'demo_crs_001',?,'course',?,?,1,?,?,?)",
                (
                    src_id,
                    uid,
                    title,
                    now,
                    note,
                    supports,
                    now,
                ),
            )
            stats["agent_research_sources_added"] += 1

        conn.commit()
    finally:
        db._release(conn)

    return stats


__all__ = ["seed_demo_data", "DEMO_PASSWORD"]
