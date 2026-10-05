"""CampusAgentRuntime API 路由(§9.1)。

所有写请求支持 Idempotency-Key。SSE 支持 Last-Event-ID 与 sequence。
鉴权使用 Bearer header(禁止 token query)。
"""
from __future__ import annotations

import json
from functools import partial
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, Header, Query, Request, Response
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

router = APIRouter(prefix="/agent-runtime", tags=["Agent 运行时"])
jobs_router = APIRouter(prefix="/agent-jobs", tags=["Agent 运行时"])
runs_router = APIRouter(prefix="/agent-runs", tags=["Agent 运行时"])
approvals_router = APIRouter(prefix="/agent-approvals", tags=["Agent 运行时"])
artifacts_router = APIRouter(prefix="/agent-artifacts", tags=["Agent 运行时"])
memories_router = APIRouter(prefix="/agent-memories", tags=["Agent 运行时"])

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


@router.get(
    "/capabilities",
    summary="获取运行时能力清单",
    responses={
        200: {
            "description": "返回 runtime 能力清单与契约版本",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "能力清单",
                            "value": {
                                "contract_version": "v1",
                                "capabilities": [
                                    {
                                        "name": "learning_goal.run",
                                        "version": "1.0",
                                        "route_policy": "reasoning_primary",
                                        "risk_level": "AUTO_SAFE",
                                        "requires_approval": False,
                                    },
                                    {
                                        "name": "final_review.plan",
                                        "version": "1.0",
                                        "route_policy": "reasoning_primary",
                                        "risk_level": "CONFIRM_REQUIRED",
                                        "requires_approval": True,
                                    },
                                ],
                            },
                        }
                    }
                }
            },
        }
    },
)
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


@jobs_router.post(
    "",
    summary="创建 Agent 任务",
    responses={
        202: {
            "description": "任务首次创建并入队",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "任务已入队",
                            "value": {
                                "job_id": "job_20261006_demo",
                                "user_id": "u_demo",
                                "job_kind": "learning_goal",
                                "status": "QUEUED",
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "updated_at": "2026-10-06T08:00:00+00:00",
                                "latest_run_id": "run_20261006_demo",
                                "pending_approval_id": None,
                                "input_ref": {"goal_id": "goal_2026_spring", "available_minutes": 90},
                            },
                        }
                    }
                }
            },
        },
        200: {
            "description": "同一幂等键与相同输入重放，返回既有任务",
            "content": {
                "application/json": {
                    "examples": {
                        "重放": {
                            "summary": "幂等重放",
                            "value": {
                                "job_id": "job_20261006_demo",
                                "user_id": "u_demo",
                                "job_kind": "learning_goal",
                                "status": "RUNNING",
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "updated_at": "2026-10-06T08:00:05+00:00",
                                "latest_run_id": "run_20261006_demo",
                                "pending_approval_id": None,
                                "input_ref": {"goal_id": "goal_2026_spring", "available_minutes": 90},
                            },
                        }
                    }
                }
            },
        },
    },
)
async def create_job(
    body: Annotated[
        AgentJobCreateIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "创建学习目标任务",
                    "value": {
                        "job_kind": "learning_goal",
                        "input_ref": {"goal_id": "goal_2026_spring", "available_minutes": 90},
                        "idempotency_key": "job_demo_20261006",
                    },
                }
            }
        ),
    ],
    request: Request,
    response: Response,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> AgentJobOut:
    """创建一个 Agent 任务并立即入队，返回任务概览。

    - 首次创建返回 202；同一幂等键与相同输入重放返回 200（body.idempotency_key 优先于 Idempotency-Key 头）。
    - Runtime 停止接单返回 503；幂等键复用于不同输入返回 409；input_ref 需通过 Handler 校验，否则 422。
    """
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


