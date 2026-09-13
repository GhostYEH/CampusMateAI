"""CampusAgentRuntime API 路由(§9.1)。

所有写请求支持 Idempotency-Key。SSE 支持 Last-Event-ID 与 sequence。
鉴权使用 Bearer header(禁止 token query)。
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import PlainTextResponse, StreamingResponse

from ...core.exceptions import AgentRuntimeError, AgentRunNotFound, ValidationFailed
from ...models.multi_role import UserRow
from ...repositories.agent_artifact_repository import AgentArtifactRepository
from ...repositories.agent_runtime_repository import AgentRuntimeRepository
from ...schemas.agent_contract_enums import (
    AGENT_CONTRACT_VERSION,
    ApprovalStatus,
    RiskLevel,
)
from ...schemas.agent_runtime import (
    AgentApprovalDecisionIn,
    AgentApprovalOut,
    AgentArtifactOut,
    AgentCapabilitiesOut,
    AgentCapabilityOut,
    AgentErrorEnvelope,
    AgentEventOut,
    AgentJobCreateIn,
    AgentJobOut,
    AgentMemoryCreateIn,
    AgentMemoryOut,
    AgentProgressOut,
    AgentRunCancelIn,
    AgentRunControlIn,
    AgentRunOut,
    NoticeManualIn,
)
from ..deps import current_user, student_only
from ..deps import ServiceContainer, get_container

router = APIRouter(prefix="/agent-runtime", tags=["agent-runtime"])
jobs_router = APIRouter(prefix="/agent-jobs", tags=["agent-runtime"])
runs_router = APIRouter(prefix="/agent-runs", tags=["agent-runtime"])
approvals_router = APIRouter(prefix="/agent-approvals", tags=["agent-runtime"])
artifacts_router = APIRouter(prefix="/agent-artifacts", tags=["agent-runtime"])
notices_manual_router = APIRouter(prefix="/notices", tags=["agent-runtime"])
memories_router = APIRouter(prefix="/agent-memories", tags=["agent-runtime"])


def _repo(container: ServiceContainer) -> AgentRuntimeRepository:
    return container.agent_runtime_repository


def _artifact_repo(container: ServiceContainer) -> AgentArtifactRepository:
    return container.agent_artifact_repository


def _memory_to_out(memory: dict) -> AgentMemoryOut:
    return AgentMemoryOut(
        memory_id=memory["memory_id"], user_id=memory["user_id"], kind=memory["kind"],
        content_summary=memory["content_summary"], sensitivity=memory["sensitivity"],
        confirmed=bool(memory["confirmed"]), withdrawn=bool(memory["withdrawn"]),
        model_may_consume=bool(memory["model_may_consume"]), created_at=memory["created_at"],
    )


def _capability_out(name: str, policy: str, risk: str, approval: bool) -> AgentCapabilityOut:
    return AgentCapabilityOut(
        name=name,
        version="1.0",
        route_policy=policy,
        risk_level=risk,
        requires_approval=approval,
    )


def _job_to_out(job: dict, *, latest_run_id: Optional[str] = None) -> AgentJobOut:
    return AgentJobOut(
        job_id=job["job_id"],
        user_id=job["user_id"],
        job_kind=job["job_kind"],
        status=job["status"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        latest_run_id=latest_run_id,
    )


# ===== capabilities =====


@router.get("/capabilities")
async def get_capabilities(
    user: UserRow = Depends(current_user),
) -> AgentCapabilitiesOut:
    """返回 runtime 能力清单 + 契约版本。"""
    return AgentCapabilitiesOut(
        contract_version=AGENT_CONTRACT_VERSION,
        capabilities=[
            _capability_out("final_review.plan", "reasoning_primary", "CONFIRM_REQUIRED", True),
            _capability_out("final_review.adjust", "reasoning_primary", "CONFIRM_REQUIRED", True),
            _capability_out("course_research.run", "reasoning_primary", "AUTO_SAFE", False),
            _capability_out("notice.workflow", "fast_structured", "AUTO_SAFE", False),
            _capability_out("citation.verify", "dual_review", "AUTO_SAFE", False),
        ],
    )


# ===== jobs =====


@jobs_router.post("")
async def create_job(
    body: AgentJobCreateIn,
    request: Request,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> AgentJobOut:
    repo = _repo(container)
    # 幂等:相同 idempotency_key 返回已有 job
    effective_key = body.idempotency_key or idempotency_key
    if effective_key:
        existing = repo.find_job_by_idempotency(user.id, effective_key)
        if existing:
            return _job_to_out(existing)
    job_id = repo.create_job(
        user_id=user.id,
        job_kind=body.job_kind,
        input_ref=body.input_ref,
        idempotency_key=effective_key,
    )
    job = repo.get_job(job_id)
    return _job_to_out(job)


@jobs_router.get("")
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
) -> list[AgentJobOut]:
    repo = _repo(container)
    result: list[AgentJobOut] = []
    for job in repo.list_jobs(user.id, page=page, page_size=page_size):
        latest = repo.get_run_by_job(job["job_id"])
        result.append(_job_to_out(job, latest_run_id=latest["run_id"] if latest else None))
    return result


@jobs_router.get("/{job_id}/runs")
async def list_job_runs(
    job_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> list[AgentRunOut]:
    repo = _repo(container)
    job = repo.get_job(job_id)
    if not job or (job["user_id"] != user.id and user.role != "admin"):
        raise AgentRunNotFound("Job 不存在")
    return [_run_to_out(run, container) for run in repo.list_runs_by_job(job_id)]


@jobs_router.get("/{job_id}")
async def get_job(
    job_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> AgentJobOut:
    repo = _repo(container)
    job = repo.get_job(job_id)
    if not job:
        raise AgentRunNotFound("Job 不存在")
    if job["user_id"] != user.id and user.role != "admin":
        raise AgentRunNotFound("Job 不存在")
    latest = repo.get_run_by_job(job_id)
    return _job_to_out(job, latest_run_id=latest["run_id"] if latest else None)


# ===== runs =====


def _run_to_out(run: dict, container: ServiceContainer) -> AgentRunOut:
    artifacts = _artifact_repo(container).list_artifacts_by_run(run["run_id"], run["user_id"])
    return AgentRunOut(
        run_id=run["run_id"], job_id=run["job_id"], user_id=run["user_id"],
        status=run["status"], phase=run["phase"], risk_level=run.get("risk_level"),
        started_at=run.get("started_at"), finished_at=run.get("finished_at"),
        created_at=run["created_at"], updated_at=run["updated_at"],
        artifact_ids=[a["artifact_id"] for a in artifacts], retry_of=run.get("retry_of"),
    )


# ===== explicit memory =====


@memories_router.get("", response_model=list[AgentMemoryOut])
async def list_memories(
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
) -> list[AgentMemoryOut]:
    return [_memory_to_out(memory) for memory in container.agent_memory_manager.list_for_user(user.id)]


@memories_router.post("", response_model=AgentMemoryOut)
async def create_memory(
    body: AgentMemoryCreateIn,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
) -> AgentMemoryOut:
    try:
        memory_id = container.agent_memory_manager.record(
            user_id=user.id, kind=body.kind, content_summary=body.content_summary,
            sensitivity=body.sensitivity, confirmed=body.confirmed,
            model_may_consume=body.model_may_consume, provenance=body.provenance,
            valid_until=body.valid_until,
        )
    except ValueError as exc:
        raise ValidationFailed(str(exc)) from exc
    memory = container.agent_runtime_repository.get_memory(memory_id, user.id)
    return _memory_to_out(memory)


@memories_router.post("/{memory_id}/withdraw", response_model=AgentMemoryOut)
async def withdraw_memory(
    memory_id: str,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
) -> AgentMemoryOut:
    memory = container.agent_memory_manager.withdraw(user_id=user.id, memory_id=memory_id)
    if memory is None:
        raise AgentRunNotFound("Memory 不存在")
    return _memory_to_out(memory)


@runs_router.get("")
async def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
) -> list[AgentRunOut]:
    return [_run_to_out(run, container) for run in _repo(container).list_runs_for_user(user.id, page=page, page_size=page_size)]


@runs_router.get("/{run_id}")
async def get_run(
    run_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> AgentRunOut:
    repo = _repo(container)
    run = repo.get_run(run_id)
    if not run:
        raise AgentRunNotFound("Run 不存在")
    if run["user_id"] != user.id and user.role != "admin":
        raise AgentRunNotFound("Run 不存在")
    return _run_to_out(run, container)


@runs_router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    body: AgentRunCancelIn,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> AgentRunOut:
    repo = _repo(container)
    run = repo.get_run(run_id)
    if not run:
        raise AgentRunNotFound("Run 不存在")
    if run["user_id"] != user.id:
        raise AgentRuntimeError("无权取消", code="AGENT_PERMISSION_DENIED", http_status=403)
    from ...services.agent_runtime.run_manager import RunManager

    manager = RunManager(repo)
    result = manager.cancel(run_id, reason=body.reason)
    return await get_run(run_id, user, container)


async def _control_run(
    run_id: str,
    *,
    action: str,
    body: AgentRunControlIn,
    idempotency_key: Optional[str],
    user: UserRow,
    container: ServiceContainer,
) -> AgentRunOut:
    repo = _repo(container)
    run = repo.get_run(run_id)
    if not run:
        raise AgentRunNotFound("Run 不存在")
    if run["user_id"] != user.id:
        raise AgentRuntimeError("无权控制此运行", code="AGENT_PERMISSION_DENIED", http_status=403)
    key = body.idempotency_key or idempotency_key or f"{action}:{run_id}"
    existing = repo.find_control(run_id, key)
    if existing:
        return await get_run(run_id, user, container)
    from ...services.agent_runtime.run_manager import RunManager
    manager = RunManager(repo, container.agent_event_store)
    if action == "pause":
        result = manager.pause(run_id, reason=body.reason)
    elif action == "resume":
        result = manager.resume(run_id)
    else:
        result = manager.retry(run_id, idempotency_key=key)
    repo.record_control(
        run_id=run_id, user_id=user.id, action=action,
        idempotency_key=key, resulting_status=result["status"],
    )
    if action == "retry":
        return _run_to_out(result, container)
    return await get_run(run_id, user, container)


@runs_router.post("/{run_id}/pause")
async def pause_run(
    run_id: str,
    body: AgentRunControlIn,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> AgentRunOut:
    return await _control_run(run_id, action="pause", body=body, idempotency_key=idempotency_key, user=user, container=container)


@runs_router.post("/{run_id}/resume")
async def resume_run(
    run_id: str,
    body: AgentRunControlIn,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> AgentRunOut:
    return await _control_run(run_id, action="resume", body=body, idempotency_key=idempotency_key, user=user, container=container)


@runs_router.post("/{run_id}/retry")
async def retry_run(
    run_id: str,
    body: AgentRunControlIn,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> AgentRunOut:
    return await _control_run(run_id, action="retry", body=body, idempotency_key=idempotency_key, user=user, container=container)


# ===== events =====


def _event_to_out(evt: dict) -> AgentEventOut:
    progress = None
    if evt.get("progress_json"):
        p = json.loads(evt["progress_json"])
        progress = AgentProgressOut(**p)
    return AgentEventOut(
        id=evt["event_id"],
        type=evt["type"],
        run_id=evt["run_id"],
        sequence=evt["sequence"],
        status=evt["status"],
        phase=evt["phase"],
        role=evt.get("role"),
        summary=evt.get("summary"),
        progress=progress,
        artifact_id=evt.get("artifact_id"),
        approval_id=evt.get("approval_id"),
        created_at=evt["created_at"],
    )


@runs_router.get("/{run_id}/events")
async def list_events(
    run_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
    after_sequence: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[AgentEventOut]:
    repo = _repo(container)
    run = repo.get_run(run_id)
    if not run:
        raise AgentRunNotFound("Run 不存在")
    if run["user_id"] != user.id and user.role != "admin":
        raise AgentRunNotFound("Run 不存在")
    events = repo.list_events(run_id, after_sequence=after_sequence, limit=limit)
    return [_event_to_out(e) for e in events]


@runs_router.get("/{run_id}/events/stream")
async def stream_events(
    run_id: str,
    request: Request,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
) -> StreamingResponse:
    """SSE 流。支持 Last-Event-ID 续传。断开不取消 run。"""
    repo = _repo(container)
    run = repo.get_run(run_id)
    if not run:
        raise AgentRunNotFound("Run 不存在")
    if run["user_id"] != user.id and user.role != "admin":
        raise AgentRunNotFound("Run 不存在")
    # 解析 Last-Event-ID 中的 sequence
    after_sequence = 0
    if last_event_id:
        try:
            # event_id 格式: evt_xxx,sequence 存在 db
            events = repo.list_events(run_id, limit=1)
            # 简单实现:从 Last-Event-ID 对应的 sequence 之后开始
            all_events = repo.list_events(run_id, limit=10000)
            for e in all_events:
                if e["event_id"] == last_event_id:
                    after_sequence = e["sequence"]
                    break
        except Exception:
            pass

    async def event_generator():
        import asyncio

        current_seq = after_sequence
        idle_count = 0
        while True:
            if await request.is_disconnected():
                break
            events = repo.list_events(run_id, after_sequence=current_seq, limit=50)
            if events:
                idle_count = 0
                for evt in events:
                    out = _event_to_out(evt)
                    payload = out.model_dump_json()
                    yield f"id: {evt['event_id']}\nevent: {evt['type']}\ndata: {payload}\n\n"
                    current_seq = evt["sequence"]
            else:
                idle_count += 1
                # 检查 run 是否已终态
                current_run = repo.get_run(run_id)
                if current_run and current_run["status"] in (
                    "SUCCEEDED",
                    "PARTIAL",
                    "FAILED",
                    "CANCELLED",
                ):
                    break
                if idle_count > 60:  # 最多空闲 60 次
                    break
            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ===== approvals =====


@approvals_router.post("/{approval_id}/decision")
async def resolve_approval(
    approval_id: str,
    body: AgentApprovalDecisionIn,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> AgentApprovalOut:
    repo = _repo(container)
    from ...services.agent_runtime.approval_gate import ApprovalGate

    gate = ApprovalGate(repo)
    result = gate.resolve(
        approval_id, decision=body.decision, reason=body.reason, user_id=user.id
    )
    apv = repo.get_approval(approval_id)
    if body.decision == "REJECTED":
        run = repo.get_run(apv.run_id)
        if run and run["status"] == "AWAITING_APPROVAL":
            container.agent_run_manager.cancel(
                apv.run_id, reason=body.reason or "用户拒绝审批"
            )
    return AgentApprovalOut(
        approval_id=apv.approval_id,
        run_id=apv.run_id,
        status=apv.status,
        risk_level=apv.risk_level,
        action_summary=apv.action_summary,
        expires_at=apv.expires_at,
        resolved_at=apv.resolved_at,
        decision_reason=apv.decision_reason,
    )


# ===== artifacts =====


@artifacts_router.get("/{artifact_id}/content")
async def get_artifact_content(
    artifact_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
):
    """返回 artifact 文本内容(Markdown / JSON)。"""
    repo = _artifact_repo(container)
    meta = repo.get_artifact(artifact_id, user.id)
    if not meta:
        raise AgentRunNotFound("Artifact 不存在")
    content = repo.read_content(artifact_id, user.id)
    if content is None:
        raise AgentRunNotFound("Artifact 内容不可读")
    return PlainTextResponse(content, media_type=meta.get("mime_type") or "text/plain")


@artifacts_router.get("/{artifact_id}")
async def get_artifact(
    artifact_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> AgentArtifactOut:
    repo = _artifact_repo(container)
    meta = repo.get_artifact(artifact_id, user.id)
    if not meta:
        raise AgentRunNotFound("Artifact 不存在")
    return AgentArtifactOut(**{
        name: meta.get(name) for name in AgentArtifactOut.model_fields
    })


# ===== notices manual =====


@notices_manual_router.post("/manual")
async def create_manual_notice(
    body: NoticeManualIn,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> dict:
    """手动提交通知文本,创建 notice_workflow job。"""
    repo = _repo(container)
    effective_key = body.idempotency_key or idempotency_key
    if effective_key:
        existing = repo.find_job_by_idempotency(user.id, effective_key)
        if existing:
            return {"job_id": existing["job_id"], "status": existing["status"]}
    job_id = repo.create_job(
        user_id=user.id,
        job_kind="notice_workflow",
        input_ref={"title": body.title, "source_name": body.source_name},
        idempotency_key=effective_key,
    )
    return {"job_id": job_id, "status": "QUEUED"}


__all__ = [
    "router",
    "jobs_router",
    "runs_router",
    "approvals_router",
    "artifacts_router",
    "memories_router",
    "notices_manual_router",
]
