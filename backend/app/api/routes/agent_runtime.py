from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import Response, StreamingResponse

from ...core.exceptions import AppException
from ...models.agent_runtime import AgentEventRow, AgentRunRow
from ...models.multi_role import UserRow
from ...schemas.agent_runtime import (
    AgentApprovalDecision, AgentApprovalOut, AgentArtifactOut, AgentEventOut,
    AgentEventPage, AgentJobCreate, AgentJobOut, AgentProgressOut, AgentRunOut,
)
from ...services.container import ServiceContainer, get_container
from ..deps import require_role


router = APIRouter(tags=["agent-runtime"])


def _container() -> ServiceContainer:
    return get_container()


def _run_out(run: AgentRunRow) -> AgentRunOut:
    total = max(run.progress_total, 0)
    percent = min(100, int(run.progress_current * 100 / total)) if total else 0
    return AgentRunOut(
        run_id=run.id, job_id=run.job_id, domain=run.domain, status=run.status,
        phase=run.phase, current_role=run.current_role,
        progress=AgentProgressOut(current=run.progress_current, total=total, percent=percent),
        context_snapshot_id=run.context_snapshot_id, created_at=run.created_at,
        updated_at=run.updated_at, finished_at=run.finished_at,
    )


def _event_out(event: AgentEventRow) -> AgentEventOut:
    total = max(event.progress_total, 0)
    percent = min(100, int(event.progress_current * 100 / total)) if total else 0
    return AgentEventOut(
        id=event.id, type=event.type, run_id=event.run_id, sequence=event.sequence,
        status=event.status, phase=event.phase, role=event.role, summary=event.summary,
        progress=AgentProgressOut(current=event.progress_current, total=total, percent=percent),
        artifact_id=event.artifact_id, approval_id=event.approval_id, created_at=event.created_at,
    )


def _owned_run(container: ServiceContainer, run_id: str, user_id: str) -> AgentRunRow:
    run = container.agent_runtime_repository.get_run(run_id=run_id, user_id=user_id)
    if run is None:
        raise AppException(code="AGENT_RUN_NOT_FOUND", http_status=404, message="运行不存在")
    return run


@router.get("/agent-runtime/capabilities")
def capabilities(user: UserRow = Depends(require_role("student"))) -> dict:
    return {
        "runtime_version": "1.0",
        "domains": ["final_review", "course_research", "notice_workflow"],
        "supports_sse_resume": True,
        "supports_approvals": True,
    }