@jobs_router.get(
    "",
    summary="分页列出任务列表",
    responses={
        200: {
            "description": "返回当前学生的任务概览分页",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "任务列表",
                            "value": [
                                {
                                    "job_id": "job_20261006_demo",
                                    "user_id": "u_demo",
                                    "job_kind": "final_review",
                                    "status": "AWAITING_APPROVAL",
                                    "created_at": "2026-10-06T08:00:00+00:00",
                                    "updated_at": "2026-10-06T08:00:30+00:00",
                                    "latest_run_id": "run_20261006_demo",
                                    "pending_approval_id": "approval_20261006_demo",
                                    "input_ref": {"goal_id": "goal_2026_spring"},
                                }
                            ],
                        }
                    }
                }
            },
        }
    },
)
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
) -> list[AgentJobOut]:
    """分页列出当前学生的 Agent 任务；等待审批的任务会带出 pending_approval_id。"""
    repo = _repo(container)
    return await _offload(_job_page, repo, user.id, page, page_size)


@jobs_router.get(
    "/{job_id}/runs",
    summary="列出任务的运行记录",
    responses={
        200: {
            "description": "返回该任务的全部运行记录",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "运行记录列表",
                            "value": [
                                {
                                    "run_id": "run_20261006_demo",
                                    "job_id": "job_20261006_demo",
                                    "user_id": "u_demo",
                                    "status": "SUCCEEDED",
                                    "phase": "IDLE",
                                    "risk_level": "AUTO_SAFE",
                                    "started_at": "2026-10-06T08:00:05+00:00",
                                    "finished_at": "2026-10-06T08:00:42+00:00",
                                    "created_at": "2026-10-06T08:00:00+00:00",
                                    "updated_at": "2026-10-06T08:00:42+00:00",
                                    "error": None,
                                    "artifact_ids": ["artifact_20261006_demo"],
                                    "retry_of": None,
                                }
                            ],
                        }
                    }
                }
            },
        }
    },
)
async def list_job_runs(
    job_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> list[AgentRunOut]:
    """列出指定任务的全部运行记录（含产物 id）；任务不存在或不属于当前用户返回 404。"""
    repo = _repo(container)
    job, runs = await _offload(lambda: (repo.get_job(job_id), repo.list_runs_by_job(job_id)))
    if not job or job["user_id"] != user.id:
        raise AgentRunNotFound("Job 不存在")
    outputs = await _offload(_run_page, repo, _artifact_repo(container), runs)
    return outputs


@jobs_router.get(
    "/{job_id}",
    summary="读取任务详情",
    responses={
        200: {
            "description": "返回单个任务概览",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "任务详情",
                            "value": {
                                "job_id": "job_20261006_demo",
                                "user_id": "u_demo",
                                "job_kind": "final_review",
                                "status": "AWAITING_APPROVAL",
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "updated_at": "2026-10-06T08:00:30+00:00",
                                "latest_run_id": "run_20261006_demo",
                                "pending_approval_id": "approval_20261006_demo",
                                "input_ref": {"goal_id": "goal_2026_spring"},
                            },
                        }
                    }
                }
            },
        }
    },
)
async def get_job(
    job_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> AgentJobOut:
    """读取单个任务概览；不存在或不属于当前用户返回 404（AGENT_RUN_NOT_FOUND）。"""
    repo = _repo(container)
    job, latest_run_id, pending_approval_id = await _offload(_job_detail, repo, job_id)
    if not job:
        raise AgentRunNotFound("Job 不存在")
    if job["user_id"] != user.id:
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


@router.get(
    "/skills",
    response_model=AgentSkillsOut,
    summary="获取可发现的技能元数据",
    responses={
        200: {
            "description": "返回可发现的 Skill/MCP 元数据清单",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "技能清单",
                            "value": {
                                "contract_version": "v1",
                                "skills": [
                                    {
                                        "skill_code": "learning_goal_center",
                                        "version": "1.0",
                                        "description": "把学习目标转为可确认、可追踪、可重规划的任务计划",
                                        "capabilities": [
                                            "goal.aggregate",
                                            "plan.generate",
                                            "plan.replan",
                                        ],
                                        "tools": ["student.read", "course.read", "task.create"],
                                        "transport": "internal",
                                        "permission_policy": "student_owned_only",
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


@memories_router.get(
    "",
    response_model=list[AgentMemoryOut],
    summary="列出显式记忆",
    responses={
        200: {
            "description": "返回当前学生的显式记忆列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "记忆列表",
                            "value": [
                                {
                                    "memory_id": "memory_20261006_demo",
                                    "user_id": "u_demo",
                                    "kind": "CONFIRMED_STUDY_GOAL",
                                    "content_summary": "希望在本学期通过数据结构期末考试",
                                    "sensitivity": "low",
                                    "confirmed": True,
                                    "withdrawn": False,
                                    "model_may_consume": True,
                                    "created_at": "2026-10-06T08:00:00+00:00",
                                }
                            ],
                        }
                    }
                }
            },
        }
    },
)
async def list_memories(
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
) -> list[AgentMemoryOut]:
    """列出当前学生的显式记忆，包含已撤回项（withdrawn=true）。"""
    memories = await _offload(container.agent_memory_manager.list_for_user, user.id)
    return [_memory_to_out(memory) for memory in memories]


@memories_router.post(
    "",
    response_model=AgentMemoryOut,
    summary="创建显式记忆",
    responses={
        200: {
            "description": "返回新建的显式记忆",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "记忆已创建",
                            "value": {
                                "memory_id": "memory_20261006_demo",
                                "user_id": "u_demo",
                                "kind": "CONFIRMED_STUDY_GOAL",
                                "content_summary": "希望在本学期通过数据结构期末考试",
                                "sensitivity": "low",
                                "confirmed": True,
                                "withdrawn": False,
                                "model_may_consume": True,
                                "created_at": "2026-10-06T08:00:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
async def create_memory(
    body: Annotated[
        AgentMemoryCreateIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "记录已确认的学习目标",
                    "value": {
                        "kind": "CONFIRMED_STUDY_GOAL",
                        "content_summary": "希望在本学期通过数据结构期末考试",
                        "sensitivity": "low",
                        "confirmed": True,
                        "model_may_consume": True,
                    },
                }
            }
        ),
    ],
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
) -> AgentMemoryOut:
    """创建一条显式记忆；仅当 confirmed 且 model_may_consume 为真时才会进入模型上下文。"""
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


@memories_router.post(
    "/{memory_id}/withdraw",
    response_model=AgentMemoryOut,
    summary="撤回显式记忆",
    responses={
        200: {
            "description": "返回撤回后的记忆（withdrawn=true）",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "记忆已撤回",
                            "value": {
                                "memory_id": "memory_20261006_demo",
                                "user_id": "u_demo",
                                "kind": "CONFIRMED_STUDY_GOAL",
                                "content_summary": "希望在本学期通过数据结构期末考试",
                                "sensitivity": "low",
                                "confirmed": True,
                                "withdrawn": True,
                                "model_may_consume": False,
                                "created_at": "2026-10-06T08:00:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
async def withdraw_memory(
    memory_id: str,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
) -> AgentMemoryOut:
    """撤回指定记忆，撤回后不再进入模型上下文；记忆不存在返回 404。"""
    memory = await _offload(
        container.agent_memory_manager.withdraw, user_id=user.id, memory_id=memory_id
    )
    if memory is None:
        raise AgentRunNotFound("Memory 不存在")
    return _memory_to_out(memory)


@runs_router.get(
    "",
    summary="分页列出运行列表",
    responses={
        200: {
            "description": "返回当前学生的运行记录分页",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "运行列表",
                            "value": [
                                {
                                    "run_id": "run_20261006_demo",
                                    "job_id": "job_20261006_demo",
                                    "user_id": "u_demo",
                                    "status": "RUNNING",
                                    "phase": "WAITING_FOR_MODEL",
                                    "risk_level": "AUTO_SAFE",
                                    "started_at": "2026-10-06T08:00:05+00:00",
                                    "finished_at": None,
                                    "created_at": "2026-10-06T08:00:00+00:00",
                                    "updated_at": "2026-10-06T08:00:20+00:00",
                                    "error": None,
                                    "artifact_ids": [],
                                    "retry_of": None,
                                }
                            ],
                        }
                    }
                }
            },
        }
    },
)
async def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
) -> list[AgentRunOut]:
    """分页列出当前学生的 Agent 运行记录（含状态、阶段与产物 id）。"""
    return await _offload(
        _runs_for_user, _repo(container), _artifact_repo(container), user.id, page, page_size
    )


@runs_router.get(
    "/{run_id}",
    summary="读取运行详情",
    responses={
        200: {
            "description": "返回单个运行详情",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "运行详情",
                            "value": {
                                "run_id": "run_20261006_demo",
                                "job_id": "job_20261006_demo",
                                "user_id": "u_demo",
                                "status": "SUCCEEDED",
                                "phase": "IDLE",
                                "risk_level": "AUTO_SAFE",
                                "started_at": "2026-10-06T08:00:05+00:00",
                                "finished_at": "2026-10-06T08:00:42+00:00",
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "updated_at": "2026-10-06T08:00:42+00:00",
                                "error": None,
                                "artifact_ids": ["artifact_20261006_demo"],
                                "retry_of": None,
                            },
                        }
                    }
                }
            },
        }
    },
)
async def get_run(
    run_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> AgentRunOut:
    """读取单个运行详情（含错误信封与产物 id）；不存在或不属于当前用户返回 404。"""
    repo = _repo(container)
    run, artifacts = await _offload(_load_run, repo, _artifact_repo(container), run_id)
    if not run:
        raise AgentRunNotFound("Run 不存在")
    if run["user_id"] != user.id:
        raise AgentRunNotFound("Run 不存在")
    return _run_to_out(run, artifacts or [])


@runs_router.post(
    "/{run_id}/cancel",
    summary="取消运行",
    responses={
        200: {
            "description": "取消成功，返回取消后的运行详情",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "运行已取消",
                            "value": {
                                "run_id": "run_20261006_demo",
                                "job_id": "job_20261006_demo",
                                "user_id": "u_demo",
                                "status": "CANCELLED",
                                "phase": "IDLE",
                                "risk_level": "AUTO_SAFE",
                                "started_at": "2026-10-06T08:00:05+00:00",
                                "finished_at": "2026-10-06T08:00:20+00:00",
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "updated_at": "2026-10-06T08:00:20+00:00",
                                "error": None,
                                "artifact_ids": [],
                                "retry_of": None,
                            },
                        }
                    }
                }
            },
        }
    },
)
async def cancel_run(
    run_id: str,
    body: Annotated[
        AgentRunCancelIn,
        Body(
            openapi_examples={
                "成功": {"summary": "取消运行", "value": {"reason": "本轮结果不再需要"}}
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> AgentRunOut:
    """取消指定运行；取消依赖状态机幂等，重复取消与终态冲突见运行控制。

    - 运行不存在或不属于当前用户返回 404（AGENT_RUN_NOT_FOUND）。
    - 无权取消他人运行返回 403（AGENT_PERMISSION_DENIED）。
    """
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
    if action == "retry":
        job = await _offload(repo.get_job, run["job_id"])
        handler = container.agent_handler_registry.require(job["job_kind"] if job else "")
        retried = await _offload(
            repo.retry_run_with_control,
            run_id=run_id,
            user_id=user.id,
            idempotency_key=key,
            handler_code=handler.code,
            handler_version=handler.version,
        )
        return await _offload(
            _run_to_out_from_repo, repo, _artifact_repo(container), retried["run"]
        )
    from ...services.agent_runtime.run_manager import RunManager
    manager = RunManager(repo, container.agent_event_store)
    if action == "pause":
        result = await _offload(manager.pause, run_id, reason=body.reason)
    else:
        result = await _offload(manager.resume, run_id)
    await _offload(repo.record_control,
        run_id=run_id, user_id=user.id, action=action,
        idempotency_key=key, resulting_status=result["status"],
    )
    refreshed, artifacts = await _offload(_load_run, repo, _artifact_repo(container), run_id)
    if refreshed is None:
        raise AgentRunNotFound("Run 不存在")
    return _run_to_out(refreshed, artifacts or [])


@runs_router.post(
    "/{run_id}/pause",
    summary="暂停运行",
    responses={
        200: {
            "description": "暂停成功，返回暂停后的运行详情",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "运行已暂停",
                            "value": {
                                "run_id": "run_20261006_demo",
                                "job_id": "job_20261006_demo",
                                "user_id": "u_demo",
                                "status": "PAUSED",
                                "phase": "IDLE",
                                "risk_level": "AUTO_SAFE",
                                "started_at": "2026-10-06T08:00:05+00:00",
                                "finished_at": None,
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "updated_at": "2026-10-06T08:00:20+00:00",
                                "error": None,
                                "artifact_ids": [],
                                "retry_of": None,
                            },
                        }
                    }
                }
            },
        }
    },
)
async def pause_run(
    run_id: str,
    body: Annotated[
        AgentRunControlIn,
        Body(
            openapi_examples={
                "成功": {"summary": "暂停运行", "value": {"idempotency_key": "pause_example_1"}}
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> AgentRunOut:
    """暂停指定运行；每次独立暂停生成新幂等键，仅网络重试复用，body 优先于请求头。

    - 运行不存在返回 404（AGENT_RUN_NOT_FOUND）。
    - 无权控制他人运行返回 403（AGENT_PERMISSION_DENIED）。
    """
    return await _control_run(run_id, action="pause", body=body, idempotency_key=idempotency_key, user=user, container=container)


@runs_router.post(
    "/{run_id}/resume",
    summary="恢复运行",
    responses={
        200: {
            "description": "恢复成功，返回恢复后的运行详情",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "运行已恢复",
                            "value": {
                                "run_id": "run_20261006_demo",
                                "job_id": "job_20261006_demo",
                                "user_id": "u_demo",
                                "status": "RUNNING",
                                "phase": "WAITING_FOR_MODEL",
                                "risk_level": "AUTO_SAFE",
                                "started_at": "2026-10-06T08:00:05+00:00",
                                "finished_at": None,
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "updated_at": "2026-10-06T08:00:35+00:00",
                                "error": None,
                                "artifact_ids": [],
                                "retry_of": None,
                            },
                        }
                    }
                }
            },
        }
    },
)
async def resume_run(
    run_id: str,
    body: Annotated[
        AgentRunControlIn,
        Body(
            openapi_examples={
                "成功": {"summary": "恢复运行", "value": {"idempotency_key": "resume_example_1"}}
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> AgentRunOut:
    """恢复已暂停的运行；每次独立恢复生成新幂等键，不与暂停键共用，body 优先于请求头。

    - 运行不存在返回 404（AGENT_RUN_NOT_FOUND）。
    - 无权控制他人运行返回 403（AGENT_PERMISSION_DENIED）。
    """
    return await _control_run(run_id, action="resume", body=body, idempotency_key=idempotency_key, user=user, container=container)


@runs_router.post(
    "/{run_id}/retry",
    summary="重试运行",
    responses={
        200: {
            "description": "重试成功，返回新建（或幂等重放的）运行详情",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "已按新运行重试",
                            "value": {
                                "run_id": "run_20261006_retry",
                                "job_id": "job_20261006_demo",
                                "user_id": "u_demo",
                                "status": "QUEUED",
                                "phase": "QUEUED",
                                "risk_level": "AUTO_SAFE",
                                "started_at": None,
                                "finished_at": None,
                                "created_at": "2026-10-06T08:05:00+00:00",
                                "updated_at": "2026-10-06T08:05:00+00:00",
                                "error": None,
                                "artifact_ids": [],
                                "retry_of": "run_20261006_demo",
                            },
                        }
                    }
                }
            },
        }
    },
)
async def retry_run(
    run_id: str,
    body: Annotated[
        AgentRunControlIn,
        Body(
            openapi_examples={
                "成功": {"summary": "重试运行", "value": {"idempotency_key": "retry_example_1"}}
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> AgentRunOut:
    """重试指定运行；首次成功返回新运行，同键重放返回原运行。

    - 首次响应丢失时可按运行控制说明回读任务运行列表，避免换键创建重复运行。
    - 运行不存在返回 404（AGENT_RUN_NOT_FOUND）；无权控制他人运行返回 403（AGENT_PERMISSION_DENIED）。
    """
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


@runs_router.get(
    "/{run_id}/events",
    summary="列出运行事件",
    responses={
        200: {
            "description": "返回该运行的事件列表（按 sequence 升序）",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "事件列表",
                            "value": [
                                {
                                    "id": "evt_20261006_001",
                                    "type": "RUN_STARTED",
                                    "run_id": "run_20261006_demo",
                                    "sequence": 1,
                                    "status": "RUNNING",
                                    "phase": "WAITING_FOR_MODEL",
                                    "role": "coordinator",
                                    "summary": "开始执行学习目标规划",
                                    "progress": {"current": 1, "total": 4, "percent": 25},
                                    "artifact_id": None,
                                    "approval_id": None,
                                    "created_at": "2026-10-06T08:00:05+00:00",
                                }
                            ],
                        }
                    }
                }
            },
        }
    },
)
async def list_events(
    run_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
    after_sequence: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[AgentEventOut]:
    """列出指定运行的事件，支持 after_sequence 增量拉取。

    - 事件以持久化序列为真源，summary 为安全摘要，不含 prompt 或凭据。
    - 运行不存在或不属于当前用户返回 404（AGENT_RUN_NOT_FOUND）。
    """
    repo = _repo(container)
    run = await _offload(repo.get_run, run_id)
    if not run:
        raise AgentRunNotFound("Run 不存在")
    if run["user_id"] != user.id:
        raise AgentRunNotFound("Run 不存在")
    events = await _offload(repo.list_events, run_id, after_sequence=after_sequence, limit=limit)
    return [_event_to_out(e) for e in events]


@runs_router.get(
    "/{run_id}/events/stream",
    summary="订阅运行事件流",
)
async def stream_events(
    run_id: str,
    request: Request,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
) -> StreamingResponse:
    """SSE 流。以持久化事件为真源,支持 Last-Event-ID 续传。断开不取消 run。

    - 游标无效或不属于该运行返回 409（AGENT_CURSOR_INVALID）。
    - 运行不存在或不属于当前用户返回 404（AGENT_RUN_NOT_FOUND）。
    """
    import time

    repo = _repo(container)
    run = await _offload(repo.get_run, run_id)
    if not run:
        raise AgentRunNotFound("Run 不存在")
    if run["user_id"] != user.id:
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


@approvals_router.post(
    "/{approval_id}/decision",
    summary="落定审批决定",
    responses={
        200: {
            "description": "返回落定后的审批记录",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "审批已通过",
                            "value": {
                                "approval_id": "approval_20261006_demo",
                                "run_id": "run_20261006_demo",
                                "status": "APPROVED",
                                "risk_level": "CONFIRM_REQUIRED",
                                "action_summary": "生成期末复习计划",
                                "expires_at": "2026-10-06T09:00:00+00:00",
                                "resolved_at": "2026-10-06T08:10:00+00:00",
                                "decision_reason": "确认可以生成",
                            },
                        }
                    }
                }
            },
        }
    },
)
async def resolve_approval(
    approval_id: str,
    body: Annotated[
        AgentApprovalDecisionIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "通过审批",
                    "value": {"decision": "APPROVED", "reason": "确认可以生成"},
                },
                "拒绝": {
                    "summary": "拒绝审批",
                    "value": {"decision": "REJECTED", "reason": "暂不需要"},
                },
            }
        ),
    ],
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


