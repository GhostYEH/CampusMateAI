"""JobHandler 契约 —— 工作流与 HTTP 路由之间的唯一边界。

路由只做认证、幂等声明、入队和响应映射;具体业务放在 Handler 里,
由 Worker 通过 `JobHandlerRegistry` 执行。任何 `if job_kind == ...` 的执行分支
都不应再出现在路由层。

Handler 可能被重复执行(至少一次投递),因此:
- 领域副作用必须自带幂等键或请求哈希;
- `recover()` 只允许在安全恢复点之后决定"重排"或"明确失败";
- 不保存 prompt、完整模型响应或敏感工具参数。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal, Protocol

from pydantic import BaseModel


class RecoveryAction(StrEnum):
    """Worker 崩溃后的恢复决策。"""

    REQUEUE = "REQUEUE"
    FAIL = "FAIL"


@dataclass(frozen=True)
class RecoveryDecision:
    """由 Handler 决定崩溃运行如何收口。"""

    action: RecoveryAction
    checkpoint: dict[str, Any] | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class HandlerContext:
    """一次执行的只读输入。"""

    run_id: str
    job_id: str
    user_id: str
    job_kind: str
    input_ref: dict[str, Any]
    checkpoint: dict[str, Any] | None
    attempt_no: int


@dataclass(frozen=True)
class HandlerResult:
    """执行结果。终态由 Worker 原子提交,Handler 不直接写状态。"""

    status: Literal["SUCCEEDED", "PARTIAL", "AWAITING_APPROVAL"]
    artifact_ids: tuple[str, ...] = ()
    job_output_patch: dict[str, Any] = field(default_factory=dict)
    checkpoint: dict[str, Any] | None = None
    summary: str | None = None


class JobHandler(Protocol):
    """工作流处理器。所有字段必须显式声明,注册表在启动时校验。"""

    code: str
    version: str
    job_kind: str
    enabled: bool
    input_model: type[BaseModel]
    max_attempts: int

    async def execute(self, context: HandlerContext) -> HandlerResult: ...
    async def recover(self, context: HandlerContext) -> RecoveryDecision: ...


class JobHandlerRegistrationError(RuntimeError):
    """Handler 注册表启动校验失败。

    这是启动期的硬失败,不允许静默降级为"默认放行";
    配置损坏时必须阻止 runtime 启动,而不是带着未知能力继续服务。
    """


__all__ = [
    "HandlerContext",
    "HandlerResult",
    "JobHandler",
    "JobHandlerRegistrationError",
    "RecoveryAction",
    "RecoveryDecision",
]
