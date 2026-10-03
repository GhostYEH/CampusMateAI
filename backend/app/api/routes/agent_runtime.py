"""CampusAgentRuntime API 路由(§9.1)。

所有写请求支持 Idempotency-Key。SSE 支持 Last-Event-ID 与 sequence。
鉴权使用 Bearer header(禁止 token query)。
"""
from __future__ import annotations

import json
from functools import partial
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import PlainTextResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from ...core.exceptions import (
    AgentCursorInvalid,
    AgentRuntimeError,
    AgentRunNotFound,
    ValidationFailed,
)
from ...models.multi_role import UserRow
from ...repositories.agent_artifact_repository import AgentArtifactRepository
from ...repositories.agent_runtime_repository import AgentRuntimeRepository
from ...repositories.agent_runtime_repository import build_request_hash
from ...schemas.agent_contract_enums import (
    AGENT_CONTRACT_VERSION,
    AgentErrorCode,
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
    AgentSkillsOut,
    AgentSkillOut,
)
from ..deps import current_user, student_only
from ..deps import ServiceContainer, get_container

router = APIRouter(prefix="/agent-runtime", tags=["agent-runtime"])
jobs_router = APIRouter(prefix="/agent-jobs", tags=["agent-runtime"])
runs_router = APIRouter(prefix="/agent-runs", tags=["agent-runtime"])
approvals_router = APIRouter(prefix="/agent-approvals", tags=["agent-runtime"])
artifacts_router = APIRouter(prefix="/agent-artifacts", tags=["agent-runtime"])
memories_router = APIRouter(prefix="/agent-memories", tags=["agent-runtime"])

# SSE 注释心跳间隔:只用于维持连接,不写库、不推进事件序列。
_SSE_HEARTBEAT_SECONDS = 15.0


def _repo(container: ServiceContainer) -> AgentRuntimeRepository:
    return container.agent_runtime_repository


def _artifact_repo(container: ServiceContainer) -> AgentArtifactRepository:
    return container.agent_artifact_repository


async def _offload(func, /, *args, **kwargs):
    """Run one bounded synchronous repository/file operation off the event loop."""
    return await run_in_threadpool(partial(func, *args, **kwargs))


def _memory_to_out(memory: dict) -> AgentMemoryOut:
    return AgentMemoryOut(
        memory_id=memory["memory_id"], user_id=memory["user_id"], kind=memory["kind"],
        content_summary=memory["content_summary"], sensitivity=memory["sensitivity"],
        confirmed=bool(memory["confirmed"]), withdrawn=bool(memory["withdrawn"]),
        model_may_consume=bool(memory["model_may_consume"]), created_at=memory["created_at"],
    )


