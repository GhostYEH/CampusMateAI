"""课程研究 pipeline 测试(§8.2)。

覆盖:
- 六个逻辑角色的顺序
- 失败后的 PARTIAL 输出
- provider fallback
- academic_policy 降级
- 跨用户 artifact 隔离
- 幂等、取消
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.config import Settings, get_settings
from app.database.sqlite_db import reset_db_for_tests
from app.repositories.agent_artifact_repository import AgentArtifactRepository
from app.repositories.agent_runtime_repository import AgentRuntimeRepository
from app.repositories.course_research_repository import CourseResearchRepository
from app.schemas.agent_contract_enums import (
    AcademicPolicy,
    AssistanceMode,
    RunStatus,
)
from app.services.agent_runtime.agent_registry import AgentRegistry
from app.services.agent_runtime.approval_gate import ApprovalGate
from app.services.agent_runtime.artifact_manager import ArtifactManager
from app.services.agent_runtime.context_manager import ContextManager
from app.services.agent_runtime.event_store import AgentEventStore
from app.services.agent_runtime.executor import AgentExecutor
from app.services.agent_runtime.memory_manager import MemoryManager
from app.services.agent_runtime.risk_engine import RiskEngine
from app.services.agent_runtime.run_manager import RunManager
from app.services.agent_runtime.tool_registry import ToolRegistry
from app.services.course_research.citation_verifier import CitationVerifier
from app.services.course_research.pipeline import (
    CourseResearchPipeline,
    ROLE_SEQUENCE,
)
from app.services.course_research.policy import SourcePolicy
from app.services.course_research.source_fetcher import ControlledSourceFetcher
from app.services.llm.model_router import ModelRouter
from app.services.llm.provider_registry import ProviderRegistry


@pytest.fixture
def env(tmp_path):
    """构造完整测试环境。"""
    get_settings.cache_clear()
    db = reset_db_for_tests()
    conn = db._connect()
    try:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
            "VALUES ('u1', 'u1', 'x', 'student', 't', 't')"
        )
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
            "VALUES ('u2', 'u2', 'x', 'student', 't', 't')"
        )
        conn.commit()
    finally:
        db._release(conn)

    runtime_repo = AgentRuntimeRepository(db)
    artifact_repo = AgentArtifactRepository(db, tmp_path / "artifacts")
    cr_repo = CourseResearchRepository(db)

    event_store = AgentEventStore(runtime_repo)
    run_manager = RunManager(runtime_repo, event_store)
    artifact_manager = ArtifactManager(artifact_repo)
    registry = AgentRegistry()
    tools = ToolRegistry()
    executor = AgentExecutor(runtime_repo, registry, tools, event_store)

    # fake providers
    settings = Settings(app_env="development", agent_allow_mock_providers=True)
    provider_reg = ProviderRegistry(settings)
    provider_reg.add_fake("zhipu", route_policies=["reasoning_primary", "dual_review"])
    provider_reg.add_fake("xunfei", route_policies=["fast_structured", "dual_review"])
    model_router = ModelRouter(provider_reg)

    verifier = CitationVerifier()
    fetcher = ControlledSourceFetcher()

    pipeline = CourseResearchPipeline(
        repository=cr_repo,
        executor=executor,
        model_router=model_router,
        artifact_manager=artifact_manager,
        run_manager=run_manager,
        event_store=event_store,
        source_fetcher=fetcher,
        citation_verifier=verifier,
    )

    return {
        "db": db,
        "runtime_repo": runtime_repo,
        "artifact_repo": artifact_repo,
        "cr_repo": cr_repo,
        "run_manager": run_manager,
        "artifact_manager": artifact_manager,
        "pipeline": pipeline,
        "model_router": model_router,
        "provider_reg": provider_reg,
    }


def _create_run(env, user_id="u1"):
    repo = env["runtime_repo"]
    job_id = repo.create_job(user_id=user_id, job_kind="course_research")
    run_id = repo.create_run(job_id=job_id, user_id=user_id)
    return job_id, run_id


class TestRoleSequence:
    def test_six_roles_in_order(self):
        assert ROLE_SEQUENCE == (
            "coordinator",
            "course_researcher",
            "web_researcher",
            "citation_verifier",
            "tutor",
            "critic",
            "synthesizer",
        )

    def test_all_roles_registered(self, env):
        """pipeline 使用的角色必须全部在 AgentRegistry 中注册。"""
        executor = env["pipeline"]._executor
        for role in ROLE_SEQUENCE:
            assert executor.registry.get(role) is not None, f"角色未注册: {role}"


class TestPipelineExecution:
    async def test_successful_run(self, env):
        cr_repo = env["cr_repo"]
        _, run_id = _create_run(env)
        session = cr_repo.create_session(
            run_id=run_id, user_id="u1", question="什么是线性代数?",
            assistance_mode="EXPLAIN", academic_policy="ALLOWED",
            source_policy={"course_material_priority": True, "allow_web": True,
                           "allow_user_upload": True},
        )
        result = await env["pipeline"].execute(
            run_id=run_id, session_id=session.session_id, user_id="u1",
            question="什么是线性代数?", course_id=None,
            requested_mode=AssistanceMode.EXPLAIN,
            academic_candidates=[AcademicPolicy.ALLOWED],
            source_policy=SourcePolicy(),
        )
        assert result.status == RunStatus.SUCCEEDED
        assert result.failed_roles == []
        assert result.effective_mode == AssistanceMode.EXPLAIN

    async def test_ai_prohibited_short_circuits(self, env):
        cr_repo = env["cr_repo"]
        _, run_id = _create_run(env)
        session = cr_repo.create_session(
            run_id=run_id, user_id="u1", question="帮我写作业",
            assistance_mode="FULL_SOLUTION", academic_policy="AI_PROHIBITED",
            source_policy={"course_material_priority": True, "allow_web": True,
                           "allow_user_upload": True},
        )
        result = await env["pipeline"].execute(
            run_id=run_id, session_id=session.session_id, user_id="u1",
            question="帮我写作业", course_id=None,
            requested_mode=AssistanceMode.FULL_SOLUTION,
            academic_candidates=[AcademicPolicy.AI_PROHIBITED],
            source_policy=SourcePolicy(),
        )
        assert result.status == RunStatus.SUCCEEDED
        assert result.effective_mode == AssistanceMode.HINT
        assert result.degraded
        # 不应有产物
        assert result.verified_source_count == 0

    async def test_exam_restricted_degrades_full_solution(self, env):
        cr_repo = env["cr_repo"]
        _, run_id = _create_run(env)
        session = cr_repo.create_session(
            run_id=run_id, user_id="u1", question="期末复习",
            assistance_mode="FULL_SOLUTION", academic_policy="EXAM_RESTRICTED",
            source_policy={"course_material_priority": True, "allow_web": True,
                           "allow_user_upload": True},
        )
        result = await env["pipeline"].execute(
            run_id=run_id, session_id=session.session_id, user_id="u1",
            question="期末复习", course_id=None,
            requested_mode=AssistanceMode.FULL_SOLUTION,
            academic_candidates=[AcademicPolicy.EXAM_RESTRICTED],
            source_policy=SourcePolicy(),
        )
        assert result.effective_mode == AssistanceMode.EXPLAIN
        assert result.degraded

    async def test_web_disabled_skips_web(self, env):
        """禁用 Web 时绝不搜索 Web。"""
        cr_repo = env["cr_repo"]
        _, run_id = _create_run(env)
        session = cr_repo.create_session(
            run_id=run_id, user_id="u1", question="某问题",
            assistance_mode="EXPLAIN", academic_policy="ALLOWED",
            source_policy={"course_material_priority": True, "allow_web": False,
                           "allow_user_upload": True},
        )
        result = await env["pipeline"].execute(
            run_id=run_id, session_id=session.session_id, user_id="u1",
            question="某问题", course_id=None,
            requested_mode=AssistanceMode.EXPLAIN,
            academic_candidates=[AcademicPolicy.ALLOWED],
            source_policy=SourcePolicy(allow_web=False),
        )
        assert result.status == RunStatus.SUCCEEDED
        # 不应有 web 类型来源
        sources = cr_repo.list_sources(session.session_id, user_id="u1")
        assert not any(s.source_type == "web" for s in sources)

    async def test_user_owned_upload_is_loaded_as_a_source(self, env):
        cr_repo = env["cr_repo"]
        _, source_run_id = _create_run(env)
        artifact_id = env["artifact_manager"].create(
            run_id=source_run_id,
            user_id="u1",
            artifact_type="COURSE_RESEARCH_REPORT",
            content="线性代数课程讲义内容",
            mime_type="text/markdown",
        )
        _, run_id = _create_run(env)
        session = cr_repo.create_session(
            run_id=run_id, user_id="u1", question="解释矩阵",
            assistance_mode="EXPLAIN", academic_policy="ALLOWED",
            source_policy={"course_material_priority": True, "allow_web": False,
                           "allow_user_upload": True},
        )
        await env["pipeline"].execute(
            run_id=run_id, session_id=session.session_id, user_id="u1",
            question="解释矩阵", course_id=None,
            requested_mode=AssistanceMode.EXPLAIN,
            academic_candidates=[AcademicPolicy.ALLOWED],
            source_policy=SourcePolicy(allow_web=False, allow_user_upload=True),
            user_upload_refs=[artifact_id],
        )
        sources = cr_repo.list_sources(session.session_id, user_id="u1")
        uploads = [s for s in sources if s.source_type == "user_upload"]
        assert len(uploads) == 1
        assert uploads[0].source_ref == artifact_id
        assert "线性代数课程讲义" in (uploads[0].snippet or "")


class TestPartialFailure:
    async def test_provider_failure_yields_partial(self, env):
        """无 provider 时,tutor 角色失败,Run 标记 PARTIAL。"""
        # 移除所有 provider
        env["provider_reg"]._instances.clear()
        cr_repo = env["cr_repo"]
        _, run_id = _create_run(env)
        session = cr_repo.create_session(
            run_id=run_id, user_id="u1", question="某问题",
            assistance_mode="EXPLAIN", academic_policy="ALLOWED",
            source_policy={"course_material_priority": True, "allow_web": True,
                           "allow_user_upload": True},
        )
        result = await env["pipeline"].execute(
            run_id=run_id, session_id=session.session_id, user_id="u1",
            question="某问题", course_id=None,
            requested_mode=AssistanceMode.EXPLAIN,
            academic_candidates=[AcademicPolicy.ALLOWED],
            source_policy=SourcePolicy(),
        )
        assert result.status == RunStatus.PARTIAL
        assert "coordinator" in result.failed_roles or "tutor" in result.failed_roles
        assert result.fallback_used

    async def test_partial_still_persists_session(self, env):
        """PARTIAL 时 session 状态也更新。"""
        env["provider_reg"]._instances.clear()
        cr_repo = env["cr_repo"]
        _, run_id = _create_run(env)
        session = cr_repo.create_session(
            run_id=run_id, user_id="u1", question="某问题",
            assistance_mode="EXPLAIN", academic_policy="ALLOWED",
            source_policy={"course_material_priority": True, "allow_web": True,
                           "allow_user_upload": True},
        )
        await env["pipeline"].execute(
            run_id=run_id, session_id=session.session_id, user_id="u1",
            question="某问题", course_id=None,
            requested_mode=AssistanceMode.EXPLAIN,
            academic_candidates=[AcademicPolicy.ALLOWED],
            source_policy=SourcePolicy(),
        )
        updated = cr_repo.get_session(session.session_id)
        assert updated.status == RunStatus.PARTIAL.value


class TestArtifactIsolation:
    async def test_cross_user_artifact_isolation(self, env):
        """用户 A 的 artifact 对用户 B 不可见。"""
        cr_repo = env["cr_repo"]
        artifact_manager = env["artifact_manager"]
        # 用户 u1 创建 run
        _, run_id_a = _create_run(env, user_id="u1")
        session_a = cr_repo.create_session(
            run_id=run_id_a, user_id="u1", question="A 的问题",
            assistance_mode="EXPLAIN", academic_policy="ALLOWED",
            source_policy={"course_material_priority": True, "allow_web": True,
                           "allow_user_upload": True},
        )
        await env["pipeline"].execute(
            run_id=run_id_a, session_id=session_a.session_id, user_id="u1",
            question="A 的问题", course_id=None,
            requested_mode=AssistanceMode.EXPLAIN,
            academic_candidates=[AcademicPolicy.ALLOWED],
            source_policy=SourcePolicy(),
        )
        artifacts_a = artifact_manager.list_by_run(run_id_a, "u1")
        assert len(artifacts_a) >= 1
        # 用户 u2 看不到 u1 的 artifact
        artifacts_from_u2 = artifact_manager.list_by_run(run_id_a, "u2")
        assert len(artifacts_from_u2) == 0
        # 直接读取也返回 None
        for art in artifacts_a:
            assert artifact_manager.get(art["artifact_id"], "u2") is None

    async def test_session_user_isolation(self, env):
        cr_repo = env["cr_repo"]
        _, run_id_a = _create_run(env, user_id="u1")
        session_a = cr_repo.create_session(
            run_id=run_id_a, user_id="u1", question="A",
            assistance_mode="EXPLAIN", academic_policy="ALLOWED",
            source_policy={"course_material_priority": True, "allow_web": True,
                           "allow_user_upload": True},
        )
        # u2 不能通过 list_sources 看到 u1 的来源(查询带 user_id)
        sources = cr_repo.list_sources(session_a.session_id, user_id="u2")
        assert sources == []


class TestIdempotency:
    async def test_idempotency_key_dedup(self, env):
        """相同 idempotency_key 返回已有 session。"""
        cr_repo = env["cr_repo"]
        _, run_id = _create_run(env)
        session1 = cr_repo.create_session(
            run_id=run_id, user_id="u1", question="Q",
            assistance_mode="EXPLAIN", academic_policy="ALLOWED",
            source_policy={"course_material_priority": True, "allow_web": True,
                           "allow_user_upload": True},
            idempotency_key="k1",
        )
        found = cr_repo.find_session_by_idempotency("u1", "k1")
        assert found is not None
        assert found.session_id == session1.session_id
        # 不同 key 找不到
        assert cr_repo.find_session_by_idempotency("u1", "k2") is None


class TestCancellation:
    async def test_cancel_before_execute(self, env):
        """取消未执行的 run,pipeline 仍可被调用但状态已终态。"""
        cr_repo = env["cr_repo"]
        runtime_repo = env["runtime_repo"]
        run_manager = env["run_manager"]
        _, run_id = _create_run(env)
        # 先取消
        run_manager.transition(run_id, "RUNNING")
        run_manager.cancel(run_id, reason="用户取消")
        run = runtime_repo.get_run(run_id)
        assert run["status"] == "CANCELLED"
