from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from ...core.exceptions import AppException
from ...models.multi_role import UserRow
from ...schemas.final_review import AdjustmentDecision, CampaignCreate, CampaignOut, CampaignRunOut, DailyAgendaOut, DailyCheckinCreate, DailyItemOut, PlanVersionOut, RuntimeStepOut
from ...services.container import ServiceContainer, get_container
from ..deps import require_role


router=APIRouter(prefix="/final-review",tags=["final-review"])
def _container()->ServiceContainer:return get_container()
def _campaign(row:dict,view:dict|None=None)->CampaignOut:
    view=view or {}; run=view.get("run"); approval=view.get("approval")
    return CampaignOut(campaign_id=row["id"],exam_id=row["exam_id"],status=row["status"],active_version=row["active_version"],daily_capacity_minutes=row["daily_capacity_minutes"],created_at=row["created_at"],updated_at=row["updated_at"],job_id=run.job_id if run else None,run_id=run.id if run else None,run_status=run.status if run else None,run_phase=run.phase if run else None,pending_approval_id=approval.id if approval is not None and approval.status=="PENDING" else None)
def _version(row:dict)->PlanVersionOut:return PlanVersionOut(**{k:row[k] for k in ("plan_version_id","campaign_id","version","parent_version_id","content","content_hash","change_reason","created_at")})
def _agenda(row:dict)->DailyAgendaOut:return DailyAgendaOut(agenda_id=row["id"],campaign_id=row["campaign_id"],plan_version=row["plan_version"],agenda_date=row["agenda_date"],items=[DailyItemOut(item_id=i["id"],title=i["title"],duration_minutes=i["duration_minutes"],status=i["status"],external_task_id=i["external_task_id"]) for i in row["items"]])
def _run_view(campaign_id:str,view:dict)->CampaignRunOut:
    run=view.get("run"); approval=view.get("approval")
    return CampaignRunOut(campaign_id=campaign_id,job_id=run.job_id if run else None,run_id=run.id if run else None,status=run.status if run else None,phase=run.phase if run else None,progress_current=run.progress_current if run else 0,progress_total=run.progress_total if run else 0,approval_id=approval.id if approval else None,approval_status=approval.status if approval else None,approval_summary=approval.summary if approval else None,approval_expires_at=approval.expires_at if approval else None,approval_decided_at=approval.decided_at if approval else None,steps=[RuntimeStepOut(step_id=s.id,sequence=s.sequence,role=s.role,status=s.status,summary=s.safe_summary,started_at=s.started_at,finished_at=s.finished_at) for s in view.get("steps") or []])
def _with_runtime(c:ServiceContainer,user_id:str,row:dict)->CampaignOut:
    workflow=c.final_review_runtime_workflow
    run=workflow.latest_run_for_campaign(user_id=user_id,campaign_id=row["id"])
    return _campaign(row,workflow.view(user_id=user_id,run=run) if run is not None else None)
def _runtime_version(c:ServiceContainer,user_id:str,campaign_id:str,idempotency_key:str)->PlanVersionOut:
    workflow=c.final_review_runtime_workflow
    view=workflow.start(user_id=user_id,campaign_id=campaign_id,idempotency_key=idempotency_key)
    run=view.get("run")
    if run is None or run.status=="FAILED":
        raise AppException(code="AGENT_RUN_FAILED",http_status=409,message="复习计划运行失败，请查看运行时间线")
    version=c.final_review_service.latest_version(user_id,campaign_id)
    approval=view.get("approval")
    return _version(version).model_copy(update={"job_id":run.job_id,"run_id":run.id,"approval_id":approval.id if approval else None})

@router.post("/campaigns",response_model=CampaignOut)
def create_campaign(payload:CampaignCreate,user:UserRow=Depends(require_role("student")),c:ServiceContainer=Depends(_container)):
    return _campaign(c.final_review_service.campaign(user.id,payload.exam_id,payload.daily_capacity_minutes))

@router.get("/campaigns",response_model=list[CampaignOut])
def list_campaigns(user:UserRow=Depends(require_role("student")),c:ServiceContainer=Depends(_container)):
    return [_with_runtime(c,user.id,row) for row in c.final_review_repository.list_campaigns(user.id)]

@router.get("/campaigns/{campaign_id}",response_model=CampaignOut)
def get_campaign(campaign_id:str,user:UserRow=Depends(require_role("student")),c:ServiceContainer=Depends(_container)):
    row=c.final_review_repository.get_campaign(user.id,campaign_id)
    if not row:raise AppException(code="AGENT_PERMISSION_DENIED",http_status=404,message="复习活动不存在")
    return _with_runtime(c,user.id,row)

