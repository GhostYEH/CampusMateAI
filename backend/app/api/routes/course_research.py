"""课程研究/作业辅助 API 路由(§9.5)。

端点:
    POST   /api/v1/course-research/runs
    GET    /api/v1/course-research/runs
    GET    /api/v1/course-research/runs/{run_id}
    POST   /api/v1/course-research/runs/{run_id}/cancel
    GET    /api/v1/course-research/runs/{run_id}/artifacts

所有写请求支持 Idempotency-Key。鉴权使用 Bearer header。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request

from ...core.exceptions import AgentRuntimeError, AgentRunNotFound
from ...models.multi_role import UserRow
from ...repositories.agent_runtime_repository import AgentRuntimeRepository
from ...repositories.course_research_repository import CourseResearchRepository
from ...schemas.agent_contract_enums import (
    AcademicPolicy,
    RunStatus,
)
from ...schemas.course_research import (
    CourseResearchArtifactListOut,
    CourseResearchArtifactOut,
    CourseResearchRunCancelIn,
    CourseResearchRunCreateIn,
    CourseResearchRunOut,
    ResearchSourceOut,
    SourcePolicyOut,
)
from ...services.agent_runtime.artifact_manager import ArtifactManager
from ...services.agent_runtime.event_store import AgentEventStore
from ...services.agent_runtime.executor import AgentExecutor
from ...services.agent_runtime.run_manager import RunManager
from ...services.course_research.citation_verifier import CitationVerifier
from ...services.course_research.pipeline import CourseResearchPipeline
from ...services.course_research.policy import SourcePolicy, build_effective_policy
from ...services.course_research.source_fetcher import ControlledSourceFetcher
from ...services.llm.model_router import ModelRouter
from ..deps import ServiceContainer, current_user, get_container, student_only

router = APIRouter(prefix="/course-research", tags=["course-research"])


def _repo(container: ServiceContainer) -> CourseResearchRepository:
    return CourseResearchRepository(container.db)


def _runtime_repo(container: ServiceContainer) -> AgentRuntimeRepository:
    return container.agent_runtime_repository


def _build_pipeline(container: ServiceContainer) -> CourseResearchPipeline:
    repo = _repo(container)
    return CourseResearchPipeline(
        repository=repo,
        executor=container.agent_executor,
        model_router=container.agent_model_router,
        artifact_manager=container.agent_artifact_manager,
        run_manager=container.agent_run_manager,
        event_store=container.agent_event_store,
        source_fetcher=ControlledSourceFetcher(),
        citation_verifier=CitationVerifier(),
        course_content_lookup=container.course_content_repository,
        retrieval_service=container.retrieval,
    )


async def _execute_pipeline_background(
    *,
    container: ServiceContainer,
    pipeline: CourseResearchPipeline,
    run_id: str,
    session_id: str,
    user_id: str,
    body: CourseResearchRunCreateIn,
    source_policy: SourcePolicy,
) -> None:
    """在响应返回后执行角色流水线，使 SSE 和取消窗口真正可用。"""
    try:
        await pipeline.execute(
            run_id=run_id,
            session_id=session_id,
            user_id=user_id,
            question=body.question,
            course_id=body.course_id,
            requested_mode=body.assistance_mode,
            academic_candidates=[body.academic_policy, AcademicPolicy.UNKNOWN],
            source_policy=source_policy,
            user_upload_refs=body.user_upload_refs,
        )
    except Exception:
        _repo(container).update_session(
            session_id,
            status=RunStatus.FAILED.value,
            error_code="AGENT_PIPELINE_FAILED",
        )
        try:
            container.agent_run_manager.transition(
                run_id, RunStatus.FAILED.value, phase="IDLE"
            )
            container.agent_event_store.append(
                run_id=run_id,
                type="RUN_FAILED",
                status=RunStatus.FAILED.value,
                phase="IDLE",
                role="coordinator",
                summary="课程研究执行失败",
            )
        except Exception:
            pass


def _session_to_out(
    session, *, artifact_ids: list[str], fallback_used: bool = False,
    effective_mode=None, academic_policy=None,
) -> CourseResearchRunOut:
    from ...schemas.agent_contract_enums import AssistanceMode
    import json as _json
    sp = _json.loads(session.source_policy_json)
    return CourseResearchRunOut(
        run_id=session.run_id,
        session_id=session.session_id,
        user_id=session.user_id,
        course_id=session.course_id,
        question=session.question,
        assistance_mode=AssistanceMode(session.assistance_mode),
        academic_policy=AcademicPolicy(session.academic_policy),
        effective_assistance_mode=effective_mode or AssistanceMode(session.assistance_mode),
        source_policy=SourcePolicyOut(**sp),
        status=RunStatus(session.status),
        created_at=session.created_at,
        updated_at=session.updated_at,
        finished_at=session.finished_at,
        error_code=session.error_code,
        artifact_ids=artifact_ids,
        fallback_used=fallback_used,
    )


@router.post("/runs")
async def create_run(
    body: CourseResearchRunCreateIn,
    request: Request,
    background_tasks: BackgroundTasks,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> CourseResearchRunOut:
    """创建课程研究 Run 并同步执行。"""
    repo = _repo(container)
    runtime_repo = _runtime_repo(container)
    effective_key = body.idempotency_key or idempotency_key
    # 幂等
    if effective_key:
        existing = repo.find_session_by_idempotency(user.id, effective_key)
        if existing:
            artifacts = container.agent_artifact_manager.list_by_run(
                existing.run_id, user.id
            )
            return _session_to_out(
                existing,
                artifact_ids=[a["artifact_id"] for a in artifacts],
            )
    # 创建 job + run
    job_id = runtime_repo.create_job(
        user_id=user.id,
        job_kind="course_research",
        input_ref={"question": body.question, "course_id": body.course_id},
        idempotency_key=effective_key,
    )
    run_id = runtime_repo.create_run(
        job_id=job_id, user_id=user.id, idempotency_key=effective_key,
    )
    # 创建 session
    source_policy = SourcePolicy(
        course_material_priority=body.source_policy.course_material_priority,
        allow_web=body.source_policy.allow_web,
        allow_user_upload=body.source_policy.allow_user_upload,
    )
    session = repo.create_session(
        run_id=run_id,
        user_id=user.id,
        question=body.question,
        assistance_mode=body.assistance_mode.value,
        academic_policy=body.academic_policy.value,
        source_policy={
            "course_material_priority": source_policy.course_material_priority,
            "allow_web": source_policy.allow_web,
            "allow_user_upload": source_policy.allow_user_upload,
        },
        course_id=body.course_id,
        job_id=job_id,
        idempotency_key=effective_key,
    )
    # 响应后执行 pipeline，客户端可在运行期间订阅 SSE。
    pipeline = _build_pipeline(container)
    effective = build_effective_policy(
        requested_mode=body.assistance_mode,
        academic_candidates=[body.academic_policy, AcademicPolicy.UNKNOWN],
        source_policy=source_policy,
    )
    background_tasks.add_task(
        _execute_pipeline_background,
        container=container,
        pipeline=pipeline,
        run_id=run_id,
        session_id=session.session_id,
        user_id=user.id,
        body=body,
        source_policy=source_policy,
    )
    return _session_to_out(
        session,
        artifact_ids=[],
        fallback_used=False,
        effective_mode=effective.effective_mode,
        academic_policy=effective.academic_policy,
    )


@router.get("/runs")
async def list_runs(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[CourseResearchRunOut]:
    """列出当前用户的课程研究 Run。"""
    repo = _repo(container)
    sessions = repo.list_sessions_by_user(user.id, limit=limit, offset=offset)
    out: list[CourseResearchRunOut] = []
    for s in sessions:
        artifacts = container.agent_artifact_manager.list_by_run(s.run_id, user.id)
        out.append(_session_to_out(
            s, artifact_ids=[a["artifact_id"] for a in artifacts],
        ))
    return out


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> CourseResearchRunOut:
    """获取单个课程研究 Run。"""
    repo = _repo(container)
    session = repo.get_session_by_run(run_id)
    if not session:
        raise AgentRunNotFound("Run 不存在")
    if session.user_id != user.id and user.role != "admin":
        raise AgentRunNotFound("Run 不存在")
    artifacts = container.agent_artifact_manager.list_by_run(run_id, user.id)
    return _session_to_out(
        session, artifact_ids=[a["artifact_id"] for a in artifacts],
    )


@router.post("/runs/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    body: CourseResearchRunCancelIn,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> CourseResearchRunOut:
    """取消课程研究 Run。"""
    repo = _repo(container)
    runtime_repo = _runtime_repo(container)
    session = repo.get_session_by_run(run_id)
    if not session:
        raise AgentRunNotFound("Run 不存在")
    if session.user_id != user.id:
        raise AgentRuntimeError(
            "无权取消", code="AGENT_PERMISSION_DENIED", http_status=403,
        )
    from ...services.agent_runtime.run_manager import RunManager
    manager = RunManager(runtime_repo)
    manager.cancel(run_id, reason=body.reason)
    repo.update_session(
        session.session_id, status=RunStatus.CANCELLED.value, finished_at=None,
    )
    container.agent_event_store.append(
        run_id=run_id,
        type="RUN_CANCELLED",
        status=RunStatus.CANCELLED.value,
        phase="IDLE",
        role="coordinator",
        summary="用户已取消课程研究",
    )
    return await get_run(run_id, user, container)


@router.get("/runs/{run_id}/artifacts")
async def list_artifacts(
    run_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> CourseResearchArtifactListOut:
    """列出 Run 的产物与来源。"""
    repo = _repo(container)
    session = repo.get_session_by_run(run_id)
    if not session:
        raise AgentRunNotFound("Run 不存在")
    if session.user_id != user.id and user.role != "admin":
        raise AgentRunNotFound("Run 不存在")
    artifacts_data = container.agent_artifact_manager.list_by_run(run_id, user.id)
    artifacts: list[CourseResearchArtifactOut] = []
    for a in artifacts_data:
        content = container.agent_artifact_manager.read_content(a["artifact_id"], user.id)
        artifacts.append(CourseResearchArtifactOut(
            artifact_id=a["artifact_id"],
            run_id=a["run_id"],
            user_id=a["user_id"],
            artifact_type=a["artifact_type"],
            version=a["version"],
            mime_type=a["mime_type"],
            size_bytes=a["size_bytes"],
            content_hash=a["content_hash"],
            download_url=a.get("download_url"),
            created_at=a["created_at"],
            content=content,
        ))
    sources_rows = repo.list_sources(session.session_id, user_id=user.id)
    sources = [
        ResearchSourceOut(
            source_id=s.source_id,
            source_type=s.source_type,
            title=s.title,
            url=s.url,
            snippet=s.snippet,
            source_ref=s.source_ref,
            accessed_at=s.accessed_at,
            is_verified=s.is_verified,
            verification_note=s.verification_note,
            supports_claim=s.supports_claim,
            is_fabricated=s.is_fabricated,
        )
        for s in sources_rows
    ]
    return CourseResearchArtifactListOut(
        run_id=run_id, artifacts=artifacts, sources=sources,
    )


__all__ = ["router"]
