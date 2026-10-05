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

from typing import Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Header, Query, Request

from ...core.exceptions import AgentIdempotencyConflict, AgentRuntimeError, AgentRunNotFound
from ...core.logging import logger
from starlette.concurrency import run_in_threadpool
from ...repositories.agent_runtime_repository import build_request_hash
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
from ...services.agent_runtime.run_manager import RunManager
from ...services.course_research.citation_verifier import CitationVerifier
from ...services.course_research.pipeline import CourseResearchPipeline
from ...services.course_research.policy import SourcePolicy, build_effective_policy
from ...services.course_research.source_fetcher import ControlledSourceFetcher
from ..deps import ServiceContainer, current_user, get_container, student_only

router = APIRouter(prefix="/course-research", tags=["课程研究"])


def _repo(container: ServiceContainer) -> CourseResearchRepository:
    return container.course_research_repository


def _runtime_repo(container: ServiceContainer) -> AgentRuntimeRepository:
    return container.agent_runtime_repository


def _build_pipeline(container: ServiceContainer) -> CourseResearchPipeline:
    return container.course_research_pipeline


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
    except Exception as exc:
        logger.warning("course_research_pipeline_failed error_type={}", type(exc).__name__)
        await run_in_threadpool(_repo(container).update_session,
            session_id,
            status=RunStatus.FAILED.value,
            error_code="AGENT_PIPELINE_FAILED",
        )
        try:
            await run_in_threadpool(container.agent_run_manager.transition,
                run_id, RunStatus.FAILED.value, phase="IDLE"
            )
            await run_in_threadpool(container.agent_event_store.append,
                run_id=run_id,
                type="RUN_FAILED",
                status=RunStatus.FAILED.value,
                phase="IDLE",
                role="coordinator",
                summary="课程研究执行失败",
            )
        except Exception as exc:
            logger.warning("course_research_failure_finalize_failed error_type={}", type(exc).__name__)


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


@router.post(
    "/runs",
    response_model=CourseResearchRunOut,
    summary="创建课程研究",
    responses={
        200: {
            "description": "已创建 Run 并受理研究流水线；首次返回 QUEUED 与空 artifact_ids",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "创建课程研究 Run",
                            "value": {
                                "run_id": "run_2026w40_0001",
                                "session_id": "sess_cr_0001",
                                "user_id": "u_demo",
                                "course_id": "course_db_2025",
                                "question": "关系数据库的范式与反范式如何取舍？",
                                "assistance_mode": "EXPLAIN",
                                "academic_policy": "UNKNOWN",
                                "effective_assistance_mode": "EXPLAIN",
                                "source_policy": {
                                    "course_material_priority": True,
                                    "allow_web": True,
                                    "allow_user_upload": True,
                                },
                                "status": "QUEUED",
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "updated_at": "2026-10-06T08:00:00+00:00",
                                "finished_at": None,
                                "error_code": None,
                                "artifact_ids": [],
                                "fallback_used": False,
                            },
                        }
                    }
                }
            },
        }
    },
)
def create_run(
    body: Annotated[
        CourseResearchRunCreateIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "创建课程研究请求",
                    "value": {
                        "course_id": "course_db_2025",
                        "question": "关系数据库的范式与反范式如何取舍？",
                        "assistance_mode": "EXPLAIN",
                        "academic_policy": "UNKNOWN",
                        "source_policy": {
                            "course_material_priority": True,
                            "allow_web": True,
                            "allow_user_upload": True,
                        },
                    },
                }
            }
        ),
    ],
    request: Request,
    background_tasks: BackgroundTasks,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> CourseResearchRunOut:
    """创建课程研究 Run；响应后执行研究流水线。

    - 首次创建返回 QUEUED 与空 artifact_ids，客户端可用 run_id 订阅 SSE 或轮询。
    - 相同幂等键重放返回已持久化的当前状态；同键不同请求体返回 409（AGENT_IDEMPOTENCY_CONFLICT）。
    """
    repo = _repo(container)
    runtime_repo = _runtime_repo(container)
    effective_key = body.idempotency_key or idempotency_key
    fingerprint = build_request_hash("course_research", body.model_dump(mode="json", exclude={"idempotency_key"}))
    # 幂等
    if effective_key:
        existing = repo.find_session_by_idempotency(user.id, effective_key)
        if existing:
            import json
            job = runtime_repo.get_job(existing.job_id) if existing.job_id else None
            prior = json.loads(job["input_ref_json"] or "{}") if job else {}
            if (
                (prior.get("request_hash") is not None and prior["request_hash"] != fingerprint)
                or existing.question != body.question
                or existing.course_id != body.course_id
                or existing.assistance_mode != body.assistance_mode.value
                or existing.academic_policy != body.academic_policy.value
                or json.loads(existing.source_policy_json) != body.source_policy.model_dump(mode="json")
            ):
                raise AgentIdempotencyConflict()
            artifacts = container.agent_artifact_manager.list_by_run(
                existing.run_id, user.id
            )
            return _session_to_out(
                existing,
                artifact_ids=[a["artifact_id"] for a in artifacts],
            )
    # 创建 job + run
    input_ref = {"question": body.question, "course_id": body.course_id, "request_hash": fingerprint}
    created = runtime_repo.create_job_with_run_and_event(
        user_id=user.id,
        job_kind="course_research",
        input_ref=input_ref,
        idempotency_key=effective_key,
        request_hash=fingerprint,
        request_id=getattr(request.state, "request_id", None),
    )
    if created["replayed"]:
        raise AgentRuntimeError("幂等请求仍在处理中", code="AGENT_INVALID_STATE", http_status=409)
    job_id, run_id = created["job_id"], created["run_id"]
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


