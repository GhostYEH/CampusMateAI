"""带租约的 Agent Worker —— 唯一允许推进 Agent Run 的执行者。

设计要点(v2):
- **租约**:领取运行必须拿到有期限租约;只有持有者可续租、写 checkpoint 或完成运行。
- **至少一次**:Handler 可能重复执行,领域副作用必须由 Handler 自行幂等。
- **崩溃恢复**:租约过期后由另一个 Worker 调用 Handler 的 `recover()` 决定重排还是明确失败,
  而不是无条件把所有中断运行标记失败。
- **不接单模式**:`disabled` 不领取任务,`drain` 排空已有队列但拒绝新任务(由路由拦截)。

HTTP 请求内不执行任何工作流;任何模式都不得悄悄回退为请求内执行。
"""
from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from ...core.exceptions import AgentRuntimeError
from ...repositories.agent_runtime_repository import AgentRuntimeRepository
from .event_store import AgentEventStore
from .handlers.base import HandlerContext, RecoveryAction
from .handlers.registry import JobHandlerRegistry

WORKER_MODE_WORKER = "worker"
WORKER_MODE_DRAIN = "drain"
WORKER_MODE_DISABLED = "disabled"
VALID_WORKER_MODES = (WORKER_MODE_WORKER, WORKER_MODE_DRAIN, WORKER_MODE_DISABLED)

# 可重试错误码。其余错误一律直接失败,避免对确定性错误反复重试。
RETRYABLE_ERROR_CODES = frozenset({"AGENT_PROVIDER_UNAVAILABLE"})

# 默认退避:1s / 5s / 15s(超出后沿用最后一次)。
DEFAULT_RETRY_BACKOFF_SECONDS = (1, 5, 15)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.isoformat()


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class WorkerRunReport:
    """一次 `run_once()` 的结果,便于测试与观测断言。"""

    action: str  # idle | executed | recovered | skipped
    run_id: Optional[str] = None


