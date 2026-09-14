"""学习通成绩事实接入 —— 解析 / 落库 / 事件 / 世界模型投影的端到端校验。

这些用例覆盖的是"学习通分数与考试此前完全没有进入世界模型"的补线:
1. 抓取层能从不稳定的页面文本中解析出提交时间与得分;
2. 分数一旦观测到就落库且不会被 None 覆盖;
3. assignment_graded / exam_discovered 事件是真被投射的;
4. ACADEMIC 与 WORLD 投影把学习通事实计入，而不是只认教务。
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from app.database.sqlite_db import Database, PERSONAL_TASK_SCHEMA_SQL
from app.models.personal_task import PersonalTaskRow
from app.repositories.chaoxing_repository import ChaoxingRepository
from app.repositories.course_content_repository import CourseContentRepository
from app.repositories.learner_event_repository import LearnerEventRepository
from app.repositories.learner_state_repository import LearnerStateRepository
from app.services.chaoxing.ChaoxingClient import ChaoxingParser
from app.services.chaoxing.course_content_sync import ChaoxingCourseContentSyncService
from app.services.learner_event_service import LearnerEventService
from app.services.learner_state_service import LearnerStateProjectionService


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _make_db() -> Database:
    return Database(None)


def _add_user(db: Database, user_id: str = "user1") -> None:
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, user_id, "hash", "now", "now"),
        )


def _insert_chaoxing_task(
    db: Database,
    *,
    user_id: str = "user1",
    task_id: str = "task_1",
    score=None,
    score_max=None,
    course_id: str = "course_1",
    remote_submitted_at=None,
    status: str = "completed",
) -> None:
    now = _now().isoformat()
    with db.transaction() as conn:
        conn.execute(
            """INSERT INTO personal_tasks (
                id, user_id, title, status, priority, importance, source, external_id,
                course_id, score, score_max, graded_at, remote_submitted_at,
                last_synced_at, completed_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task_id, user_id, "学习通作业", status, "medium", "unknown",
                "chaoxing", task_id, course_id, score, score_max,
                now if score is not None else None,
                remote_submitted_at, now, now if status == "completed" else None,
                now, now,
            ),
        )


