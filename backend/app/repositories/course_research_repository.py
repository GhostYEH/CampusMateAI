import hashlib,json
from datetime import datetime,timezone
from uuid import uuid4
from ..core.exceptions import AppException
from ..database.sqlite_db import Database
def _now():return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def _id(p):return f"{p}_{uuid4().hex}"
def _dump(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))
class CourseResearchRepository:
 def __init__(self,db:Database):self.db=db
 def create(self,user_id:str,payload:dict,key:str,effective_mode:str,roles:list[str],warnings:list[str])->tuple[dict,bool]:
  request_hash=hashlib.sha256(_dump(payload).encode()).hexdigest()
  with self.db.transaction() as conn:
   old=conn.execute("SELECT * FROM course_research_sessions WHERE user_id=? AND idempotency_key=?",(user_id,key)).fetchone()
   if old:
    if old["request_hash"]!=request_hash:raise AppException(code="AGENT_IDEMPOTENCY_CONFLICT",http_status=409,message="幂等键冲突")
    return dict(old),True
   rid=_id("research");now=_now();question_digest=hashlib.sha256(payload["question"].encode()).hexdigest()
   conn.execute("INSERT INTO course_research_sessions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(rid,user_id,payload.get("course_id"),question_digest,payload["mode"],effective_mode,payload["academic_policy"],_dump(payload["source_policy"]),"RUNNING",_dump(roles),_dump(warnings),key,request_hash,now,now))
   return dict(conn.execute("SELECT * FROM course_research_sessions WHERE id=?",(rid,)).fetchone()),False
 def finish(self,research_id:str,status:str,summary:str,sources:list[dict],warnings:list[str],roles:list[str])->dict:
  with self.db.transaction() as conn:
   for sequence,role in enumerate(roles, start=1):
    conn.execute("INSERT INTO course_research_steps VALUES(?,?,?,?,?,?,?)",(_id("step"),research_id,sequence,role,"SUCCEEDED",f"{role} 已完成受控处理",_now()))
   for source in sources:
    sid=_id("source");conn.execute("INSERT INTO course_research_sources VALUES(?,?,?,?,?,?,?,?)",(sid,research_id,source["source_type"],source["safe_label"],source.get("content_ref"),source["content_digest"],source["verification_status"],_now()))
   conn.execute("INSERT INTO course_research_reports VALUES(?,?,?,?,?,?)",(_id("report"),research_id,summary,"[]",None,_now()))
   conn.execute("UPDATE course_research_sessions SET status=?,warning_codes_json=?,updated_at=? WHERE id=?",(status,_dump(warnings),_now(),research_id))
  return self.get_by_id(research_id)
 def get_by_id(self,research_id:str,user_id:str|None=None)->dict|None:
  with self.db.query() as conn:
   row=conn.execute("SELECT * FROM course_research_sessions WHERE id=?"+(" AND user_id=?" if user_id else ""),(research_id,user_id) if user_id else (research_id,)).fetchone()
   if not row:return None
   data=dict(row);report=conn.execute("SELECT * FROM course_research_reports WHERE research_id=?",(research_id,)).fetchone();sources=conn.execute("SELECT * FROM course_research_sources WHERE research_id=? ORDER BY created_at,id",(research_id,)).fetchall()
   steps=conn.execute("SELECT * FROM course_research_steps WHERE research_id=? ORDER BY sequence",(research_id,)).fetchall()
  data["report_summary"]=report["summary"] if report else "";data["sources"]=[dict(s) for s in sources];data["steps"]=[dict(s) for s in steps];return data
