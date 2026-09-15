"""统一"今日待办"事实源的契约测试。

覆盖: 上海时区自然日边界、跨午夜、无截止时间、已逾期、已提交/已批阅、
未来事项排除、用户隔离、统一排序、学习通条目只读。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.database.sqlite_db import Database
from app.repositories.chaoxing_repository import ChaoxingRepository
from app.repositories.multi_role_repository import CourseRepository
from app.repositories.personal_task_repository import PersonalTaskRepository
from app.services.agenda_service import SHANGHAI, TodayAgendaService

# 2026-09-15 是周二；固定"现在"避免测试随时间漂移。
NOW = datetime(2026, 9, 15, 12, 0, 0, tzinfo=SHANGHAI)


@pytest.fixture
def db() -> Database:
    database = Database(None)
    with database.transaction() as conn:
        for user_id in ("user1", "user2"):
            conn.execute(
                "INSERT INTO users (id, username, password_hash, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, user_id, "hash", "now", "now"),
            )
    yield database
    database.dispose()


class FakeEduConnector:
    """最小教务连接器替身: 只暴露 list_schedule_items(与容器真实入口一致)。"""

    def __init__(self, entries):
        self._entries = entries

    def list_schedule_items(self, user_id, *, semester=None, include_stale: bool = False):
        return [entry for entry in self._entries if getattr(entry, "user_id", user_id) == user_id]


class ScheduleEntry:
    def __init__(self, *, id, user_id="user1", course_name="高等数学", weekday=2,
                 start_section=1, start_time="08:00", location="教三 201", is_stale=0):
        self.id = id
        self.user_id = user_id
        self.course_name = course_name
        self.weekday = weekday
        self.start_section = start_section
        self.start_time = start_time
        self.location = location
        self.is_stale = is_stale


class FakeContainer:
    def __init__(self, db: Database, *, edu=None, bound: bool = False):
        self.db = db
        self.personal_task_repository = PersonalTaskRepository(db)
        self.chaoxing_repository = ChaoxingRepository(db)
        self.course_repository = CourseRepository(db)
        self.edu_connector = edu
        if bound:
            self.chaoxing_repository.save_credentials("user1", {"cookie": "A"})


def _iso(value: datetime) -> str:
    return value.isoformat()


def _force_created_at(db: Database, task_id: str, moment: datetime) -> None:
    """`create_task` 只写当前时间，而 update_task 不允许改 created_at。

    为了测"历史遗留待办"这类时间相关的行为，这里直接改库，避免为了测试放宽
    生产仓库的字段白名单。
    """
    with db.transaction() as conn:
        conn.execute(
            "UPDATE personal_tasks SET created_at = ? WHERE id = ?",
            (moment.isoformat(), task_id),
        )


def _at(hour: int, minute: int = 0, *, day: int = 15) -> datetime:
    return datetime(2026, 9, day, hour, minute, 0, tzinfo=SHANGHAI)


def _chaoxing_task(container: FakeContainer, *, title: str, external_id: str,
                   deadline: datetime | None = None, status: str = "pending",
                   completed_at: datetime | None = None, score=None,
                   submitted_at: str | None = None, user_id: str = "user1"):
    repo = container.personal_task_repository
    row = repo.create_task(
        user_id=user_id, title=title, source="chaoxing", external_id=external_id,
        deadline=_iso(deadline) if deadline else None,
        source_name="高等数学", last_synced_at=_iso(NOW - timedelta(minutes=5)),
    )
    if completed_at is not None:
        repo.complete(row.id, user_id=user_id)
    fields = {}
    if completed_at is not None:
        fields["completed_at"] = _iso(completed_at)
    if score is not None:
        fields["score"] = score
        fields["score_max"] = 100
    if submitted_at is not None:
        fields["remote_submitted_at"] = submitted_at
    if fields:
        repo.update_task(row.id, user_id=user_id, fields=fields)
    return repo.get_task(row.id, user_id=user_id)


def _personal_task(container: FakeContainer, *, title: str, deadline: datetime | None = None,
                   created_at: datetime | None = None, status: str = "pending",
                   completed_at: datetime | None = None, user_id: str = "user1"):
    repo = container.personal_task_repository
    row = repo.create_task(
        user_id=user_id, title=title,
        deadline=_iso(deadline) if deadline else None,
        source_name="个人安排",
    )
    fields = {}
    if completed_at is not None:
        repo.complete(row.id, user_id=user_id)
        fields["completed_at"] = _iso(completed_at)
    if fields:
        repo.update_task(row.id, user_id=user_id, fields=fields)
    if created_at is not None:
        _force_created_at(container.db, row.id, created_at)
    return repo.get_task(row.id, user_id=user_id)


def _build(container: FakeContainer, user_id: str = "user1") -> dict:
    return TodayAgendaService(container).build(user_id=user_id, now=NOW)


def _titles(payload: dict) -> list[str]:
    return [item["title"] for item in payload["items"]]


# ---------- 上海时区自然日边界 ----------

def test_shanghai_day_boundary_not_utc_date_truncation(db):
    """今天 23:30(+08:00) 算今天；次日 00:30(+08:00) 不算今天。

    后者的 UTC 日期恰好是 09-15，如果按 UTC 或字符串截断判断就会误判成今天。
    """
    container = FakeContainer(db)
    _personal_task(container, title="今天深夜截止", deadline=_at(23, 30))
    _personal_task(container, title="次日凌晨截止", deadline=_at(0, 30, day=16))

    payload = _build(container)

    assert payload["date"] == "2026-09-15"
    assert payload["timezone"] == "Asia/Shanghai"
    assert _titles(payload) == ["今天深夜截止"]


def test_cross_midnight_overdue_is_classified_overdue(db):
    container = FakeContainer(db)
    _personal_task(container, title="昨晚就该交", deadline=_at(23, 0, day=14))

    payload = _build(container)

    assert payload["items"][0]["status"] == "overdue"
    assert payload["summary"]["overdue"] == 1


# ---------- 学习通作业 ----------

def test_overdue_pending_assignment_included_and_future_excluded(db):
    container = FakeContainer(db, bound=True)
    _chaoxing_task(container, title="逾期作业", external_id="w1",
                   deadline=_at(20, 0, day=10))
    _chaoxing_task(container, title="下周才交", external_id="w2",
                   deadline=_at(20, 0, day=20))

    payload = _build(container)

    assert _titles(payload) == ["逾期作业"]
    assert payload["items"][0]["kind"] == "assignment"
    assert payload["items"][0]["source"] == "chaoxing"
    assert payload["items"][0]["status"] == "overdue"


def test_completed_today_counted_completed_yesterday_excluded(db):
    container = FakeContainer(db, bound=True)
    _chaoxing_task(container, title="今天交的", external_id="w1",
                   deadline=_at(20, 0), completed_at=_at(9, 0))
    _chaoxing_task(container, title="昨天交的", external_id="w2",
                   deadline=_at(20, 0, day=14), completed_at=_at(9, 0, day=14))

    payload = _build(container)

    assert _titles(payload) == ["今天交的"]
    assert payload["summary"]["completed"] == 1
    assert payload["summary"]["pending"] == 0


def test_graded_and_submitted_statuses_are_distinguished(db):
    container = FakeContainer(db, bound=True)
    _chaoxing_task(container, title="已批阅", external_id="w1", deadline=_at(20, 0),
                   completed_at=_at(9, 0), score=88)
    _chaoxing_task(container, title="已提交待批阅", external_id="w2", deadline=_at(21, 0),
                   completed_at=_at(9, 30), submitted_at=_iso(_at(9, 30)))

    statuses = {item["title"]: item["status"] for item in _build(container)["items"]}

    assert statuses["已批阅"] == "graded"
    assert statuses["已提交待批阅"] == "submitted"


def test_assignment_without_deadline_is_not_today(db):
    """学习通作业没有截止时间时无法判断属于今天，不猜测、不硬塞。"""
    container = FakeContainer(db, bound=True)
    _chaoxing_task(container, title="没有截止时间", external_id="w1")

    assert _build(container)["items"] == []


# ---------- 个人待办(77 件问题的根因) ----------

def test_timeless_historical_personal_tasks_are_not_today(db):
    """历史遗留的无期限待办不能被当成"今天" —— 这正是"77 件待完成"的根因。"""
    container = FakeContainer(db)
    for index in range(77):
        _personal_task(
            container, title=f"历史待办 {index}",
            created_at=datetime(2026, 8, 1, 10, 0, tzinfo=SHANGHAI),
        )
    _personal_task(container, title="今天新建的无期限待办", created_at=_at(8, 0))

    payload = _build(container)

    assert _titles(payload) == ["今天新建的无期限待办"]
    assert payload["summary"]["total"] == 1


def test_personal_task_due_today_included_future_excluded(db):
    container = FakeContainer(db)
    _personal_task(container, title="今天截止", deadline=_at(18, 0))
    _personal_task(container, title="后天截止", deadline=_at(18, 0, day=17))

    assert _titles(_build(container)) == ["今天截止"]


# ---------- 学习通考试 ----------

def test_exam_today_enters_agenda_and_graded_exam_counts_completed(db):
    container = FakeContainer(db, bound=True)
    container.chaoxing_repository.upsert_exam(
        user_id="user1", external_id="c1:e1", title="期中测验",
        exam_at=_iso(_at(14, 0)), status="discovered",
    )
    container.chaoxing_repository.upsert_exam(
        user_id="user1", external_id="c1:e2", title="已出分的测验",
        exam_at=_iso(_at(10, 0)), score=92, score_max=100, status="discovered",
    )
    container.chaoxing_repository.upsert_exam(
        user_id="user1", external_id="c1:e3", title="明天的考试",
        exam_at=_iso(_at(10, 0, day=16)), status="discovered",
    )
    container.chaoxing_repository.upsert_exam(
        user_id="user1", external_id="c1:e4", title="没有时间的考试",
        status="discovered",
    )

    payload = _build(container)
    by_title = {item["title"]: item for item in payload["items"]}

    assert set(by_title) == {"期中测验", "已出分的测验"}
    assert by_title["期中测验"]["kind"] == "exam"
    assert by_title["期中测验"]["status"] == "pending"
    assert by_title["已出分的测验"]["status"] == "graded"
    assert payload["summary"]["completed"] == 1


# ---------- 今天的课程 ----------

def test_today_classes_come_from_schedule_only_when_present(db):
    without_schedule = FakeContainer(db)
    payload = _build(without_schedule)
    assert payload["sources"]["schedule"]["state"] == "unavailable"
    assert not [item for item in payload["items"] if item["kind"] == "class"]

    with_schedule = FakeContainer(
        db,
        edu=FakeEduConnector([
            ScheduleEntry(id="s1", weekday=2),
            ScheduleEntry(id="s2", weekday=3),            # 不是今天
            ScheduleEntry(id="s3", weekday=2, is_stale=1),  # 已过期
        ]),
    )
    payload = _build(with_schedule)
    classes = [item for item in payload["items"] if item["kind"] == "class"]

    assert [item["source_id"] for item in classes] == ["s1"]
    assert classes[0]["starts_at"].startswith("2026-09-15T08:00")
    assert classes[0]["completable"] is False


# ---------- 排序 ----------

def test_ordering_follows_spec(db):
    container = FakeContainer(
        db, bound=True,
        edu=FakeEduConnector([ScheduleEntry(id="s1", weekday=2)]),
    )
    _personal_task(container, title="无具体时刻", created_at=_at(7, 0))
    _personal_task(container, title="今天个人待办", deadline=_at(19, 0))
    _chaoxing_task(container, title="今天截止作业", external_id="w1", deadline=_at(20, 0))
    _chaoxing_task(container, title="逾期作业", external_id="w2", deadline=_at(20, 0, day=10))
    _chaoxing_task(container, title="今天已完成", external_id="w3", deadline=_at(20, 0),
                   completed_at=_at(8, 0))
    container.chaoxing_repository.upsert_exam(
        user_id="user1", external_id="c1:e1", title="今天考试",
        exam_at=_iso(_at(14, 0)), status="discovered",
    )

    assert _titles(_build(container)) == [
        "逾期作业",
        "今天考试",
        "今天截止作业",
        "今天个人待办",
        "高等数学",
        "无具体时刻",
        "今天已完成",
    ]


# ---------- 操作边界 ----------

def test_chaoxing_items_are_read_only_personal_items_are_editable(db):
    container = FakeContainer(db, bound=True)
    _chaoxing_task(container, title="学习通作业", external_id="w1", deadline=_at(20, 0))
    _personal_task(container, title="个人待办", deadline=_at(18, 0))

    by_title = {item["title"]: item for item in _build(container)["items"]}

    assert by_title["学习通作业"]["editable"] is False
    assert by_title["学习通作业"]["completable"] is False
    assert by_title["个人待办"]["editable"] is True
    assert by_title["个人待办"]["completable"] is True


# ---------- 用户隔离 ----------

def test_users_are_strictly_isolated(db):
    container = FakeContainer(db, bound=True)
    _chaoxing_task(container, title="user1 的作业", external_id="w1", deadline=_at(20, 0))
    _personal_task(container, title="user2 的待办", deadline=_at(18, 0), user_id="user2")

    assert _titles(_build(container, "user1")) == ["user1 的作业"]
    assert _titles(_build(container, "user2")) == ["user2 的待办"]


# ---------- 来源状态(区分"真的没有"与"取不到") ----------

def test_source_state_distinguishes_not_bound_never_synced_and_ok(db):
    unbound = _build(FakeContainer(db))
    assert unbound["sources"]["chaoxing"]["state"] == "not_bound"
    assert unbound["items"] == []

    bound_only = _build(FakeContainer(db, bound=True))
    assert bound_only["sources"]["chaoxing"]["state"] == "never_synced"

    with_data = FakeContainer(db, bound=True)
    _chaoxing_task(with_data, title="今天截止作业", external_id="w1", deadline=_at(20, 0))
    payload = _build(with_data)
    assert payload["sources"]["chaoxing"]["state"] == "ok"
    assert payload["stale"] is False
    assert payload["last_chaoxing_synced_at"] is not None


def test_stale_is_reported_when_last_sync_is_old(db):
    container = FakeContainer(db, bound=True)
    repo = container.personal_task_repository
    row = repo.create_task(
        user_id="user1", title="很久以前同步的作业", source="chaoxing",
        external_id="w1", deadline=_iso(_at(20, 0)),
        last_synced_at=_iso(NOW - timedelta(days=3)),
    )
    assert row is not None

    payload = _build(container)

    assert payload["stale"] is True
    assert payload["sources"]["chaoxing"]["state"] == "stale"


def test_summary_counts_match_items(db):
    container = FakeContainer(db, bound=True)
    _chaoxing_task(container, title="逾期", external_id="w1", deadline=_at(20, 0, day=10))
    _chaoxing_task(container, title="今天", external_id="w2", deadline=_at(20, 0))
    _chaoxing_task(container, title="今天完成", external_id="w3", deadline=_at(20, 0),
                   completed_at=_at(9, 0))

    summary = _build(container)["summary"]

    assert summary == {"total": 3, "pending": 2, "completed": 1, "overdue": 1}


# ---------- 路由级契约 ----------

def _student_client():
    from fastapi.testclient import TestClient

    from app.core.config import Settings
    from app.main import create_app
    from app.services.container import reset_container_for_tests
    from app.services.demo_seeder import seed_demo_data

    settings = Settings(
        app_env="test", database_url="sqlite:///:memory:",
        auto_seed_demo_users=True, auto_import_demo=False, llm_provider="none",
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    client = TestClient(create_app())
    login = client.post("/api/v1/auth/login",
                        json={"username": "student_demo", "password": "Demo123456"})
    assert login.status_code == 200
    return client, container, {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_agenda_route_requires_authentication():
    client, _container, _headers = _student_client()
    assert client.get("/api/v1/agenda/today").status_code == 401


def test_agenda_route_returns_unified_contract_for_today_personal_task():
    client, container, headers = _student_client()
    today_deadline = datetime.now(SHANGHAI).replace(hour=23, minute=0, second=0,
                                                    microsecond=0)
    created = client.post("/api/v1/tasks", headers=headers, json={
        "title": "今天要交的申请材料",
        "deadline": today_deadline.isoformat(),
        "source_name": "个人安排",
    })
    assert created.status_code == 201
    task_id = created.json()["id"]

    response = client.get("/api/v1/agenda/today", headers=headers)
    assert response.status_code == 200
    payload = response.json()

    assert payload["date"] == datetime.now(SHANGHAI).date().isoformat()
    assert payload["timezone"] == "Asia/Shanghai"
    assert set(payload["summary"]) == {"total", "pending", "completed", "overdue"}
    assert set(payload["sources"]) == {"chaoxing", "personal", "schedule"}

    item = next(row for row in payload["items"] if row["source_id"] == task_id)
    assert item["kind"] == "personal_task"
    assert item["source"] == "personal"
    assert item["editable"] is True
    assert item["completable"] is True
    assert item["route"] == f"/tasks/personal/{task_id}"
    assert item["status"] == "pending"
    # 未绑定学习通时必须如实说明，而不是伪装成"今天没有待办"。
    assert payload["sources"]["chaoxing"]["state"] == "not_bound"


def test_agenda_route_does_not_treat_old_timeless_task_as_today():
    client, container, headers = _student_client()
    created = client.post("/api/v1/tasks", headers=headers, json={
        "title": "很久以前记下的无期限待办", "source_name": "个人安排",
    })
    assert created.status_code == 201
    task_id = created.json()["id"]
    _force_created_at(container.db, task_id, datetime(2026, 8, 1, 10, 0, tzinfo=SHANGHAI))

    payload = client.get("/api/v1/agenda/today", headers=headers).json()

    assert not [row for row in payload["items"] if row["source_id"] == task_id]


def test_completing_personal_task_is_reflected_in_agenda():
    client, _container, headers = _student_client()
    today_deadline = datetime.now(SHANGHAI).replace(hour=23, minute=0, second=0,
                                                    microsecond=0)
    created = client.post("/api/v1/tasks", headers=headers, json={
        "title": "今天要完成的事", "deadline": today_deadline.isoformat(),
        "source_name": "个人安排",
    })
    task_id = created.json()["id"]

    before = client.get("/api/v1/agenda/today", headers=headers).json()
    # 演示数据里也有今天的事项，因此只断言相对变化，不写死绝对值。
    assert next(row for row in before["items"]
                if row["source_id"] == task_id)["status"] == "pending"
    pending_before = before["summary"]["pending"]
    completed_before = before["summary"]["completed"]

    assert client.post(f"/api/v1/tasks/{task_id}/complete",
                       headers=headers).status_code == 200

    after = client.get("/api/v1/agenda/today", headers=headers).json()
    assert after["summary"]["pending"] == pending_before - 1
    assert after["summary"]["completed"] == completed_before + 1
    assert next(row for row in after["items"]
                if row["source_id"] == task_id)["status"] == "completed"


def test_expired_chaoxing_session_is_reported_and_wins_over_empty(db):
    """登录态过期必须优先于"今天没有事项"，否则用户会以为数据没丢。

    今日待办自身不触网，登录态只读 /chaoxing/status 写下的进程内缓存。
    """
    from app.schemas.chaoxing import ChaoxingSyncStatus
    from app.services.chaoxing.session_cache import invalidate, set_cached

    container = FakeContainer(db, bound=True)
    invalidate("user1")
    try:
        # 没有缓存时只能是 unknown，绝不猜成 online。
        assert _build(container)["sources"]["chaoxing"]["auth_state"] == "unknown"

        set_cached("user1", ChaoxingSyncStatus(status="expired"))
        payload = _build(container)
        assert payload["sources"]["chaoxing"]["auth_state"] == "expired"
        assert payload["sources"]["chaoxing"]["state"] == "expired"
        assert "过期" in payload["sources"]["chaoxing"]["message"]
    finally:
        invalidate("user1")


def test_online_session_keeps_normal_ok_state(db):
    from app.schemas.chaoxing import ChaoxingSyncStatus
    from app.services.chaoxing.session_cache import invalidate, set_cached

    container = FakeContainer(db, bound=True)
    _chaoxing_task(container, title="今天截止作业", external_id="w1", deadline=_at(20, 0))
    set_cached("user1", ChaoxingSyncStatus(status="online"))
    try:
        payload = _build(container)
        assert payload["sources"]["chaoxing"]["auth_state"] == "online"
        assert payload["sources"]["chaoxing"]["state"] == "ok"
    finally:
        invalidate("user1")


def test_schedule_source_is_ok_when_schedule_exists_but_empty_today(db):
    """有课表但今天没课 ≠ 课表不可用。前者是 ok/0 条，后者才是 unavailable。"""
    container = FakeContainer(db, edu=FakeEduConnector([ScheduleEntry(id="s9", weekday=5)]))
    payload = _build(container)
    assert payload["sources"]["schedule"]["state"] == "ok"
    assert payload["sources"]["schedule"]["item_count"] == 0
    assert not [item for item in payload["items"] if item["kind"] == "class"]

    # 完全没导入过课表 -> 如实上报不可用，而不是"今天没有课"
    no_schedule = _build(FakeContainer(db))
    assert no_schedule["sources"]["schedule"]["state"] == "unavailable"
    assert no_schedule["sources"]["schedule"]["message"]


def test_schedule_connector_failure_does_not_break_the_agenda(db):
    class ExplodingConnector:
        def list_schedule_items(self, user_id, **kwargs):
            raise RuntimeError("edu connector down")

    container = FakeContainer(db, edu=ExplodingConnector())
    _personal_task(container, title="今天截止", deadline=_at(18, 0))

    payload = _build(container)

    assert payload["sources"]["schedule"]["state"] == "unavailable"
    assert _titles(payload) == ["今天截止"]