def _insert_chaoxing_exam(
    db: Database,
    *,
    user_id: str = "user1",
    exam_id: str = "exam_1",
    external_id: str = "course_1:quiz_1",
    exam_at=None,
    course_id: str = "course_1",
    score=None,
) -> None:
    now = _now().isoformat()
    with db.transaction() as conn:
        conn.execute(
            """INSERT INTO chaoxing_exams (
                id, user_id, course_id, external_id, title, exam_at, score, score_max,
                status, source_url, first_seen_at, last_synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (exam_id, user_id, course_id, external_id, "单元测验", exam_at,
             score, None, "discovered", None, now, now),
        )


# --------------------------------------------------------------------------
# 1. 抓取层解析
# --------------------------------------------------------------------------

def test_parse_score_reads_graded_assignment_text():
    assert ChaoxingParser.parse_score("已批阅 88分") == (88.0, None)
    assert ChaoxingParser.parse_score("成绩：92.5/100") == (92.5, 100.0)
    assert ChaoxingParser.parse_score("得分 76.5 分") == (76.5, None)


def test_parse_score_ignores_dates_and_ungraded_text():
    # 未提交的条目不应该产出分数，日期里的时间也不该被误判成分数。
    assert ChaoxingParser.parse_score("未交 截止：2024/03/05 12:30") == (None, None)
    assert ChaoxingParser.parse_score("待批阅") == (None, None)
    assert ChaoxingParser.parse_score("") == (None, None)


def test_parse_submitted_at_reads_platform_timestamp():
    iso = ChaoxingParser.parse_submitted_at("提交时间：2024-03-05 12:30")
    assert iso is not None
    assert iso.startswith("2024-03-05T12:30:00+08:00")


def test_parse_submitted_at_returns_none_without_marker():
    assert ChaoxingParser.parse_submitted_at("2024-03-05 12:30") is None
    assert ChaoxingParser.parse_submitted_at("已交") is None


def test_parse_exam_at_reads_millisecond_timestamp():
    iso = ChaoxingParser.parse_exam_at({"begintime": "1710000000000"})
    assert iso is not None
    parsed = datetime.fromisoformat(iso)
    assert parsed.tzinfo is not None
    assert parsed.year == 2024


def test_parse_exam_at_falls_back_to_end_time():
    iso = ChaoxingParser.parse_exam_at({"endtime": "2024-06-01 09:00"})
    assert iso is not None
    assert iso.startswith("2024-06-01T09:00:00+08:00")


def test_parse_metadata_score_prefers_structured_fields():
    assert ChaoxingParser.parse_metadata_score({"score": "90", "totalScore": "100"}) == (90.0, 100.0)
    assert ChaoxingParser.parse_metadata_score({}) == (None, None)


# --------------------------------------------------------------------------
# 2. 落库
# --------------------------------------------------------------------------

def test_upsert_exam_is_idempotent_and_flags_changes():
    db = _make_db()
    _add_user(db)
    repo = ChaoxingRepository(db)
    first = repo.upsert_exam(
        user_id="user1", external_id="c1:q1", title="单元测验", course_id="course_1",
    )
    assert first["is_new"] is True and first["changed"] is True
    second = repo.upsert_exam(
        user_id="user1", external_id="c1:q1", title="单元测验", course_id="course_1",
    )
    assert second["is_new"] is False and second["changed"] is False
    third = repo.upsert_exam(
        user_id="user1", external_id="c1:q1", title="单元测验", course_id="course_1",
        score=88.0, exam_at="2024-06-01T09:00:00+08:00",
    )
    assert third["is_new"] is False and third["changed"] is True
    stored = repo.list_exams(user_id="user1")
    assert len(stored) == 1
    assert stored[0]["score"] == 88.0


def test_legacy_database_gains_score_columns_and_exam_table(tmp_path):
    """旧库升级: personal_tasks 补成绩列，且新建 chaoxing_exams 表。"""
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(path))
    # 用当前 schema 建表，再删掉本次新增的列，精确模拟"升级前"的旧库。
    conn.executescript(PERSONAL_TASK_SCHEMA_SQL)
    for column in ("remote_submitted_at", "score", "score_max", "graded_at"):
        conn.execute(f"ALTER TABLE personal_tasks DROP COLUMN {column}")
    conn.commit()
    conn.close()

    db = Database(path)
    try:
        with db.query() as conn:
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(personal_tasks)").fetchall()
            }
            tables = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
        assert {"remote_submitted_at", "score", "score_max", "graded_at"} <= columns
        assert "chaoxing_exams" in tables
    finally:
        db.dispose()


# --------------------------------------------------------------------------
# 3. 事件
# --------------------------------------------------------------------------

def _event_service(db: Database) -> LearnerEventService:
    return LearnerEventService(
        LearnerEventRepository(db),
        personal_task_repository=None,
        course_content_repository=None,
    )


def test_assignment_graded_derives_band_from_score():
    db = _make_db()
    _add_user(db)
    service = _event_service(db)
    result = service.record_chaoxing_assignment_graded(
        user_id="user1", task_id="task_1", course_id="course_1",
        score=88.0, score_max=100.0, observed_at=_now(),
    )
    assert result is not None and result.created is True
    events, _ = service.list_events(user_id="user1", page=1, page_size=10)
    assert events[0].event_type == "assignment_graded"
    assert events[0].payload["normalized_score_band"] == "80_89"
    assert events[0].payload["score"] == 88.0


def test_assignment_graded_dedupes_on_same_score():
    db = _make_db()
    _add_user(db)
    service = _event_service(db)
    kwargs = dict(
        user_id="user1", task_id="task_1", course_id="course_1",
        score=88.0, observed_at=_now(),
    )
    assert service.record_chaoxing_assignment_graded(**kwargs).created is True
    assert service.record_chaoxing_assignment_graded(**kwargs).created is False


def test_assignment_submitted_prefers_remote_submitted_at():
    db = _make_db()
    _add_user(db)
    service = _event_service(db)
    remote = (_now() - timedelta(days=3)).isoformat()
    task = PersonalTaskRow(
        id="task_1", user_id="user1", title="作业", status="completed",
        source="chaoxing", external_id="ext_1", remote_submitted_at=remote,
        last_synced_at=_now().isoformat(), completed_at=_now().isoformat(),
    )
    result = service.record_chaoxing_assignment_submitted(task, observed_at=_now())
    assert result is not None
    events, _ = service.list_events(user_id="user1", page=1, page_size=10)
    row = events[0]
    assert row.event_type == "assignment_submitted"
    # 真实提交时间优先于同步观测时间，否则"晚同步"会整体推后完成时间。
    assert row.occurred_at == remote
    assert row.payload["submitted_at_source"] == "remote"
    assert row.data_quality == "verified"


def test_exam_candidates_persist_and_project_once():
    """exam_candidate 落库成 chaoxing_exams，并只在新发现/变化时投射事件。"""
    db = _make_db()
    _add_user(db)

    class _Container:
        def __init__(self) -> None:
            self.chaoxing_repository = ChaoxingRepository(db)
            self.course_content_repository = CourseContentRepository(db)
            self.learner_event_service = _event_service(db)

    service = ChaoxingCourseContentSyncService(_Container())
    items = [{
        "kind": "exam_candidate",
        "external_id": "quiz_1",
        "title": "单元测验",
        "source_url": "https://chaoxing.example/exam/1",
        "metadata": {"exam_at": "2024-06-01T09:00:00+08:00", "score": 88.0},
    }]
    service._persist_exams(
        user_id="user1", course_id="course_1", items=items, course_external_id="11_22",
    )
    stored = ChaoxingRepository(db).list_exams(user_id="user1")
    assert len(stored) == 1
    assert stored[0]["external_id"] == "11_22:quiz_1"
    assert stored[0]["score"] == 88.0

    events, total = _event_service(db).list_events(user_id="user1", page=1, page_size=10)
    assert total == 1
    assert events[0].event_type == "exam_discovered"

    # 重复同步同一条考试不应重复投射事件。
    service._persist_exams(
        user_id="user1", course_id="course_1", items=items, course_external_id="11_22",
    )
    _, total = _event_service(db).list_events(user_id="user1", page=1, page_size=10)
    assert total == 1


def test_exam_discovered_event_is_recorded():
    db = _make_db()
    _add_user(db)
    service = _event_service(db)
    result = service.record_chaoxing_exam_discovered(
        user_id="user1", exam_id="exam_1", course_id="course_1",
        exam_time_bucket="within_7d", observed_at=_now(),
    )
    assert result is not None and result.created is True
    events, _ = service.list_events(user_id="user1", page=1, page_size=10)
    assert events[0].event_type == "exam_discovered"
    assert events[0].payload["exam_time_bucket"] == "within_7d"


# --------------------------------------------------------------------------
# 4. 世界模型投影
# --------------------------------------------------------------------------

def _projection_service(db: Database) -> LearnerStateProjectionService:
    return LearnerStateProjectionService(
        LearnerStateRepository(db),
        learner_event_repository=LearnerEventRepository(db),
    )


def test_academic_grade_observation_counts_chaoxing_scores():
    db = _make_db()
    _add_user(db)
    _insert_chaoxing_task(db, task_id="t1", score=88.0, score_max=100.0)
    _insert_chaoxing_task(db, task_id="t2", score=95.0, score_max=100.0)
    service = _projection_service(db)
    result = service.project_academic("user1", as_of=_now())
    grade = next(s for s in result.snapshots if s.state_type == "grade_observation")
    assert grade.value["observed_grade_count"] == 2
    assert grade.value["platform_grade_count"] == 2
    assert grade.value["edu_grade_count"] == 0
    assert grade.value["score_band_distribution"] == {"80_89": 1, "90_100": 1}
    assert grade.value["has_observed_grades"] is True
    # 只有学习通观测时可信度低于教务权威数据。
    assert grade.data_quality == "partial"


def test_academic_exam_exposure_counts_chaoxing_exams():
    db = _make_db()
    _add_user(db)
    future = (_now() + timedelta(days=3)).isoformat()
    _insert_chaoxing_exam(db, exam_id="e1", external_id="c1:q1", exam_at=future)
    service = _projection_service(db)
    result = service.project_academic("user1", as_of=_now())
    exam = next(s for s in result.snapshots if s.state_type == "exam_exposure")
    assert exam.value["upcoming_exam_count"] == 1
    assert exam.value["platform_exam_count"] == 1
    assert exam.value["time_bucket_distribution"] == {"within_7d": 1}


def test_world_academic_progress_counts_chaoxing_scores():
    db = _make_db()
    _add_user(db)
    _insert_chaoxing_task(db, task_id="t1", score=70.0, course_id="course_1")
    _insert_chaoxing_task(db, task_id="t2", score=50.0, course_id="course_2")
    service = _projection_service(db)
    result = service.project_world("user1", as_of=_now())
    progress = next(s for s in result.snapshots if s.state_type == "academic_progress")
    assert progress.value["observed_course_count"] == 2
    assert progress.value["observed_passed_count"] == 1
    assert progress.value["platform_grade_count"] == 2
    assert progress.value["platform_average_score"] == 60.0


def test_world_workload_pressure_counts_chaoxing_exams():
    db = _make_db()
    _add_user(db)
    future = (_now() + timedelta(days=2)).isoformat()
    _insert_chaoxing_exam(db, exam_id="e1", external_id="c1:q1", exam_at=future)
    service = _projection_service(db)
    result = service.project_world("user1", as_of=_now())
    pressure = next(s for s in result.snapshots if s.state_type == "workload_pressure")
    assert pressure.value["exam_count"] == 1


def test_upsert_exam_keeps_confirmed_score_when_later_sync_omits_it():
    """某轮同步不再回传分数/考试时间时，已确认的事实必须保留。"""
    db = _make_db()
    _add_user(db)
    repo = ChaoxingRepository(db)
    repo.upsert_exam(
        user_id="user1", external_id="c1:q1", title="单元测验", course_id="course_1",
        score=88.0, score_max=100.0, exam_at="2024-06-01T09:00:00+08:00",
    )
    # 第二轮只拿到标题（chapter card 缺字段 / 分片失败）。
    second = repo.upsert_exam(
        user_id="user1", external_id="c1:q1", title="单元测验", course_id="course_1",
    )
    stored = repo.list_exams(user_id="user1")[0]
    assert stored["score"] == 88.0
    assert stored["score_max"] == 100.0
    assert stored["exam_at"] == "2024-06-01T09:00:00+08:00"
    # 没有实际变化就不应重新投射事件。
    assert second["changed"] is False
    assert second["score"] == 88.0
    assert second["exam_at"] == "2024-06-01T09:00:00+08:00"


def test_zero_score_is_treated_as_observed_failure():
    """0 分是有效成绩，不能被当成"未观测"丢弃。"""
    db = _make_db()
    _add_user(db)
    _insert_chaoxing_task(db, task_id="t1", score=0.0, score_max=100.0)
    service = _projection_service(db)

    academic = service.project_academic("user1", as_of=_now())
    grade = next(s for s in academic.snapshots if s.state_type == "grade_observation")
    assert grade.value["score_band_distribution"] == {"0_59": 1}

    world = service.project_world("user1", as_of=_now())
    progress = next(s for s in world.snapshots if s.state_type == "academic_progress")
    assert progress.value["platform_grade_count"] == 1
    assert progress.value["platform_average_score"] == 0.0
    assert progress.value["observed_passed_count"] == 0

    event_service = _event_service(db)
    graded = event_service.record_chaoxing_assignment_graded(
        user_id="user1", task_id="t1", course_id="course_1",
        score=0.0, score_max=100.0, observed_at=_now(),
    )
    assert graded is not None and graded.created is True
    events, _ = event_service.list_events(user_id="user1", page=1, page_size=10)
    assert events[0].payload["normalized_score_band"] == "0_59"


def test_parse_score_rejects_full_score_and_weight_descriptions():
    """裸"X分"不能把满分/总分/权重当成实得分。"""
    assert ChaoxingParser.parse_score("第三次作业 截止：2026-08-20 已交 满分100分") == (None, None)
    assert ChaoxingParser.parse_score("第一章作业 总分：100分 未交") == (None, None)
    assert ChaoxingParser.parse_score("小测验 共 20 分 已批阅") == (None, None)
    assert ChaoxingParser.parse_score("作业 权重 30分 已交") == (None, None)
    # 批阅语境下的真实分数仍要采信，带满分的形式也要采信。
    assert ChaoxingParser.parse_score("已批阅 88分") == (88.0, None)
    assert ChaoxingParser.parse_score("已批阅 92/100") == (92.0, 100.0)


def test_learning_activity_prefers_remote_submitted_at():
    """晚同步时完成时间取平台回传的真实提交时间，而不是本地"发现已完成"时间。"""
    db = _make_db()
    _add_user(db)
    service = _projection_service(db)
    # 真实提交在 10 天前(超出 7 天窗口)，本地 completed_at 因晚同步是今天。
    tasks = [{
        "id": "t1", "status": "completed", "deleted_at": None,
        "completed_at": _now().isoformat(),
        "remote_submitted_at": (_now() - timedelta(days=10)).isoformat(),
    }]
    value, _, _, _ = service._activity(
        events=[], sessions=[], tasks=tasks, as_of=_now(), user_id="user1"
    )
    assert value["observed_completed_tasks_7d"] == 0
    assert value["observed_completed_tasks_30d"] == 1