@router.get("/campaigns/{campaign_id}/run",response_model=CampaignRunOut)
def get_campaign_run(campaign_id:str,user:UserRow=Depends(require_role("student")),c:ServiceContainer=Depends(_container)):
    if not c.final_review_repository.get_campaign(user.id,campaign_id):raise AppException(code="AGENT_PERMISSION_DENIED",http_status=404,message="复习活动不存在")
    workflow=c.final_review_runtime_workflow
    run=workflow.latest_run_for_campaign(user_id=user.id,campaign_id=campaign_id)
    if run is None:raise AppException(code="AGENT_RUN_NOT_FOUND",http_status=404,message="该复习活动还没有运行记录")
    return _run_view(campaign_id,workflow.view(user_id=user.id,run=run))

@router.post("/campaigns/{campaign_id}/plans/generate",response_model=PlanVersionOut)
def generate_plan(campaign_id:str,idempotency_key:str|None=Header(default=None,alias="Idempotency-Key",max_length=128),user:UserRow=Depends(require_role("student")),c:ServiceContainer=Depends(_container)):
    """带 `Idempotency-Key` 时走 Runtime（生成后停在激活审批）；不带时保持旧的直接生成语义。"""
    if idempotency_key:
        return _runtime_version(c,user.id,campaign_id,idempotency_key)
    return _version(c.final_review_service.generate(user.id,campaign_id))

@router.get("/campaigns/{campaign_id}/plan-versions",response_model=list[PlanVersionOut])
def versions(campaign_id:str,user:UserRow=Depends(require_role("student")),c:ServiceContainer=Depends(_container)):
    if not c.final_review_repository.get_campaign(user.id,campaign_id):raise AppException(code="AGENT_PERMISSION_DENIED",http_status=404,message="复习活动不存在")
    return [_version(v) for v in c.final_review_repository.versions(campaign_id)]

@router.post("/campaigns/{campaign_id}/activate",response_model=CampaignOut)
def activate(campaign_id:str,user:UserRow=Depends(require_role("student")),c:ServiceContainer=Depends(_container)):
    workflow=c.final_review_runtime_workflow
    run=workflow.latest_run_for_campaign(user_id=user.id,campaign_id=campaign_id)
    if run is not None and workflow.pending_approval(user_id=user.id,run=run) is not None:
        raise AppException(code="AGENT_APPROVAL_REQUIRED",http_status=409,message="该复习计划需要先完成激活审批")
    return _campaign(c.final_review_service.activate(user.id,campaign_id))

@router.get("/campaigns/{campaign_id}/agendas/today",response_model=DailyAgendaOut)
def today(campaign_id:str,user:UserRow=Depends(require_role("student")),c:ServiceContainer=Depends(_container)):
    return _agenda(c.final_review_service.today(user.id,campaign_id))

@router.post("/daily-items/{item_id}/complete",response_model=DailyItemOut)
def complete_item(item_id:str,user:UserRow=Depends(require_role("student")),c:ServiceContainer=Depends(_container)):
    item=c.final_review_repository.complete_daily_item(user.id,item_id)
    if not item:raise AppException(code="AGENT_PERMISSION_DENIED",http_status=404,message="每日任务不存在")
    return DailyItemOut(item_id=item["id"],title=item["title"],duration_minutes=item["duration_minutes"],status=item["status"],external_task_id=item["external_task_id"])

@router.post("/campaigns/{campaign_id}/daily-checkins")
def checkin(campaign_id:str,payload:DailyCheckinCreate,user:UserRow=Depends(require_role("student")),c:ServiceContainer=Depends(_container)):
    if not c.final_review_repository.get_campaign(user.id,campaign_id):raise AppException(code="AGENT_PERMISSION_DENIED",http_status=404,message="复习活动不存在")
    return c.final_review_repository.add_checkin(campaign_id,user.id,payload.model_dump())

@router.post("/campaigns/{campaign_id}/adjustments/analyze")
def analyze(campaign_id:str,user:UserRow=Depends(require_role("student")),c:ServiceContainer=Depends(_container)):
    return c.final_review_service.analyze(user.id,campaign_id)

@router.post("/adjustment-proposals/{proposal_id}/decision")
def decide(proposal_id:str,payload:AdjustmentDecision,user:UserRow=Depends(require_role("student")),c:ServiceContainer=Depends(_container)):
    return c.final_review_service.decide(user.id,proposal_id,payload.decision)
