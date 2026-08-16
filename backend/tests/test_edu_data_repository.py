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