@artifacts_router.get(
    "/{artifact_id}/content",
    summary="读取产物正文",
)
async def get_artifact_content(
    artifact_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
):
    """返回 artifact 文本内容(Markdown / JSON)。

    - 响应为 text/plain 或对应 mime_type 的纯文本，非 JSON 结构。
    - 产物不存在返回 404（AGENT_RUN_NOT_FOUND）；内容不可读同样返回 404。
    """
    repo = _artifact_repo(container)
    meta, content = await _offload(_read_artifact_content, repo, artifact_id, user.id)
    if not meta:
        raise AgentRunNotFound("Artifact 不存在")
    if content is None:
        raise AgentRunNotFound("Artifact 内容不可读")
    return PlainTextResponse(content, media_type=meta.get("mime_type") or "text/plain")


@artifacts_router.get(
    "/{artifact_id}",
    summary="读取产物元数据",
    responses={
        200: {
            "description": "返回产物元数据（不含正文）",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "产物元数据",
                            "value": {
                                "artifact_id": "artifact_20261006_demo",
                                "run_id": "run_20261006_demo",
                                "user_id": "u_demo",
                                "artifact_type": "PLAN",
                                "version": 1,
                                "mime_type": "application/json",
                                "size_bytes": 2048,
                                "content_hash": "3f786850e387550fdab836ed7e6dc881de23001b",
                                "download_url": None,
                                "created_at": "2026-10-06T08:00:42+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
async def get_artifact(
    artifact_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> AgentArtifactOut:
    """读取单个产物的元数据；不存在或不属于当前用户返回 404（AGENT_RUN_NOT_FOUND）。"""
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
