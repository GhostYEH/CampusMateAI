"""EduDataRepository 教务数据持久化与幂等同步测试。

验证：
- 课表/成绩落库
- 重复同步幂等（unchanged）
- 字段变化触发 update
- 消失条目标记 is_stale（软删除）
- 学期列表查询
"""
from __future__ import annotations

import pytest

from app.database.sqlite_db import Database
from app.models.edu import BINDING_ACTIVE, EduBindingRow
from app.repositories.edu_data_repository import EduDataRepository
from app.schemas.edu import EduGrade, EduGradeItem, EduSchedule, EduScheduleItem


@pytest.fixture
def db():
    database = Database(None)
    with database.transaction() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("user_test_001", "test_user_001", "x", "student", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO universities (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("uni_test_001", "Fixture大学", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z"),
        )
        conn.execute(
            """
            INSERT INTO edu_systems (id, university_id, system_key, system_type, provider,
                auth_type, login_execution_mode, captcha_type, requires_campus_network,
                requires_vpn, status, verification_status, supported_features, source,
                is_mock, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("esys_test_001", "uni_test_001", "undergraduate-main", "undergrad", "zhengfang",
             "form", "backend_http", "none", 0, 0, "active", "unverified", "[]", "fixture",
             0, "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z"),
        )
    yield database
    database.dispose()


@pytest.fixture
def repo(db):
    return EduDataRepository(db)


@pytest.fixture
def binding():
    return EduBindingRow(
        id="bind_test_001",
        user_id="user_test_001",
        edu_system_id="esys_test_001",
        university_id="uni_test_001",
        provider="zhengfang",
        system_type="undergrad",
        connection_status=BINDING_ACTIVE,
    )


def _schedule(items=None):
    return EduSchedule(
        semester="2024-2025秋季",
        items=items or [
            EduScheduleItem(course_name="高等数学", course_code="MATH101", weekday=1, start_section=1, end_section=2, weeks="1-16"),
            EduScheduleItem(course_name="程序设计", course_code="CS101", weekday=3, start_section=3, end_section=4, weeks="1-16"),
        ],
    )


def _grade(items=None):
    return EduGrade(
        semester="2024-2025秋季",
        gpa=3.75,
        items=items or [
            EduGradeItem(course_name="高等数学", course_code="MATH101", credit=4.0, score="88", grade_point=3.7),
            EduGradeItem(course_name="程序设计", course_code="CS101", credit=3.0, score="92", grade_point=4.0),
        ],
    )


def test_sync_schedule_inserts(repo, binding):
    stats = repo.sync_schedule_items(binding=binding, schedule=_schedule(), sync_batch_id="batch_001")
    assert stats.inserted == 2
    assert stats.updated == 0
    assert stats.unchanged == 0
    items = repo.list_schedule_items(user_id=binding.user_id, semester="2024-2025秋季")
    assert len(items) == 2


def test_sync_schedule_idempotent(repo, binding):
    repo.sync_schedule_items(binding=binding, schedule=_schedule(), sync_batch_id="batch_001")
    stats2 = repo.sync_schedule_items(binding=binding, schedule=_schedule(), sync_batch_id="batch_002")
    assert stats2.inserted == 0
    assert stats2.updated == 0
    assert stats2.unchanged == 2


def test_sync_schedule_update_on_change(repo, binding):
    repo.sync_schedule_items(binding=binding, schedule=_schedule(), sync_batch_id="batch_001")
    updated_schedule = EduSchedule(
        semester="2024-2025秋季",
        items=[
            EduScheduleItem(course_name="高等数学(改)", course_code="MATH101", weekday=1, start_section=1, end_section=2, weeks="1-16"),
            EduScheduleItem(course_name="程序设计", course_code="CS101", weekday=3, start_section=3, end_section=4, weeks="1-16"),
        ],
    )
    stats = repo.sync_schedule_items(binding=binding, schedule=updated_schedule, sync_batch_id="batch_002")
    assert stats.updated == 1
    assert stats.unchanged == 1
    items = repo.list_schedule_items(user_id=binding.user_id, semester="2024-2025秋季")
    by_code = {it.course_code: it for it in items}
    assert by_code["MATH101"].course_name == "高等数学(改)"


def test_sync_schedule_stale_on_removal(repo, binding):
    repo.sync_schedule_items(binding=binding, schedule=_schedule(), sync_batch_id="batch_001")
    smaller = EduSchedule(
        semester="2024-2025秋季",
        items=[EduScheduleItem(course_name="高等数学", course_code="MATH101", weekday=1, start_section=1, end_section=2, weeks="1-16")],
    )
    stats = repo.sync_schedule_items(binding=binding, schedule=smaller, sync_batch_id="batch_002")
    assert stats.unchanged == 1
    assert stats.removed == 1
    active = repo.list_schedule_items(user_id=binding.user_id, semester="2024-2025秋季", include_stale=False)
    assert len(active) == 1
    all_items = repo.list_schedule_items(user_id=binding.user_id, semester="2024-2025秋季", include_stale=True)
    assert len(all_items) == 2
    stale = [it for it in all_items if it.is_stale]
    assert len(stale) == 1
    assert stale[0].course_code == "CS101"


def test_sync_schedule_semesters(repo, binding):
    repo.sync_schedule_items(binding=binding, schedule=_schedule(), sync_batch_id="batch_001")
    other = EduSchedule(
        semester="2024-2025春季",
        items=[EduScheduleItem(course_name="离散数学", course_code="MATH201", weekday=2, start_section=1, end_section=2, weeks="1-16")],
    )
    repo.sync_schedule_items(binding=binding, schedule=other, sync_batch_id="batch_002")
    semesters = repo.list_semesters_with_schedule(binding.user_id)
    assert "2024-2025秋季" in semesters
    assert "2024-2025春季" in semesters


def test_sync_grade_inserts(repo, binding):
    stats = repo.sync_grade_items(binding=binding, grade=_grade(), sync_batch_id="batch_001")
    assert stats.inserted == 2
    items = repo.list_grade_items(user_id=binding.user_id, semester="2024-2025秋季")
    assert len(items) == 2


def test_sync_grade_idempotent(repo, binding):
    repo.sync_grade_items(binding=binding, grade=_grade(), sync_batch_id="batch_001")
    stats2 = repo.sync_grade_items(binding=binding, grade=_grade(), sync_batch_id="batch_002")
    assert stats2.unchanged == 2
    assert stats2.inserted == 0


def test_sync_grade_update_on_score_change(repo, binding):
    repo.sync_grade_items(binding=binding, grade=_grade(), sync_batch_id="batch_001")
    updated = EduGrade(
        semester="2024-2025秋季",
        gpa=3.8,
        items=[
            EduGradeItem(course_name="高等数学", course_code="MATH101", credit=4.0, score="95", grade_point=4.0),
            EduGradeItem(course_name="程序设计", course_code="CS101", credit=3.0, score="92", grade_point=4.0),
        ],
    )
    stats = repo.sync_grade_items(binding=binding, grade=updated, sync_batch_id="batch_002")
    assert stats.updated == 1
    items = repo.list_grade_items(user_id=binding.user_id, semester="2024-2025秋季")
    by_code = {it.course_code: it for it in items}
    assert by_code["MATH101"].score == "95"


def test_sync_grade_stale_on_removal(repo, binding):
    repo.sync_grade_items(binding=binding, grade=_grade(), sync_batch_id="batch_001")
    smaller = EduGrade(
        semester="2024-2025秋季",
        items=[EduGradeItem(course_name="高等数学", course_code="MATH101", credit=4.0, score="88", grade_point=3.7)],
    )
    stats = repo.sync_grade_items(binding=binding, grade=smaller, sync_batch_id="batch_002")
    assert stats.removed == 1
    active = repo.list_grade_items(user_id=binding.user_id, semester="2024-2025秋季", include_stale=False)
    assert len(active) == 1


def test_clear_user_data(repo, binding):
    repo.sync_schedule_items(binding=binding, schedule=_schedule(), sync_batch_id="batch_001")
    repo.sync_grade_items(binding=binding, grade=_grade(), sync_batch_id="batch_001")
    repo.clear_user_data(binding.user_id)
    assert repo.list_schedule_items(user_id=binding.user_id) == []
    assert repo.list_grade_items(user_id=binding.user_id) == []


def test_sync_schedule_skips_empty_course_name(repo, binding):
    bad = EduSchedule(
        semester="2024-2025秋季",
        items=[
            EduScheduleItem(course_name="", course_code="X1"),
            EduScheduleItem(course_name=None, course_code="X2"),
            EduScheduleItem(course_name="有效课程", course_code="X3", weekday=1, start_section=1),
        ],
    )
    stats = repo.sync_schedule_items(binding=binding, schedule=bad, sync_batch_id="batch_001")
    assert stats.failed == 2
    assert stats.inserted == 1


# ===== 课程详情完整字段持久化测试 =====


def test_sync_schedule_persists_full_fields(repo, binding):
    """教务系统能提供多少字段就保存多少，详情弹窗能读到全部。"""
    schedule = EduSchedule(
        semester="2024-2025秋季",
        items=[
            EduScheduleItem(
                course_name="社会心理学",
                course_code="PSY20301",
                teacher="张三,李四",
                teachers=["张三", "李四"],
                location="逸夫楼 A302",
                campus="主校区",
                building="逸夫楼",
                classroom="A302",
                weekday=2,
                start_section=3,
                end_section=4,
                start_time="10:00",
                end_time="11:40",
                weeks="1-8,10-16",
                credit=2.0,
                course_nature="专业必修",
                course_category="专业基础课",
                course_type="必修",
                teaching_class="社会心理学-01",
                class_name="心理类-2401",
                college="社会学院",
                department="社会学系",
                assessment_method="考试",
                exam_type="期末考试",
                total_hours=32.0,
                theory_hours=24.0,
                practice_hours=8.0,
                language="中文",
                note="详情备注",
                semester_id="2024-2025-1",
                extra_info={"课程归属": "专业基础课程", "授课语言": "中文"},
            ),
        ],
    )
    repo.sync_schedule_items(binding=binding, schedule=schedule, sync_batch_id="batch_001")
    items = repo.list_schedule_items(user_id=binding.user_id, semester="2024-2025秋季")
    assert len(items) == 1
    it = items[0]
    assert it.course_name == "社会心理学"
    assert it.course_code == "PSY20301"
    assert it.teachers == ["张三", "李四"]
    assert it.credit == 2.0
    assert it.course_nature == "专业必修"
    assert it.course_category == "专业基础课"
    assert it.teaching_class == "社会心理学-01"
    assert it.college == "社会学院"
    assert it.assessment_method == "考试"
    assert it.weeks == "1-8,10-16"
    assert it.campus == "主校区"
    assert it.total_hours == 32.0
    assert it.extra_info == {"课程归属": "专业基础课程", "授课语言": "中文"}


def test_sync_schedule_multiple_teachers(repo, binding):
    """多教师必须保留全部，不能只留第一个。"""
    schedule = EduSchedule(
        semester="2024-2025秋季",
        items=[
            EduScheduleItem(
                course_name="联合授课研讨",
                course_code="SEM301",
                teacher="张三,李四,王五",
                teachers=["张三", "李四", "王五"],
                weekday=1, start_section=1, end_section=2, weeks="1-16",
            ),
        ],
    )
    repo.sync_schedule_items(binding=binding, schedule=schedule, sync_batch_id="batch_001")
    it = repo.list_schedule_items(user_id=binding.user_id, semester="2024-2025秋季")[0]
    assert it.teachers == ["张三", "李四", "王五"]


def test_sync_schedule_multi_location_not_deduped(repo, binding):
    """同一课程同一星期同一节次，不同周次不同地点，必须保留两条 session。"""
    schedule = EduSchedule(
        semester="2024-2025秋季",
        items=[
            EduScheduleItem(course_name="数据结构", course_code="CS201", location="A101", weekday=4, start_section=1, end_section=2, weeks="1-8"),
            EduScheduleItem(course_name="数据结构", course_code="CS201", location="B202", weekday=4, start_section=1, end_section=2, weeks="9-16"),
        ],
    )
    repo.sync_schedule_items(binding=binding, schedule=schedule, sync_batch_id="batch_001")
    items = repo.list_schedule_items(user_id=binding.user_id, semester="2024-2025秋季")
    assert len(items) == 2
    locs = {it.location for it in items}
    assert locs == {"A101", "B202"}


def test_sync_schedule_odd_even_weeks_preserved(repo, binding):
    """单双周/非连续周次必须原样保留，不能被错误解析成 1-16。"""
    schedule = EduSchedule(
        semester="2024-2025秋季",
        items=[
            EduScheduleItem(course_name="大学体育", course_code="PE201", weekday=5, start_section=3, end_section=4, weeks="1,3,5,7,9,11,13,15", week_text="单周"),
            EduScheduleItem(course_name="实验心理学", course_code="PSY301", weekday=3, start_section=3, end_section=4, weeks="1-8,10-16"),
        ],
    )
    repo.sync_schedule_items(binding=binding, schedule=schedule, sync_batch_id="batch_001")
    items = {it.course_code: it for it in repo.list_schedule_items(user_id=binding.user_id, semester="2024-2025秋季")}
    assert items["PE201"].weeks == "1,3,5,7,9,11,13,15"
    assert items["PE201"].week_text == "单周"
    assert items["PSY301"].weeks == "1-8,10-16"


def test_sync_schedule_idempotent_with_full_fields(repo, binding):
    """重复同步含新字段的课程，结果应 unchanged，不重复插入。"""
    schedule = EduSchedule(
        semester="2024-2025秋季",
        items=[
            EduScheduleItem(course_name="社会心理学", course_code="PSY203", teachers=["张三", "李四"], credit=2.0, course_nature="专业必修", weekday=2, start_section=3, end_section=4, weeks="1-16", extra_info={"开课学院": "社会学院"}),
        ],
    )
    repo.sync_schedule_items(binding=binding, schedule=schedule, sync_batch_id="b1")
    stats2 = repo.sync_schedule_items(binding=binding, schedule=schedule, sync_batch_id="b2")
    assert stats2.inserted == 0
    assert stats2.unchanged == 1
    assert len(repo.list_schedule_items(user_id=binding.user_id, semester="2024-2025秋季")) == 1


def test_sync_schedule_update_on_field_change(repo, binding):
    """字段变化（如学分/教师）应触发 update。"""
    schedule = EduSchedule(
        semester="2024-2025秋季",
        items=[EduScheduleItem(course_name="高数", course_code="MATH101", credit=3.0, teacher="张三", weekday=1, start_section=1, end_section=2, weeks="1-16")],
    )
    repo.sync_schedule_items(binding=binding, schedule=schedule, sync_batch_id="b1")
    updated = EduSchedule(
        semester="2024-2025秋季",
        items=[EduScheduleItem(course_name="高数", course_code="MATH101", credit=4.0, teacher="张三,李四", teachers=["张三", "李四"], weekday=1, start_section=1, end_section=2, weeks="1-16")],
    )
    stats = repo.sync_schedule_items(binding=binding, schedule=updated, sync_batch_id="b2")
    assert stats.updated == 1
    it = repo.list_schedule_items(user_id=binding.user_id, semester="2024-2025秋季")[0]
    assert it.credit == 4.0
    assert it.teachers == ["张三", "李四"]


def test_sync_schedule_empty_fields_safe(repo, binding):
    """无教师/无地点/无学分等空字段必须正常保存与展示，不报错。"""
    schedule = EduSchedule(
        semester="2024-2025秋季",
        items=[
            EduScheduleItem(course_name="自习研讨课", course_code="SEM101", location="研讨室-3", weekday=6, start_section=3, end_section=4, weeks="2-14"),
            EduScheduleItem(course_name="在线慕课", course_code="ONL101", teacher="孙老师", weekday=7, start_section=1, end_section=2, weeks="1-8"),
        ],
    )
    repo.sync_schedule_items(binding=binding, schedule=schedule, sync_batch_id="b1")
    items = {it.course_code: it for it in repo.list_schedule_items(user_id=binding.user_id, semester="2024-2025秋季")}
    assert items["SEM101"].teacher is None
    assert items["SEM101"].credit is None
    assert items["ONL101"].location is None


def test_sync_schedule_section_11_12_safe(repo, binding):
    """11-12 节课程必须正常保存，不假设一天只有 10 节。"""
    schedule = EduSchedule(
        semester="2024-2025秋季",
        items=[EduScheduleItem(course_name="夜间选修", course_code="AST101", weekday=3, start_section=11, end_section=12, weeks="1-16")],
    )
    repo.sync_schedule_items(binding=binding, schedule=schedule, sync_batch_id="b1")
    it = repo.list_schedule_items(user_id=binding.user_id, semester="2024-2025秋季")[0]
    assert it.start_section == 11
    assert it.end_section == 12


def test_sync_schedule_semester_isolation(repo, binding):
    """切换学期只能看到对应学期课程，不能串学期。"""
    s1 = EduSchedule(semester="2025-2026-2", items=[EduScheduleItem(course_name="A", course_code="A1", weekday=1, start_section=1, end_section=2, weeks="1-16")])
    s2 = EduSchedule(semester="2026-2027-1", items=[EduScheduleItem(course_name="B", course_code="B1", weekday=1, start_section=1, end_section=2, weeks="1-16")])
    repo.sync_schedule_items(binding=binding, schedule=s1, sync_batch_id="b1")
    repo.sync_schedule_items(binding=binding, schedule=s2, sync_batch_id="b2")
    autumn = repo.list_schedule_items(user_id=binding.user_id, semester="2026-2027-1")
    spring = repo.list_schedule_items(user_id=binding.user_id, semester="2025-2026-2")
    assert len(autumn) == 1 and autumn[0].course_code == "B1"
    assert len(spring) == 1 and spring[0].course_code == "A1"