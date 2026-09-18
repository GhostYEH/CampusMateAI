"""期末复习 API 路由(§9.3)。

完整闭环: Campaign → Plan → Agenda → Evidence → Analyzer → Proposal → Approval → 新版本。

约束:
- Plan versions 不可变
- Analyzer 只产生 proposal,不直接改 active plan
- 只接受 server /student/exams 返回的 exam_id
- 只允许当前 student 访问自己的 campaign
- 写请求支持 Idempotency-Key
"""
from __future__ import annotations

import json
import hashlib
from typing import Optional

from fastapi import APIRouter, Depends, Header, Request

from ...core.exceptions import (
    AgentApprovalRequired,
    AgentIdempotencyConflict,
    AgentRuntimeError,
    Forbidden,
    NotFoundError,
    ValidationFailed,
)
from ...models.multi_role import UserRow
from ...repositories.agent_runtime_repository import build_request_hash
from ...repositories.final_review_repository import FinalReviewRepository
from ...schemas.agent_contract_enums import ApprovalStatus, RiskLevel
from ...schemas.final_review import (
    ActivateIn,
    ActivateOut,
    AdjustmentAnalyzeIn,
    AdjustmentAnalyzeOut,
    AdjustmentDecisionIn,
    AdjustmentDecisionOut,
    AdjustmentProposalOut,
    CompleteItemIn,
    CompleteItemOut,
    DailyAgendaOut,
    DailyCheckinIn,
    DailyCheckinOut,
    DailyItemOut,
    FinalReviewCampaignIn,
    FinalReviewCampaignOut,
    PlanGenerateIn,
    PlanGenerateOut,
    PlanVersionOut,
)
from ..deps import ServiceContainer, get_container, student_only

router = APIRouter(prefix="/final-review", tags=["final-review"])

# 审批后的实际执行由这两个 Handler 经 Gateway 完成,路由不再直接写计划状态。
_ACTIVATE_JOB_KIND = "final_review_plan_activate"
_ADJUST_APPLY_JOB_KIND = "final_review_adjust_apply"


def _repo(container: ServiceContainer) -> FinalReviewRepository:
    return FinalReviewRepository(container.db)


def _settle_waiting_run(container: ServiceContainer, approval_id: Optional[str], status: str) -> None:
    """把等待该审批的 Run 收口到指定终态(仅用于拒绝/取消,不产生领域副作用)。"""
    if not approval_id:
        return
    approval = container.agent_runtime_repository.get_approval(approval_id)
    run = container.agent_runtime_repository.get_run(approval.run_id) if approval else None
    if run and run["status"] == "AWAITING_APPROVAL":
        container.agent_run_manager.transition(approval.run_id, status, phase="IDLE")


