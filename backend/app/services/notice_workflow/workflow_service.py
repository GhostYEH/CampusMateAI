"""通知工作流服务(§8.3) — Source → Interpreter → Workflow → Risk → Action → Tracking。

关键约束:
1. 自动化默认关闭。AUTO_SAFE 在自动化关闭时只 PROPOSED,不自动执行。
2. 用户批准只对指定 action 生效,不扩大为永久授权。
3. MANUAL_ONLY 永不自动执行;无官方接口只生成步骤/材料/待办,不声称已办理。
4. Tool 执行使用 idempotency_key + 业务核对;超时未知结果不盲目重试。
5. 跨用户访问禁止;敏感字段不进入响应。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ...core.exceptions import AppException, Forbidden, InvalidTransition, NotFoundError
from ...models.notice_workflow import (
    NoticeWorkflowActionRow,
    NoticeWorkflowRow,
)
from ...repositories.notice_workflow_repository import NoticeWorkflowRepository
from ...repositories.personal_task_repository import PersonalTaskRepository
from ...repositories.notice_repository import NoticeRepository
from ...schemas.notice_workflow import (
    ACTION_STATUSES,
    WORKFLOW_STATUSES,
)
from .interpreter import (
    Interpretation,
    NoticeInterpreter,
    content_fingerprint,
    detect_confirm_required_markers,
    detect_manual_only_markers,
)
from .source_registry import ensure_sources_seeded, resolve_source_by_code


# ===== 领域异常(不复用共享 exceptions.py,在此定义) =====


class WorkflowNotFound(NotFoundError):
    code = "WORKFLOW_NOT_FOUND"
    message = "通知工作流不存在。"


class WorkflowActionNotFound(NotFoundError):
    code = "WORKFLOW_ACTION_NOT_FOUND"
    message = "工作流动作不存在。"


class WorkflowStateConflict(InvalidTransition):
    code = "WORKFLOW_STATE_CONFLICT"
    message = "工作流当前状态不允许该操作。"


class ActionStateConflict(InvalidTransition):
    code = "ACTION_STATE_CONFLICT"
    message = "动作当前状态不允许该操作。"


# ===== 常量 =====

_TERMINAL_WORKFLOW = ("COMPLETED", "EXPIRED", "FAILED")
_TERMINAL_ACTION = ("DONE", "REJECTED", "EXPIRED", "FAILED")
_DEFAULT_ACTION_TTL = timedelta(days=30)
_MANUAL_ONLY_ACTION_TYPES = frozenset(
    {"external_submit", "payment", "auth_login", "identity_verify", "formal_register"}
)
_CONFIRM_REQUIRED_ACTION_TYPES = frozenset(
    {"prepare_message", "schedule_conflict", "update_plan", "prepare_form"}
)
_AUTO_SAFE_ACTION_TYPES = frozenset(
    {"create_task", "add_reminder", "link_course", "generate_checklist"}
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def classify_risk(action_type: str, notice_text: str) -> str:
    """RiskEngine 分类(§5.5、§8.3)。"""
    if action_type in _MANUAL_ONLY_ACTION_TYPES:
        return "MANUAL_ONLY"
    if action_type in _CONFIRM_REQUIRED_ACTION_TYPES:
        return "CONFIRM_REQUIRED"
    if action_type in _AUTO_SAFE_ACTION_TYPES:
        # 即使 AUTO_SAFE 类型,若文本命中 MANUAL_ONLY 标记则升级
        if detect_manual_only_markers(notice_text):
            return "MANUAL_ONLY"
        return "AUTO_SAFE"
    # 未知类型默认 MANUAL_ONLY(安全优先)
    return "MANUAL_ONLY"


def _is_valid_workflow_transition(old: str, new: str) -> bool:
    if old == new:
        return True
    if old in _TERMINAL_WORKFLOW:
        return False
    table = {
        "CREATED": {"ANALYZING", "FAILED", "EXPIRED"},
        "ANALYZING": {
            "WAITING_CONFIRMATION",
            "PROCESSING",
            "COMPLETED",
            "FAILED",
            "EXPIRED",
        },
        "WAITING_CONFIRMATION": {"PROCESSING", "COMPLETED", "FAILED", "EXPIRED"},
        "PROCESSING": {"COMPLETED", "FAILED", "EXPIRED"},
    }
    return new in table.get(old, set())


def _is_valid_action_transition(old: str, new: str) -> bool:
    if old == new:
        return True
    if old in _TERMINAL_ACTION:
        return False
    table = {
        "PROPOSED": {"APPROVED", "REJECTED", "EXPIRED", "FAILED"},
        "APPROVED": {"EXECUTING", "EXPIRED", "FAILED"},
        "EXECUTING": {"DONE", "FAILED"},
    }
    return new in table.get(old, set())


# ===== 服务 =====


class NoticeWorkflowService:
    def __init__(
        self,
        *,
        repository: NoticeWorkflowRepository,
        interpreter: NoticeInterpreter,
        notice_repository: NoticeRepository,
        personal_task_repository: PersonalTaskRepository,
    ) -> None:
        self._repo = repository
        self._interp = interpreter
        self._notice_repo = notice_repository
        self._task_repo = personal_task_repository
        ensure_sources_seeded(repository)

    # ===== 创建工作流 =====

    def create_workflow_for_notice(
        self,
        *,
        user_id: str,
        notice_id: str,
        source_code: str = "manual_input",
        idempotency_key: Optional[str] = None,
    ) -> NoticeWorkflowRow:
        """为已持久化的 notice 创建工作流。兼容幂等与去重。"""
        # 幂等
        if idempotency_key:
            existing = self._repo.find_workflow_by_idempotency(user_id, idempotency_key)
            if existing:
                return existing
        # 读取 notice
        notice = self._notice_repo.list_notices(user_id)
        notice_row = next((n for n in notice if n.id == notice_id), None)
        if notice_row is None:
            raise WorkflowNotFound("通知不存在或无权访问")
        content = notice_row.content or notice_row.title or ""
        fp = content_fingerprint(content, user_id=user_id)
        # 去重:同指纹已有活跃工作流则返回
        active = self._repo.get_active_workflow_by_fingerprint(user_id, fp)
        if active:
            return active
        source = self._repo.get_source_by_code(source_code)
        source_id = source.source_id if source else None
        workflow = self._repo.create_workflow(
            user_id=user_id,
            notice_id=notice_id,
            content_fingerprint=fp,
            source_id=source_id,
            idempotency_key=idempotency_key,
        )
        # 立即进入 ANALYZING 并解释
        self._repo.update_workflow_status(workflow.workflow_id, "ANALYZING")
        self._analyze_and_plan(workflow.workflow_id, user_id, content, source_code)
        return self._repo.get_workflow(workflow.workflow_id)  # type: ignore[return-value]

    def _analyze_and_plan(
        self,
        workflow_id: str,
        user_id: str,
        content: str,
        source_code: str,
    ) -> None:
        interp = self._interp.interpret(content, source_code)
        self._repo.update_workflow_interpretation(
            workflow_id,
            title=interp.title,
            deadline=interp.deadline,
            location=interp.location,
            audience=interp.audience,
            materials=interp.materials,
            steps=interp.steps,
            source_evidence=interp.source_evidence,
            confidence=interp.confidence,
            uncertainty=interp.uncertainty,
        )
        # 生成 actions
        actions = self._plan_actions(workflow_id, user_id, content, interp)
        # 推进状态
        self._advance_after_planning(workflow_id, user_id, actions, source_code)

    def _plan_actions(
        self,
        workflow_id: str,
        user_id: str,
        notice_text: str,
        interp: Interpretation,
    ) -> list[NoticeWorkflowActionRow]:
        expires_at = (_now() + _DEFAULT_ACTION_TTL).isoformat()
        actions: list[NoticeWorkflowActionRow] = []
        # 1. 创建个人待办(AUTO_SAFE)
        actions.append(
            self._repo.create_action(
                workflow_id=workflow_id,
                user_id=user_id,
                action_type="create_task",
                title=f"创建待办: {interp.title or '校园通知'}",
                risk_level=classify_risk("create_task", notice_text),
                params={
                    "title": interp.title or "校园通知",
                    "deadline": interp.deadline,
                    "materials": interp.materials,
                    "location": interp.location,
                },
                expires_at=expires_at,
            )
        )
        # 2. 材料清单(AUTO_SAFE)
        if interp.materials:
            actions.append(
                self._repo.create_action(
                    workflow_id=workflow_id,
                    user_id=user_id,
                    action_type="generate_checklist",
                    title="生成材料清单",
                    risk_level=classify_risk("generate_checklist", notice_text),
                    params={"materials": interp.materials},
                    expires_at=expires_at,
                )
            )
        # 3. 提醒(AUTO_SAFE)
        if interp.deadline:
            actions.append(
                self._repo.create_action(
                    workflow_id=workflow_id,
                    user_id=user_id,
                    action_type="add_reminder",
                    title="设置截止提醒",
                    risk_level=classify_risk("add_reminder", notice_text),
                    params={"deadline": interp.deadline},
                    expires_at=expires_at,
                )
            )
        # 4. MANUAL_ONLY:外部提交(无官方接口,只生成指导)
        manual_markers = detect_manual_only_markers(notice_text)
        if manual_markers:
            actions.append(
                self._repo.create_action(
                    workflow_id=workflow_id,
                    user_id=user_id,
                    action_type="external_submit",
                    title="外部提交(需手动办理)",
                    risk_level="MANUAL_ONLY",
                    params={"markers": manual_markers},
                    expires_at=expires_at,
                )
            )
        # 5. CONFIRM_REQUIRED:准备消息/调整日程(需用户确认)
        confirm_markers = detect_confirm_required_markers(notice_text)
        if confirm_markers:
            actions.append(
                self._repo.create_action(
                    workflow_id=workflow_id,
                    user_id=user_id,
                    action_type="prepare_message",
                    title="准备消息/调整(需确认)",
                    risk_level="CONFIRM_REQUIRED",
                    params={"markers": confirm_markers},
                    expires_at=expires_at,
                )
            )
        return actions

    def _advance_after_planning(
        self,
        workflow_id: str,
        user_id: str,
        actions: list[NoticeWorkflowActionRow],
        source_code: str,
    ) -> None:
        wf = self._repo.get_workflow(workflow_id)
        if not wf:
            return
        has_confirm = any(a.risk_level == "CONFIRM_REQUIRED" for a in actions)
        has_manual = any(a.risk_level == "MANUAL_ONLY" for a in actions)
        auto_actions = [
            a for a in actions if a.risk_level == "AUTO_SAFE"
        ]
        # 自动化是否开启(按来源)
        source = self._repo.get_source_by_code(source_code)
        automation_on = bool(source and source.automation_enabled)
        if has_confirm:
            self._repo.update_workflow_status(workflow_id, "WAITING_CONFIRMATION")
            return
        if auto_actions and automation_on:
            self._repo.update_workflow_status(workflow_id, "PROCESSING")
            for a in auto_actions:
                if a.status == "PROPOSED":
                    self._execute_auto_safe(a, user_id, workflow_id)
            self._maybe_complete(workflow_id)
            return
        # 无自动化或只有 MANUAL_ONLY:等待用户手动操作
        if has_manual or auto_actions:
            self._repo.update_workflow_status(workflow_id, "WAITING_CONFIRMATION")
        else:
            self._repo.update_workflow_status(workflow_id, "COMPLETED")

    # ===== 查询 =====

    def list_sources(self):
        return self._repo.list_sources()

    def patch_source(
        self,
        source_id: str,
        *,
        automation_enabled: Optional[bool] = None,
        display_name: Optional[str] = None,
    ):
        return self._repo.update_source(
            source_id,
            automation_enabled=automation_enabled,
            display_name=display_name,
        )

    def get_workflow(
        self, workflow_id: str, *, user_id: str
    ) -> NoticeWorkflowRow:
        wf = self._repo.get_workflow(workflow_id)
        if not wf:
            raise WorkflowNotFound()
        if wf.user_id != user_id:
            raise WorkflowNotFound()
        return wf

    def list_actions(
        self, workflow_id: str, *, user_id: str
    ) -> list[NoticeWorkflowActionRow]:
        self.get_workflow(workflow_id, user_id=user_id)
        return self._repo.list_actions_by_workflow(workflow_id)

    # ===== 重新分析 =====

    def reanalyze(
        self,
        workflow_id: str,
        *,
        user_id: str,
        idempotency_key: Optional[str] = None,
    ) -> NoticeWorkflowRow:
        wf = self.get_workflow(workflow_id, user_id=user_id)
        if wf.status in _TERMINAL_WORKFLOW and wf.status != "COMPLETED":
            raise WorkflowStateConflict("终态工作流不可重新分析")
        if idempotency_key:
            existing = self._repo.find_action_by_idempotency(user_id, idempotency_key)
            if existing:
                return wf
        # 读取 notice 内容
        notice = self._notice_repo.list_notices(user_id)
        notice_row = next((n for n in notice if n.id == wf.notice_id), None)
        content = (notice_row.content or notice_row.title or "") if notice_row else ""
        source_code = "manual_input"
        if wf.source_id:
            src = self._repo.get_source(wf.source_id)
            if src:
                source_code = src.code
        self._repo.update_workflow_status(workflow_id, "ANALYZING")
        self._analyze_and_plan(workflow_id, user_id, content, source_code)
        return self._repo.get_workflow(workflow_id)  # type: ignore[return-value]

    # ===== Action 决策 =====

    def decide_action(
        self,
        action_id: str,
        *,
        user_id: str,
        decision: str,
        reason: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> NoticeWorkflowActionRow:
        action = self._repo.get_action(action_id)
        if not action:
            raise WorkflowActionNotFound()
        if action.user_id != user_id:
            raise WorkflowActionNotFound()
        if idempotency_key:
            existing = self._repo.find_action_by_idempotency(user_id, idempotency_key)
            if existing and existing.action_id == action_id:
                return existing
        if not _is_valid_action_transition(action.status, decision):
            raise ActionStateConflict(
                f"动作当前状态 {action.status} 不允许转换为 {decision}"
            )
        self._repo.update_action_status(action_id, decision)
        # APPROVED + AUTO_SAFE → 可立即执行(用户显式批准)
        if decision == "APPROVED" and action.risk_level == "AUTO_SAFE":
            self._repo.update_action_status(action_id, "EXECUTING")
            self._execute_auto_safe(action, user_id, action.workflow_id)
        # 推进工作流
        self._maybe_complete(action.workflow_id)
        return self._repo.get_action(action_id)  # type: ignore[return-value]

    # ===== Action 执行 =====

    def execute_action(
        self,
        action_id: str,
        *,
        user_id: str,
        idempotency_key: Optional[str] = None,
    ) -> NoticeWorkflowActionRow:
        action = self._repo.get_action(action_id)
        if not action:
            raise WorkflowActionNotFound()
        if action.user_id != user_id:
            raise WorkflowActionNotFound()
        if idempotency_key:
            existing = self._repo.find_action_by_idempotency(user_id, idempotency_key)
            if existing and existing.action_id == action_id and existing.status == "DONE":
                return existing
        # MANUAL_ONLY 永不自动执行
        if action.risk_level == "MANUAL_ONLY":
            self._repo.update_action_status(
                action_id,
                "FAILED",
                error_code="MANUAL_ONLY_NOT_EXECUTABLE",
                error_message="该事项无官方接口或需身份验证,请手动办理。",
            )
            return self._repo.get_action(action_id)  # type: ignore[return-value]
        # CONFIRM_REQUIRED 必须先批准
        if action.risk_level == "CONFIRM_REQUIRED" and action.status != "APPROVED":
            raise ActionStateConflict("需先批准再执行")
        if not _is_valid_action_transition(action.status, "EXECUTING"):
            raise ActionStateConflict(
                f"动作当前状态 {action.status} 不允许执行"
            )
        self._repo.update_action_status(action_id, "EXECUTING")
        self._execute_auto_safe(action, user_id, action.workflow_id)
        self._maybe_complete(action.workflow_id)
        return self._repo.get_action(action_id)  # type: ignore[return-value]

    # ===== 内部:执行 AUTO_SAFE =====

    def _execute_auto_safe(
        self,
        action: NoticeWorkflowActionRow,
        user_id: str,
        workflow_id: str,
    ) -> None:
        params: dict[str, Any] = {}
        if action.params_json:
            try:
                params = json.loads(action.params_json)
            except (ValueError, TypeError):
                params = {}
        try:
            if action.action_type == "create_task":
                task = self._task_repo.create_task(
                    user_id=user_id,
                    title=str(params.get("title", "校园通知待办")),
                    deadline=params.get("deadline"),
                    materials=params.get("materials"),
                    location=params.get("location"),
                    source_name="notice_workflow",
                    source_notice_id=f"nwf:{workflow_id}",
                    priority="medium",
                    importance="normal",
                )
                self._repo.update_action_status(
                    action.action_id,
                    "DONE",
                    external_ref=task.id,
                    result={"task_id": task.id, "created": True},
                )
            elif action.action_type == "generate_checklist":
                self._repo.update_action_status(
                    action.action_id,
                    "DONE",
                    result={"checklist": params.get("materials", [])},
                )
            elif action.action_type == "add_reminder":
                # 本地提醒由客户端调度;服务端只记录
                self._repo.update_action_status(
                    action.action_id,
                    "DONE",
                    result={"reminder_deadline": params.get("deadline")},
                )
            elif action.action_type == "prepare_message":
                # 只生成草稿,不发送;绝不声称已发送
                self._repo.update_action_status(
                    action.action_id,
                    "DONE",
                    result={"draft_prepared": True, "sent": False},
                )
            elif action.action_type == "link_course":
                self._repo.update_action_status(
                    action.action_id, "DONE", result={"linked": True}
                )
            else:
                # 未知 AUTO_SAFE 类型:不执行,标记 FAILED
                self._repo.update_action_status(
                    action.action_id,
                    "FAILED",
                    error_code="UNKNOWN_ACTION_TYPE",
                    error_message=f"未知的动作类型: {action.action_type}",
                )
        except Exception as exc:
            # 超时/未知结果不盲目重试:标记 FAILED 而非重试
            self._repo.update_action_status(
                action.action_id,
                "FAILED",
                error_code="EXECUTION_ERROR",
                error_message=str(exc)[:256],
            )

    def _maybe_complete(self, workflow_id: str) -> None:
        wf = self._repo.get_workflow(workflow_id)
        if not wf or wf.status in _TERMINAL_WORKFLOW:
            return
        actions = self._repo.list_actions_by_workflow(workflow_id)
        if not actions:
            return
        # 过期超时 action
        self._repo.expire_pending_actions(workflow_id, before_iso=_now_iso())
        actions = self._repo.list_actions_by_workflow(workflow_id)
        all_done = all(a.status in _TERMINAL_ACTION for a in actions)
        any_failed = any(a.status == "FAILED" for a in actions)
        has_pending_confirm = any(
            a.risk_level == "CONFIRM_REQUIRED" and a.status == "PROPOSED"
            for a in actions
        )
        if has_pending_confirm and wf.status != "WAITING_CONFIRMATION":
            self._repo.update_workflow_status(workflow_id, "WAITING_CONFIRMATION")
            return
        if all_done:
            if any_failed:
                self._repo.update_workflow_status(
                    workflow_id, "COMPLETED",
                    error_code="PARTIAL_FAILURE",
                    error_message="部分动作执行失败",
                )
            else:
                self._repo.update_workflow_status(workflow_id, "COMPLETED")
        elif wf.status == "WAITING_CONFIRMATION" and not has_pending_confirm:
            self._repo.update_workflow_status(workflow_id, "PROCESSING")

    # ===== 过期检查 =====

    def expire_overdue(self, workflow_id: str, *, user_id: str) -> int:
        self.get_workflow(workflow_id, user_id=user_id)
        return self._repo.expire_pending_actions(
            workflow_id, before_iso=_now_iso()
        )


__all__ = [
    "ActionStateConflict",
    "NoticeWorkflowService",
    "WorkflowActionNotFound",
    "WorkflowNotFound",
    "WorkflowStateConflict",
    "classify_risk",
]