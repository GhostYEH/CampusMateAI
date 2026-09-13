import json
from fastapi import APIRouter,Depends,Header
from ...models.multi_role import UserRow
from ...schemas.course_research import ResearchCreate,ResearchOut,ResearchSourceOut
from ...services.container import ServiceContainer,get_container
from ..deps import require_role
router=APIRouter(prefix="/course-research",tags=["course-research"])
def _c():return get_container()
def _out(row):return ResearchOut(research_id=row["id"],course_id=row["course_id"],requested_mode=row["requested_mode"],effective_mode=row["effective_mode"],academic_policy=row["academic_policy"],source_policy=json.loads(row["source_policy_json"]),status=row["status"],roles=json.loads(row["roles_json"]),warning_codes=json.loads(row["warning_codes_json"]),report_summary=row["report_summary"],sources=[ResearchSourceOut(source_id=s["id"],source_type=s["source_type"],safe_label=s["safe_label"],verification_status=s["verification_status"]) for s in row["sources"]],created_at=row["created_at"])
@router.post("/sessions",response_model=ResearchOut)
def create(payload:ResearchCreate,idempotency_key:str=Header(alias="Idempotency-Key",min_length=1,max_length=128),user:UserRow=Depends(require_role("student")),c:ServiceContainer=Depends(_c)):
 return _out(c.course_research_pipeline.run(user.id,payload.model_dump(mode="json"),idempotency_key))
@router.get("/sessions/{research_id}",response_model=ResearchOut)
def get(research_id:str,user:UserRow=Depends(require_role("student")),c:ServiceContainer=Depends(_c)):
 row=c.course_research_repository.get_by_id(research_id,user.id)
 if not row:
  from ...core.exceptions import AppException
  raise AppException(code="AGENT_PERMISSION_DENIED",http_status=404,message="研究任务不存在")
 return _out(row)
