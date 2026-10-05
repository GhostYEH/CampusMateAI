"""规划器读取通知的截断行为与仓库层 limit。

回归点：
- `list_notices(limit=..)` 在 SQL 层截断，不把该用户全部通知读入内存；
- 规划器传 `MAX_NOTICES + 1`，多取的那条只用于判定是否截断，再在 Python 侧切片；
- 未超限时不得误报 `notices_truncated`（若改为传 MAX_NOTICES，少一条就会永不触发）。
"""
from __future__ import annotations

from app.core.config import Settings
from app.core.security import hash_password
from app.repositories.notice_repository import NoticeRepository
from app.services.container import reset_container_for_tests
from app.services.learning_planner_service import MAX_NOTICES

SEED_EXTRA = 3


def _setup():
    container = reset_container_for_tests(Settings(app_env="test", database_url="sqlite:///:memory:"))
    student = container.user_repository.create_user(
        username="notice_trunc_student", password_hash=hash_password("Demo123456"), role="student"
    )
    return container, student


def _seed_notices(container, user_id: str, count: int) -> None:
    repo: NoticeRepository = container.notice_repository
    for index in range(count):
        repo.create_or_update_notice(
            user_id=user_id,
            source="chaoxing",
            external_id=f"trunc-{index}",
            title=f"通知 {index}",
            # 递增时间戳保证倒序稳定，便于断言"取到的是最新的一批"。
            published_at=str(1783209663000 + index),
        )


def test_list_notices_limit_truncates_in_sql_and_keeps_newest() -> None:
    container, student = _setup()
    _seed_notices(container, student.id, MAX_NOTICES + SEED_EXTRA)

    repo: NoticeRepository = container.notice_repository
    limited = repo.list_notices(student.id, limit=MAX_NOTICES)
    unlimited = repo.list_notices(student.id)

    assert len(limited) == MAX_NOTICES
    assert len(unlimited) == MAX_NOTICES + SEED_EXTRA
    # 最新在前：limit 结果应等于全量结果的前缀。
    assert [row.external_id for row in limited] == [
        row.external_id for row in unlimited[:MAX_NOTICES]
    ]


def test_list_notices_without_limit_keeps_legacy_semantics() -> None:
    container, student = _setup()
    _seed_notices(container, student.id, MAX_NOTICES + SEED_EXTRA)

    rows = container.notice_repository.list_notices(student.id)
    assert len(rows) == MAX_NOTICES + SEED_EXTRA


def test_planner_flags_truncation_when_notices_exceed_cap() -> None:
    container, student = _setup()
    _seed_notices(container, student.id, MAX_NOTICES + SEED_EXTRA)

    plan = container.learning_planner_service.generate(
        user_id=student.id, available_minutes=30, force_new=True,
        idempotency_key="notice-trunc-exceeded",
    )

    assert "notices_truncated" in plan.run.warning_codes


def test_planner_does_not_flag_truncation_at_exact_cap() -> None:
    container, student = _setup()
    _seed_notices(container, student.id, MAX_NOTICES)

    plan = container.learning_planner_service.generate(
        user_id=student.id, available_minutes=30, force_new=True,
        idempotency_key="notice-trunc-exact",
    )

    assert "notices_truncated" not in plan.run.warning_codes
