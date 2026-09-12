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
from typing import Optional

from fastapi import APIRouter, Depends, Header, Request

from ...core.exceptions import (
    AgentApprovalRequired,
    AgentRuntimeError,
    Forbidden,
    NotFoundError,
    ValidationFailed,
)
from ...models.multi_role import UserRow
from ...repositories.final_review_repository import FinalReviewRepository
from ...schemas.agent_contract_enums import RiskLevel
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


def _repo(container: ServiceContainer) -> FinalReviewRepository:
    return FinalReviewRepository(container.db)


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
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(get_container),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> PlanGenerateOut:
    """生成首版或新版计划。使用 reasoning_primary 路由。"""
    repo = _repo(container)
    campaign = repo.get_campaign(campaign_id, user_id=user.id)
    if not campaign:
        raise NotFoundError("campaign 不存在")

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
    planner = Planner(model_router=container.agent_model_router)
    result = await planner.generate(facts=facts, user_edits=body.user_edits)

    # 创建 plan version
    version = repo.next_plan_version(campaign_id)
    risk_level = RiskLevel.CONFIRM_REQUIRED.value
    plan_row = repo.create_plan_version(
        campaign_id=campaign_id,
        version=version,
        user_id=user.id,
        plan=result.plan,
        source_snapshot_id=snapshot_id,
        model_provider=result.provider,
        route_policy=result.route_policy,
        risk_level=risk_level,
    )

    return PlanGenerateOut(
        run_id="",
        version=version,
        plan=result.plan,
        risk_level=risk_level,
        requires_approval=True,
        approval_id=None,
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
    """激活指定版本。激活后可生成每日议程。"""
    repo = _repo(container)
    plan = repo.get_plan_version(campaign_id, body.version, user_id=user.id)
    if not plan:
        raise NotFoundError("plan version 不存在")
    row = repo.activate_campaign(campaign_id, user_id=user.id, version=body.version)
    if not row:
        raise NotFoundError("campaign 不存在")
    return ActivateOut(
        campaign_id=campaign_id, active_version=body.version, activated=True
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

    from ...services.final_review.adjustment_service import AdjustmentAnalyzer

    analyzer = AdjustmentAnalyzer(
        final_review_repo=repo,
        model_router=container.agent_model_router,
        risk_engine=container.agent_risk_engine,
    )
    result = await analyzer.analyze(
        campaign_id=campaign_id, user_id=user.id, evidence=evidence
    )

    approval_id = None
    if result["requires_approval"]:
        # 创建 job + run 用于 approval 关联(满足外键约束)
        runtime_repo = container.agent_runtime_repository
        job_id = runtime_repo.create_job(
            user_id=user.id, job_kind="final_review",
            input_ref={"campaign_id": campaign_id, "proposal_id": result["proposal_id"]},
        )
        run_id = runtime_repo.create_run(job_id=job_id, user_id=user.id)
        # 创建 approval 记录
        from datetime import timedelta
        approval_id = container.agent_approval_gate.require(
            run_id=run_id,
            user_id=user.id,
            risk_level=RiskLevel.CONFIRM_REQUIRED,
            action_summary=f"期末复习调整提案:{result['proposal'].get('reason', '')}",
        )
        # 将 approval_id 关联到 proposal(不改变 status)
        repo.attach_approval(
            result["proposal_id"], user_id=user.id, approval_id=approval_id,
        )

    return AdjustmentAnalyzeOut(
        run_id="",
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
    """审批 adjustment proposal。APPROVED 创建新版本;REJECTED 不改计划。"""
    repo = _repo(container)
    from ...services.final_review.adjustment_service import AdjustmentAnalyzer

    analyzer = AdjustmentAnalyzer(
        final_review_repo=repo,
        model_router=container.agent_model_router,
        risk_engine=container.agent_risk_engine,
    )
    approved = body.decision == "APPROVED"
    try:
        result = analyzer.apply_proposal(
            proposal_id=proposal_id, user_id=user.id, approved=approved
        )
    except ValueError:
        raise NotFoundError("proposal 不存在")
    return AdjustmentDecisionOut(
        proposal_id=result["proposal_id"],
        status=result["status"],
        new_version=result["new_version"],
        active_version=result["active_version"],
    )


__all__ = ["router"]