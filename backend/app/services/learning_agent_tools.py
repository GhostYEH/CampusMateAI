from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ..core.exceptions import Forbidden, NotFoundError
from ..models.learning_plan import TASK_CREATING_ITEM_TYPES


ALLOWED_TOOL_SPECS = {
    "read_core_state": "READ",
    "read_knowledge_state": "READ",
    "read_personal_tasks": "READ",
    "search_course_materials": "READ",
    "propose_learning_plan": "PROPOSE",
    "suggest_create_personal_task": "PROPOSE",
    "suggest_open_course_material": "PROPOSE",
    "create_personal_task": "WRITE",
    "update_plan_created_task": "WRITE",
    "undo_plan_action": "WRITE",
}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    capability: str


class LearningAgentToolRegistry:
    """Closed tool registry. An LLM receives no callable for arbitrary services."""

    specs = {name: ToolSpec(name, capability) for name, capability in ALLOWED_TOOL_SPECS.items()}

    def __init__(self, container) -> None:
        self.container = container

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self.specs))

    def invoke(self, *, name: str, user_id: str, arguments: dict[str, Any] | None = None) -> Any:
        spec = self.specs.get(name)
        if spec is None:
            raise Forbidden("工具不在允许列表中")
        args = arguments or {}
        if name == "read_core_state":
            result = self.container.learner_state_service.project_user(
                user_id, as_of=datetime.now(timezone.utc), trigger="agent_read"
            )
            return [{"state_type": s.state_type, "value": s.value, "confidence": s.confidence, "data_quality": s.data_quality} for s in result.snapshots]
        if name == "read_knowledge_state":
            course_id = str(args.get("course_id", ""))
            if not course_id or not self.container.knowledge_repository.user_can_access_course(user_id=user_id, course_id=course_id):
                raise NotFoundError()
            result = self.container.knowledge_service.project_knowledge(
                user_id=user_id, course_id=course_id,
                as_of=datetime.now(timezone.utc), trigger="agent_read"
            )
            return [{"knowledge_code": s.scope_id, "value": s.value, "confidence": s.confidence, "data_quality": s.data_quality} for s in result.snapshots]
        if name == "read_personal_tasks":
            rows, _ = self.container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
            return [{"task_id": row.id, "course_id": row.course_id, "deadline": row.deadline, "status": row.status} for row in rows]
        if name == "search_course_materials":
            query = str(args.get("query", ""))[:256].strip()
            course_id = str(args.get("course_id", ""))
            if not query or not course_id or not self.container.knowledge_repository.user_can_access_course(user_id=user_id, course_id=course_id):
                return []
            # Reuse the existing retrieval index only as a relevance signal. Its
            # global document corpus is never returned unless a user-owned
            # course-content row is the allowlisted reference.
            try:
                self.container.retrieval.search(query, k=5)
            except Exception:
                return []
            rows = self.container.course_content_repository.list_items(user_id=user_id, course_id=course_id, include_stale=False, page=1, page_size=20)
            terms = set(query.casefold().split())
            return [{"content_ref": row.id, "title": row.title, "kind": row.kind, "relevance_score": 1.0 if terms.intersection(row.title.casefold().split()) else 0.0} for row in rows[:5]]
        if spec.capability == "PROPOSE":
            if name == "propose_learning_plan":
                return self.container.learning_planner_service.generate(user_id=user_id, **{k: args[k] for k in ("available_minutes", "course_id", "window_start", "window_end") if k in args})
            return {"proposal": name, "course_id": args.get("course_id"), "knowledge_code": args.get("knowledge_code")}
        if name == "create_personal_task":
            plan_id = str(args.get("plan_id", ""))
            item_id = str(args.get("item_id", ""))
            plan = self.container.learning_plan_repository.get_plan(plan_id, user_id=user_id)
            if plan is None or plan.status != "ACCEPTED":
                raise Forbidden("写工具需要已明确接受的计划")
            item = next((item for item in plan.items if item.item_id == item_id and item.item_type in TASK_CREATING_ITEM_TYPES), None)
            if item is None:
                raise NotFoundError()
            # The execution service uses the server-side item and ignores any
            # client/model supplied task fields.
            return self.container.learning_planner_service.execute(user_id=user_id, plan_id=plan_id)
        if name == "update_plan_created_task":
            plan_id = str(args.get("plan_id", ""))
            task_id = str(args.get("task_id", ""))
            plan = self.container.learning_plan_repository.get_plan(plan_id, user_id=user_id)
            task = self.container.personal_task_repository.get_task(task_id, user_id=user_id)
            if plan is None or plan.status not in {"ACCEPTED", "EXECUTED", "PARTIALLY_EXECUTED"} or task is None:
                raise NotFoundError()
            if task.source != "learning_plan" or not task.external_id or not task.external_id.startswith(plan_id + ":"):
                raise Forbidden("只能更新本计划创建的任务")
            fields = {key: value for key, value in args.items() if key in {"title", "deadline", "reminder_minutes"}}
            updated = self.container.personal_task_repository.update_task(task_id, user_id=user_id, fields=fields)
            return {"task_id": updated.id, "status": updated.status} if updated else {"task_id": task_id, "status": task.status}
        if name == "undo_plan_action":
            return self.container.learning_planner_service.undo(user_id=user_id, plan_id=str(args.get("plan_id", "")))
        raise Forbidden("写工具只能由服务端计划执行器调用")


__all__ = ["ALLOWED_TOOL_SPECS", "LearningAgentToolRegistry", "ToolSpec"]