@router.get(
    "/runs",
    summary="列出课程研究",
    responses={
        200: {
            "description": "返回当前用户的课程研究 Run 列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "列出课程研究 Run",
                            "value": [
                                {
                                    "run_id": "run_2026w40_0001",
                                    "session_id": "sess_cr_0001",
                                    "user_id": "u_demo",
                                    "course_id": "course_db_2025",
                                    "question": "关系数据库的范式与反范式如何取舍？",
                                    "assistance_mode": "EXPLAIN",
                                    "academic_policy": "UNKNOWN",
                                    "effective_assistance_mode": "EXPLAIN",
                                    "source_policy": {
                                        "course_material_priority": True,
                                        "allow_web": True,
                                        "allow_user_upload": True,
                                    },
                                    "status": "SUCCEEDED",
                                    "created_at": "2026-10-06T08:00:00+00:00",
                                    "updated_at": "2026-10-06T08:05:00+00:00",
                                    "finished_at": "2026-10-06T08:05:00+00:00",
                                    "error_code": None,
                                    "artifact_ids": ["art_cr_0001"],
                                    "fallback_used": False,
                                }
                            ],
                        }
                    }
                }
            },
        }
    },
)
def list_runs(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[CourseResearchRunOut]:
    """列出当前用户的课程研究 Run。

    - limit 取值 1–200，offset 从 0 开始；始终只返回本人数据。
    """
    repo = _repo(container)
    sessions = repo.list_sessions_by_user(user.id, limit=limit, offset=offset)
    out: list[CourseResearchRunOut] = []
    for s in sessions:
        artifacts = container.agent_artifact_manager.list_by_run(s.run_id, user.id)
        out.append(_session_to_out(
            s, artifact_ids=[a["artifact_id"] for a in artifacts],
        ))
    return out


@router.get(
    "/runs/{run_id}",
    summary="读取课程研究",
    responses={
        200: {
            "description": "返回指定课程研究 Run 的概览",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "读取课程研究 Run",
                            "value": {
                                "run_id": "run_2026w40_0001",
                                "session_id": "sess_cr_0001",
                                "user_id": "u_demo",
                                "course_id": "course_db_2025",
                                "question": "关系数据库的范式与反范式如何取舍？",
                                "assistance_mode": "EXPLAIN",
                                "academic_policy": "UNKNOWN",
                                "effective_assistance_mode": "EXPLAIN",
                                "source_policy": {
                                    "course_material_priority": True,
                                    "allow_web": True,
                                    "allow_user_upload": True,
                                },
                                "status": "SUCCEEDED",
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "updated_at": "2026-10-06T08:05:00+00:00",
                                "finished_at": "2026-10-06T08:05:00+00:00",
                                "error_code": None,
                                "artifact_ids": ["art_cr_0001"],
                                "fallback_used": False,
                            },
                        }
                    }
                }
            },
        }
    },
)
def get_run(
    run_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> CourseResearchRunOut:
    """获取单个课程研究 Run。

    - Run 不存在或不属于当前用户时返回 404（AGENT_RUN_NOT_FOUND）。
    """
    repo = _repo(container)
    session = repo.get_session_by_run(run_id)
    if not session:
        raise AgentRunNotFound("Run 不存在")
    if session.user_id != user.id:
        raise AgentRunNotFound("Run 不存在")
    artifacts = container.agent_artifact_manager.list_by_run(run_id, user.id)
    return _session_to_out(
        session, artifact_ids=[a["artifact_id"] for a in artifacts],
    )


@router.post(
    "/runs/{run_id}/cancel",
    summary="取消课程研究",
    responses={
        200: {
            "description": "取消成功，返回状态为 CANCELLED 的 Run",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "取消课程研究 Run",
                            "value": {
                                "run_id": "run_2026w40_0001",
                                "session_id": "sess_cr_0001",
                                "user_id": "u_demo",
                                "course_id": "course_db_2025",
                                "question": "关系数据库的范式与反范式如何取舍？",
                                "assistance_mode": "EXPLAIN",
                                "academic_policy": "UNKNOWN",
                                "effective_assistance_mode": "EXPLAIN",
                                "source_policy": {
                                    "course_material_priority": True,
                                    "allow_web": True,
                                    "allow_user_upload": True,
                                },
                                "status": "CANCELLED",
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "updated_at": "2026-10-06T08:02:00+00:00",
                                "finished_at": None,
                                "error_code": None,
                                "artifact_ids": [],
                                "fallback_used": False,
                            },
                        }
                    }
                }
            },
        }
    },
)
def cancel_run(
    run_id: str,
    body: Annotated[
        CourseResearchRunCancelIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "取消并说明原因",
                    "value": {"reason": "问题已解决，无需继续研究"},
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> CourseResearchRunOut:
    """取消课程研究 Run。

    - Run 不存在返回 404（AGENT_RUN_NOT_FOUND）；无权取消返回 403（AGENT_PERMISSION_DENIED）。
    """
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
    return get_run(run_id, user, container)


@router.get(
    "/runs/{run_id}/artifacts",
    summary="列出研究产物",
    responses={
        200: {
            "description": "返回 Run 的产物与来源清单",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "列出研究产物与来源",
                            "value": {
                                "run_id": "run_2026w40_0001",
                                "artifacts": [
                                    {
                                        "artifact_id": "art_cr_0001",
                                        "run_id": "run_2026w40_0001",
                                        "user_id": "u_demo",
                                        "artifact_type": "COURSE_RESEARCH_REPORT",
                                        "version": 1,
                                        "mime_type": "text/markdown",
                                        "size_bytes": 4096,
                                        "content_hash": "9f2c1a7b4d",
                                        "download_url": None,
                                        "created_at": "2026-10-06T08:05:00+00:00",
                                    }
                                ],
                                "sources": [
                                    {
                                        "source_id": "src_0001",
                                        "source_type": "course_material",
                                        "title": "第 3 章 关系数据库设计.pdf",
                                        "url": None,
                                        "snippet": "第三范式要求消除非主属性对码的传递依赖。",
                                        "accessed_at": "2026-10-06T08:04:00+00:00",
                                        "is_verified": True,
                                        "is_fabricated": False,
                                    }
                                ],
                            },
                        }
                    }
                }
            },
        }
    },
)
def list_artifacts(
    run_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> CourseResearchArtifactListOut:
    """列出 Run 的产物与来源。

    - Run 不存在或不属于当前用户时返回 404（AGENT_RUN_NOT_FOUND）。
    """
    repo = _repo(container)
    session = repo.get_session_by_run(run_id)
    if not session:
        raise AgentRunNotFound("Run 不存在")
    if session.user_id != user.id:
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