@router.post("/agent-jobs", response_model=AgentJobOut)
def create_job(
    payload: AgentJobCreate,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> AgentJobOut:
    job, run, reused = container.agent_runtime_repository.create_job_idempotent(
        user_id=user.id, domain=payload.domain, objective_summary=payload.objective_summary,
        total_steps=payload.total_steps, idempotency_key=idempotency_key,
    )
    if not reused:
        container.agent_event_store.append(run_id=run.id, event_type="RUN_QUEUED", summary="任务已进入队列")
    return AgentJobOut(
        job_id=job.id, domain=job.domain, objective_summary=job.objective_summary,
        status=job.status, run=_run_out(run),
    )


@router.get("/agent-jobs/{job_id}", response_model=AgentJobOut)
def get_job(job_id: str, user: UserRow = Depends(require_role("student")),
            container: ServiceContainer = Depends(_container)) -> AgentJobOut:
    job = container.agent_runtime_repository.get_job(job_id=job_id, user_id=user.id)
    run = container.agent_runtime_repository.latest_run_for_job(job_id=job_id, user_id=user.id)
    if job is None or run is None:
        raise AppException(code="AGENT_RUN_NOT_FOUND", http_status=404, message="任务不存在")
    return AgentJobOut(job_id=job.id, domain=job.domain, objective_summary=job.objective_summary,
                       status=job.status, run=_run_out(run))


@router.get("/agent-runs/{run_id}", response_model=AgentRunOut)
def get_run(run_id: str, user: UserRow = Depends(require_role("student")),
            container: ServiceContainer = Depends(_container)) -> AgentRunOut:
    return _run_out(_owned_run(container, run_id, user.id))


@router.post("/agent-runs/{run_id}/cancel", response_model=AgentRunOut)
def cancel_run(run_id: str, user: UserRow = Depends(require_role("student")),
               container: ServiceContainer = Depends(_container)) -> AgentRunOut:
    run = _owned_run(container, run_id, user.id)
    if run.status in {"SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"}:
        if run.status == "CANCELLED":
            return _run_out(run)
        raise AppException(code="AGENT_INVALID_STATE", http_status=409, message="运行已结束")
    updated = container.agent_runtime_repository.update_run(run_id=run.id, status="CANCELLED", phase="IDLE")
    container.agent_event_store.append(run_id=run.id, event_type="RUN_CANCELLED", summary="运行已取消")
    return _run_out(updated)


@router.get("/agent-runs/{run_id}/events", response_model=AgentEventPage)
def get_events(run_id: str, after_event_id: str | None = None, limit: int = Query(200, ge=1, le=500),
               user: UserRow = Depends(require_role("student")),
               container: ServiceContainer = Depends(_container)) -> AgentEventPage:
    _owned_run(container, run_id, user.id)
    rows = container.agent_event_store.replay(run_id=run_id, last_event_id=after_event_id)
    rows = rows[:limit]
    return AgentEventPage(items=[_event_out(row) for row in rows], total=len(rows), has_more=False)


@router.get("/agent-runs/{run_id}/events/stream")
async def stream_events(request: Request, run_id: str,
                        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
                        user: UserRow = Depends(require_role("student")),
                        container: ServiceContainer = Depends(_container)) -> StreamingResponse:
    _owned_run(container, run_id, user.id)

    async def generate():
        cursor = last_event_id
        heartbeat = 0
        while not await request.is_disconnected():
            events = container.agent_event_store.replay(run_id=run_id, last_event_id=cursor)
            for event in events:
                cursor = event.id
                payload = _event_out(event).model_dump_json()
                yield f"id: {event.id}\nevent: {event.type}\ndata: {payload}\n\n"
            heartbeat += 1
            if not events and heartbeat % 30 == 0:
                yield ": heartbeat\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.post("/agent-approvals/{approval_id}/decision", response_model=AgentApprovalOut)
def decide_approval(approval_id: str, payload: AgentApprovalDecision,
                    user: UserRow = Depends(require_role("student")),
                    container: ServiceContainer = Depends(_container)) -> AgentApprovalOut:
    row = container.agent_approval_gate.decide(
        approval_id=approval_id, user_id=user.id, decision=payload.decision,
        now=datetime.now(timezone.utc).replace(microsecond=0),
    )
    return AgentApprovalOut(
        approval_id=row.id, run_id=row.run_id, status=row.status, risk_level=row.risk_level,
        summary=row.summary, expires_at=row.expires_at, created_at=row.created_at,
    )


@router.get("/agent-artifacts/{artifact_id}", response_model=AgentArtifactOut)
def get_artifact(artifact_id: str, user: UserRow = Depends(require_role("student")),
                 container: ServiceContainer = Depends(_container)) -> AgentArtifactOut:
    row = container.agent_artifact_repository.get(artifact_id=artifact_id, user_id=user.id)
    if row is None:
        raise AppException(code="AGENT_PERMISSION_DENIED", http_status=404, message="Artifact 不存在")
    return AgentArtifactOut(
        artifact_id=row.id, run_id=row.run_id, artifact_type=row.artifact_type,
        version=row.version, mime_type=row.mime_type, size_bytes=row.size_bytes,
        content_hash=row.content_hash, created_at=row.created_at,
    )


@router.get("/agent-artifacts/{artifact_id}/content")
def get_artifact_content(artifact_id: str, user: UserRow = Depends(require_role("student")),
                         container: ServiceContainer = Depends(_container)) -> Response:
    row = container.agent_artifact_repository.get(artifact_id=artifact_id, user_id=user.id)
    if row is None:
        raise AppException(code="AGENT_PERMISSION_DENIED", http_status=404, message="Artifact 不存在")
    return Response(container.agent_artifact_manager.read(artifact_id=artifact_id, user_id=user.id), media_type=row.mime_type)