class AgentWorker:
    """单进程、可并发受限的工作者。"""

    def __init__(
        self,
        repository: AgentRuntimeRepository,
        registry: JobHandlerRegistry,
        event_store: Optional[AgentEventStore] = None,
        *,
        mode: str = WORKER_MODE_WORKER,
        worker_id: Optional[str] = None,
        lease_seconds: float = 30.0,
        heartbeat_seconds: float = 10.0,
        poll_interval_seconds: float = 0.5,
        concurrency: int = 1,
        clock: Callable[[], datetime] = _utc_now,
        sleeper: Callable[[float], Any] = asyncio.sleep,
    ) -> None:
        if mode not in VALID_WORKER_MODES:
            raise ValueError(f"未知的 AGENT_RUNTIME_MODE: {mode}")
        if lease_seconds <= 0 or heartbeat_seconds <= 0 or poll_interval_seconds < 0:
            raise ValueError("租约、心跳与轮询间隔必须为正数")
        if heartbeat_seconds >= lease_seconds:
            raise ValueError("心跳间隔必须小于租约时长,否则无法在过期前续租")
        if concurrency < 1:
            raise ValueError("并发度必须 >= 1")
        self._repo = repository
        self._registry = registry
        self._events = event_store or AgentEventStore(repository)
        self._mode = mode
        # worker_id 随机且不可复用:重启后的实例不得沿用旧租约身份。
        self.worker_id = worker_id or f"worker_{uuid.uuid4().hex[:16]}"
        self._lease_seconds = lease_seconds
        self._heartbeat_seconds = heartbeat_seconds
        self._poll_interval = poll_interval_seconds
        self._concurrency = concurrency
        self._clock = clock
        self._sleeper = sleeper
        self._stopping = False
        self._tasks: list[asyncio.Task] = []

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def accepts_new_jobs(self) -> bool:
        """路由据此判断能否入队新任务。`drain` 只排空不接新单。"""
        return self._mode == WORKER_MODE_WORKER

    @property
    def is_running(self) -> bool:
        return any(not task.done() for task in self._tasks)

    # ===== 生命周期 =====

    async def start(self) -> None:
        if self._mode == WORKER_MODE_DISABLED:
            return
        if self.is_running:
            return
        self._stopping = False
        for _ in range(self._concurrency):
            self._tasks.append(asyncio.ensure_future(self._loop()))

    async def stop(self) -> None:
        """停止领取并等待当前运行写完 checkpoint。"""
        self._stopping = True
        tasks, self._tasks = self._tasks, []
        # 不取消正在执行的 loop：它必须先让当前 Handler 收口并写入 checkpoint/终态。
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _loop(self) -> None:
        while not self._stopping:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - Worker 循环不能因单次异常退出
                pass
            if self._stopping:
                break
            if self._poll_interval:
                try:
                    await self._sleeper(self._poll_interval)
                except asyncio.CancelledError:
                    raise

    # ===== 单次调度 =====

    async def run_once(self) -> WorkerRunReport:
        """恢复过期租约 → 领取一个可执行的 Run → 执行。"""
        now = self._clock()
        recovered = await self._recover_expired_leases(now)
        if recovered is not None:
            return recovered
        if self._mode == WORKER_MODE_DISABLED:
            return WorkerRunReport(action="skipped")
        run = self._repo.claim_next_run(
            owner=self.worker_id,
            now=_iso(now),
            lease_expires_at=_iso(now + timedelta(seconds=self._lease_seconds)),
        )
        if run is None:
            return WorkerRunReport(action="idle")
        return await self._execute_claimed(run, now)

    async def _recover_expired_leases(self, now: datetime) -> Optional[WorkerRunReport]:
        """租约过期后按 Handler 决策收口;有效租约绝不抢占。"""
        for run in self._repo.list_expired_lease_runs(now=_iso(now)):
            expires_at = _parse_iso(run.get("lease_expires_at"))
            if expires_at is None or expires_at > now:
                continue
            if run["status"] not in {"RUNNING", "QUEUED"}:
                continue
            if await self._recover_run(run, now):
                return WorkerRunReport(action="recovered", run_id=run["run_id"])
        return None

    async def _recover_run(self, run: dict, now: datetime) -> bool:
        """把中断的运行交回 Handler 决策:重排(从 checkpoint 继续)或明确失败。"""
        run_id = run["run_id"]
        handler = self._registry.get(run.get("handler_code") or "")
        context = self._build_context(run)
        # 先留下可审计的观测点,再交回 Handler 决策。
        self._events.append(
            run_id=run_id, type="RUN_RECOVERY_STARTED", status=run["status"],
            phase="RECOVERY_CHECKING", role="runtime",
            summary="检测到执行中断，正在检查安全恢复点",
        )
        if handler is None:
            return self._fail_run(
                run, error_code="AGENT_CAPABILITY_DISABLED",
                error_message="运行对应的处理器已不可用", now=now,
                event_type="RUN_FAILED", summary="运行对应的能力已下线，已终止",
            )
        try:
            decision = await handler.recover(context)
        except AgentRuntimeError as exc:
            return self._fail_run(
                run, error_code=exc.code, error_message=str(exc)[:256], now=now,
                event_type="RUN_FAILED", summary="运行无法恢复，已终止",
            )
        except Exception as exc:  # noqa: BLE001 - 恢复失败必须稳定收口
            return self._fail_run(
                run, error_code="AGENT_INVALID_STATE", error_message=str(exc)[:256], now=now,
                event_type="RUN_FAILED", summary="运行恢复检查失败，已终止",
            )
        if decision is None or decision.action is RecoveryAction.FAIL:
            return self._fail_run(
                run,
                error_code=(getattr(decision, "error_code", None) or "AGENT_INVALID_STATE"),
                error_message="运行中断后无法安全恢复",
                now=now, event_type="RUN_FAILED",
                summary="运行中断后无法安全恢复，已终止",
            )
        try:
            self._repo.transition_run_with_event(
                run_id, "QUEUED",
                expected_statuses=["RUNNING", "QUEUED"],
                phase="IDLE", clear_lease=True,
                next_attempt_at=_iso(now),
                checkpoint=decision.checkpoint or context.checkpoint,
                event_type="RUN_RECOVERED", event_status="QUEUED", event_phase="IDLE",
                event_summary="检测到执行中断，已按安全恢复点重新排队",
            )
            return True
        except AgentRuntimeError:
            return False

    # ===== 执行 =====

    async def _execute_claimed(self, run: dict, now: datetime) -> WorkerRunReport:
        run_id = run["run_id"]
        heartbeat = asyncio.ensure_future(self._heartbeat(run_id))
        try:
            result = await self._invoke_handler(run)
        except AgentRuntimeError as exc:
            return self._handle_failure(run, exc, now)
        except Exception as exc:  # noqa: BLE001 - 未建模异常统一转成 FAILED
            return self._handle_failure(
                run,
                AgentRuntimeError(str(exc)[:256], code="AGENT_INVALID_STATE", http_status=409),
                now,
            )
        finally:
            heartbeat.cancel()
            try:
                await heartbeat
            except (asyncio.CancelledError, Exception):  # noqa: B014
                pass
        return self._finish_success(run, result, now)

    async def _invoke_handler(self, run: dict):
        handler = self._registry.get(run.get("handler_code") or "")
        if handler is None:
            raise AgentRuntimeError(
                "运行对应的处理器已不可用", code="AGENT_CAPABILITY_DISABLED", http_status=409
            )
        context = self._build_context(run)
        return await handler.execute(context)

    def _build_context(self, run: dict) -> HandlerContext:
        job = self._repo.get_job(run["job_id"]) or {}
        input_ref = job.get("input_ref", job.get("input_ref_json"))
        if isinstance(input_ref, str):
            try:
                input_ref = json.loads(input_ref)
            except (TypeError, ValueError):
                input_ref = {}
        if not isinstance(input_ref, dict):
            input_ref = {}
        checkpoint: Optional[dict] = None
        raw_checkpoint = run.get("checkpoint_json")
        if raw_checkpoint:
            try:
                loaded = json.loads(raw_checkpoint)
                if isinstance(loaded, dict):
                    checkpoint = loaded
            except (TypeError, ValueError):
                checkpoint = None
        return HandlerContext(
            run_id=run["run_id"],
            job_id=run["job_id"],
            user_id=run["user_id"],
            job_kind=job.get("job_kind") or (run.get("handler_code") or ""),
            input_ref=input_ref,
            checkpoint=checkpoint,
            attempt_no=int(run.get("attempt_no") or 0),
        )

    def _finish_success(self, run: dict, result, now: datetime) -> WorkerRunReport:
        run_id = run["run_id"]
        if getattr(result, "status", None) == "AWAITING_APPROVAL":
            # 审批等待不占 Worker:释放租约,由审批结果重新排队。
            self._repo.transition_run_with_event(
                run_id, "AWAITING_APPROVAL",
                expected_statuses=["RUNNING"], lease_owner=self.worker_id,
                phase="WAITING_FOR_APPROVAL", clear_lease=True,
                checkpoint=getattr(result, "checkpoint", None),
                event_type="APPROVAL_REQUIRED", event_status="AWAITING_APPROVAL",
                event_phase="WAITING_FOR_APPROVAL",
                event_summary=getattr(result, "summary", None) or "需要用户确认后继续",
            )
            return WorkerRunReport(action="executed", run_id=run_id)
        checkpoint = getattr(result, "checkpoint", None)
        if checkpoint:
            # checkpoint 先落库:此后即使进程崩溃,重放也不会产生第二次领域副作用。
            self._repo.save_checkpoint(
                run_id, self.worker_id, checkpoint,
                heartbeat_at=_iso(self._clock()),
            )
        self._repo.complete_run_with_job_output_and_event(
            run_id,
            getattr(result, "status", "SUCCEEDED"),
            lease_owner=self.worker_id,
            expected_statuses=["RUNNING"],
            job_input_ref_patch=getattr(result, "job_output_patch", None) or {},
            phase="PERSISTING_RESULT",
            event_role="planner",
            event_summary=getattr(result, "summary", None),
        )
        return WorkerRunReport(action="executed", run_id=run_id)

    def _handle_failure(self, run: dict, exc: AgentRuntimeError, now: datetime) -> WorkerRunReport:
        run_id = run["run_id"]
        max_attempts = self._max_attempts_for(run)
        attempt_no = int(run.get("attempt_no") or 1)
        if exc.code in RETRYABLE_ERROR_CODES and attempt_no < max_attempts:
            delay = DEFAULT_RETRY_BACKOFF_SECONDS[
                min(attempt_no - 1, len(DEFAULT_RETRY_BACKOFF_SECONDS) - 1)
            ]
            try:
                self._repo.transition_run_with_event(
                    run_id, "QUEUED",
                    expected_statuses=["RUNNING"], lease_owner=self.worker_id,
                    phase="IDLE", clear_lease=True,
                    next_attempt_at=_iso(now + timedelta(seconds=delay)),
                    error_code=exc.code, error_message=str(exc)[:256],
                    event_type="RUN_RETRY_SCHEDULED", event_status="QUEUED",
                    event_phase="IDLE",
                    event_summary=f"执行失败，{delay} 秒后重试（第 {attempt_no}/{max_attempts} 次）",
                )
                return WorkerRunReport(action="executed", run_id=run_id)
            except AgentRuntimeError:
                pass  # 并发下已被其它路径收口,落到下面的明确失败
        self._fail_run(
            run, error_code=exc.code or "AGENT_INVALID_STATE", error_message=str(exc)[:256],
            now=now, event_type="RUN_FAILED", summary="运行失败，请稍后重试",
        )
        return WorkerRunReport(action="executed", run_id=run_id)

    def _fail_run(
        self, run: dict, *, error_code: str, error_message: str, now: datetime,
        event_type: str, summary: str,
    ) -> bool:
        try:
            self._repo.transition_run_with_event(
                run["run_id"], "FAILED",
                expected_statuses=["RUNNING", "QUEUED"],
                lease_owner=self.worker_id if run.get("status") == "RUNNING" else None,
                phase="IDLE", clear_lease=True,
                error_code=error_code, error_message=error_message,
                event_type=event_type, event_status="FAILED", event_phase="IDLE",
                event_summary=summary,
            )
            return True
        except AgentRuntimeError:
            return False

    def _max_attempts_for(self, run: dict) -> int:
        handler = self._registry.get(run.get("handler_code") or "")
        declared = getattr(handler, "max_attempts", 3)
        try:
            value = int(declared)
        except (TypeError, ValueError):
            value = 3
        return max(1, value)

    # ===== 心跳 =====

    async def _heartbeat(self, run_id: str) -> None:
        while True:
            try:
                await self._sleeper(self._heartbeat_seconds)
            except asyncio.CancelledError:
                return
            now = self._clock()
            try:
                self._repo.renew_run_lease(
                    run_id, self.worker_id,
                    heartbeat_at=_iso(now),
                    lease_expires_at=_iso(now + timedelta(seconds=self._lease_seconds)),
                )
            except AgentRuntimeError:
                return  # 租约已不属于本 Worker:停止续租,交给恢复流程


__all__ = [
    "AgentWorker",
    "WorkerRunReport",
    "VALID_WORKER_MODES",
    "WORKER_MODE_DISABLED",
    "WORKER_MODE_DRAIN",
    "WORKER_MODE_WORKER",
]
