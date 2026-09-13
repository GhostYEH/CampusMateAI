"""Planner —— 输出结构化 plan proposal(§8.1)。

使用 reasoning_primary 路由策略(智谱优先)。
模型输出为结构化 JSON plan,经 Pydantic 校验后才持久化。
失败时降级到确定性规则生成(fallback)。
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from ...schemas.agent_contract_enums import RiskLevel
from ..llm.model_router import ModelRouter


MAX_PLANNING_HORIZON_DAYS = 365


class PlannerOutput:
    """Planner 结构化输出。"""

    def __init__(
        self,
        *,
        plan: dict[str, Any],
        provider: str,
        route_policy: str,
        fallback_reason: Optional[str] = None,
    ) -> None:
        self.plan = plan
        self.provider = provider
        self.route_policy = route_policy
        self.fallback_reason = fallback_reason

    @property
    def used_fallback(self) -> bool:
        return self.fallback_reason is not None


def _deterministic_plan(
    *,
    exams: list[dict],
    daily_capacity_minutes: int,
    intensity: str,
    rest_days: list[str],
) -> dict[str, Any]:
    """确定性降级计划:按考试日期均匀分配复习任务。"""
    if not exams:
        return {"days": [], "total_minutes": 0, "strategy": "empty"}

    sorted_exams = sorted(exams, key=lambda e: e.get("exam_date", ""))
    today = datetime.now(timezone.utc).date()
    # 取最早考试日期作为目标
    try:
        earliest = datetime.fromisoformat(sorted_exams[0]["exam_date"]).date()
    except (ValueError, KeyError):
        earliest = today + timedelta(days=14)

    requested_days = max((earliest - today).days, 1)
    days_available = min(requested_days, MAX_PLANNING_HORIZON_DAYS)
    intensity_factor = {"low": 0.6, "medium": 1.0, "high": 1.3}.get(intensity, 1.0)
    daily_minutes = int(daily_capacity_minutes * intensity_factor)

    days: list[dict[str, Any]] = []
    rest_set = {d.lower() for d in rest_days}
    weekday_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

    for i in range(days_available):
        d = today + timedelta(days=i)
        wd = weekday_names[d.weekday()]
        if wd in rest_set:
            days.append({"date": d.isoformat(), "items": [], "minutes": 0, "rest": True})
            continue
        items = []
        for exam in sorted_exams:
            course = exam.get("course_name", "复习")
            items.append({
                "title": f"{course} 复习",
                "course_name": course,
                "minutes": max(daily_minutes // len(sorted_exams), 15),
            })
        days.append({
            "date": d.isoformat(),
            "items": items,
            "minutes": sum(it["minutes"] for it in items),
            "rest": False,
        })

    return {
        "days": days,
        "total_minutes": sum(d["minutes"] for d in days),
        "strategy": "deterministic_even_split",
        "planning_horizon_days": days_available,
        "planning_horizon_truncated": requested_days > days_available,
        "target_exams": [e.get("id", "") for e in sorted_exams],
    }


def _build_planner_prompt(facts: dict[str, Any]) -> list[dict]:
    """构建 planner 模型 prompt。不包含敏感数据。"""
    exams_summary = [
        {"id": e.get("id"), "course": e.get("course_name"), "date": e.get("exam_date")}
        for e in facts.get("exams", [])
    ]
    system_msg = (
        "你是期末复习计划助手。根据学生考试安排和每日容量,生成结构化复习计划。"
        "输出 JSON,包含 days 数组,每个 day 有 date/items/minutes。"
        "items 中每个 item 有 title/course_name/minutes。"
        "不要包含敏感个人信息。"
    )
    user_msg = json.dumps(
        {
            "exams": exams_summary,
            "daily_capacity_minutes": facts.get("daily_capacity_minutes"),
            "intensity": facts.get("intensity"),
            "rest_days": facts.get("rest_days"),
            "preferred_periods": facts.get("preferred_periods"),
        },
        ensure_ascii=False,
    )
    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


def _parse_model_plan(content: str) -> Optional[dict[str, Any]]:
    """解析模型输出为 plan dict。失败返回 None。"""
    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    if "days" not in data or not isinstance(data["days"], list):
        return None
    return data


class Planner:
    """期末复习计划生成器。"""

    def __init__(self, *, model_router: ModelRouter) -> None:
        self._router = model_router

    async def generate(
        self,
        *,
        facts: dict[str, Any],
        user_edits: Optional[dict[str, Any]] = None,
        run_id: Optional[str] = None,
    ) -> PlannerOutput:
        """生成结构化 plan。模型失败降级到确定性规则。"""
        exams = facts.get("exams", [])
        daily_capacity = facts.get("daily_capacity_minutes", 120)
        intensity = facts.get("intensity", "medium")
        rest_days = facts.get("rest_days", [])

        # 尝试模型路由
        messages = _build_planner_prompt(facts)
        try:
            result = await self._router.route(
                messages,
                route_policy="reasoning_primary",
                temperature=0.3,
                max_tokens=2048,
                run_id=run_id,
            )
            if result.response and result.response.content:
                plan = _parse_model_plan(result.response.content)
                if plan:
                    # 合并用户编辑
                    if user_edits:
                        plan["user_edits"] = user_edits
                    return PlannerOutput(
                        plan=plan,
                        provider=result.provider_name,
                        route_policy="reasoning_primary",
                        fallback_reason=result.fallback_reason,
                    )
        except Exception:
            pass

        # 降级到确定性规则
        plan = _deterministic_plan(
            exams=exams,
            daily_capacity_minutes=daily_capacity,
            intensity=intensity,
            rest_days=rest_days,
        )
        if user_edits:
            plan["user_edits"] = user_edits
        return PlannerOutput(
            plan=plan,
            provider="deterministic",
            route_policy="reasoning_primary",
            fallback_reason="model_unavailable_or_invalid_output",
        )


__all__ = ["Planner", "PlannerOutput"]
