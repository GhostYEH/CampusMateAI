"""Agent demo 数据隔离测试(§14)。

验证:
1. demo seed 创建确定性 demo user 拥有的三领域场景数据。
2. reset_agent_demo 只删除 demo user 数据,不影响其他用户。
3. reset 在 production 环境被拒绝。
4. reset 幂等。
5. demo 数据不绑定真实学生。
"""
from __future__ import annotations

import sqlite3

import pytest

from app.core.config import Settings
from app.database.sqlite_db import reset_db_for_tests
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import (
    AGENT_DEMO_CAMPAIGN_ID,
    AGENT_DEMO_EXAM_IDS,
    AGENT_DEMO_JOB_ID,
    AGENT_DEMO_RUN_ID,
    seed_demo_data,
)


def _make_container():
    return reset_container_for_tests(
        Settings(
            app_env="test",
            database_url="sqlite:///:memory:",
            auto_seed_demo_users=True,
            auto_import_demo=False,
            llm_provider="none",
            agent_allow_mock_providers=True,
        )
    )


def _seed(container):
    return seed_demo_data(container, force=True)


def _conn(container):
    return container.db._connect()


def _release(container, conn):
    container.db._release(conn)


@pytest.fixture
def container_with_demo():
    container = _make_container()
    _seed(container)
    return container


class TestDemoSeedIsolated:
    """demo seed 创建的数据全部绑定 demo user,且确定性 ID 正确。"""

    def test_demo_user_exists(self, container_with_demo):
        container = container_with_demo
        user = container.user_repository.get_user_by_username("agent_demo")
        assert user is not None
        assert user.role == "student"

    def test_three_exams_seeded(self, container_with_demo):
        container = container_with_demo
        user = container.user_repository.get_user_by_username("agent_demo")
        conn = _conn(container)
        try:
            rows = conn.execute(
                "SELECT id, user_id FROM student_exams WHERE id IN (?,?,?)",
                tuple(AGENT_DEMO_EXAM_IDS),
            ).fetchall()
            assert len(rows) == 3
            for _id, uid in rows:
                assert uid == user.id, f"exam {_id} 未绑定 demo user"
        finally:
            _release(container, conn)

    def test_campaign_seeded(self, container_with_demo):
        container = container_with_demo
        user = container.user_repository.get_user_by_username("agent_demo")
        conn = _conn(container)
        try:
            row = conn.execute(
                "SELECT user_id, status, daily_capacity_minutes "
                "FROM final_review_campaigns WHERE campaign_id = ?",
                (AGENT_DEMO_CAMPAIGN_ID,),
            ).fetchone()
            assert row is not None
            assert row[0] == user.id
            assert row[1] == "draft"
            assert row[2] == 120
        finally:
            _release(container, conn)

    def test_agent_job_and_run_seeded(self, container_with_demo):
        container = container_with_demo
        user = container.user_repository.get_user_by_username("agent_demo")
        conn = _conn(container)
        try:
            job = conn.execute(
                "SELECT user_id, job_kind, status FROM agent_jobs WHERE job_id = ?",
                (AGENT_DEMO_JOB_ID,),
            ).fetchone()
            assert job is not None
            assert job[0] == user.id
            assert job[1] == "final_review"
            assert job[2] == "QUEUED"

            run = conn.execute(
                "SELECT user_id, status, phase FROM agent_runs WHERE run_id = ?",
                (AGENT_DEMO_RUN_ID,),
            ).fetchone()
            assert run is not None
            assert run[0] == user.id
            assert run[1] == "QUEUED"
            assert run[2] == "IDLE"
        finally:
            _release(container, conn)

    def test_model_call_seeded_with_fake_provider(self, container_with_demo):
        container = container_with_demo
        conn = _conn(container)
        try:
            row = conn.execute(
                "SELECT provider, route_policy, status FROM agent_model_calls "
                "WHERE call_id = 'demo_mc_001'"
            ).fetchone()
            assert row is not None
            assert row[0] == "fake"
            assert row[1] == "reasoning_primary"
            assert row[2] == "completed"
        finally:
            _release(container, conn)

    def test_course_research_session_and_sources_seeded(self, container_with_demo):
        container = container_with_demo
        user = container.user_repository.get_user_by_username("agent_demo")
        conn = _conn(container)
        try:
            sess = conn.execute(
                "SELECT user_id, question, assistance_mode, academic_policy "
                "FROM course_research_sessions WHERE session_id = 'demo_crs_001'"
            ).fetchone()
            assert sess is not None
            assert sess[0] == user.id
            assert sess[1] == "解释极限的定义(演示)"
            assert sess[2] == "EXPLAIN"
            assert sess[3] == "ALLOWED"

            sources = conn.execute(
                "SELECT source_id, supports_claim, verification_note "
                "FROM course_research_sources WHERE session_id = 'demo_crs_001' "
                "ORDER BY source_id"
            ).fetchall()
            assert len(sources) == 2
            # 受控冲突:一个 supports=1,一个 supports=0
            supports_values = {s[1] for s in sources}
            assert supports_values == {0, 1}
        finally:
            _release(container, conn)

    def test_chaoxing_notice_seeded(self, container_with_demo):
        container = container_with_demo
        user = container.user_repository.get_user_by_username("agent_demo")
        conn = _conn(container)
        try:
            row = conn.execute(
                "SELECT user_id, source, external_id FROM notices "
                "WHERE id = 'demo_notice_chaoxing_001'"
            ).fetchone()
            assert row is not None
            assert row[0] == user.id
            assert row[1] == "agent_demo"
            assert row[2] == "demo_chaoxing_001"
        finally:
            _release(container, conn)

    def test_demo_data_not_bound_to_real_students(self, container_with_demo):
        """demo 数据不应绑定 student_demo_01..30(真实演示学生)。"""
        container = container_with_demo
        conn = _conn(container)
        try:
            # 取一个真实演示学生
            s01 = container.user_repository.get_user_by_username("student_demo_01")
            if s01 is None:
                pytest.skip("student_demo_01 不存在")
            # agent_runs 不应有 s01 的记录
            count = conn.execute(
                "SELECT COUNT(*) FROM agent_runs WHERE user_id = ?", (s01.id,)
            ).fetchone()[0]
            assert count == 0
            # final_review_campaigns 不应有 s01 的记录
            count = conn.execute(
                "SELECT COUNT(*) FROM final_review_campaigns WHERE user_id = ?",
                (s01.id,),
            ).fetchone()[0]
            assert count == 0
        finally:
            _release(container, conn)


