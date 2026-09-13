from __future__ import annotations

import json
from datetime import date

from ..core.exceptions import AppException
from ..repositories.final_review_repository import FinalReviewRepository
from ..repositories.personal_task_repository import PersonalTaskRepository

SOURCE_NAME = "期末复习计划"
SOURCE = "final_review"


class FinalReviewService:
    """期末复习领域服务。

    写入类方法接受可选的 `run_id`，便于 Runtime 工作流把领域写入归属到具体运行；
    不传时保持旧的直接调用语义，旧 HTTP 行为不变。
    """

    def __init__(self, repository: FinalReviewRepository, tasks: PersonalTaskRepository) -> None:
        self.repo,self.tasks=repository,tasks

    # ===== 活动与归属 =====

    def campaign(self,user_id:str,exam_id:str,capacity:int)->dict:
        if not self.repo.exam_owned(user_id,exam_id): raise AppException(code="AGENT_PERMISSION_DENIED",http_status=404,message="考试不存在")
        return self.repo.create_campaign(user_id,exam_id,capacity)[0]

    def verify_scope(self,user_id:str,campaign_id:str)->dict:
        """验证考试与复习活动归属；不通过时抛 404，不泄露他人资源是否存在。"""
        campaign=self.repo.get_campaign(user_id,campaign_id)
        if not campaign: raise AppException(code="AGENT_PERMISSION_DENIED",http_status=404,message="复习活动不存在")
        if not self.repo.exam_owned(user_id,campaign["exam_id"]): raise AppException(code="AGENT_PERMISSION_DENIED",http_status=404,message="考试不存在")
        return campaign

    # ===== 计划版本 =====

    def generate(self,user_id:str,campaign_id:str,run_id:str|None=None)->dict:
        campaign=self.repo.get_campaign(user_id,campaign_id)
        if not campaign: raise AppException(code="AGENT_PERMISSION_DENIED",http_status=404,message="复活动不存在")
        existing=self.repo.versions(campaign_id)
        if existing:return existing[-1]
        capacity=campaign["daily_capacity_minutes"]
        content={"days":[{"day_offset":0,"items":[{"title":"复习核心知识点","duration_minutes":min(45,capacity)},{"title":"完成诊断练习","duration_minutes":min(30,max(15,capacity-45))}]}],"explanation_codes":["EXAM_DATE_OBSERVED","CAPACITY_RESPECTED"]}
        return self.repo.create_version(campaign_id,content,"INITIAL_PLAN",created_by_run=run_id)

    def latest_version(self,user_id:str,campaign_id:str)->dict|None:
        campaign=self.repo.get_campaign(user_id,campaign_id)
        if not campaign: raise AppException(code="AGENT_PERMISSION_DENIED",http_status=404,message="复习活动不存在")
        versions=self.repo.versions(campaign_id)
        return versions[-1] if versions else None

    def today(self,user_id:str,campaign_id:str)->dict:
        campaign=self.repo.get_campaign(user_id,campaign_id)
        if not campaign or not campaign["active_version"]: raise AppException(code="AGENT_INVALID_STATE",http_status=409,message="计划尚未激活")
        versions=self.repo.versions(campaign_id); version=next(v for v in versions if v["version"]==campaign["active_version"])
        return self.repo.agenda(campaign_id,version["version"],date.today().isoformat(),version["content"]["days"][0]["items"])

    # ===== 激活与待办落地 =====

    def activate_version(self,user_id:str,campaign_id:str,version:int)->dict:
        campaign=self.repo.get_campaign(user_id,campaign_id)
        if not campaign:raise AppException(code="AGENT_PERMISSION_DENIED",http_status=404,message="复习活动不存在")
        self.repo.activate(campaign_id,version)
        return self.repo.get_campaign(user_id,campaign_id)

    def materialize_today(self,user_id:str,campaign_id:str)->int:
        """按 campaign:version:item 幂等键创建今日待办，已有 external_task_id 的条目直接跳过。"""
        agenda=self.today(user_id,campaign_id)
        created=0
        for item in agenda["items"]:
            if item["external_task_id"]:
                continue
            task=self.tasks.create_task(
                user_id=user_id,title=item["title"],source_name=SOURCE_NAME,
                source=SOURCE,external_id=f"{campaign_id}:{agenda['plan_version']}:{item['id']}",
            )
            self.repo.link_daily_item_task(item["id"],task.id)
            created+=1
        return created

    def today_task_count(self,user_id:str,campaign_id:str)->int:
        agenda=self.today(user_id,campaign_id)
        return self.repo.linked_item_count(campaign_id,agenda["plan_version"],agenda["agenda_date"])

    def activate(self,user_id:str,campaign_id:str)->dict:
        version=self.latest_version(user_id,campaign_id)
        if version is None:raise AppException(code="AGENT_INVALID_STATE",http_status=409,message="没有可激活计划")
        self.activate_version(user_id,campaign_id,version["version"])
        self.materialize_today(user_id,campaign_id)
        return self.repo.get_campaign(user_id,campaign_id)

    # ===== 调整建议 =====

    def analyze(self,user_id:str,campaign_id:str)->dict:
        campaign=self.repo.get_campaign(user_id,campaign_id); checkin=self.repo.latest_checkin(campaign_id)
        if not campaign or not checkin: raise AppException(code="AGENT_INVALID_STATE",http_status=409,message="缺少每日反馈")
        content={"capacity_multiplier":0.8 if checkin["completion_percent"]<60 else 1.0,"explanation_codes":["LOW_COMPLETION_OBSERVED"] if checkin["completion_percent"]<60 else ["PACE_MAINTAINED"]}
        return self.repo.create_proposal(campaign_id,campaign["active_version"] or 1,content,"CHECKIN_EVIDENCE")

    def decide(self,user_id:str,proposal_id:str,decision:str)->dict:
        proposal=self.repo.get_proposal(user_id,proposal_id)
        if not proposal or proposal["status"]!="PENDING":raise AppException(code="AGENT_INVALID_STATE",http_status=409,message="调整建议不可处理")
        self.repo.decide_proposal(proposal_id,decision)
        if decision=="REJECTED":return {"status":"REJECTED","new_version":None}
        versions=self.repo.versions(proposal["campaign_id"]); base=next(v for v in versions if v["version"]==proposal["base_version"])
        content=dict(base["content"]); content["adjustment"]=json.loads(proposal["content_json"])
        created=self.repo.create_version(proposal["campaign_id"],content,"APPROVED_ADJUSTMENT",base["plan_version_id"])
        self.repo.activate(proposal["campaign_id"],created["version"])
        return {"status":"APPROVED","new_version":created}
