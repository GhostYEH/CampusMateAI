"""仓储写事务：用 Database.transaction(immediate=True) 保留预占写锁的意图。

覆盖:
- 独立调用在读改写前发出 BEGIN IMMEDIATE
- 提交仓储只在 student_write 时预占写锁
- 外层尚未写入 / 外层已写入的嵌套调用都由最外层负责预占，嵌套用保存点
- 异常回滚不留下半截写入

（跨 Database 实例的并发不丢更新由 test_notice_workflow_concurrency.py 覆盖。）
"""
from __future__ import annotations

import pytest

from app.core.exceptions import SubmissionNotFound
from app.database.sqlite_db import Database
from app.repositories.notice_workflow_repository import NoticeWorkflowRepository
from app.repositories.personal_task_repository import PersonalTaskRepository
from app.repositories.submission_repository import SubmissionRepository
from app.repositories.user_repository import UserRepository


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "repo-transactions.sqlite3")
    yield database
    database.dispose()


def _trace(db, monkeypatch) -> list[str]:
    statements: list[str] = []
    original = db._connect

    def connect():
        conn = original()
        conn.set_trace_callback(statements.append)
        return conn

    monkeypatch.setattr(db, "_connect", connect)
    return statements


def _begin_immediate_count(statements: list[str]) -> int:
    return sum(1 for sql in statements if sql.strip().upper() == "BEGIN IMMEDIATE")


def test_import_batch_reserves_write_lock_before_reading(db, monkeypatch):
    user = UserRepository(db).create_user(username="importer", password_hash="x")
    repo = PersonalTaskRepository(db)
    statements = _trace(db, monkeypatch)

    created, skipped = repo.create_import_batch(
        user_id=user.id, tasks=[{"title": "第一条"}, {"title": "第二条"}]
    )

    assert len(created) == 2 and skipped == []
    assert _begin_immediate_count(statements) == 1
    # 预占写锁必须发生在任何读取之前（否则会出现读改写丢失更新）。
    begin_index = next(i for i, sql in enumerate(statements) if sql.strip().upper() == "BEGIN IMMEDIATE")
    first_read = next(i for i, sql in enumerate(statements) if "FROM personal_tasks" in sql)
    assert begin_index < first_read


def test_submission_write_reserves_lock_only_for_student_writes(db, monkeypatch):
    users = UserRepository(db)
    student = users.create_user(username="student", password_hash="x")
    repo = SubmissionRepository(db)
    statements = _trace(db, monkeypatch)

    # 无对应作业：学生写入会在预占写锁后校验并失败，但 BEGIN IMMEDIATE 已发出。
    with pytest.raises(Exception):
        repo.upsert_submission(
            assignment_id="missing", student_id=student.id, status="submitted", student_write=True
        )
    assert _begin_immediate_count(statements) == 1

    # 非学生写入沿用原来的普通事务：不应预占写锁。
    statements.clear()
    with pytest.raises(Exception):
        repo.upsert_submission(assignment_id="missing", student_id=student.id, student_write=False)
    assert _begin_immediate_count(statements) == 0


def test_notice_workflow_writes_reserve_write_lock(db, monkeypatch):
    user = UserRepository(db).create_user(username="workflow-owner", password_hash="x")
    repo = NoticeWorkflowRepository(db)
    workflow = repo.create_workflow(
        user_id=user.id, notice_id="notice", content_fingerprint="fingerprint",
    )
    repo.update_workflow_interpretation(workflow.workflow_id, steps=[{"text": "first"}])

    statements = _trace(db, monkeypatch)
    repo.mark_step_done(workflow.workflow_id, 0)
    assert _begin_immediate_count(statements) == 1

    statements.clear()
    source = repo.create_source(code="manual_input", display_name="Manual", kind="manual")
    statements.clear()
    repo.update_source_preference(source.source_id, user.id, automation_enabled=True)
    assert _begin_immediate_count(statements) == 1


@pytest.mark.parametrize("write_before_inner", [False, True])
def test_nested_repository_transaction_defers_lock_to_outermost(db, monkeypatch, write_before_inner):
    """外层尚未写入 / 已写入的嵌套调用都由最外层预占写锁，嵌套用保存点。"""
    user = UserRepository(db).create_user(username="nested", password_hash="x")
    repo = PersonalTaskRepository(db)
    statements = _trace(db, monkeypatch)

    with db.transaction() as outer:
        if write_before_inner:
            outer.execute("UPDATE users SET updated_at = 'nested' WHERE id = ?", (user.id,))
        created, _ = repo.create_import_batch(user_id=user.id, tasks=[{"title": "嵌套任务"}])
        assert len(created) == 1

    # 嵌套操作永远只用保存点，不会自己再开一个事务。
    assert any("SAVEPOINT" in sql.upper() for sql in statements)
    if write_before_inner:
        # 外层已写入：写锁已由外层隐式持有，嵌套不再重复预占。
        assert _begin_immediate_count(statements) == 0
    else:
        # 外层尚未写入：由最外层补一次 BEGIN IMMEDIATE 提前预占写锁。
        assert _begin_immediate_count(statements) == 1
    stored, total = repo.list_tasks(user.id, status="pending", page=1, page_size=10)
    assert total == 1 and stored[0].title == "嵌套任务"


def test_nested_repository_transaction_rolls_back_with_outer_failure(db, monkeypatch):
    user = UserRepository(db).create_user(username="nested-rollback", password_hash="x")
    repo = PersonalTaskRepository(db)

    with pytest.raises(RuntimeError, match="outer aborted"):
        with db.transaction() as outer:
            repo.create_import_batch(user_id=user.id, tasks=[{"title": "不应保留"}])
            outer.execute("UPDATE users SET updated_at = 'nested' WHERE id = ?", (user.id,))
            raise RuntimeError("outer aborted")

    _, total = repo.list_tasks(user.id, status="pending", page=1, page_size=10)
    assert total == 0


def test_repository_failure_rolls_back_without_partial_write(db):
    user = UserRepository(db).create_user(username="attachment-owner", password_hash="x")
    repo = SubmissionRepository(db)

    with pytest.raises(SubmissionNotFound):
        repo.add_attachment(
            submission_id="missing-submission",
            original_filename="a.txt",
            stored_filename="a.txt",
            mime_type="text/plain",
            size_bytes=1,
            storage_path="unused",
            student_write=True,
        )

    with db.query() as conn:
        assert conn.execute("SELECT COUNT(*) FROM submission_attachments").fetchone()[0] == 0