class TestResetAgentDemo:
    """reset_agent_demo 只删除 demo user 数据,不影响其他用户。"""

    def test_dry_run_reports_counts(self, container_with_demo):
        container = container_with_demo
        from scripts.reset_agent_demo import reset_agent_demo

        result = reset_agent_demo(
            apply=False, as_json=False, settings=container.settings, db=container.db
        )
        assert result["status"] == "dry_run"
        assert result["demo_user"] == "agent_demo"
        assert result["total"] > 0
        # 应包含三领域表
        counts = result["counts"]
        assert counts.get("student_exams", 0) == 3
        assert counts.get("final_review_campaigns", 0) == 1
        assert counts.get("agent_jobs", 0) == 1
        assert counts.get("agent_runs", 0) == 1

    def test_apply_deletes_demo_data(self, container_with_demo):
        container = container_with_demo
        from scripts.reset_agent_demo import reset_agent_demo

        result = reset_agent_demo(
            apply=True, as_json=False, settings=container.settings, db=container.db
        )
        assert result["status"] == "ok"
        assert result["total_deleted"] > 0

        # 验证 demo 数据已被删除
        conn = _conn(container)
        try:
            for table, key in [
                ("student_exams", "id"),
                ("final_review_campaigns", "campaign_id"),
                ("agent_jobs", "job_id"),
                ("agent_runs", "run_id"),
            ]:
                count = conn.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
                # demo 数据已删,但可能有其他 demo user 的非 agent 数据(如课程)。
                # agent runtime 表应清空(demo user 是唯一 agent 数据拥有者)。
                if table in ("student_exams", "final_review_campaigns", "agent_jobs", "agent_runs"):
                    assert count == 0, f"{table} 未清空: {count}"
        finally:
            _release(container, conn)

    def test_reset_preserves_other_users(self, container_with_demo):
        """reset 不删除其他用户的 agent 数据。"""
        container = container_with_demo
        from scripts.reset_agent_demo import reset_agent_demo

        # 创建另一个用户并给它一条 agent_runs 记录
        conn = _conn(container)
        try:
            other_user = container.user_repository.get_user_by_username("student_demo_01")
            if other_user is None:
                pytest.skip("student_demo_01 不存在")
            conn.execute(
                "INSERT INTO agent_jobs (job_id, user_id, job_kind, status, "
                "created_at, updated_at) VALUES ('other_job_001', ?, "
                "'final_review', 'QUEUED', 't', 't')",
                (other_user.id,),
            )
            conn.execute(
                "INSERT INTO agent_runs (run_id, job_id, user_id, status, phase, "
                "created_at, updated_at) VALUES ('other_run_001', 'other_job_001', "
                "?, 'QUEUED', 'IDLE', 't', 't')",
                (other_user.id,),
            )
            conn.commit()
        finally:
            _release(container, conn)

        # 执行 reset
        result = reset_agent_demo(
            apply=True, as_json=False, settings=container.settings, db=container.db
        )
        assert result["status"] == "ok"

        # 验证其他用户的 job/run 仍在
        conn = _conn(container)
        try:
            job_count = conn.execute(
                "SELECT COUNT(*) FROM agent_jobs WHERE job_id = 'other_job_001'"
            ).fetchone()[0]
            run_count = conn.execute(
                "SELECT COUNT(*) FROM agent_runs WHERE run_id = 'other_run_001'"
            ).fetchone()[0]
            assert job_count == 1, "reset 误删其他用户的 agent_job"
            assert run_count == 1, "reset 误删其他用户的 agent_run"
        finally:
            _release(container, conn)

    def test_reset_is_idempotent(self, container_with_demo):
        """再次 reset 应返回 0 删除。"""
        container = container_with_demo
        from scripts.reset_agent_demo import reset_agent_demo

        reset_agent_demo(
            apply=True, as_json=False, settings=container.settings, db=container.db
        )
        result = reset_agent_demo(
            apply=True, as_json=False, settings=container.settings, db=container.db
        )
        assert result["status"] == "ok"
        assert result["total_deleted"] == 0

    def test_reset_does_not_delete_demo_user_itself(self, container_with_demo):
        """reset 不删除 demo user 账号本身。"""
        container = container_with_demo
        from scripts.reset_agent_demo import reset_agent_demo

        reset_agent_demo(
            apply=True, as_json=False, settings=container.settings, db=container.db
        )
        user = container.user_repository.get_user_by_username("agent_demo")
        assert user is not None, "reset 误删了 demo user 账号"

    def test_reset_does_not_delete_demo_courses(self, container_with_demo):
        """reset 不删除 demo 课程/班级/选课(非 agent runtime 数据)。"""
        container = container_with_demo
        from scripts.reset_agent_demo import reset_agent_demo

        conn = _conn(container)
        try:
            before_courses = conn.execute(
                "SELECT COUNT(*) FROM courses"
            ).fetchone()[0]
        finally:
            _release(container, conn)

        reset_agent_demo(
            apply=True, as_json=False, settings=container.settings, db=container.db
        )

        conn = _conn(container)
        try:
            after_courses = conn.execute(
                "SELECT COUNT(*) FROM courses"
            ).fetchone()[0]
            assert after_courses == before_courses, "reset 误删了 demo 课程"
        finally:
            _release(container, conn)


