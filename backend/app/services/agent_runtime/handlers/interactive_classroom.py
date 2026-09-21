"""互动课堂的受管工具与 Handler —— CPM 触发 magicclass 生成的唯一合法路径。

为什么要有这一层：
- 创建互动课堂会调用外部 magicclass 并**产生真实费用**，属于有成本的外部动作。
  它必须经过 `ToolInvocationGateway` 的完整流水线：角色授权、资源归属、
  `RiskEngine` 定级、`ApprovalGate` 审批、`claim_tool_call` 幂等、审计事件。
  LLM / counselor 绝不能直接调用 `magicclassClient`。
- 只读工具（inspect/list/propose/status/open）声明为 `AUTO_SAFE`，
  可以在学生提问时直接调用，不产生任何外部任务与费用。
- `interactive_classroom.generate` 声明为 `CONFIRM_REQUIRED + requires_approval`，
  学生必须明确确认后才真正生成。

幂等与"确认后参数变化必须重新确认"：
- 幂等键按 Run 固定（`run:{run_id}`），而 Gateway 的声明键是
  `(run_id, idempotency_key, request_hash)`，其中 `request_hash` 由**参数**决定。
  因此：参数完全相同 → 命中既有声明，重放首次结果，副作用恰好一次；
  参数被改动 → request_hash 变化 → 生成**新**的声明，也就必须重新走一次审批。
  这正是"确认绑定具体 user_id/course_id/请求内容"的语义。

隐私约束：工具入参与结果只保留业务引用（course_id / session_id / 状态 / 计数），
不保存 prompt、完整模型响应、访问码或 Cookie。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from ....core.exceptions import AgentRuntimeError, CourseNotFound, Forbidden
from ....schemas.agent_contract_enums import RiskLevel
from ..tool_gateway import ToolInvocationGateway, ToolInvocationRequest
from ..tool_registry import ToolSpec
from .base import HandlerContext, HandlerResult, RecoveryAction, RecoveryDecision

class ContainerRef:
    """延迟解析 ServiceContainer。

    工具与 Handler 的注册发生在 `ServiceContainer` 构造**之前**（注册表要先冻结
    再构造容器），因此构建工具时只能拿到一个占位引用，执行期才真正解析。
    """

    def __init__(self) -> None:
        self._container: Any = None

    def bind(self, container: Any) -> None:
        self._container = container

    def __call__(self) -> Any:
        if self._container is None:
            raise AgentRuntimeError(
                "服务容器尚未就绪", code="AGENT_INVALID_STATE", http_status=409
            )
        return self._container


INSPECT_TOOL = "interactive_classroom.inspect_context"
LIST_TOOL = "interactive_classroom.list"
PROPOSE_TOOL = "interactive_classroom.propose"
GENERATE_TOOL = "interactive_classroom.generate"
STATUS_TOOL = "interactive_classroom.status"
OPEN_TOOL = "interactive_classroom.open"

_STAGE_APPLIED = "APPLIED"
_STAGE_AWAITING_APPROVAL = "AWAITING_APPROVAL"

# 意图标签（与后端 schemas/magicclass.py 的 MODE_INTENT_LABELS 一致）
_MODE_LABELS: Dict[str, str] = {
    "adaptive": "自动推荐",
    "explain": "概念讲解",
    "quiz": "练习测验",
    "simulation": "实验模拟",
    "visualization": "3D/可视化",
    "mindmap": "思维导图",
    "coding": "编程实验",
    "pbl": "项目式学习",
    "review": "考前复习",
}


def classroom_deep_link(course_id: str, session_id: str = "") -> str:
    """CampusMate **内部**深链。绝不返回 magic class 内部地址或凭据。"""
    base = f"/courses/{course_id}?tab=mentoring"
    return f"{base}&session={session_id}" if session_id else base


# ===== 参数模型 =====


class _OwnedArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: str = Field(..., min_length=1, max_length=128)
    user_id: str = Field(..., min_length=1, max_length=128)


class ProposeArgs(_OwnedArgs):
    mode: str = Field("adaptive", max_length=32)


class GenerateArgs(_OwnedArgs):
    mode: str = Field("adaptive", max_length=32)
    learning_objective: Optional[str] = Field(None, max_length=500)
    current_difficulty: Optional[str] = Field(None, max_length=500)
    desired_duration_minutes: Optional[int] = Field(None, ge=5, le=180)
    difficulty_level: Optional[str] = Field(None, max_length=16)
    wants_more_practice: bool = False
    selected_material_ids: list[str] = Field(default_factory=list, max_length=20)


class SessionArgs(_OwnedArgs):
    session_id: str = Field(..., min_length=1, max_length=128)


class InteractiveClassroomInput(BaseModel):
    """`interactive_classroom` 命令输入。未知键保持透传，不破坏旧客户端。"""

    model_config = ConfigDict(extra="allow")

    course_id: str = Field(..., min_length=1, max_length=128)
    mode: str = Field("adaptive", max_length=32)
    learning_objective: Optional[str] = Field(None, max_length=500)
    current_difficulty: Optional[str] = Field(None, max_length=500)
    desired_duration_minutes: Optional[int] = Field(None, ge=5, le=180)
    difficulty_level: Optional[str] = Field(None, max_length=16)
    wants_more_practice: bool = False
    selected_material_ids: list[str] = Field(default_factory=list, max_length=20)
    # 注意：**不接受**客户端提供的 approval_id。审批 id 只能来自服务端 checkpoint
    # 或工具调用自己记录的值，否则一次批准可以被复用到别的课程/别的参数上。
    user_id: Optional[str] = None


# ===== 工具构造 =====


def _owner_from_args(arguments: dict) -> Optional[str]:
    value = (arguments or {}).get("user_id")
    return str(value) if value else None


def _resolve_course(container: Any, user_id: str, course_id: str):
    """复用统一课程访问策略；工具层不得绕过它。"""
    user = container.user_repository.get_user_by_id(user_id)
    if user is None:
        raise AgentRuntimeError(
            "用户不存在", code="AGENT_RUN_NOT_FOUND", http_status=404
        )
    try:
        from ...magicclass.course_context import assert_course_access

        return assert_course_access(container, user, course_id), user
    except CourseNotFound as exc:
        raise AgentRuntimeError(
            "课程不存在", code="AGENT_RUN_NOT_FOUND", http_status=404
        ) from exc
    except Forbidden as exc:
        raise AgentRuntimeError(
            "无权访问该课程", code="AGENT_TOOL_REJECTED", http_status=403
        ) from exc


def _context_and_plan(container: Any, user: Any, course: Any, mode: str) -> Dict[str, Any]:
    """只读地构造课程上下文与生成计划（不创建任何外部任务）。"""
    from dataclasses import replace

    from ...magicclass.course_context import ContextLimits, build_learning_context
    from ...magicclass.requirement_builder import choose_adaptive_mode, normalize_mode

    limits = ContextLimits(
        total_chars=container.settings.magicclass_course_context_max_chars
    )
    context = build_learning_context(container, user, course, limits=limits)
    requested = normalize_mode(mode)
    resolved = requested
    adaptive_reason = None
    if requested == "adaptive":
        signals = replace(
            context.signals,
            external_3d_available=bool(container.settings.magicclass_external_3d_available),
        )
        resolved, adaptive_reason = choose_adaptive_mode(signals)
    return {
        "context": context,
        "requested_mode": requested,
        "mode": resolved,
        "mode_label": _MODE_LABELS.get(resolved, resolved),
        "adaptive_reason": adaptive_reason,
    }


def _material_refs(context: Any) -> list[dict]:
    return [
        {"id": ref.id, "title": ref.title, "kind": ref.kind}
        for ref in getattr(context, "materials", ()) or ()
    ]


def build_inspect_context_tool(container: Any) -> ToolSpec:
    async def _execute(arguments: dict) -> dict:
        course, user = _resolve_course(
            container, arguments["user_id"], arguments["course_id"]
        )
        plan = _context_and_plan(container, user, course, arguments.get("mode", "adaptive"))
        status = await container.magicclass_classroom_service.status()
        context = plan["context"]
        return {
            "course_id": course.id,
            "course_name": course.name,
            "materials": _material_refs(context),
            "context_sources": dict(context.sources),
            "context_updated_at": dict(context.updated_at),
            "context_warnings": list(context.warnings),
            "context_truncated": bool(context.truncated),
            "capabilities": dict(status.get("capabilities") or {}),
            "external_3d_available": bool(status.get("external_3d_available", True)),
            "can_generate": bool(status.get("enabled")),
            "reason": status.get("reason"),
        }

    return ToolSpec(
        tool_code=INSPECT_TOOL,
        resource="interactive_classroom_context",
        action="read",
        risk_level=RiskLevel.AUTO_SAFE,
        args_model=_OwnedArgs,
        ownership_resolver=_owner_from_args,
        executor=_execute,
        result_builder=lambda outcome: outcome,
        summary_builder=lambda args: f"读取课程 {args.get('course_id')} 的学习上下文",
    )


def build_list_tool(container: Any) -> ToolSpec:
    async def _execute(arguments: dict) -> dict:
        course, user = _resolve_course(
            container, arguments["user_id"], arguments["course_id"]
        )
        service = container.magicclass_classroom_service
        items = service.list_classrooms(user_id=user.id, course_id=course.id)
        return {
            "course_id": course.id,
            "items": [
                {
                    "session_id": item.get("session_id"),
                    "mode": item.get("mode"),
                    "mode_label": _MODE_LABELS.get(item.get("mode"), item.get("mode")),
                    "scenes_count": item.get("scenes_count"),
                    "created_at": item.get("created_at"),
                    "deep_link": classroom_deep_link(course.id, item.get("session_id") or ""),
                }
                for item in items
            ],
        }

    return ToolSpec(
        tool_code=LIST_TOOL,
        resource="interactive_classroom",
        action="list",
        risk_level=RiskLevel.AUTO_SAFE,
        args_model=_OwnedArgs,
        ownership_resolver=_owner_from_args,
        executor=_execute,
        result_builder=lambda outcome: outcome,
        summary_builder=lambda args: f"列出课程 {args.get('course_id')} 的历史课堂",
    )


def build_propose_tool(container: Any) -> ToolSpec:
    async def _execute(arguments: dict) -> dict:
        course, user = _resolve_course(
            container, arguments["user_id"], arguments["course_id"]
        )
        plan = _context_and_plan(container, user, course, arguments.get("mode", "adaptive"))
        status = await container.magicclass_classroom_service.status()
        context = plan["context"]
        return {
            "course_id": course.id,
            "course_name": course.name,
            "requested_mode": plan["requested_mode"],
            "mode": plan["mode"],
            "mode_label": plan["mode_label"],
            "adaptive_reason": plan["adaptive_reason"],
            "materials": _material_refs(context),
            "context_warnings": list(context.warnings),
            "intent_note": "内容形态只是生成意图，最终包含哪些形式由生成器根据课程内容决定。",
            "can_generate": bool(status.get("enabled")),
            "reason": status.get("reason"),
        }

    return ToolSpec(
        tool_code=PROPOSE_TOOL,
        resource="interactive_classroom",
        action="propose",
        risk_level=RiskLevel.AUTO_SAFE,
        args_model=ProposeArgs,
        ownership_resolver=_owner_from_args,
        executor=_execute,
        result_builder=lambda outcome: outcome,
        summary_builder=lambda args: (
            f"为课程 {args.get('course_id')} 提出互动课堂方案（{args.get('mode')}）"
        ),
    )


def build_generate_tool(container_provider) -> ToolSpec:
    """真正调用 magic class 的工具 —— 必须审批，且副作用恰好一次。"""

    async def _execute(arguments: dict) -> dict:
        container = container_provider()
        course, user = _resolve_course(
            container, arguments["user_id"], arguments["course_id"]
        )
        from ...magicclass.course_context import ContextLimits, build_learning_context
        from ...magicclass.requirement_builder import (
            GenerationRequestSnapshot,
            StudentBrief,
        )

        service = container.magicclass_classroom_service
        limits = ContextLimits(
            total_chars=container.settings.magicclass_course_context_max_chars
        )
        selected = list(arguments.get("selected_material_ids") or [])
        mode = str(arguments.get("mode", "adaptive"))
        context = build_learning_context(
            container, user, course, limits=limits, selected_material_ids=selected
        )
        # 用**服务端解析出的**授权资料 id 固化快照：客户端提交的 id 若越权/不存在，
        # 会被 course_context 过滤掉并记录在 unresolved_material_ids 里，绝不写进快照。
        snapshot = GenerationRequestSnapshot(
            requested_mode=mode,
            mode=mode,
            learning_objective=arguments.get("learning_objective"),
            current_difficulty=arguments.get("current_difficulty"),
            desired_duration_minutes=arguments.get("desired_duration_minutes"),
            difficulty_level=arguments.get("difficulty_level"),
            wants_more_practice=bool(arguments.get("wants_more_practice")),
            selected_material_ids=tuple(context.selected_material_ids),
        )
        resolved = set(context.selected_material_ids)
        brief = StudentBrief(
            learning_objective=snapshot.learning_objective,
            current_difficulty=snapshot.current_difficulty,
            desired_duration_minutes=snapshot.desired_duration_minutes,
            difficulty_level=snapshot.difficulty_level,
            wants_more_practice=snapshot.wants_more_practice,
            selected_material_titles=tuple(
                ref.title for ref in context.materials if ref.id in resolved
            ),
        )
        session = await service.generate(
            user_id=user.id,
            course_id=course.id,
            context=context,
            mode=mode,
            brief=brief,
            # CPM 生成的课堂同样要能被 retry，且不丢个性化
            request_snapshot=snapshot,
        )
        return {
            "course_id": course.id,
            "session_id": session.session_id,
            "status": session.status,
            "step": session.step,
            "mode": session.mode,
            "mode_label": _MODE_LABELS.get(session.mode, session.mode),
            "adaptive_reason": session.adaptive_reason,
            "materials_unresolved": list(context.unresolved_material_ids),
            "deep_link": classroom_deep_link(course.id, session.session_id),
        }

    return ToolSpec(
        tool_code=GENERATE_TOOL,
        resource="interactive_classroom",
        action="generate",
        risk_level=RiskLevel.CONFIRM_REQUIRED,
        requires_approval=True,
        args_model=GenerateArgs,
        ownership_resolver=_owner_from_args,
        executor=_execute,
        result_builder=lambda outcome: outcome,
        summary_builder=lambda args: (
            f"为课程 {args.get('course_id')} 生成互动课堂（{args.get('mode')}）"
        ),
    )


def build_status_tool(container: Any) -> ToolSpec:
    async def _execute(arguments: dict) -> dict:
        course, user = _resolve_course(
            container, arguments["user_id"], arguments["course_id"]
        )
        service = container.magicclass_classroom_service
        session = service.get_session(
            user_id=user.id, course_id=course.id, session_id=arguments["session_id"]
        )
        if session is None:
            raise AgentRuntimeError(
                "课堂生成任务不存在", code="AGENT_RUN_NOT_FOUND", http_status=404
            )
        session = await service.poll(session)
        return {
            "course_id": course.id,
            "session_id": session.session_id,
            "status": session.status,
            "step": session.step,
            "progress": session.progress,
            "message": session.message,
            "error": session.error,
            "error_code": session.error_code,
            "partial": bool(session.partial),
            "mode": session.mode,
            "mode_label": _MODE_LABELS.get(session.mode, session.mode),
            "deep_link": classroom_deep_link(course.id, session.session_id),
        }

    return ToolSpec(
        tool_code=STATUS_TOOL,
        resource="interactive_classroom",
        action="read",
        risk_level=RiskLevel.AUTO_SAFE,
        args_model=SessionArgs,
        ownership_resolver=_owner_from_args,
        executor=_execute,
        result_builder=lambda outcome: outcome,
        summary_builder=lambda args: f"查询课堂任务 {args.get('session_id')} 的状态",
    )


def build_open_tool(container_provider) -> ToolSpec:
    """只返回 CampusMate 内部深链，绝不返回 magic class 地址或凭据。"""

    async def _execute(arguments: dict) -> dict:
        container = container_provider()
        course, user = _resolve_course(
            container, arguments["user_id"], arguments["course_id"]
        )
        service = container.magicclass_classroom_service
        session = service.get_session(
            user_id=user.id, course_id=course.id, session_id=arguments["session_id"]
        )
        if session is None:
            raise AgentRuntimeError(
                "课堂生成任务不存在", code="AGENT_RUN_NOT_FOUND", http_status=404
            )
        # 只有真实成功终态才允许"打开"；不臆造可打开的地址。
        ready = session.status == "succeeded" and bool(session.classroom_id)
        return {
            "course_id": course.id,
            "session_id": session.session_id,
            "status": session.status,
            "ready": ready,
            "deep_link": classroom_deep_link(course.id, session.session_id) if ready else None,
        }

    return ToolSpec(
        tool_code=OPEN_TOOL,
        resource="interactive_classroom",
        action="read",
        risk_level=RiskLevel.AUTO_SAFE,
        args_model=SessionArgs,
        ownership_resolver=_owner_from_args,
        executor=_execute,
        result_builder=lambda outcome: outcome,
        summary_builder=lambda args: f"打开课堂 {args.get('session_id')}",
    )


def build_interactive_classroom_tools(container_provider) -> tuple[ToolSpec, ...]:
    return (
        build_inspect_context_tool(container_provider),
        build_list_tool(container_provider),
        build_propose_tool(container_provider),
        build_generate_tool(container_provider),
        build_status_tool(container_provider),
        build_open_tool(container_provider),
    )


# ===== Handler =====


class InteractiveClassroomGenerateHandler:
    """经 Gateway 执行的互动课堂生成。审批通过后才真正调用 magic class。

    注意：`code` 必须与 `job_kind` 一致 —— Job 记录里存的是 `handler_code`，
    而 `JobHandlerRegistry` 是按 `job_kind` 索引的，两者不同会导致崩溃恢复时
    找不到处理器（表现为运行被误判为 `AGENT_CAPABILITY_DISABLED`）。
    """

    code = "interactive_classroom"
    version = "1.0.0"
    job_kind = "interactive_classroom"
    enabled = True
    input_model: type[BaseModel] = InteractiveClassroomInput
    max_attempts = 3
    tools: tuple[str, ...] = (GENERATE_TOOL,)
    role_code = "tutor"

    def __init__(self, gateway: ToolInvocationGateway, *, enabled: bool = True) -> None:
        self._gateway = gateway
        self.enabled = enabled

    def _arguments(self, payload: InteractiveClassroomInput, context: HandlerContext) -> dict:
        return {
            "course_id": payload.course_id,
            "user_id": context.user_id,
            "mode": payload.mode,
            "learning_objective": payload.learning_objective,
            "current_difficulty": payload.current_difficulty,
            "desired_duration_minutes": payload.desired_duration_minutes,
            "difficulty_level": payload.difficulty_level,
            "wants_more_practice": bool(payload.wants_more_practice),
            "selected_material_ids": list(payload.selected_material_ids or []),
        }

    def _summary(self, result_ref: dict) -> str:
        label = result_ref.get("mode_label") or result_ref.get("mode") or "互动课堂"
        return f"{label}已开始生成"

    async def execute(self, context: HandlerContext) -> HandlerResult:
        payload = self.input_model.model_validate(context.input_ref)
        checkpoint = context.checkpoint or {}
        if checkpoint.get("stage") == _STAGE_APPLIED:
            # 副作用已完成：恢复时直接返回既有结果，不再触碰领域 Service。
            result_ref = dict(checkpoint.get("result") or {})
            return HandlerResult(
                status="SUCCEEDED",
                job_output_patch=result_ref,
                checkpoint=checkpoint,
                summary=self._summary(result_ref),
            )

        # 审批 id **只**来自本 Run 的 checkpoint（由 Gateway 在开票时写入）。
        # 绝不读取 input_ref 里的 approval_id —— 那是跨请求复用漏洞的入口。
        approval_id = checkpoint.get("approval_id")
        # 幂等键按 Run 固定；Gateway 的声明键包含 request_hash，
        # 因此"参数被改动"会生成新声明，必须重新审批。
        outcome = await self._gateway.invoke(
            ToolInvocationRequest(
                run_id=context.run_id,
                role_code=self.role_code,
                tool_name=GENERATE_TOOL,
                arguments=self._arguments(payload, context),
                idempotency_key=f"run:{context.run_id}",
                approval_id=approval_id,
            )
        )
        if outcome.status == "AWAITING_APPROVAL":
            return HandlerResult(
                status="AWAITING_APPROVAL",
                checkpoint={
                    "stage": _STAGE_AWAITING_APPROVAL,
                    "call_id": outcome.call_id,
                    "approval_id": outcome.approval_id,
                },
                summary="等待学生确认后生成互动课堂",
            )

        result_ref = dict(outcome.result_ref or {})
        return HandlerResult(
            status="SUCCEEDED",
            job_output_patch=result_ref,
            checkpoint={
                "stage": _STAGE_APPLIED,
                "call_id": outcome.call_id,
                "result": result_ref,
            },
            summary=self._summary(result_ref),
        )

    async def recover(self, context: HandlerContext) -> RecoveryDecision:
        """副作用由 Gateway 幂等声明 + checkpoint 双重保护，任何中断都可安全重排。"""
        return RecoveryDecision(action=RecoveryAction.REQUEUE, checkpoint=context.checkpoint)


__all__ = [
    "GENERATE_TOOL",
    "INSPECT_TOOL",
    "LIST_TOOL",
    "OPEN_TOOL",
    "PROPOSE_TOOL",
    "STATUS_TOOL",
    "ContainerRef",
    "InteractiveClassroomGenerateHandler",
    "InteractiveClassroomInput",
    "build_interactive_classroom_tools",
    "classroom_deep_link",
]
