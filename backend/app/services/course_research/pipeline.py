import hashlib
from ...core.exceptions import AppException
from ...models.course_research import VerifiedResearchSource
from ...repositories.course_research_repository import CourseResearchRepository
from .citation_verifier import order_verified_sources
from .policy import decide_research_policy
class CourseResearchPipeline:
 BASE_ROLES=["coordinator","course_researcher"]
 FINAL_ROLES=["citation_verifier","tutor","critic","synthesizer"]
 def __init__(self,repository:CourseResearchRepository,db):self.repo,self.db=repository,db
 def run(self,user_id:str,payload:dict,idempotency_key:str)->dict:
  if payload.get("course_id"):
   with self.db.query() as conn:
    owned=conn.execute(
     """SELECT 1 FROM courses c WHERE c.id=? AND (c.owner_user_id=? OR EXISTS (
        SELECT 1 FROM class_groups cg JOIN enrollments e ON e.class_group_id=cg.id
        WHERE cg.course_id=c.id AND e.user_id=? AND e.status='active' AND e.member_role='student'))""",
     (payload["course_id"],user_id,user_id),
    ).fetchone()
   if not owned:raise AppException(code="AGENT_PERMISSION_DENIED",http_status=404,message="课程不存在")
  decision=decide_research_policy(payload["mode"],payload["academic_policy"])
  effective=decision.effective_mode
  warnings=list(decision.warning_codes)
  if payload["source_policy"]["allow_web"]:
   warnings.append("WEB_RETRIEVAL_NOT_CONFIGURED")
  roles=self.BASE_ROLES+(["web_researcher"] if payload["source_policy"]["allow_web"] else [])+self.FINAL_ROLES
  row,reused=self.repo.create(user_id,payload,idempotency_key,effective,roles,warnings)
  if reused:return self.repo.get_by_id(row["id"])
  source_models=[]
  if payload.get("course_id"):
   source_models=[VerifiedResearchSource(source_type="COURSE_METADATA",safe_label="已授权课程资料",content_digest=hashlib.sha256(payload["course_id"].encode()).hexdigest())]
  sources=[source.__dict__ for source in order_verified_sources(source_models)]
  status="SUCCEEDED" if sources else "PARTIAL";summary="已根据授权来源生成学习提示。" if sources else "当前没有可验证课程来源，仅返回问题拆解建议。"
  if not sources:warnings.append("NO_VERIFIED_SOURCES")
  return self.repo.finish(row["id"],status,summary,sources,warnings,roles)