def _job_to_out(
    job: dict,
    *,
    latest_run_id: Optional[str] = None,
    pending_approval_id: Optional[str] = None,
) -> AgentJobOut:
    input_ref = job.get("input_ref", job.get("input_ref_json", {}))
    if isinstance(input_ref, str):
        try:
            input_ref = json.loads(input_ref)
        except (TypeError, ValueError):
            input_ref = {}
    return AgentJobOut(
        job_id=job["job_id"],
        user_id=job["user_id"],
        job_kind=job["job_kind"],
        status=job["status"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        latest_run_id=latest_run_id,
        pending_approval_id=pending_approval_id,
        input_ref=input_ref if isinstance(input_ref, dict) else {},
    )


def _job_input_ref(job: dict) -> dict:
    """Decode the server-owned job input reference without exposing raw payloads."""
    value = job.get("input_ref", job.get("input_ref_json", {}))
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            value = {}
    return value if isinstance(value, dict) else {}


# ===== capabilities =====


@router.get("/capabilities")
async def get_capabilities(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> AgentCapabilitiesOut:
    """返回 runtime 能力清单 + 契约版本。

    清单由启动时冻结的 `CapabilityRegistry` 生成,不再在路由里硬编码;
    新增能力只能追加到 `capabilities.default.json`,已发布语义由启动校验钉死。
    """
    return AgentCapabilitiesOut(
        contract_version=AGENT_CONTRACT_VERSION,
        capabilities=[
            AgentCapabilityOut(**item)
            for item in container.agent_capability_registry.describe()
        ],
    )


# ===== jobs =====


def _pending_approval_id(repo, run_id: Optional[str], run: Optional[dict] = None) -> Optional[str]:
    """取该 Run 上待处理的审批单 id（仅 AWAITING_APPROVAL 时有意义）。"""
    if not run_id:
        return None
    run = run if run is not None else repo.get_run(run_id)
    if not run or run.get("status") != "AWAITING_APPROVAL":
        return None
    pending = [
        item
        for item in repo.list_approvals_by_run(run_id)
        if item.get("status") == "PENDING"
    ]
    return pending[-1]["approval_id"] if pending else None


def _job_page(repo, user_id: str, page: int, page_size: int) -> list[AgentJobOut]:
    result = []
    for job in repo.list_jobs(user_id, page=page, page_size=page_size):
        latest = repo.get_run_by_job(job["job_id"])
        result.append(_job_to_out(job, latest_run_id=latest["run_id"] if latest else None))
    return result


def _job_detail(repo, job_id: str) -> tuple[dict | None, Optional[str], Optional[str]]:
    job = repo.get_job(job_id)
    if not job:
        return None, None, None
    latest = repo.get_run_by_job(job_id)
    run_id = latest["run_id"] if latest else None
    return job, run_id, _pending_approval_id(repo, run_id)


def _run_page(repo, artifact_repo, runs: list[dict]) -> list[AgentRunOut]:
    result = []
    for run in runs:
        artifacts = artifact_repo.list_artifacts_by_run(run["run_id"], run["user_id"])
        result.append(_run_to_out(run, artifacts=artifacts))
    return result


def _load_run(repo, artifact_repo, run_id: str) -> tuple[dict | None, Optional[list[dict]]]:
    run = repo.get_run(run_id)
    if not run:
        return None, None
    artifacts = artifact_repo.list_artifacts_by_run(run["run_id"], run["user_id"])
    return run, artifacts


def _runs_for_user(repo, artifact_repo, user_id: str, page: int, page_size: int) -> list[AgentRunOut]:
    runs = repo.list_runs_for_user(user_id, page=page, page_size=page_size)
    return _run_page(repo, artifact_repo, runs)


def _run_to_out_from_repo(repo, artifact_repo, run: dict) -> AgentRunOut:
    artifacts = artifact_repo.list_artifacts_by_run(run["run_id"], run["user_id"])
    return _run_to_out(run, artifacts=artifacts)


def _poll_sse(repo, run_id: str, current_seq: int) -> tuple[list[dict], Optional[dict]]:
    events = repo.list_events(run_id, after_sequence=current_seq, limit=50)
    current_run = None if events else repo.get_run(run_id)
    return events, current_run


def _read_artifact_content(repo, artifact_id: str, user_id: str):
    metadata = repo.get_artifact(artifact_id, user_id)
    return (metadata, repo.read_content(artifact_id, user_id)) if metadata else (None, None)


def _resolve_approval_sync(repo, container, approval_id: str, body, user_id: str, key: str):
    from ...services.agent_runtime.approval_gate import ApprovalGate

    result = ApprovalGate(repo).resolve(
        approval_id, decision=body.decision, reason=body.reason, user_id=user_id
    )
    approval = repo.get_approval(approval_id)
    if not result.get("replayed"):
        repo.record_control(
            run_id=approval.run_id,
            user_id=user_id,
            action="approval_approve" if body.decision == "APPROVED" else "approval_reject",
            idempotency_key=key,
            resulting_status=approval.status,
        )
        run = repo.get_run(approval.run_id)
        if run and run["status"] == "AWAITING_APPROVAL":
            if body.decision == "REJECTED":
                container.agent_run_manager.cancel(
                    approval.run_id, reason=body.reason or "用户拒绝审批"
                )
            else:
                container.agent_run_manager.transition(
                    approval.run_id,
                    "QUEUED",
                    phase="QUEUED",
                    event_type="APPROVAL_GRANTED",
                    event_status="QUEUED",
                    event_phase="QUEUED",
                    event_role="runtime",
                    event_summary="审批已通过，运行重新排队执行",
                )
    return approval


@jobs_router.post("")
async def create_job(
    body: AgentJobCreateIn,
    request: Request,
    response: Response,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> AgentJobOut:
    repo = _repo(container)
    # Runtime 停止接单时必须明确返回 503，不能回退到请求内执行。
    if not container.agent_worker.accepts_new_jobs:
        raise AgentRuntimeError(
            "Agent 运行时当前不接受新任务",
            code="AGENT_RUNTIME_UNAVAILABLE", http_status=503,
        )

    handler = container.agent_handler_registry.require(body.job_kind)
    try:
        handler.input_model.model_validate(body.input_ref)
    except Exception as exc:
        raise ValidationFailed("Agent Job 输入未通过 Handler Schema 校验") from exc

    effective_key = body.idempotency_key or idempotency_key
    request_hash = build_request_hash(body.job_kind, body.input_ref)
    # 兼容原子幂等声明上线前创建的旧 Job，同时避免把不同请求误当重放。
    if effective_key:
        existing = await _offload(repo.find_job_by_idempotency, user.id, effective_key)
        if existing:
            if build_request_hash(existing["job_kind"], _job_input_ref(existing)) != request_hash:
                raise AgentRuntimeError(
                    "幂等键已用于不同的请求",
                    code="AGENT_IDEMPOTENCY_CONFLICT", http_status=409,
                )
            _, latest_run, pending_approval = await _offload(_job_detail, repo, existing["job_id"])
            response.status_code = 200
            return _job_to_out(
                existing,
                latest_run_id=latest_run,
                pending_approval_id=pending_approval,
            )

    created = await _offload(
        repo.create_job_with_run_and_event,
        user_id=user.id,
        job_kind=body.job_kind,
        input_ref=body.input_ref,
        idempotency_key=effective_key,
        request_hash=request_hash,
        handler_code=handler.code,
        handler_version=handler.version,
    )
    response.status_code = 200 if created["replayed"] else 202
    job = created["job"]
    return _job_to_out(
        job,
        latest_run_id=created["run_id"],
        pending_approval_id=await _offload(_pending_approval_id, repo, created["run_id"]),
    )


@jobs_router.get("")
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
) -> list[AgentJobOut]:
    repo = _repo(container)
    return await _offload(_job_page, repo, user.id, page, page_size)


@jobs_router.get("/{job_id}/runs")
async def list_job_runs(
    job_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> list[AgentRunOut]:
    repo = _repo(container)
    job, runs = await _offload(lambda: (repo.get_job(job_id), repo.list_runs_by_job(job_id)))
    if not job or (job["user_id"] != user.id and user.role != "admin"):
        raise AgentRunNotFound("Job 不存在")
    outputs = await _offload(_run_page, repo, _artifact_repo(container), runs)
    return outputs


@jobs_router.get("/{job_id}")
async def get_job(
    job_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> AgentJobOut:
    repo = _repo(container)
    job, latest_run_id, pending_approval_id = await _offload(_job_detail, repo, job_id)
    if not job:
        raise AgentRunNotFound("Job 不存在")
    if job["user_id"] != user.id and user.role != "admin":
        raise AgentRunNotFound("Job 不存在")
    return _job_to_out(
        job,
        latest_run_id=latest_run_id,
        pending_approval_id=pending_approval_id,
    )


# ===== runs =====


def _run_to_out(run: dict, artifacts: list[dict]) -> AgentRunOut:
    error = None
    if run.get("error_code"):
        allowed_codes = {item.value for item in AgentErrorCode}
        code = run["error_code"] if run["error_code"] in allowed_codes else AgentErrorCode.AGENT_INVALID_STATE.value
        error = AgentErrorEnvelope(
            code=code,
            message=(run.get("error_message") or "运行未能完成")[:256],
            request_id=run.get("request_id") or f"run:{run['run_id']}",
        )
    return AgentRunOut(
        run_id=run["run_id"], job_id=run["job_id"], user_id=run["user_id"],
        status=run["status"], phase=run["phase"], risk_level=run.get("risk_level"),
        started_at=run.get("started_at"), finished_at=run.get("finished_at"),
        created_at=run["created_at"], updated_at=run["updated_at"],
        error=error, artifact_ids=[a["artifact_id"] for a in artifacts], retry_of=run.get("retry_of"),
    )


@router.get("/skills", response_model=AgentSkillsOut)
async def get_skills(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> AgentSkillsOut:
    """返回可发现的 Skill/MCP 元数据；执行仍必须经过 Runtime 治理。"""
    return AgentSkillsOut(
        contract_version=AGENT_CONTRACT_VERSION,
        skills=[AgentSkillOut(
            skill_code=skill.skill_code, version=skill.version,
            description=skill.description, capabilities=list(skill.capabilities),
            tools=list(skill.tools), transport=skill.transport,
            permission_policy=skill.permission_policy,
        ) for skill in container.agent_skill_registry.list_skills()],
    )


# ===== explicit memory =====


@memories_router.get("", response_model=list[AgentMemoryOut])
async def list_memories(
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
) -> list[AgentMemoryOut]:
    memories = await _offload(container.agent_memory_manager.list_for_user, user.id)
    return [_memory_to_out(memory) for memory in memories]


@memories_router.post("", response_model=AgentMemoryOut)
async def create_memory(
    body: AgentMemoryCreateIn,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
) -> AgentMemoryOut:
    try:
        memory_id = await _offload(
            container.agent_memory_manager.record,
            user_id=user.id, kind=body.kind, content_summary=body.content_summary,
            sensitivity=body.sensitivity, confirmed=body.confirmed,
            model_may_consume=body.model_may_consume, provenance=body.provenance,
            valid_until=body.valid_until,
        )
    except ValueError as exc:
        raise ValidationFailed(str(exc)) from exc
    memory = await _offload(container.agent_runtime_repository.get_memory, memory_id, user.id)
    return _memory_to_out(memory)


@memories_router.post("/{memory_id}/withdraw", response_model=AgentMemoryOut)
async def withdraw_memory(
    memory_id: str,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
) -> AgentMemoryOut:
    memory = await _offload(
        container.agent_memory_manager.withdraw, user_id=user.id, memory_id=memory_id
    )
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
    return await _offload(
        _runs_for_user, _repo(container), _artifact_repo(container), user.id, page, page_size
    )


@runs_router.get("/{run_id}")
async def get_run(
    run_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> AgentRunOut:
    repo = _repo(container)
    run, artifacts = await _offload(_load_run, repo, _artifact_repo(container), run_id)
    if not run:
        raise AgentRunNotFound("Run 不存在")
    if run["user_id"] != user.id and user.role != "admin":
        raise AgentRunNotFound("Run 不存在")
    return _run_to_out(run, artifacts or [])


@runs_router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    body: AgentRunCancelIn,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> AgentRunOut:
    repo = _repo(container)
    run = await _offload(repo.get_run, run_id)
    if not run:
        raise AgentRunNotFound("Run 不存在")
    if run["user_id"] != user.id:
        raise AgentRuntimeError("无权取消", code="AGENT_PERMISSION_DENIED", http_status=403)
    from ...services.agent_runtime.run_manager import RunManager

    manager = RunManager(repo)
    await _offload(manager.cancel, run_id, reason=body.reason)
    refreshed, artifacts = await _offload(_load_run, repo, _artifact_repo(container), run_id)
    if refreshed is None:
        raise AgentRunNotFound("Run 不存在")
    return _run_to_out(refreshed, artifacts or [])


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
    run = await _offload(repo.get_run, run_id)
    if not run:
        raise AgentRunNotFound("Run 不存在")
    if run["user_id"] != user.id:
        raise AgentRuntimeError("无权控制此运行", code="AGENT_PERMISSION_DENIED", http_status=403)
    key = body.idempotency_key or idempotency_key or f"{action}:{run_id}"
    existing = await _offload(repo.find_control, run_id, key)
    if existing:
        refreshed, artifacts = await _offload(_load_run, repo, _artifact_repo(container), run_id)
        if refreshed is None:
            raise AgentRunNotFound("Run 不存在")
        return _run_to_out(refreshed, artifacts or [])
    from ...services.agent_runtime.run_manager import RunManager
    manager = RunManager(repo, container.agent_event_store)
    if action == "pause":
        result = await _offload(manager.pause, run_id, reason=body.reason)
    elif action == "resume":
        result = await _offload(manager.resume, run_id)
    else:
        job = await _offload(repo.get_job, run["job_id"])
        handler = container.agent_handler_registry.require(job["job_kind"] if job else "")
        result = await _offload(manager.retry,
            run_id,
            idempotency_key=key,
            handler_code=handler.code,
            handler_version=handler.version,
        )
    if action == "retry":
        await _offload(repo.record_control,
            run_id=run_id, user_id=user.id, action=action,
            idempotency_key=key, resulting_status=result["status"],
        )
        return await _offload(_run_to_out_from_repo, repo, _artifact_repo(container), result)
    await _offload(repo.record_control,
        run_id=run_id, user_id=user.id, action=action,
        idempotency_key=key, resulting_status=result["status"],
    )
    refreshed, artifacts = await _offload(_load_run, repo, _artifact_repo(container), run_id)
    if refreshed is None:
        raise AgentRunNotFound("Run 不存在")
    return _run_to_out(refreshed, artifacts or [])


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
    run = await _offload(repo.get_run, run_id)
    if not run:
        raise AgentRunNotFound("Run 不存在")
    if run["user_id"] != user.id and user.role != "admin":
        raise AgentRunNotFound("Run 不存在")
    events = await _offload(repo.list_events, run_id, after_sequence=after_sequence, limit=limit)
    return [_event_to_out(e) for e in events]


@runs_router.get("/{run_id}/events/stream")
async def stream_events(
    run_id: str,
    request: Request,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
) -> StreamingResponse:
    """SSE 流。以持久化事件为真源,支持 Last-Event-ID 续传。断开不取消 run。"""
    import time

    repo = _repo(container)
    run = await _offload(repo.get_run, run_id)
    if not run:
        raise AgentRunNotFound("Run 不存在")
    if run["user_id"] != user.id and user.role != "admin":
        raise AgentRunNotFound("Run 不存在")
    # 直接按 (run_id, event_id) 索引定位 sequence,不再扫描历史事件列表。
    after_sequence = 0
    if last_event_id:
        sequence = await _offload(repo.get_event_sequence, run_id, last_event_id)
        if sequence is None:
            # 游标不属于该 Run 或已不存在:明确报错,客户端改走 REST 全量归并。
            raise AgentCursorInvalid("事件游标无效或不属于该运行")
        after_sequence = sequence

    terminal_statuses = {"SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"}

    async def event_generator():
        current_seq = after_sequence
        last_activity = time.monotonic()
        while True:
            if await request.is_disconnected():
                return
            events, current_run = await _offload(_poll_sse, repo, run_id, current_seq)
            if events:
                for evt in events:
                    out = _event_to_out(evt)
                    yield (
                        f"id: {evt['event_id']}\nevent: {evt['type']}\n"
                        f"data: {out.model_dump_json()}\n\n"
                    )
                    current_seq = evt["sequence"]
                last_activity = time.monotonic()
                # 终态事件发送完毕后才关闭,避免客户端漏掉最后一条。
                if events[-1]["status"] in terminal_statuses:
                    return
                continue
            if current_run and current_run["status"] in terminal_statuses:
                # 终态 Run 已无新事件(例如客户端用终态游标重连)。
                return
            # 同进程靠通知唤醒;跨进程或通知丢失时最多等 1 秒后回落查询。
            awaited = await container.agent_event_notifier.wait(run_id, timeout=1.0)
            if awaited:
                continue
            if time.monotonic() - last_activity >= _SSE_HEARTBEAT_SECONDS:
                # 注释心跳只维持连接:不写库、不推进 sequence、不改变客户端业务状态。
                yield ": keep-alive\n\n"
                last_activity = time.monotonic()

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
    """落定一次审批决定。

    - 决策本身是**幂等**的：重复提交同一个决定返回同一结果（不会 409）；
    - 相反的决定一律 409，绝不覆盖已生效的决定；
    - `Idempotency-Key` 会被**真正记录**（`agent_run_controls`），而不是收下就丢；
    - 只有**本次真正落定**的决定才会驱动 Run 状态迁移 ——
      重放不会把已经跑完的 Run 再取消/再排队一次。
    """
    repo = _repo(container)
    key = body.idempotency_key or idempotency_key or f"approval:{approval_id}"
    apv = await _offload(_resolve_approval_sync, repo, container, approval_id, body, user.id, key)
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
    meta, content = await _offload(_read_artifact_content, repo, artifact_id, user.id)
    if not meta:
        raise AgentRunNotFound("Artifact 不存在")
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
    meta = await _offload(repo.get_artifact, artifact_id, user.id)
    if not meta:
        raise AgentRunNotFound("Artifact 不存在")
    return AgentArtifactOut(**{
        name: meta.get(name) for name in AgentArtifactOut.model_fields
    })


__all__ = [
    "router",
    "jobs_router",
    "runs_router",
    "approvals_router",
    "artifacts_router",
    "memories_router",
]
