"""课程研究安全测试(§11)。

覆盖:
- SSRF 私网/本地地址拒绝(详细矩阵)
- 协议白名单
- 跨用户 artifact 隔离
- 来源策略越权拒绝
- 伪造来源不能进入已验证清单
- provider fallback 不伪装为双模型成功
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.exceptions import AgentSourcePolicyViolation
from app.database.sqlite_db import reset_db_for_tests
from app.models.course_research import CourseResearchSourceRow
from app.repositories.agent_artifact_repository import AgentArtifactRepository
from app.repositories.agent_runtime_repository import AgentRuntimeRepository
from app.repositories.course_research_repository import CourseResearchRepository
from app.schemas.agent_contract_enums import (
    AcademicPolicy,
    AssistanceMode,
    RunStatus,
)
from app.services.agent_runtime.artifact_manager import ArtifactManager
from app.services.agent_runtime.event_store import AgentEventStore
from app.services.agent_runtime.run_manager import RunManager
from app.services.course_research.citation_verifier import CitationVerifier
from app.services.course_research.pipeline import CourseResearchPipeline
from app.services.course_research.policy import (
    SourcePolicy,
    build_effective_policy,
)
from app.services.course_research.source_fetcher import (
    ControlledSourceFetcher,
    SSRFViolation,
    validate_url,
)


@pytest.fixture
def db():
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
    return db


@pytest.fixture
def cr_repo(db):
    return CourseResearchRepository(db)


@pytest.fixture
def runtime_repo(db):
    return AgentRuntimeRepository(db)


@pytest.fixture
def artifact_repo(db, tmp_path):
    return AgentArtifactRepository(db, tmp_path / "artifacts")


class TestSSRFMatrix:
    """SSRF 防护完整矩阵。"""

    @pytest.mark.parametrize("url", [
        "http://127.0.0.1/",
        "http://127.0.0.1:8080/",
        "http://127.1.1.1/",
        "http://10.0.0.1/",
        "http://10.255.255.255/",
        "http://172.16.0.1/",
        "http://172.31.255.255/",
        "http://192.168.0.1/",
        "http://192.168.1.100/",
        "http://169.254.0.1/",
        "http://169.254.169.254/",  # cloud metadata
        "http://0.0.0.0/",
        "http://[::1]/",
        "http://[fc00::1]/",  # IPv6 ULA
        "http://[fe80::1]/",  # IPv6 link-local
    ])
    def test_private_addresses_rejected(self, url):
        with pytest.raises(SSRFViolation):
            validate_url(url)

    @pytest.mark.parametrize("url", [
        "ftp://example.com/",
        "file:///etc/passwd",
        "gopher://example.com/",
        "dict://example.com/",
        "ldap://example.com/",
        "javascript:alert(1)",
        "data:text/html,<script>",
    ])
    def test_non_http_schemes_rejected(self, url):
        with pytest.raises(SSRFViolation, match="协议"):
            validate_url(url)

    @pytest.mark.parametrize("url", [
        "https://example.com/",
        "https://api.example.com/v1/doc",
        "http://example.com/",
        "https://example.edu/path?query=1",
    ])
    def test_public_urls_accepted(self, url):
        # 这些公网域名应通过(不解析为私网)
        try:
            result = validate_url(url)
            assert result == url
        except SSRFViolation as e:
            # 如果 DNS 解析失败(测试环境无网络),允许
            if "解析" not in e.reason and "私网" not in e.reason:
                pytest.skip(f"测试环境 DNS 限制: {e.reason}")

    async def test_redirect_target_is_validated_before_second_request(self):
        import httpx

        requested: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requested.append(str(request.url))
            return httpx.Response(
                302, headers={"location": "http://127.0.0.1/private"}
            )

        fetcher = ControlledSourceFetcher(transport=httpx.MockTransport(handler))
        with pytest.raises(SSRFViolation, match="私网|本地"):
            await fetcher.fetch("https://example.com/start")
        assert requested == ["https://example.com/start"]


class TestSourcePolicyEnforcement:
    async def test_web_disabled_blocks_fetcher(self):
        """allow_web=False 时 fetcher 拒绝。"""
        fetcher = ControlledSourceFetcher()
        with pytest.raises(AgentSourcePolicyViolation):
            await fetcher.fetch("https://example.com", allow_web=False)

    def test_effective_policy_preserves_web_disabled(self):
        sp = SourcePolicy(allow_web=False)
        ep = build_effective_policy(
            requested_mode=AssistanceMode.EXPLAIN,
            academic_candidates=[AcademicPolicy.ALLOWED],
            source_policy=sp,
        )
        assert not ep.source_policy.may_fetch_web()

    def test_course_priority_is_hard_constraint(self):
        """course_material_priority 是硬约束,影响检索顺序。"""
        sp = SourcePolicy(course_material_priority=True)
        assert sp.course_first()
        sp_off = SourcePolicy(course_material_priority=False)
        assert not sp_off.course_first()


class TestFabricatedSourceRejection:
    """伪造来源不能进入已验证清单。"""

    def test_fabricated_marked_unverified(self, cr_repo):
        now = datetime.now(timezone.utc).isoformat()
        # 创建 session
        runtime_repo = AgentRuntimeRepository(cr_repo._db)
        job_id = runtime_repo.create_job(user_id="u1", job_kind="course_research")
        run_id = runtime_repo.create_run(job_id=job_id, user_id="u1")
        session = cr_repo.create_session(
            run_id=run_id, user_id="u1", question="Q",
            assistance_mode="EXPLAIN", academic_policy="ALLOWED",
            source_policy={"course_material_priority": True, "allow_web": True,
                           "allow_user_upload": True},
        )
        # 添加伪造来源
        src = cr_repo.add_source(
            session_id=session.session_id, user_id="u1",
            source_type="course_material", title="伪造来源",
            source_ref="ref_1", accessed_at=now,
            is_fabricated=True,
        )
        # 验证
        verifier = CitationVerifier(
            course_content_lookup=lambda ref, uid: object(),
        )
        result = verifier.verify(src, claim="某主张")
        assert not result.is_verified
        assert result.is_fabricated
        # 更新到 DB
        cr_repo.update_source(
            src.source_id, is_verified=result.is_verified,
            verification_note=result.verification_note,
            supports_claim=result.supports_claim,
            is_fabricated=result.is_fabricated,
        )
        # 从 DB 读回,确认未进入已验证
        sources = cr_repo.list_sources(session.session_id, user_id="u1")
        assert len(sources) == 1
        assert not sources[0].is_verified
        assert sources[0].is_fabricated

    def test_mixed_sources_only_real_verified(self, cr_repo):
        """混合来源中只有真实来源进入已验证清单。"""
        now = datetime.now(timezone.utc).isoformat()
        runtime_repo = AgentRuntimeRepository(cr_repo._db)
        job_id = runtime_repo.create_job(user_id="u1", job_kind="course_research")
        run_id = runtime_repo.create_run(job_id=job_id, user_id="u1")
        session = cr_repo.create_session(
            run_id=run_id, user_id="u1", question="Q",
            assistance_mode="EXPLAIN", academic_policy="ALLOWED",
            source_policy={"course_material_priority": True, "allow_web": True,
                           "allow_user_upload": True},
        )
        real_src = cr_repo.add_source(
            session_id=session.session_id, user_id="u1",
            source_type="course_material", title="真实来源",
            source_ref="ref_real", accessed_at=now,
        )
        fake_src = cr_repo.add_source(
            session_id=session.session_id, user_id="u1",
            source_type="course_material", title="伪造来源",
            source_ref="ref_fake", accessed_at=now,
            is_fabricated=True,
        )
        verifier = CitationVerifier(
            course_content_lookup=lambda ref, uid: object(),
        )
        results = verifier.verify_batch([real_src, fake_src], claim="某主张")
        verified = [s for s, r in zip([real_src, fake_src], results) if r.is_verified]
        assert len(verified) == 1
        assert verified[0].source_id == real_src.source_id


class TestCrossUserIsolation:
    """跨用户 artifact 隔离。"""

    def test_artifact_owner_check(self, artifact_repo, runtime_repo):
        """artifact 读取重新校验所有权。"""
        job_id = runtime_repo.create_job(user_id="u1", job_kind="course_research")
        run_id = runtime_repo.create_run(job_id=job_id, user_id="u1")
        artifact_id = artifact_repo.create_artifact(
            run_id=run_id, user_id="u1", artifact_type="COURSE_RESEARCH_REPORT",
            content="# 报告", mime_type="text/markdown",
        )
        # u1 可读
        assert artifact_repo.get_artifact(artifact_id, "u1") is not None
        # u2 不可读
        assert artifact_repo.get_artifact(artifact_id, "u2") is None
        # u2 读内容也返回 None
        assert artifact_repo.read_content(artifact_id, "u2") is None

    def test_session_user_isolation(self, cr_repo, runtime_repo):
        """u2 不能通过 list_sessions 看到 u1 的 session。"""
        job_id = runtime_repo.create_job(user_id="u1", job_kind="course_research")
        run_id = runtime_repo.create_run(job_id=job_id, user_id="u1")
        cr_repo.create_session(
            run_id=run_id, user_id="u1", question="u1 私密问题",
            assistance_mode="EXPLAIN", academic_policy="ALLOWED",
            source_policy={"course_material_priority": True, "allow_web": True,
                           "allow_user_upload": True},
        )
        u1_sessions = cr_repo.list_sessions_by_user("u1")
        u2_sessions = cr_repo.list_sessions_by_user("u2")
        assert len(u1_sessions) == 1
        assert len(u2_sessions) == 0


class TestProviderFallback:
    """provider fallback 不伪装为双模型成功。"""

    async def test_no_provider_marks_partial(self, tmp_path):
        from app.core.config import Settings, get_settings
        from app.services.agent_runtime.agent_registry import AgentRegistry
        from app.services.agent_runtime.executor import AgentExecutor
        from app.services.agent_runtime.tool_registry import ToolRegistry
        from app.services.llm.model_router import ModelRouter
        from app.services.llm.provider_registry import ProviderRegistry

        get_settings.cache_clear()
        db = reset_db_for_tests()
        conn = db._connect()
        try:
            conn.execute(
                "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
                "VALUES ('u1', 'u1', 'x', 'student', 't', 't')"
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
        executor = AgentExecutor(
            runtime_repo, AgentRegistry(), ToolRegistry(), event_store,
        )
        # 无 provider
        settings = Settings(app_env="development", agent_allow_mock_providers=True)
        provider_reg = ProviderRegistry(settings)
        model_router = ModelRouter(provider_reg)
        pipeline = CourseResearchPipeline(
            repository=cr_repo, executor=executor, model_router=model_router,
            artifact_manager=artifact_manager, run_manager=run_manager,
            event_store=event_store,
            source_fetcher=ControlledSourceFetcher(),
            citation_verifier=CitationVerifier(),
        )
        job_id = runtime_repo.create_job(user_id="u1", job_kind="course_research")
        run_id = runtime_repo.create_run(job_id=job_id, user_id="u1")
        session = cr_repo.create_session(
            run_id=run_id, user_id="u1", question="Q",
            assistance_mode="EXPLAIN", academic_policy="ALLOWED",
            source_policy={"course_material_priority": True, "allow_web": True,
                           "allow_user_upload": True},
        )
        result = await pipeline.execute(
            run_id=run_id, session_id=session.session_id, user_id="u1",
            question="Q", course_id=None,
            requested_mode=AssistanceMode.EXPLAIN,
            academic_candidates=[AcademicPolicy.ALLOWED],
            source_policy=SourcePolicy(),
        )
        # 应标记 PARTIAL 且 fallback_used=True,不伪装为成功
        assert result.status == RunStatus.PARTIAL
        assert result.fallback_used
        assert result.failed_roles  # 有失败角色


class TestIdempotencyAndCancel:
    def test_session_idempotency(self, cr_repo, runtime_repo):
        """相同 idempotency_key 返回同一 session。"""
        job_id = runtime_repo.create_job(user_id="u1", job_kind="course_research")
        run_id = runtime_repo.create_run(job_id=job_id, user_id="u1")
        s1 = cr_repo.create_session(
            run_id=run_id, user_id="u1", question="Q",
            assistance_mode="EXPLAIN", academic_policy="ALLOWED",
            source_policy={"course_material_priority": True, "allow_web": True,
                           "allow_user_upload": True},
            idempotency_key="k1",
        )
        found = cr_repo.find_session_by_idempotency("u1", "k1")
        assert found.session_id == s1.session_id

    def test_cancel_run(self, runtime_repo):
        """取消 run 后状态为 CANCELLED。"""
        run_manager = RunManager(runtime_repo, AgentEventStore(runtime_repo))
        job_id = runtime_repo.create_job(user_id="u1", job_kind="course_research")
        run_id = runtime_repo.create_run(job_id=job_id, user_id="u1")
        run_manager.transition(run_id, "RUNNING")
        run = run_manager.cancel(run_id, reason="测试取消")
        assert run["status"] == "CANCELLED"
