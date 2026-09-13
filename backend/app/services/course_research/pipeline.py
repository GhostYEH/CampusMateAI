"""Coordinator 逻辑角色调度 pipeline(§8.2)。

V1 由一个 AgentExecutor 切换逻辑角色执行阶段,不创建独立进程。
顺序: Coordinator -> CourseResearcher -> WebResearcher -> CitationVerifier
      -> Tutor -> Critic -> Synthesizer
任一角色失败后,已完成阶段保留,Run 标记 PARTIAL 并产出部分结果。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ...models.course_research import CourseResearchSourceRow
from ...repositories.course_research_repository import CourseResearchRepository
from ...schemas.agent_contract_enums import (
    AcademicPolicy,
    AgentEventType,
    ArtifactType,
    AssistanceMode,
    RunPhase,
    RunStatus,
)
from ...services.agent_runtime.artifact_manager import ArtifactManager
from ...services.agent_runtime.event_store import AgentEventStore
from ...services.agent_runtime.executor import AgentExecutor
from ...services.agent_runtime.run_manager import RunManager
from ...services.llm.model_router import ModelRouter
from .citation_verifier import CitationVerifier
from .policy import (
    EffectivePolicy,
    SourcePolicy,
    build_effective_policy,
)
from .source_fetcher import ControlledSourceFetcher


# 逻辑角色顺序(§8.2)
ROLE_SEQUENCE: tuple[str, ...] = (
    "coordinator",
    "course_researcher",
    "web_researcher",
    "citation_verifier",
    "tutor",
    "critic",
    "synthesizer",
)


@dataclass
class _StageContext:
    """阶段间共享的执行上下文。"""

    run_id: str
    session_id: str
    user_id: str
    question: str
    course_id: Optional[str]
    effective: EffectivePolicy
    course_sources: list[CourseResearchSourceRow] = field(default_factory=list)
    web_sources: list[CourseResearchSourceRow] = field(default_factory=list)
    upload_sources: list[CourseResearchSourceRow] = field(default_factory=list)
    verified_sources: list[CourseResearchSourceRow] = field(default_factory=list)
    unverified_sources: list[CourseResearchSourceRow] = field(default_factory=list)
    tutor_answer: str = ""
    critic_notes: str = ""
    fallback_used: bool = False
    failed_roles: list[str] = field(default_factory=list)


@dataclass
class CourseResearchResult:
    """pipeline 执行结果。"""

    run_id: str
    session_id: str
    status: RunStatus
    artifact_ids: list[str]
    verified_source_count: int
    unverified_source_count: int
    fallback_used: bool
    failed_roles: list[str]
    effective_mode: AssistanceMode
    academic_policy: AcademicPolicy
    degraded: bool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CourseResearchPipeline:
    """Coordinator 调度 pipeline。

    复用现有 runtime 服务:
    - agent_executor: 逻辑角色切换、step/event
    - model_router: 模型路由
    - artifact_manager: 产物写入
    - run_manager: 状态转换
    - repository: course_research 持久化
    """

    def __init__(
        self,
        *,
        repository: CourseResearchRepository,
        executor: AgentExecutor,
        model_router: ModelRouter,
        artifact_manager: ArtifactManager,
        run_manager: RunManager,
        event_store: AgentEventStore,
        source_fetcher: ControlledSourceFetcher,
        citation_verifier: CitationVerifier,
        course_content_lookup=None,
        retrieval_service=None,
    ) -> None:
        self._repo = repository
        self._executor = executor
        self._router = model_router
        self._artifacts = artifact_manager
        self._runs = run_manager
        self._events = event_store
        self._fetcher = source_fetcher
        self._verifier = citation_verifier
        self._course_lookup = course_content_lookup
        self._retrieval = retrieval_service

    async def execute(
        self,
        *,
        run_id: str,
        session_id: str,
        user_id: str,
        question: str,
        course_id: Optional[str],
        requested_mode: AssistanceMode,
        academic_candidates: list[AcademicPolicy],
        source_policy: SourcePolicy,
        user_upload_refs: Optional[list[str]] = None,
    ) -> CourseResearchResult:
        """执行完整 pipeline。"""
        user_upload_refs = user_upload_refs or []
        # 构建有效策略
        effective = build_effective_policy(
            requested_mode=requested_mode,
            academic_candidates=academic_candidates,
            source_policy=source_policy,
        )
        ctx = _StageContext(
            run_id=run_id,
            session_id=session_id,
            user_id=user_id,
            question=question,
            course_id=course_id,
            effective=effective,
        )
        self._load_user_uploads(ctx, user_upload_refs)
        # 转入 RUNNING
        self._safe_transition(run_id, RunStatus.RUNNING, RunPhase.CONTEXT_BUILDING)
        self._emit(
            run_id, AgentEventType.RUN_STARTED, RunStatus.RUNNING,
            RunPhase.CONTEXT_BUILDING, role="coordinator",
            summary="开始课程研究",
        )
        # AI_PROHIBITED: 仅允许 HINT,不进行完整研究
        if effective.academic_policy == AcademicPolicy.AI_PROHIBITED:
            return await self._finish_with_policy_block(ctx, effective)

        # 顺序执行逻辑角色；每个边界都重读持久化取消状态。
        stages = (
            self._run_coordinator,
            self._run_course_researcher,
            self._run_web_researcher,
            self._run_citation_verifier,
            self._run_tutor,
            self._run_critic,
            self._run_synthesizer,
        )
        for stage in stages:
            await stage(ctx)
            if self._executor.is_cancelled(run_id):
                self._repo.update_session(
                    session_id, status=RunStatus.CANCELLED.value, finished_at=_now()
                )
                return CourseResearchResult(
                    run_id=run_id,
                    session_id=session_id,
                    status=RunStatus.CANCELLED,
                    artifact_ids=[],
                    verified_source_count=len(ctx.verified_sources),
                    unverified_source_count=len(ctx.unverified_sources),
                    fallback_used=ctx.fallback_used,
                    failed_roles=ctx.failed_roles,
                    effective_mode=effective.effective_mode,
                    academic_policy=effective.academic_policy,
                    degraded=effective.degraded,
                )

        # 根据失败情况决定终态
        if ctx.failed_roles:
            status = RunStatus.PARTIAL
            self._safe_transition(run_id, status, RunPhase.IDLE)
            self._emit(
                run_id, AgentEventType.RUN_PARTIAL, status, RunPhase.IDLE,
                summary=f"部分角色失败: {', '.join(ctx.failed_roles)}",
            )
        else:
            status = RunStatus.SUCCEEDED
            self._safe_transition(run_id, status, RunPhase.IDLE)
            self._emit(
                run_id, AgentEventType.RUN_COMPLETED, status, RunPhase.IDLE,
                summary="研究完成",
            )
        self._repo.update_session(
            session_id, status=status.value, finished_at=_now(),
        )
        return CourseResearchResult(
            run_id=run_id,
            session_id=session_id,
            status=status,
            artifact_ids=[],  # 由 synthesizer 填充
            verified_source_count=len(ctx.verified_sources),
            unverified_source_count=len(ctx.unverified_sources),
            fallback_used=ctx.fallback_used,
            failed_roles=ctx.failed_roles,
            effective_mode=effective.effective_mode,
            academic_policy=effective.academic_policy,
            degraded=effective.degraded,
        )

    # ===== 各角色实现 =====

    async def _run_coordinator(self, ctx: _StageContext) -> None:
        """Coordinator: 分解问题,规划检索。"""
        step_id = self._begin_step(ctx, "coordinator", 1, "分解研究问题")
        try:
            # 使用 reasoning_primary 路由
            result = await self._route(
                ctx, "coordinator", "reasoning_primary",
                prompt=f"分解以下课程研究问题,列出检索关键词:\n{ctx.question}",
            )
            if result is None:
                ctx.failed_roles.append("coordinator")
                ctx.fallback_used = True
            self._finish_step(ctx, "coordinator", step_id, "问题已分解")
        except Exception:
            ctx.failed_roles.append("coordinator")
            self._finish_step(ctx, "coordinator", step_id, "分解失败", failed=True)

    async def _run_course_researcher(self, ctx: _StageContext) -> None:
        """CourseResearcher: 检索课程资料(优先)。"""
        if not ctx.effective.source_policy.course_first():
            return
        step_id = self._begin_step(ctx, "course_researcher", 2, "检索课程资料")
        try:
            # 优先使用 CourseContentRepository
            if self._course_lookup is not None and ctx.course_id:
                items = self._course_lookup.list_items(
                    user_id=ctx.user_id, course_id=ctx.course_id,
                ) or []
                for item in items[:5]:
                    src = self._repo.add_source(
                        session_id=ctx.session_id,
                        user_id=ctx.user_id,
                        source_type="course_material",
                        title=getattr(item, "title", "课程资料"),
                        source_ref=getattr(item, "id", None),
                        snippet=getattr(item, "description", None),
                        accessed_at=_now(),
                    )
                    ctx.course_sources.append(src)
            # 复用 RetrievalService(BM25)
            if self._retrieval is not None and self._retrieval.is_ready:
                try:
                    chunks = self._retrieval.search(ctx.question, k=5)
                except Exception:
                    chunks = []
                for rc in chunks:
                    doc = rc.document
                    if doc is None:
                        continue
                    src = self._repo.add_source(
                        session_id=ctx.session_id,
                        user_id=ctx.user_id,
                        source_type="course_material",
                        title=doc.title,
                        source_ref=doc.document_id,
                        snippet=rc.chunk.content[:500],
                        accessed_at=_now(),
                    )
                    ctx.course_sources.append(src)
            self._finish_step(ctx, "course_researcher", step_id, f"检索到 {len(ctx.course_sources)} 条课程资料")
        except Exception:
            ctx.failed_roles.append("course_researcher")
            self._finish_step(ctx, "course_researcher", step_id, "检索失败", failed=True)

    async def _run_web_researcher(self, ctx: _StageContext) -> None:
        """WebResearcher: 公共 Web 检索(策略允许时)。"""
        if not ctx.effective.source_policy.may_fetch_web():
            # 硬约束:禁用 Web 时不搜索
            self._emit(
                ctx.run_id, AgentEventType.TOOL_COMPLETED, RunStatus.RUNNING,
                RunPhase.WAITING_FOR_TOOL, role="web_researcher",
                summary="来源策略禁止 Web 检索,跳过",
            )
            return
        step_id = self._begin_step(ctx, "web_researcher", 3, "检索公共 Web")
        try:
            # V1 对用户明确提供的公开 URL 做受控抓取。没有可验证 URL
            # 时明确跳过，绝不把“未查询”伪装成检索成功。
            urls = list(dict.fromkeys(re.findall(r"https?://[^\s<>\]\[\)]+", ctx.question)))[:5]
            if not urls:
                self._finish_step(
                    ctx, "web_researcher", step_id, "未提供公开 URL，已跳过 Web 抓取"
                )
                return
            for url in urls:
                fetched = await self._fetcher.fetch(url, allow_web=True)
                src = self._repo.add_source(
                    session_id=ctx.session_id,
                    user_id=ctx.user_id,
                    source_type="web",
                    title=fetched.title,
                    url=fetched.url,
                    snippet=fetched.snippet,
                    accessed_at=fetched.accessed_at,
                )
                ctx.web_sources.append(src)
            self._finish_step(
                ctx,
                "web_researcher",
                step_id,
                f"已受控抓取 {len(ctx.web_sources)} 个公开来源",
            )
        except Exception:
            ctx.failed_roles.append("web_researcher")
            self._finish_step(ctx, "web_researcher", step_id, "Web 检索失败", failed=True)

    async def _run_citation_verifier(self, ctx: _StageContext) -> None:
        """CitationVerifier: 校验引用存在性与支持性。"""
        step_id = self._begin_step(ctx, "citation_verifier", 4, "验证引用")
        try:
            all_sources = ctx.course_sources + ctx.web_sources + ctx.upload_sources
            results = self._verifier.verify_batch(
                all_sources, claim=ctx.question, supports_map=None,
            )
            for src, res in zip(all_sources, results):
                self._repo.update_source(
                    src.source_id,
                    is_verified=res.is_verified,
                    verification_note=res.verification_note,
                    supports_claim=res.supports_claim,
                    is_fabricated=res.is_fabricated,
                )
                if res.is_verified and res.supports_claim:
                    ctx.verified_sources.append(src)
                else:
                    ctx.unverified_sources.append(src)
            self._finish_step(
                ctx, "citation_verifier", step_id,
                f"已验证 {len(ctx.verified_sources)},未验证 {len(ctx.unverified_sources)}",
            )
        except Exception:
            ctx.failed_roles.append("citation_verifier")
            self._finish_step(ctx, "citation_verifier", step_id, "验证失败", failed=True)

    async def _run_tutor(self, ctx: _StageContext) -> None:
        """Tutor: 按有效辅助模式生成解答。"""
        step_id = self._begin_step(ctx, "tutor", 5, f"生成 {ctx.effective.effective_mode.value} 解答")
        try:
            mode = ctx.effective.effective_mode
            source_snippets = "\n".join(
                f"- {s.title}: {s.snippet or ''}" for s in ctx.verified_sources[:5]
            )
            prompt = (
                f"基于以下来源,以 {mode.value} 模式回答问题。\n"
                f"问题: {ctx.question}\n来源:\n{source_snippets}\n"
                f"仅使用上述来源,不要编造。"
            )
            result = await self._route(
                ctx, "tutor", "reasoning_primary", prompt=prompt,
            )
            if result is None:
                ctx.failed_roles.append("tutor")
                ctx.fallback_used = True
                ctx.tutor_answer = "模型不可用,无法生成解答。"
            else:
                ctx.tutor_answer = result
            self._finish_step(ctx, "tutor", step_id, "解答已生成")
        except Exception:
            ctx.failed_roles.append("tutor")
            ctx.tutor_answer = "解答生成失败。"
            self._finish_step(ctx, "tutor", step_id, "解答失败", failed=True)

    async def _run_critic(self, ctx: _StageContext) -> None:
        """Critic: 检查覆盖、不确定性、学术策略。"""
        step_id = self._begin_step(ctx, "critic", 6, "审查覆盖与策略")
        try:
            result = await self._route(
                ctx, "critic", "dual_review",
                prompt=f"审查以下解答的覆盖度与策略合规性:\n{ctx.tutor_answer}",
            )
            if result is None:
                ctx.fallback_used = True
                ctx.critic_notes = "审查不可用,已降级。"
            else:
                ctx.critic_notes = result
            self._finish_step(ctx, "critic", step_id, "审查完成")
        except Exception:
            ctx.failed_roles.append("critic")
            ctx.critic_notes = "审查失败。"
            self._finish_step(ctx, "critic", step_id, "审查失败", failed=True)

    async def _run_synthesizer(self, ctx: _StageContext) -> None:
        """Synthesizer: 生成带引用的 Markdown 报告。"""
        step_id = self._begin_step(ctx, "synthesizer", 7, "综合报告")
        try:
            report_md = self._build_report_markdown(ctx)
            artifact_id = self._artifacts.create(
                run_id=ctx.run_id,
                user_id=ctx.user_id,
                artifact_type=ArtifactType.COURSE_RESEARCH_REPORT.value,
                content=report_md,
                mime_type="text/markdown",
                version=1,
            )
            self._emit(
                ctx.run_id, AgentEventType.ARTIFACT_CREATED, RunStatus.RUNNING,
                RunPhase.PERSISTING_RESULT, role="synthesizer",
                summary="报告产物已创建", artifact_id=artifact_id,
            )
            # 同时写一个 citation bundle(JSON)
            citation_bundle = {
                "verified": [s.source_id for s in ctx.verified_sources],
                "unverified": [s.source_id for s in ctx.unverified_sources],
            }
            citation_artifact_id = self._artifacts.create(
                run_id=ctx.run_id,
                user_id=ctx.user_id,
                artifact_type=ArtifactType.CITATION_BUNDLE.value,
                content=citation_bundle,
                mime_type="application/json",
                version=1,
            )
            self._repo.create_report(
                session_id=ctx.session_id,
                user_id=ctx.user_id,
                artifact_id=artifact_id,
                content_hash="sha256:" + str(hash(report_md)),
                mime_type="text/markdown",
                size_bytes=len(report_md.encode("utf-8")),
                verified_source_count=len(ctx.verified_sources),
                unverified_source_count=len(ctx.unverified_sources),
                fallback_used=ctx.fallback_used,
            )
            self._finish_step(ctx, "synthesizer", step_id, "报告已生成")
        except Exception:
            ctx.failed_roles.append("synthesizer")
            self._finish_step(ctx, "synthesizer", step_id, "综合失败", failed=True)

    def _build_report_markdown(self, ctx: _StageContext) -> str:
        """生成带引用的 Markdown 报告。"""
        lines: list[str] = []
        lines.append(f"# 课程研究报告\n")
        lines.append(f"**问题**: {ctx.question}\n")
        lines.append(f"**辅助模式**: {ctx.effective.effective_mode.value}")
        if ctx.effective.degraded:
            lines.append(f" (已从 {ctx.effective.requested_mode.value} 降级)")
        lines.append(f"\n**学术策略**: {ctx.effective.academic_policy.value}\n")
        lines.append(f"## 解答\n\n{ctx.tutor_answer}\n")
        if ctx.critic_notes:
            lines.append(f"## 审查备注\n\n{ctx.critic_notes}\n")
        lines.append("## 引用\n")
        if ctx.verified_sources:
            lines.append("\n### 已验证来源\n")
            for i, s in enumerate(ctx.verified_sources, 1):
                lines.append(f"{i}. {s.title} — {s.verification_note or ''}")
        if ctx.unverified_sources:
            lines.append("\n### 未验证来源\n")
            for i, s in enumerate(ctx.unverified_sources, 1):
                tag = " [伪造]" if s.is_fabricated else ""
                lines.append(f"{i}. {s.title}{tag} — {s.verification_note or '未验证'}")
        if ctx.fallback_used:
            lines.append("\n---\n*本次研究使用了模型 fallback。*\n")
        return "\n".join(lines)

    async def _finish_with_policy_block(
        self, ctx: _StageContext, effective: EffectivePolicy,
    ) -> CourseResearchResult:
        """AI_PROHIBITED: 仅提示,不研究。"""
        self._safe_transition(ctx.run_id, RunStatus.SUCCEEDED, RunPhase.IDLE)
        self._emit(
            ctx.run_id, AgentEventType.RUN_COMPLETED, RunStatus.SUCCEEDED,
            RunPhase.IDLE, role="coordinator",
            summary="学术策略禁止 AI 代答,仅提供提示",
        )
        self._repo.update_session(
            ctx.session_id, status=RunStatus.SUCCEEDED.value, finished_at=_now(),
        )
        return CourseResearchResult(
            run_id=ctx.run_id,
            session_id=ctx.session_id,
            status=RunStatus.SUCCEEDED,
            artifact_ids=[],
            verified_source_count=0,
            unverified_source_count=0,
            fallback_used=False,
            failed_roles=[],
            effective_mode=effective.effective_mode,
            academic_policy=effective.academic_policy,
            degraded=effective.degraded,
        )

    # ===== 辅助 =====

    def _load_user_uploads(self, ctx: _StageContext, refs: list[str]) -> None:
        """Resolve only artifacts owned by the current user into research sources."""
        if not refs or not ctx.effective.source_policy.may_use_user_upload():
            return
        for ref in refs[:20]:
            artifact = self._artifacts.get(ref, ctx.user_id)
            if not artifact:
                continue
            content = self._artifacts.read_content(ref, ctx.user_id) or ""
            source = self._repo.add_source(
                session_id=ctx.session_id,
                user_id=ctx.user_id,
                source_type="user_upload",
                title=f"用户资料 {ref}",
                source_ref=ref,
                snippet=content[:500],
                accessed_at=_now(),
            )
            ctx.upload_sources.append(source)

    def _begin_step(
        self, ctx: _StageContext, role: str, sequence: int, summary: str,
    ) -> str:
        self._emit(
            ctx.run_id, AgentEventType.TOOL_STARTED, RunStatus.RUNNING,
            RunPhase.WAITING_FOR_TOOL, role=role, summary=summary,
            progress={"current": sequence, "total": len(ROLE_SEQUENCE),
                      "percent": int(sequence * 100 / len(ROLE_SEQUENCE))},
        )
        return self._executor.begin_step(
            run_id=ctx.run_id, role=role, phase="WAITING_FOR_TOOL",
            sequence=sequence, summary=summary,
        )

    def _finish_step(
        self, ctx: _StageContext, role: str, step_id: str, summary: str,
        *, failed: bool = False,
    ) -> None:
        evt = AgentEventType.TOOL_FAILED if failed else AgentEventType.TOOL_COMPLETED
        self._emit(
            ctx.run_id, evt, RunStatus.RUNNING, RunPhase.WAITING_FOR_TOOL,
            role=role, summary=summary,
        )

    def _emit(
        self, run_id: str, evt_type: AgentEventType, status: RunStatus,
        phase: RunPhase, *, role: Optional[str] = None,
        summary: Optional[str] = None, progress: Optional[dict] = None,
        artifact_id: Optional[str] = None,
    ) -> None:
        try:
            self._events.append(
                run_id=run_id, type=evt_type.value, status=status.value,
                phase=phase.value, role=role, summary=summary,
                progress=progress, artifact_id=artifact_id,
            )
        except Exception:
            pass

    def _safe_transition(
        self, run_id: str, to_status: RunStatus, phase: RunPhase,
    ) -> None:
        try:
            self._runs.transition(run_id, to_status.value, phase=phase.value)
        except Exception:
            pass

    async def _route(
        self, ctx: _StageContext, role: str, policy: str, *, prompt: str,
    ) -> Optional[str]:
        """按策略路由模型调用。失败返回 None。"""
        try:
            messages = [
                {"role": "system", "content": f"你是课程研究角色: {role}。"},
                {"role": "user", "content": prompt},
            ]
            result = await self._router.route(
                messages, route_policy=policy, max_tokens=1024,
                run_id=ctx.run_id,
            )
            if result.response is None:
                return None
            return result.response.content
        except Exception:
            return None


__all__ = ["CourseResearchPipeline", "CourseResearchResult", "ROLE_SEQUENCE"]