def _validate_exam_ids(user_id: str, exam_ids: list[str], container: ServiceContainer) -> None:
    """校验 exam_ids 全部来自 server /student/exams(即 student_exams 表)。"""
    if not exam_ids:
        raise ValidationFailed("至少需要一个 exam_id")
    # 确保 student_exams 表存在
    conn = container.db._connect()
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS student_exams ("
            "id TEXT PRIMARY KEY, user_id TEXT NOT NULL, course_name TEXT NOT NULL, "
            "exam_date TEXT NOT NULL, start_time TEXT, end_time TEXT, location TEXT, "
            "seat_number TEXT, exam_type TEXT, reminder_enabled INTEGER NOT NULL DEFAULT 1, "
            "notes TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        conn.commit()
        placeholders = ",".join("?" for _ in exam_ids)
        rows = conn.execute(
            f"SELECT id FROM student_exams WHERE user_id = ? AND id IN ({placeholders})",
            [user_id, *exam_ids],
        ).fetchall()
    finally:
        container.db._release(conn)
    found_ids = {r["id"] for r in rows}
    missing = set(exam_ids) - found_ids
    if missing:
        raise ValidationFailed(
            f"exam_id 不存在或不属于当前用户: {sorted(missing)}"
        )


def _campaign_to_out(row) -> FinalReviewCampaignOut:
    return FinalReviewCampaignOut(
        campaign_id=row.campaign_id,
        user_id=row.user_id,
        exam_ids=json.loads(row.exam_ids_json),
        daily_capacity_minutes=row.daily_capacity_minutes,
        preferred_periods=json.loads(row.preferred_periods_json),
        rest_days=json.loads(row.rest_days_json),
        intensity=row.intensity,
        status=row.status,
        active_version=row.active_version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _plan_to_out(row) -> PlanVersionOut:
    return PlanVersionOut(
        campaign_id=row.campaign_id,
        version=row.version,
        plan=json.loads(row.plan_json),
        source_snapshot_id=row.source_snapshot_id,
        model_provider=row.model_provider,
        route_policy=row.route_policy,
        risk_level=row.risk_level,
        approval_id=row.approval_id,
        supersedes_version=row.supersedes_version,
        created_at=row.created_at,
    )


def _proposal_to_out(row) -> AdjustmentProposalOut:
    return AdjustmentProposalOut(
        proposal_id=row.proposal_id,
        campaign_id=row.campaign_id,
        source_version=row.source_version,
        proposal=json.loads(row.proposal_json),
        risk_level=row.risk_level,
        status=row.status,
        approval_id=row.approval_id,
        target_version=row.target_version,
        reason=row.reason,
        created_at=row.created_at,
    )


def _item_to_out(row) -> DailyItemOut:
    return DailyItemOut(
        item_id=row.item_id,
        title=row.title,
        course_name=row.course_name,
        scheduled_minutes=row.scheduled_minutes,
        sort_order=row.sort_order,
        status=row.status,
        personal_task_id=row.personal_task_id,
        difficulty=row.difficulty,
    )


def _request_hash(payload: dict) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ===== Campaigns =====


@router.post("/campaigns")
async def create_campaign(
    body: FinalReviewCampaignIn,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> FinalReviewCampaignOut:
    """创建 campaign。只接受 server /student/exams 返回的 exam_id。"""
    repo = _repo(container)
    _validate_exam_ids(user.id, body.exam_ids, container)

    effective_key = body.idempotency_key or idempotency_key
    if effective_key:
        existing = repo.find_campaign_by_idempotency(user.id, effective_key)
        if existing:
            return _campaign_to_out(existing)

    row = repo.create_campaign(
        user_id=user.id,
        exam_ids=body.exam_ids,
        daily_capacity_minutes=body.daily_capacity_minutes,
        preferred_periods=body.preferred_periods,
        rest_days=body.rest_days,
        intensity=body.intensity,
        idempotency_key=effective_key,
    )
    return _campaign_to_out(row)


@router.get("/campaigns")
async def list_campaigns(
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
) -> list[FinalReviewCampaignOut]:
    repo = _repo(container)
    rows = repo.list_campaigns(user.id)
    return [_campaign_to_out(r) for r in rows]


@router.get("/campaigns/{campaign_id}")
async def get_campaign(
    campaign_id: str,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
) -> FinalReviewCampaignOut:
    repo = _repo(container)
    row = repo.get_campaign(campaign_id, user_id=user.id)
    if not row:
        raise NotFoundError("campaign 不存在")
    return _campaign_to_out(row)


# ===== Plans =====


@router.post("/campaigns/{campaign_id}/plans/generate")
async def generate_plan(
    campaign_id: str,
    body: PlanGenerateIn,
    request: Request,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> PlanGenerateOut:
    """生成首版或新版计划。使用 reasoning_primary 路由。"""
    repo = _repo(container)
    campaign = repo.get_campaign(campaign_id, user_id=user.id)
    if not campaign:
        raise NotFoundError("campaign 不存在")

    effective_key = body.idempotency_key or idempotency_key
    request_ref = {
        "campaign_id": campaign_id,
        "request_hash": _request_hash({
            "campaign_id": campaign_id,
            "user_edits": body.user_edits,
        }),
    }
    runtime_repo = container.agent_runtime_repository
    if effective_key:
        existing_job = runtime_repo.find_job_by_idempotency(user.id, effective_key)
        if existing_job:
            existing_ref = json.loads(existing_job.get("input_ref_json") or "{}")
            if (
                existing_job["job_kind"] != "final_review_plan_generate"
                or existing_ref.get("request_hash") != request_ref["request_hash"]
            ):
                raise AgentIdempotencyConflict()
            existing_run = runtime_repo.get_run_by_job(existing_job["job_id"])
            existing_version = existing_ref.get("version")
            if existing_run and existing_version:
                existing_plan = repo.get_plan_version(
                    campaign_id, int(existing_version), user_id=user.id
                )
                if existing_plan:
                    return PlanGenerateOut(
                        run_id=existing_run["run_id"],
                        version=existing_plan.version,
                        plan=json.loads(existing_plan.plan_json),
                        risk_level=existing_plan.risk_level,
                        requires_approval=True,
                        approval_id=existing_plan.approval_id,
                    )
            raise AgentRuntimeError(
                "幂等请求仍在处理中", code="AGENT_INVALID_STATE", http_status=409
            )

    job_id = runtime_repo.create_job(
        user_id=user.id,
        job_kind="final_review_plan_generate",
        input_ref=request_ref,
        idempotency_key=effective_key,
    )
    run_id = runtime_repo.create_run(
        job_id=job_id,
        user_id=user.id,
        request_id=getattr(request.state, "request_id", None),
        idempotency_key=effective_key,
    )
    container.agent_run_manager.transition(
        run_id, "RUNNING", phase="WAITING_FOR_MODEL"
    )

    # 构建上下文
    from ...services.final_review.context import ContextSnapshotBuilder
    from ...services.final_review.planner import Planner

    ctx_builder = ContextSnapshotBuilder(
        final_review_repo=repo,
        context_manager=container.agent_context_manager,
        db=container.db,
    )
    snapshot_id, facts = ctx_builder.build(
        user_id=user.id, campaign_id=campaign_id
    )

    # 生成计划
    # 取消检查点:进入计划生成前确认 run 仍可推进。
    container.agent_run_manager.assert_active(run_id)
    planner = Planner(model_router=container.agent_model_router)
    result = await planner.generate(
        facts=facts, user_edits=body.user_edits, run_id=run_id
    )

    # 创建 plan version
    version = repo.next_plan_version(campaign_id)
    risk_level = RiskLevel.CONFIRM_REQUIRED.value
    # 审批必须绑定"具体工具 + 具体参数"：这里提前签发，稍后 activate 命令
    # 会用同一组 (campaign_id, version, user_id) 触发该工具，指纹必须完全一致。
    from ...services.agent_runtime.handlers.final_review import PLAN_ACTIVATE_TOOL
    from ...services.agent_runtime.tool_gateway import build_request_hash

    approval_id = container.agent_approval_gate.require(
        run_id=run_id,
        user_id=user.id,
        risk_level=RiskLevel.CONFIRM_REQUIRED,
        action_summary=f"激活期末复习计划版本 {version}",
        tool_name=PLAN_ACTIVATE_TOOL,
        request_hash=build_request_hash(
            PLAN_ACTIVATE_TOOL,
            {"campaign_id": campaign_id, "version": int(version), "user_id": user.id},
        ),
    )
    plan_row = repo.create_plan_version(
        campaign_id=campaign_id,
        version=version,
        user_id=user.id,
        plan=result.plan,
        source_snapshot_id=snapshot_id,
        model_provider=result.provider,
        route_policy=result.route_policy,
        risk_level=risk_level,
        approval_id=approval_id,
    )
    artifact_id = container.agent_artifact_manager.create(
        run_id=run_id,
        user_id=user.id,
        artifact_type="FINAL_REVIEW_PLAN",
        content={
            "campaign_id": campaign_id,
            "version": version,
            "plan": result.plan,
            "risk_level": risk_level,
            "approval_id": approval_id,
        },
        mime_type="application/json",
        version=version,
    )
    container.agent_event_store.append(
        run_id=run_id,
        type="ARTIFACT_CREATED",
        status="RUNNING",
        phase="PERSISTING_RESULT",
        role="planner",
        summary="复习计划制品已生成",
        artifact_id=artifact_id,
    )
    runtime_repo.update_job_input_ref(
        job_id,
        {**request_ref, "version": version, "approval_id": approval_id},
    )
    container.agent_run_manager.transition(
        run_id,
        "AWAITING_APPROVAL",
        phase="WAITING_FOR_APPROVAL",
        risk_level=risk_level,
    )
    container.agent_event_store.append(
        run_id=run_id,
        type="APPROVAL_REQUIRED",
        status="AWAITING_APPROVAL",
        phase="WAITING_FOR_APPROVAL",
        role="planner",
        summary="复习计划已生成，等待确认后激活",
        approval_id=approval_id,
    )

    return PlanGenerateOut(
        run_id=run_id,
        version=version,
        plan=result.plan,
        risk_level=risk_level,
        requires_approval=True,
        approval_id=approval_id,
    )


@router.get("/campaigns/{campaign_id}/plan-versions")
async def list_plan_versions(
    campaign_id: str,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
) -> list[PlanVersionOut]:
    repo = _repo(container)
    rows = repo.list_plan_versions(campaign_id, user_id=user.id)
    return [_plan_to_out(r) for r in rows]


@router.get("/campaigns/{campaign_id}/plan-versions/{version}")
async def get_plan_version(
    campaign_id: str,
    version: int,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
) -> PlanVersionOut:
    repo = _repo(container)
    row = repo.get_plan_version(campaign_id, version, user_id=user.id)
    if not row:
        raise NotFoundError("plan version 不存在")
    return _plan_to_out(row)


# ===== Activate =====


@router.post("/campaigns/{campaign_id}/activate")
async def activate_campaign(
    campaign_id: str,
    body: ActivateIn,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> ActivateOut:
    """激活指定版本。

    路由只创建命令:审批后的实际激活由 Handler 经 `ToolInvocationGateway` 执行,
    最终状态由 Worker 原子写入,进程在中间崩溃也能从 checkpoint 恢复且只激活一次。
    """
    repo = _repo(container)
    plan = repo.get_plan_version(campaign_id, body.version, user_id=user.id)
    if not plan:
        raise NotFoundError("plan version 不存在")
    if not plan.approval_id:
        raise AgentApprovalRequired(details={"approval_id": None})
    approval = container.agent_runtime_repository.get_approval(plan.approval_id)
    if not approval or approval.status != "APPROVED":
        raise AgentApprovalRequired(details={"approval_id": plan.approval_id})

    campaign = repo.get_campaign(campaign_id, user_id=user.id)
    if not campaign:
        raise NotFoundError("campaign 不存在")
    if campaign.active_version == body.version:
        # 幂等:同一版本已经激活,不重复入队。
        return ActivateOut(
            campaign_id=campaign_id,
            active_version=body.version,
            activated=True,
            status="ACTIVE",
        )

    handler = container.agent_handler_registry.require(_ACTIVATE_JOB_KIND)
    input_ref = {
        "campaign_id": campaign_id,
        "version": body.version,
        "approval_id": plan.approval_id,
    }
    created = container.agent_runtime_repository.create_job_with_run_and_event(
        user_id=user.id,
        job_kind=handler.job_kind,
        input_ref=input_ref,
        idempotency_key=(
            body.idempotency_key
            or idempotency_key
            or f"{_ACTIVATE_JOB_KIND}:{campaign_id}:{body.version}"
        ),
        request_hash=build_request_hash(handler.job_kind, input_ref),
        handler_code=handler.code,
        handler_version=handler.version,
    )
    return ActivateOut(
        campaign_id=campaign_id,
        active_version=body.version,
        activated=False,
        status="PENDING",
        run_id=created["run_id"],
    )


# ===== Daily agenda =====


@router.get("/campaigns/{campaign_id}/agendas/today")
async def get_today_agenda(
    campaign_id: str,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
) -> DailyAgendaOut:
    """获取今日议程。若不存在则按 active version 生成。"""
    repo = _repo(container)
    campaign = repo.get_campaign(campaign_id, user_id=user.id)
    if not campaign:
        raise NotFoundError("campaign 不存在")
    if campaign.active_version is None:
        raise AgentRuntimeError("campaign 尚未激活", code="AGENT_INVALID_STATE")

    from ...services.final_review.agenda_service import AgendaService

    agenda_svc = AgendaService(
        final_review_repo=repo,
        personal_task_repo=container.personal_task_repository,
    )
    result = agenda_svc.generate_today(
        campaign_id=campaign_id,
        plan_version=campaign.active_version,
        user_id=user.id,
    )
    return DailyAgendaOut(
        agenda_id=result["agenda_id"],
        campaign_id=result["campaign_id"],
        plan_version=result["plan_version"],
        agenda_date=result["agenda_date"],
        total_minutes=result["total_minutes"],
        items=[DailyItemOut(**it) for it in result["items"]],
    )


@router.post("/daily-items/{item_id}/complete")
async def complete_item(
    item_id: str,
    body: CompleteItemIn,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> CompleteItemOut:
    """完成 agenda item。"""
    repo = _repo(container)
    from ...services.final_review.agenda_service import AgendaService

    agenda_svc = AgendaService(
        final_review_repo=repo,
        personal_task_repo=container.personal_task_repository,
    )
    result = agenda_svc.complete_item(
        item_id=item_id,
        user_id=user.id,
        difficulty=body.difficulty,
        feedback=body.feedback,
    )
    if not result:
        raise NotFoundError("item 不存在")
    from datetime import datetime, timezone
    return CompleteItemOut(
        item_id=item_id,
        status=result["status"],
        completed_at=result.get("completed_at") or datetime.now(timezone.utc).isoformat(),
    )


@router.post("/campaigns/{campaign_id}/daily-checkins")
async def daily_checkin(
    campaign_id: str,
    body: DailyCheckinIn,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> DailyCheckinOut:
    """每日签到/晚间反馈。记录完成情况和反馈作为 evidence。"""
    repo = _repo(container)
    campaign = repo.get_campaign(campaign_id, user_id=user.id)
    if not campaign:
        raise NotFoundError("campaign 不存在")

    from ...services.final_review.agenda_service import AgendaService

    agenda_svc = AgendaService(
        final_review_repo=repo,
        personal_task_repo=container.personal_task_repository,
    )
    count = agenda_svc.record_checkin(
        campaign_id=campaign_id,
        user_id=user.id,
        report_date=body.report_date,
        completed_item_ids=body.completed_item_ids,
        insufficient_time=body.insufficient_time,
        difficulty_notes=body.difficulty_notes,
    )
    return DailyCheckinOut(recorded=True, evidence_count=count)


# ===== Adjustments =====


@router.post("/campaigns/{campaign_id}/adjustments/analyze")
async def analyze_adjustments(
    campaign_id: str,
    body: AdjustmentAnalyzeIn,
    request: Request,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> AdjustmentAnalyzeOut:
    """Analyzer 分析证据,产生 adjustment proposal。不直接改 active plan。"""
    repo = _repo(container)
    campaign = repo.get_campaign(campaign_id, user_id=user.id)
    if not campaign:
        raise NotFoundError("campaign 不存在")
    if campaign.active_version is None:
        raise AgentRuntimeError("campaign 尚未激活", code="AGENT_INVALID_STATE")

    # 收集 evidence
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date().isoformat()
    agenda = repo.get_agenda_by_date(
        campaign_id, campaign.active_version, today, user_id=user.id
    )
    missed_items = []
    completed_items = []
    if agenda:
        items = repo.list_items(agenda.agenda_id, user_id=user.id)
        for it in items:
            if it.status == "pending":
                missed_items.append({"item_id": it.item_id, "title": it.title})
            elif it.status == "completed":
                completed_items.append({"item_id": it.item_id, "title": it.title})

    evidence = {
        "missed_items": missed_items,
        "completed_items": completed_items,
        "insufficient_time": len(missed_items) > 0,
    }

    runtime_repo = container.agent_runtime_repository
    effective_key = body.idempotency_key or idempotency_key
    request_ref = {
        "campaign_id": campaign_id,
        "request_hash": _request_hash({"campaign_id": campaign_id}),
    }
    if effective_key:
        existing_job = runtime_repo.find_job_by_idempotency(user.id, effective_key)
        if existing_job:
            existing_ref = json.loads(existing_job.get("input_ref_json") or "{}")
            if (
                existing_job["job_kind"] != "final_review_adjustment"
                or existing_ref.get("request_hash") != request_ref["request_hash"]
            ):
                raise AgentIdempotencyConflict()
            existing_run = runtime_repo.get_run_by_job(existing_job["job_id"])
            proposal_id = existing_ref.get("proposal_id")
            proposal = repo.get_proposal(proposal_id, user_id=user.id) if proposal_id else None
            if existing_run and proposal:
                return AdjustmentAnalyzeOut(
                    run_id=existing_run["run_id"],
                    proposal_id=proposal.proposal_id,
                    risk_level=proposal.risk_level,
                    requires_approval=bool(proposal.approval_id),
                    approval_id=proposal.approval_id,
                )
            raise AgentRuntimeError("幂等请求仍在处理中", code="AGENT_INVALID_STATE", http_status=409)

    checkins = repo.list_checkin_evidence(campaign_id, user_id=user.id)
    evidence["checkins"] = checkins
    evidence["difficulty_notes"] = [
        item["difficulty_notes"] for item in checkins if item["difficulty_notes"]
    ]
    evidence["insufficient_time"] = evidence["insufficient_time"] or any(
        item["insufficient_time"] for item in checkins
    )
    job_id = runtime_repo.create_job(
        user_id=user.id,
        job_kind="final_review_adjustment",
        input_ref=request_ref,
        idempotency_key=effective_key,
    )
    run_id = runtime_repo.create_run(
        job_id=job_id,
        user_id=user.id,
        request_id=getattr(request.state, "request_id", None),
        idempotency_key=effective_key,
    )
    container.agent_run_manager.transition(
        run_id, "RUNNING", phase="WAITING_FOR_MODEL"
    )

    from ...services.final_review.adjustment_service import AdjustmentAnalyzer

    # 取消检查点:进入模型分析前确认 run 仍可推进,避免取消后继续消耗额度。
    container.agent_run_manager.assert_active(run_id)
    analyzer = AdjustmentAnalyzer(
        final_review_repo=repo,
        model_router=container.agent_model_router,
        risk_engine=container.agent_risk_engine,
    )
    result = await analyzer.analyze(
        campaign_id=campaign_id,
        user_id=user.id,
        evidence=evidence,
        run_id=run_id,
    )

    approval_id = None
    if result["requires_approval"]:
        # 创建 approval 记录
        from datetime import timedelta
        from ...services.agent_runtime.handlers.final_review import ADJUST_APPLY_TOOL
        from ...services.agent_runtime.tool_gateway import build_request_hash

        approval_id = container.agent_approval_gate.require(
            run_id=run_id,
            user_id=user.id,
            risk_level=RiskLevel.CONFIRM_REQUIRED,
            action_summary=f"期末复习调整提案:{result['proposal'].get('reason', '')}",
            tool_name=ADJUST_APPLY_TOOL,
            request_hash=build_request_hash(
                ADJUST_APPLY_TOOL,
                {
                    "proposal_id": result["proposal_id"],
                    "approved": True,
                    "user_id": user.id,
                },
            ),
        )
        # 将 approval_id 关联到 proposal(不改变 status)
        repo.attach_approval(
            result["proposal_id"], user_id=user.id, approval_id=approval_id,
        )
        runtime_repo.update_job_input_ref(
            job_id,
            {
                **request_ref,
                "proposal_id": result["proposal_id"],
                "approval_id": approval_id,
            },
        )
        container.agent_run_manager.transition(
            run_id,
            "AWAITING_APPROVAL",
            phase="WAITING_FOR_APPROVAL",
            risk_level=result["risk_level"],
        )
    else:
        runtime_repo.update_job_input_ref(
            job_id,
            {**request_ref, "proposal_id": result["proposal_id"]},
        )
        container.agent_run_manager.transition(run_id, "SUCCEEDED", phase="IDLE")

    return AdjustmentAnalyzeOut(
        run_id=run_id,
        proposal_id=result["proposal_id"],
        risk_level=result["risk_level"],
        requires_approval=result["requires_approval"],
        approval_id=approval_id,
    )


@router.get("/campaigns/{campaign_id}/adjustment-proposals")
async def list_proposals(
    campaign_id: str,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
) -> list[AdjustmentProposalOut]:
    repo = _repo(container)
    rows = repo.list_proposals(campaign_id, user_id=user.id)
    return [_proposal_to_out(r) for r in rows]


@router.post("/adjustment-proposals/{proposal_id}/decision")
async def proposal_decision(
    proposal_id: str,
    body: AdjustmentDecisionIn,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> AdjustmentDecisionOut:
    """审批 adjustment proposal。

    路由只解析用户审批并创建命令:批准后的新版本由 Handler 经 Gateway 创建并激活,
    最终状态由 Worker 原子写入;拒绝则不创建任何命令,计划保持不变。
    """
    repo = _repo(container)
    proposal = repo.get_proposal(proposal_id, user_id=user.id)
    if not proposal:
        raise NotFoundError("proposal 不存在")

    approved = body.decision == "APPROVED"
    if proposal.approval_id:
        approval = container.agent_runtime_repository.get_approval(proposal.approval_id)
        if approval is not None and approval.status == ApprovalStatus.PENDING.value:
            # 路由只解析用户审批,不执行写操作;过期由 ApprovalGate 判定(过期绝不等于批准)。
            container.agent_approval_gate.resolve(
                proposal.approval_id,
                decision=body.decision,
                reason=body.reason,
                user_id=user.id,
            )
        elif approved and approval is not None and approval.status != ApprovalStatus.APPROVED.value:
            raise AgentRuntimeError(
                f"审批未通过({approval.status})，不能执行该调整",
                code="AGENT_INVALID_STATE",
                http_status=410 if approval.status == ApprovalStatus.EXPIRED.value else 409,
            )

    if not approved:
        # 拒绝只做收口:标记提案被拒并结束等待中的 Run,绝不改动计划。
        repo.resolve_proposal(
            proposal_id,
            user_id=user.id,
            status="rejected",
            approval_id=proposal.approval_id,
        )
        _settle_waiting_run(container, proposal.approval_id, "CANCELLED")
        return AdjustmentDecisionOut(
            proposal_id=proposal_id, status="rejected", new_version=None
        )

    if proposal.status != "pending":
        # 幂等:已处理的提案直接回显既有结果,不重复入队。
        return AdjustmentDecisionOut(
            proposal_id=proposal_id,
            status=proposal.status,
            new_version=proposal.target_version,
        )

    handler = container.agent_handler_registry.require(_ADJUST_APPLY_JOB_KIND)
    input_ref = {
        "proposal_id": proposal_id,
        "approved": True,
        "approval_id": proposal.approval_id,
    }
    created = container.agent_runtime_repository.create_job_with_run_and_event(
        user_id=user.id,
        job_kind=handler.job_kind,
        input_ref=input_ref,
        idempotency_key=(
            body.idempotency_key or idempotency_key or f"{_ADJUST_APPLY_JOB_KIND}:{proposal_id}"
        ),
        request_hash=build_request_hash(handler.job_kind, input_ref),
        handler_code=handler.code,
        handler_version=handler.version,
    )
    return AdjustmentDecisionOut(
        proposal_id=proposal_id, status="pending", pending=True, run_id=created["run_id"]
    )


__all__ = ["router"]