class TestResetRejectsProduction:
    """production 环境拒绝执行 reset。"""

    def test_rejects_production(self):
        # 构造一个 production settings(绕过 __init__ 校验,直接设置属性)
        # Settings 在 production 下有严格校验,我们用一个简单的 mock
        class FakeSettings:
            app_env = "production"

        from scripts.reset_agent_demo import reset_agent_demo

        result = reset_agent_demo(apply=True, as_json=False, settings=FakeSettings())
        assert result["status"] == "rejected"
        assert "production" in result["reason"]


class TestSeedIsIdempotent:
    """重复 seed 不创建重复 demo agent 数据。"""

    def test_second_seed_does_not_duplicate(self, container_with_demo):
        container = container_with_demo
        # 再次 seed
        _seed(container)
        conn = _conn(container)
        try:
            # 三个考试(不重复)
            count = conn.execute(
                "SELECT COUNT(*) FROM student_exams WHERE id IN (?,?,?)",
                tuple(AGENT_DEMO_EXAM_IDS),
            ).fetchone()[0]
            assert count == 3
            # 一个 campaign
            count = conn.execute(
                "SELECT COUNT(*) FROM final_review_campaigns WHERE campaign_id = ?",
                (AGENT_DEMO_CAMPAIGN_ID,),
            ).fetchone()[0]
            assert count == 1
            # 一个 job
            count = conn.execute(
                "SELECT COUNT(*) FROM agent_jobs WHERE job_id = ?",
                (AGENT_DEMO_JOB_ID,),
            ).fetchone()[0]
            assert count == 1
            # 一个 run
            count = conn.execute(
                "SELECT COUNT(*) FROM agent_runs WHERE run_id = ?",
                (AGENT_DEMO_RUN_ID,),
            ).fetchone()[0]
            assert count == 1
            # 一个 model_call
            count = conn.execute(
                "SELECT COUNT(*) FROM agent_model_calls WHERE call_id = 'demo_mc_001'"
            ).fetchone()[0]
            assert count == 1
            # 一个 research session
            count = conn.execute(
                "SELECT COUNT(*) FROM course_research_sessions WHERE session_id = 'demo_crs_001'"
            ).fetchone()[0]
            assert count == 1
            # 两个 sources
            count = conn.execute(
                "SELECT COUNT(*) FROM course_research_sources WHERE session_id = 'demo_crs_001'"
            ).fetchone()[0]
            assert count == 2
        finally:
            _release(container, conn)
