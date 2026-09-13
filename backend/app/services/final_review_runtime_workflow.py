"""期末复习 Runtime 工作流 —— Runtime 的第一个真实业务调用方。

设计约束（第一批垂直薄片）：

- 只支持线性步骤，持久化在现有 `agent_run_steps` / `agent_tool_calls` /
  `agent_events` / `agent_approvals` / `agent_context_snapshots` / `agent_artifacts` 上；
- 每个领域写入都是「先读后写」，因此进程在中途死亡后重放不会产生重复计划或待办；
- 只有能在数据层被证明的动作才允许继续，否则运行直接 `FAILED`，不做盲目重放。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from ..core.exceptions import AppException
from ..models.agent_runtime import AgentRunRow, AgentRunStepRow
from ..repositories.agent_artifact_repository import AgentArtifactRepository
from ..repositories.agent_runtime_repository import AgentRuntimeRepository
from .agent_runtime.approval_gate import ApprovalGate
from .agent_runtime.artifact_manager import ArtifactManager
from .agent_runtime.event_store import AgentEventStore
from .agent_runtime.executor import AgentExecutor
from .final_review_service import FinalReviewService

DOMAIN = "final_review"
ROLE = "planner"
TOTAL_STEPS = 7
APPROVAL_STEP = 4
ACTIVATION_STEP = 5
ARTIFACT_TYPE = "FINAL_REVIEW_PLAN"
APPROVAL_TTL_MINUTES = 30
FINISHED_STATUSES = frozenset({"SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"})
ACTIVATION_TOOL = "plan.activate"

# sequence, tool, phase, 步骤说明
STEPS: tuple[tuple[int, str, str, str], ...] = (
    (1, "exam.read", "CONTEXT_BUILDING", "验证考试与复习活动归属"),
    (2, "plan.propose", "WAITING_FOR_MODEL", "生成复习计划版本"),
    (3, "plan.propose", "VALIDATING_OUTPUT", "持久化计划检查点"),
    (4, ACTIVATION_TOOL, "WAITING_FOR_APPROVAL", "创建激活审批"),
    (5, ACTIVATION_TOOL, "WAITING_FOR_TOOL", "激活复习计划版本"),
    (6, "task.create", "WAITING_FOR_TOOL", "幂等创建今日待办"),
    (7, "artifact.create", "PERSISTING_RESULT", "生成计划 Artifact"),
)
_STEP_BY_SEQUENCE = {sequence: (tool, phase, label) for sequence, tool, phase, label in STEPS}


def _digest(value) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


class FinalReviewRuntimeWorkflow:
    def __init__(self, *, repository: AgentRuntimeRepository,
                 artifact_repository: AgentArtifactRepository,
                 executor: AgentExecutor,
                 events: AgentEventStore,
                 approvals: ApprovalGate,
                 artifacts: ArtifactManager,
                 service: FinalReviewService) -> None:
        self._repo = repository
        self._artifact_repo = artifact_repository
        self._executor = executor
        self._events = events
        self._approvals = approvals
        self._artifacts = artifacts
        self._review = service

    # ===== 对外入口 =====

    def start(self, *, user_id: str, campaign_id: str, idempotency_key: str) -> dict:
        job, run, reused = self._repo.create_job_idempotent(
            user_id=user_id, domain=DOMAIN,
            objective_summary=f"期末复习计划 · {campaign_id}",
            total_steps=TOTAL_STEPS, idempotency_key=idempotency_key,
        )
        if reused:
            self._events.append(run_id=run.id, event_type="RUN_REUSED", summary="重复请求命中同一运行")
            if run.status in FINISHED_STATUSES:
                return self.view(user_id, run)
        else:
            self._events.append(run_id=run.id, event_type="RUN_QUEUED", summary="期末复习运行已排队")
        return self._advance(user_id=user_id, run=run, campaign_id=campaign_id)

    def resume(self, *, user_id: str, run_id: str) -> dict:
        run = self._repo.get_run(run_id=run_id, user_id=user_id)
        if run is None:
            raise AppException(code="AGENT_RUN_NOT_FOUND", http_status=404, message="运行不存在")
        if run.domain != DOMAIN:
            raise AppException(code="AGENT_INVALID_STATE", http_status=409, message="该运行不属于期末复习工作流")
        if run.status in FINISHED_STATUSES:
            return self.view(user_id, run)
        campaign = self._campaign_for_run(user_id, run)
        if campaign is None:
            self._fail(user_id, run, "无法证明该运行可恢复，已终止")
            return self.view(user_id, self._repo.get_run(run_id=run.id, user_id=user_id))
        # 只有在执行器真正被调度时才把运行标记为恢复中。
        self._repo.update_run(run_id=run.id, status=run.status, phase="RECOVERY_CHECKING", current_role=ROLE)
        self._events.append(run_id=run.id, event_type="RUN_RECOVERY_STARTED", summary="执行器已接管，从最后完成步骤继续")
        run = self._repo.get_run(run_id=run.id, user_id=user_id)
        return self._advance(user_id=user_id, run=run, campaign_id=campaign["id"])

    def decide(self, *, user_id: str, approval_id: str, decision: str, now: datetime) -> dict:
        row = self._approvals.decide(approval_id=approval_id, user_id=user_id, decision=decision, now=now)
        run = self._repo.get_run(run_id=row.run_id, user_id=user_id)
        if run is None or run.domain != DOMAIN:
            return {"approval": row, "run": run, "steps": [], "campaign_id": None}
        if row.status == "APPROVED":
            self._events.append(run_id=run.id, event_type="APPROVAL_GRANTED",
                                summary="用户已确认激活复习计划", approval_id=row.id)
            view = self.resume(user_id=user_id, run_id=run.id)
            view["approval"] = self._repo.latest_approval_for_run(run_id=run.id)
            return view
        self._events.append(run_id=run.id, event_type="APPROVAL_DENIED",
                            summary="用户未通过激活审批", approval_id=row.id)
        for sequence in range(ACTIVATION_STEP, TOTAL_STEPS + 1):
            step = self._step(run.id, sequence)
            if step is not None and step.status not in {"DONE", "SKIPPED"}:
                self._repo.finish_step(run_id=run.id, sequence=sequence, status="SKIPPED", safe_summary="审批未通过")
        self._repo.update_run(run_id=run.id, status="CANCELLED", phase="IDLE", current_role=ROLE)
        return self.view(user_id, self._repo.get_run(run_id=run.id, user_id=user_id))

    def can_resume(self, run: AgentRunRow) -> bool:
        """启动恢复判定：只有能反查到仍存在的领域对象，才认为旧运行可恢复。"""
        if run.domain != DOMAIN or run.status in FINISHED_STATUSES:
            return False
        try:
            return self._campaign_for_run(run.user_id, run) is not None
        except AppException:
            return False

    def steps(self, *, user_id: str, run_id: str) -> list[AgentRunStepRow]:
        run = self._repo.get_run(run_id=run_id, user_id=user_id)
        if run is None:
            raise AppException(code="AGENT_RUN_NOT_FOUND", http_status=404, message="运行不存在")
        return self._repo.list_steps(run_id=run.id)

    def latest_run_for_campaign(self, *, user_id: str, campaign_id: str) -> AgentRunRow | None:
        return self._repo.find_run_for_scope(user_id=user_id, domain=DOMAIN, key="campaign_id", value=campaign_id)

    # ===== 推进循环 =====

    def _advance(self, *, user_id: str, run: AgentRunRow, campaign_id: str) -> dict:
        run = self._repo.update_run(run_id=run.id, status="RUNNING", phase="CONTEXT_BUILDING", current_role=ROLE)
        for sequence, _tool, _phase, label in STEPS:
            self._repo.ensure_step(run_id=run.id, sequence=sequence, role=ROLE, safe_summary=label)
        for _ in range(TOTAL_STEPS + 2):
            step = self._next_step(run.id)
            if step is None:
                return self._succeed(user_id, run)
            tool, phase, _label = _STEP_BY_SEQUENCE[step.sequence]
            if step.sequence == APPROVAL_STEP:
                paused = self._ensure_approval(user_id=user_id, run=run, campaign_id=campaign_id, step=step)
                return self.view(user_id, paused)
            self._repo.update_run(run_id=run.id, status="RUNNING", phase=phase, current_role=ROLE)
            if step.sequence == ACTIVATION_STEP:
                paused = self._activation_gate(user_id=user_id, run=run)
                if paused is not None:
                    return self.view(user_id, paused)
            failure = self._execute(user_id=user_id, run=run, campaign_id=campaign_id,
                                    step=step, tool=tool)
            if failure is not None:
                return self.view(user_id, failure)
            run = self._repo.get_run(run_id=run.id, user_id=user_id)
        return self.view(user_id, self._repo.get_run(run_id=run.id, user_id=user_id))

    def _next_step(self, run_id: str) -> AgentRunStepRow | None:
        for step in self._repo.list_steps(run_id=run_id):
            if step.status not in {"DONE", "SKIPPED"}:
                return step
        return None

    def _step(self, run_id: str, sequence: int) -> AgentRunStepRow | None:
        for step in self._repo.list_steps(run_id=run_id):
            if step.sequence == sequence:
                return step
        return None

    # ===== 单步执行 =====

    def _execute(self, *, user_id: str, run: AgentRunRow, campaign_id: str,
                 step: AgentRunStepRow, tool: str) -> AgentRunRow | None:
        handlers = {
            1: self._step_verify_scope,
            2: self._step_generate_version,
            3: self._step_checkpoint,
            5: self._step_activate,
            6: self._step_materialize_tasks,
            7: self._step_create_artifact,
        }
        handler = handlers.get(step.sequence)
        if handler is None:
            return self._fail(user_id, run, f"步骤 {step.sequence} 没有对应处理器")
        self._repo.start_step(run_id=run.id, sequence=step.sequence)
        try:
            summary = handler(user_id=user_id, run=run, campaign_id=campaign_id, step=step)
        except AppException as error:
            self._repo.finish_step(run_id=run.id, sequence=step.sequence, status="FAILED",
                                   safe_summary=f"失败：{error.code}")
            return self._fail(user_id, run, f"步骤 {step.sequence} 失败：{error.code}")
        except Exception as error:  # noqa: BLE001 - 任何异常都必须落成可诊断的失败运行
            self._repo.finish_step(run_id=run.id, sequence=step.sequence, status="FAILED",
                                   safe_summary="失败：内部错误")
            return self._fail(user_id, run, f"步骤 {step.sequence} 失败：{type(error).__name__}")
        self._repo.finish_step(run_id=run.id, sequence=step.sequence, status="DONE", safe_summary=summary)
        self._repo.set_progress(run_id=run.id, current=step.sequence)
        self._events.append(run_id=run.id, event_type="STEP_COMPLETED",
                            summary=f"{step.sequence}. {summary}")
        return None

    def _run_tool(self, *, user_id: str, run: AgentRunRow, sequence: int, tool: str,
                  arguments: dict, action):
        """幂等工具调用：已成功则不重放；未完成则交由 action 依据领域状态自行对账。"""
        idempotency_key = f"{run.id}:{sequence}"
        if tool == ACTIVATION_TOOL:
            # 此处风险已由审批替代，RiskEngine 不再放行 CONFIRM_REQUIRED。
            call, _reused = self._repo.begin_tool_call(
                run_id=run.id, tool_name=tool, idempotency_key=idempotency_key, request_hash=_digest(arguments),
            )
        else:
            call, _reused = self._executor.authorize_tool(
                run_id=run.id, role=ROLE, tool_name=tool, actor_user_id=user_id, owner_user_id=user_id,
                arguments=arguments, idempotency_key=idempotency_key, automation_enabled=True,
            )
        if call.status == "SUCCEEDED":
            return False
        try:
            action()
        except Exception as error:  # noqa: BLE001
            self._executor.finish_tool_call(call_id=call.id, status="FAILED",
                                            error_code=getattr(error, "code", type(error).__name__))
            raise
        self._executor.finish_tool_call(call_id=call.id, status="SUCCEEDED",
                                        result_digest=_digest(arguments))
        return True

    # ===== 各步骤实现 =====

    def _step_verify_scope(self, *, user_id: str, run: AgentRunRow, campaign_id: str, **_kwargs) -> str:
        campaign = self._review.verify_scope(user_id, campaign_id)
        if run.context_snapshot_id is None:
            self._repo.create_context_snapshot(
                run_id=run.id, user_id=user_id,
                scope={"campaign_id": campaign_id, "exam_id": campaign["exam_id"], "domain": DOMAIN},
                facts={"daily_capacity_minutes": campaign["daily_capacity_minutes"]},
                source_refs=[f"student_exams:{campaign['exam_id']}"],
                source_digest=_digest({"campaign_id": campaign_id, "exam_id": campaign["exam_id"]}),
                valid_until=(_utcnow() + timedelta(days=30)).isoformat(),
            )
        return "考试与复习活动归属已确认"

    def _step_generate_version(self, *, user_id: str, run: AgentRunRow, campaign_id: str, **_kwargs) -> str:
        self._run_tool(
            user_id=user_id, run=run, sequence=2, tool="plan.propose",
            arguments={"campaign_id": campaign_id},
            action=lambda: self._review.generate(user_id, campaign_id, run_id=run.id),
        )
        version = self._review.latest_version(user_id, campaign_id)
        if version is None:
            raise AppException(code="AGENT_INVALID_STATE", http_status=409, message="计划版本未落库")
        return f"计划版本 v{version['version']} 已生成"

    def _step_checkpoint(self, *, user_id: str, run: AgentRunRow, campaign_id: str, **_kwargs) -> str:
        # 独立连接回读，证明上一步的写入确实已提交，而不是只存在于进程内存里。
        version = self._review.latest_version(user_id, campaign_id)
        if version is None:
            raise AppException(code="AGENT_INVALID_STATE", http_status=409, message="计划版本未落库")
        return f"检查点已持久化 v{version['version']} · {version['content_hash'][:12]}"

    def _ensure_approval(self, *, user_id: str, run: AgentRunRow, campaign_id: str,
                         step: AgentRunStepRow) -> AgentRunRow | None:
        version = self._review.latest_version(user_id, campaign_id)
        if version is None:
            return self._fail(user_id, run, "缺少计划版本，无法创建激活审批")
        expected = _digest({"campaign_id": campaign_id, "version": version["version"]})
        pending = self._repo.pending_approval_for_run(run_id=run.id)
        if pending is None:
            self._repo.start_step(run_id=run.id, sequence=step.sequence)
            now = _utcnow()
            approval = self._repo.create_approval(
                run_id=run.id, user_id=user_id, risk_level="CONFIRM_REQUIRED",
                action_digest=expected, summary=f"确认激活复习计划 v{version['version']}",
                expires_at=(now + timedelta(minutes=APPROVAL_TTL_MINUTES)).isoformat(),
                now=now.isoformat(),
            )
            self._repo.finish_step(run_id=run.id, sequence=step.sequence, status="DONE",
                                   safe_summary="已创建激活审批")
            self._repo.set_progress(run_id=run.id, current=step.sequence)
            self._events.append(run_id=run.id, event_type="APPROVAL_REQUIRED",
                                summary="等待用户确认激活复习计划", approval_id=approval.id)
        elif pending.action_digest != expected:
            self._repo.decide_approval(approval_id=pending.id, user_id=user_id, status="EXPIRED",
                                       decided_at=_utcnow().isoformat())
            self._events.append(run_id=run.id, event_type="APPROVAL_EXPIRED",
                                summary="计划版本已变化，原审批失效", approval_id=pending.id)
        return self._repo.update_run(run_id=run.id, status="AWAITING_APPROVAL",
                                     phase="WAITING_FOR_APPROVAL", current_role=ROLE)

    def _activation_gate(self, *, user_id: str, run: AgentRunRow) -> AgentRunRow | None:
        approval = self._repo.latest_approval_for_run(run_id=run.id)
        if approval is None:
            return self._fail(user_id, run, "缺少激活审批，拒绝继续")
        if approval.status == "PENDING":
            return self._repo.update_run(run_id=run.id, status="AWAITING_APPROVAL",
                                         phase="WAITING_FOR_APPROVAL", current_role=ROLE)
        if approval.status in {"REJECTED", "EXPIRED"}:
            for sequence in range(ACTIVATION_STEP, TOTAL_STEPS + 1):
                step = self._step(run.id, sequence)
                if step is not None and step.status not in {"DONE", "SKIPPED"}:
                    self._repo.finish_step(run_id=run.id, sequence=sequence, status="SKIPPED",
                                           safe_summary="审批未通过")
            self._events.append(run_id=run.id, event_type="RUN_CANCELLED", summary="审批未通过，计划未激活")
            return self._repo.update_run(run_id=run.id, status="CANCELLED", phase="IDLE", current_role=ROLE)
        return None

    def _step_activate(self, *, user_id: str, run: AgentRunRow, campaign_id: str, **_kwargs) -> str:
        version = self._review.latest_version(user_id, campaign_id)
        approval = self._repo.latest_approval_for_run(run_id=run.id)
        if version is None or approval is None:
            raise AppException(code="AGENT_INVALID_STATE", http_status=409, message="缺少可激活的计划版本或审批")
        if approval.action_digest != _digest({"campaign_id": campaign_id, "version": version["version"]}):
            raise AppException(code="AGENT_INVALID_STATE", http_status=409,
                               message="审批与当前计划版本不一致，拒绝激活")
        self._run_tool(
            user_id=user_id, run=run, sequence=5, tool=ACTIVATION_TOOL,
            arguments={"campaign_id": campaign_id, "version": version["version"]},
            action=lambda: self._review.activate_version(user_id, campaign_id, version["version"]),
        )
        return f"计划 v{version['version']} 已激活"

    def _step_materialize_tasks(self, *, user_id: str, run: AgentRunRow, campaign_id: str, **_kwargs) -> str:
        self._run_tool(
            user_id=user_id, run=run, sequence=6, tool="task.create",
            arguments={"campaign_id": campaign_id},
            action=lambda: self._review.materialize_today(user_id, campaign_id),
        )
        return f"今日待办已就绪（{self._review.today_task_count(user_id, campaign_id)} 项）"

    def _step_create_artifact(self, *, user_id: str, run: AgentRunRow, campaign_id: str, **_kwargs) -> str:
        version = self._review.latest_version(user_id, campaign_id)
        if version is None:
            raise AppException(code="AGENT_INVALID_STATE", http_status=409, message="缺少计划版本")
        payload = json.dumps(
            {"campaign_id": campaign_id, "version": version["version"],
             "content_hash": version["content_hash"], "content": version["content"]},
            ensure_ascii=False, sort_keys=True, indent=2,
        ).encode("utf-8")

        def action():
            existing = self._artifact_repo.find(run_id=run.id, artifact_type=ARTIFACT_TYPE,
                                                version=version["version"])
            if existing is not None:
                return existing
            return self._artifacts.create(
                user_id=user_id, run_id=run.id, artifact_type=ARTIFACT_TYPE,
                version=version["version"], mime_type="application/json", content=payload,
            )

        self._run_tool(user_id=user_id, run=run, sequence=7, tool="artifact.create",
                       arguments={"campaign_id": campaign_id, "version": version["version"]}, action=action)
        artifact = self._artifact_repo.find(run_id=run.id, artifact_type=ARTIFACT_TYPE,
                                            version=version["version"])
        return f"计划 Artifact 已生成 {artifact.id if artifact else version['version']}"

    # ===== 收尾与视图 =====

    def _succeed(self, user_id: str, run: AgentRunRow) -> dict:
        updated = self._repo.update_run(run_id=run.id, status="SUCCEEDED", phase="IDLE", current_role=ROLE)
        self._events.append(run_id=run.id, event_type="RUN_SUCCEEDED", summary="期末复习计划已就绪")
        return self.view(user_id, updated)

    def _fail(self, user_id: str, run: AgentRunRow, message: str) -> AgentRunRow:
        updated = self._repo.update_run(run_id=run.id, status="FAILED", phase="IDLE", current_role=ROLE)
        self._events.append(run_id=run.id, event_type="RUN_FAILED", summary=message)
        return updated

    def _campaign_for_run(self, user_id: str, run: AgentRunRow) -> dict | None:
        if not run.context_snapshot_id:
            return None
        snapshot = self._repo.get_context_snapshot(snapshot_id=run.context_snapshot_id, user_id=user_id)
        if snapshot is None:
            return None
        campaign_id = snapshot["scope"].get("campaign_id")
        if not campaign_id:
            return None
        return self._review.repo.get_campaign(user_id, campaign_id)

    def pending_approval(self, *, user_id: str, run: AgentRunRow):
        """该运行是否还有未决审批；用于阻止旧接口绕过审批直接激活。"""
        if run.domain != DOMAIN:
            return None
        return self._repo.pending_approval_for_run(run_id=run.id)

    def view(self, *, user_id: str, run: AgentRunRow | None) -> dict:
        if run is None:
            return {"run": None, "steps": [], "approval": None, "campaign_id": None}
        approval = self._repo.pending_approval_for_run(run_id=run.id)
        if approval is None:
            approval = self._repo.latest_approval_for_run(run_id=run.id)
        snapshot = (self._repo.get_context_snapshot(snapshot_id=run.context_snapshot_id, user_id=user_id)
                    if run.context_snapshot_id else None)
        return {
            "run": run,
            "steps": self._repo.list_steps(run_id=run.id),
            "approval": approval,
            "campaign_id": snapshot["scope"].get("campaign_id") if snapshot else None,
        }
