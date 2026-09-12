"""Adjustment Service —— Analyzer 产生 adjustment proposal(§8.1)。

关键约束:Analyzer 只产生 adjustment proposal,不直接修改 active plan。
应用 adjustment 创建新版本而非覆盖旧版本。

风险分级:
- AUTO_SAFE: 仅重排序,不改变总负荷(用户启用时显示建议)
- CONFIRM_REQUIRED: 新增/移动/删除任务或显著改变负荷 → ApprovalGate
- MANUAL_ONLY: 不会出现在期末复习场景(留给外部系统操作)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from ...repositories.final_review_repository import FinalReviewRepository
from ...schemas.agent_contract_enums import RiskLevel
from ..agent_runtime.risk_engine import RiskEngine
from ..llm.model_router import ModelRouter


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AdjustmentAnalyzer:
    """Analyzer:分析证据,产生 adjustment proposal。"""

    def __init__(
        self,
        *,
        final_review_repo: FinalReviewRepository,
        model_router: ModelRouter,
        risk_engine: RiskEngine,
    ) -> None:
        self._repo = final_review_repo
        self._router = model_router
        self._risk_engine = risk_engine

    async def analyze(
        self,
        *,
        campaign_id: str,
        user_id: str,
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        """分析证据,产生 adjustment proposal。

        evidence 包含:completed_items、missed_items、insufficient_time、difficulty_notes。
        返回 {proposal_id, risk_level, requires_approval, proposal}。
        不直接修改 active plan。
        """
        campaign = self._repo.get_campaign(campaign_id, user_id=user_id)
        if not campaign:
            raise ValueError("campaign 不存在或无权访问")
        if campaign.active_version is None:
            raise ValueError("campaign 尚未激活任何 plan version")

        source_version = campaign.active_version
        plan_row = self._repo.get_plan_version(campaign_id, source_version, user_id=user_id)
        if not plan_row:
            raise ValueError("active plan version 不存在")

        plan = json.loads(plan_row.plan_json)

        # 尝试模型分析
        proposal = await self._model_analyze(plan, evidence)
        if not proposal:
            # 降级到规则分析
            proposal = self._rule_analyze(plan, evidence)

        # 评定风险
        risk_level = self._assess_risk(proposal)
        assessment = self._risk_engine.assess(
            "plan.update", user_enabled_auto=(risk_level == RiskLevel.AUTO_SAFE.value)
        )
        # 取更严格的风险级别
        if risk_level == RiskLevel.CONFIRM_REQUIRED.value:
            requires_approval = True
        else:
            requires_approval = assessment.requires_approval

        # 持久化 proposal(不修改 plan)
        proposal_row = self._repo.create_proposal(
            campaign_id=campaign_id,
            user_id=user_id,
            source_version=source_version,
            proposal=proposal,
            risk_level=risk_level,
            model_provider=proposal.get("_provider", "deterministic"),
            route_policy="reasoning_primary",
            reason=proposal.get("reason"),
        )

        return {
            "proposal_id": proposal_row.proposal_id,
            "risk_level": risk_level,
            "requires_approval": requires_approval,
            "proposal": proposal,
        }

    def apply_proposal(
        self,
        *,
        proposal_id: str,
        user_id: str,
        approved: bool,
    ) -> dict[str, Any]:
        """应用 proposal。approved=True 时创建新版本;approved=False 不改计划。

        返回 {proposal_id, status, new_version, active_version}。
        """
        proposal_row = self._repo.get_proposal(proposal_id, user_id=user_id)
        if not proposal_row:
            raise ValueError("proposal 不存在或无权访问")
        if proposal_row.status != "pending":
            return {
                "proposal_id": proposal_id,
                "status": proposal_row.status,
                "new_version": proposal_row.target_version,
                "active_version": None,
            }

        if not approved:
            self._repo.resolve_proposal(
                proposal_id, user_id=user_id, status="rejected"
            )
            return {
                "proposal_id": proposal_id,
                "status": "rejected",
                "new_version": None,
                "active_version": None,
            }

        # approved:创建新版本
        campaign = self._repo.get_campaign(proposal_row.campaign_id, user_id=user_id)
        if not campaign:
            raise ValueError("campaign 不存在")

        source_plan_row = self._repo.get_plan_version(
            proposal_row.campaign_id, proposal_row.source_version, user_id=user_id
        )
        if not source_plan_row:
            raise ValueError("source plan version 不存在")

        source_plan = json.loads(source_plan_row.plan_json)
        proposal = json.loads(proposal_row.proposal_json)

        # 构建新 plan
        new_plan = self._apply_adjustment(source_plan, proposal)
        new_version = self._repo.next_plan_version(proposal_row.campaign_id)

        self._repo.create_plan_version(
            campaign_id=proposal_row.campaign_id,
            version=new_version,
            user_id=user_id,
            plan=new_plan,
            source_snapshot_id=source_plan_row.source_snapshot_id,
            model_provider=proposal_row.model_provider or "deterministic",
            route_policy="reasoning_primary",
            risk_level=proposal_row.risk_level,
            supersedes_version=proposal_row.source_version,
        )

        # 激活新版本
        self._repo.activate_campaign(
            proposal_row.campaign_id, user_id=user_id, version=new_version
        )

        # 标记 proposal
        self._repo.resolve_proposal(
            proposal_id,
            user_id=user_id,
            status="approved",
            target_version=new_version,
        )

        return {
            "proposal_id": proposal_id,
            "status": "approved",
            "new_version": new_version,
            "active_version": new_version,
        }

    async def _model_analyze(
        self, plan: dict, evidence: dict
    ) -> Optional[dict[str, Any]]:
        """尝试用模型分析。失败返回 None。"""
        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是期末复习调整分析助手。根据学生完成情况和反馈,"
                        "提出调整建议。输出 JSON,包含 adjustments 数组和 reason。"
                        "不要直接修改计划,只提供建议。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "missed_items": evidence.get("missed_items", []),
                            "insufficient_time": evidence.get("insufficient_time", False),
                            "difficulty_notes": evidence.get("difficulty_notes"),
                            "current_strategy": plan.get("strategy"),
                        },
                        ensure_ascii=False,
                    ),
                },
            ]
            result = await self._router.route(
                messages,
                route_policy="reasoning_primary",
                temperature=0.3,
                max_tokens=1024,
            )
            if result.response and result.response.content:
                data = json.loads(result.response.content)
                if isinstance(data, dict) and "adjustments" in data:
                    data["_provider"] = result.provider_name
                    return data
        except Exception:
            pass
        return None

    def _rule_analyze(self, plan: dict, evidence: dict) -> dict[str, Any]:
        """规则降级分析。"""
        missed = evidence.get("missed_items", [])
        insufficient = evidence.get("insufficient_time", False)

        adjustments = []
        if insufficient or missed:
            # 降低负荷建议
            adjustments.append({
                "action": "reduce_load",
                "reason": "学生报告时间不足或有未完成项",
                "reduce_minutes_per_day": 30,
            })
        if not adjustments:
            adjustments.append({
                "action": "no_change",
                "reason": "无足够证据建议调整",
            })

        return {
            "adjustments": adjustments,
            "reason": adjustments[0]["reason"],
            "_provider": "deterministic",
        }

    def _assess_risk(self, proposal: dict) -> str:
        """评定 proposal 风险级别。"""
        adjustments = proposal.get("adjustments", [])
        for adj in adjustments:
            action = adj.get("action", "")
            if action in ("add_task", "delete_task", "change_exam_priority"):
                return RiskLevel.CONFIRM_REQUIRED.value
            if action in ("reduce_load", "increase_load", "move_task"):
                return RiskLevel.CONFIRM_REQUIRED.value
        # 仅重排序或无变更 → AUTO_SAFE
        return RiskLevel.AUTO_SAFE.value

    def _apply_adjustment(self, source_plan: dict, proposal: dict) -> dict:
        """将 adjustment 应用到 plan,生成新 plan。"""
        new_plan = json.loads(json.dumps(source_plan))  # deep copy
        adjustments = proposal.get("adjustments", [])

        for adj in adjustments:
            action = adj.get("action", "")
            if action == "reduce_load":
                reduce = adj.get("reduce_minutes_per_day", 0)
                for day in new_plan.get("days", []):
                    if day.get("rest"):
                        continue
                    for item in day.get("items", []):
                        item["minutes"] = max(item.get("minutes", 0) - reduce // max(len(day["items"]), 1), 15)
                    day["minutes"] = sum(it.get("minutes", 0) for it in day.get("items", []))
            elif action == "increase_load":
                increase = adj.get("increase_minutes_per_day", 0)
                for day in new_plan.get("days", []):
                    if day.get("rest"):
                        continue
                    for item in day.get("items", []):
                        item["minutes"] = item.get("minutes", 0) + increase // max(len(day["items"]), 1)
                    day["minutes"] = sum(it.get("minutes", 0) for it in day.get("items", []))
            elif action == "reorder":
                # 重排序:交换 items 顺序
                for day in new_plan.get("days", []):
                    items = day.get("items", [])
                    if len(items) > 1:
                        day["items"] = list(reversed(items))

        new_plan["strategy"] = source_plan.get("strategy", "") + "_adjusted"
        new_plan["adjustment_applied"] = True
        return new_plan


__all__ = ["AdjustmentAnalyzer"]