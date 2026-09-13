from __future__ import annotations

from fastapi import APIRouter, Depends

from ...core.exceptions import AppException
from ...models.multi_role import UserRow
from ...schemas.final_review import AdjustmentDecision, CampaignCreate, CampaignOut, DailyAgendaOut, DailyCheckinCreate, DailyItemOut, PlanVersionOut
from ...services.container import ServiceContainer, get_container
from ..deps import require_role


router=APIRouter(prefix="/final-review",tags=["final-review"])
def _container()->ServiceContainer:return get_container()
def _campaign(row:dict)->CampaignOut:return CampaignOut(campaign_id=row["id"],exam_id=row["exam_id"],status=row["status"],active_version=row["active_version"],daily_capacity_minutes=row["daily_capacity_minutes"],created_at=row["created_at"],updated_at=row["updated_at"])
def _version(row:dict)->PlanVersionOut:return PlanVersionOut(**{k:row[k] for k in ("plan_version_id","campaign_id","version","parent_version_id","content","content_hash","change_reason","created_at")})
def _agenda(row:dict)->DailyAgendaOut:return DailyAgendaOut(agenda_id=row["id"],campaign_id=row["campaign_id"],plan_version=row["plan_version"],agenda_date=row["agenda_date"],items=[DailyItemOut(item_id=i["id"],title=i["title"],duration_minutes=i["duration_minutes"],status=i["status"],external_task_id=i["external_task_id"]) for i in row["items"]])

@router.post("/campaigns",response_model=CampaignOut)
def create_campaign(payload:CampaignCreate,user:UserRow=Depends(require_role("student")),c:ServiceContainer=Depends(_container)):
    return _campaign(c.final_review_service.campaign(user.id,payload.exam_id,payload.daily_capacity_minutes))

@router.get("/campaigns",response_model=list[CampaignOut])
def list_campaigns(user:UserRow=Depends(require_role("student")),c:ServiceContainer=Depends(_container)):
    return [_campaign(row) for row in c.final_review_repository.list_campaigns(user.id)]

@router.get("/campaigns/{campaign_id}",response_model=CampaignOut)
def get_campaign(campaign_id:str,user:UserRow=Depends(require_role("student")),c:ServiceContainer=Depends(_container)):
    row=c.final_review_repository.get_campaign(user.id,campaign_id)
    if not row:raise AppException(code="AGENT_PERMISSION_DENIED",http_status=404,message="复习活动不存在")
    return _campaign(row)

@router.post("/campaigns/{campaign_id}/plans/generate",response_model=PlanVersionOut)
def generate_plan(campaign_id:str,user:UserRow=Depends(require_role("student")),c:ServiceContainer=Depends(_container)):
    return _version(c.final_review_service.generate(user.id,campaign_id))

@router.get("/campaigns/{campaign_id}/plan-versions",response_model=list[PlanVersionOut])
def versions(campaign_id:str,user:UserRow=Depends(require_role("student")),c:ServiceContainer=Depends(_container)):
    if not c.final_review_repository.get_campaign(user.id,campaign_id):raise AppException(code="AGENT_PERMISSION_DENIED",http_status=404,message="复习活动不存在")
    return [_version(v) for v in c.final_review_repository.versions(campaign_id)]

@router.post("/campaigns/{campaign_id}/activate",response_model=CampaignOut)
def activate(campaign_id:str,user:UserRow=Depends(require_role("student")),c:ServiceContainer=Depends(_container)):
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
