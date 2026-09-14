"""期末复习领域服务(历史遗留壳)。

期末复习的读写现在由两处承担:

- 只读与命令入口:`api/routes/final_review.py` + `repositories/final_review_repository.py`;
- 审批后的高风险写操作:`services/agent_runtime/handlers/final_review.py`,
  经 `ToolInvocationGateway` 执行,终态由 `AgentWorker` 原子写入。

本模块保留类名只为兼容早期导入方,但它**不再提供任何领域副作用**:
早期版本在这里直接 `activate` 计划、直接应用调整,绕过了 Gateway 的
角色授权、参数 Schema、资源归属与审批复核,是"审批未通过但副作用已发生"的窗口。
写操作请改用受管接口(`POST /final-review/campaigns/{id}/activate`、
`POST /final-review/adjustment-proposals/{id}/decision`)。
"""
from __future__ import annotations

from ..core.exceptions import AgentRuntimeError
from ..repositories.final_review_repository import FinalReviewRepository
from ..repositories.personal_task_repository import PersonalTaskRepository

_LEGACY_WRITE_MESSAGE = (
    "期末复习写操作必须经 ToolInvocationGateway 执行，"
    "请改用受管接口 POST /final-review/campaigns/{campaign_id}/activate 或 "
    "POST /final-review/adjustment-proposals/{proposal_id}/decision"
)


class FinalReviewService:
    """已停用的写入口,仅保留签名以便早期调用方显式失败而不是静默绕过策略。"""

    def __init__(self, repository: FinalReviewRepository, tasks: PersonalTaskRepository) -> None:
        self.repo, self.tasks = repository, tasks

    def campaign(self, user_id: str, exam_id: str, capacity: int) -> dict:
        raise AgentRuntimeError(_LEGACY_WRITE_MESSAGE, code="AGENT_INVALID_STATE", http_status=409)

    def generate(self, user_id: str, campaign_id: str) -> dict:
        raise AgentRuntimeError(_LEGACY_WRITE_MESSAGE, code="AGENT_INVALID_STATE", http_status=409)

    def today(self, user_id: str, campaign_id: str) -> dict:
        raise AgentRuntimeError(_LEGACY_WRITE_MESSAGE, code="AGENT_INVALID_STATE", http_status=409)

    def activate(self, user_id: str, campaign_id: str) -> dict:
        raise AgentRuntimeError(_LEGACY_WRITE_MESSAGE, code="AGENT_INVALID_STATE", http_status=409)

    def analyze(self, user_id: str, campaign_id: str) -> dict:
        raise AgentRuntimeError(_LEGACY_WRITE_MESSAGE, code="AGENT_INVALID_STATE", http_status=409)

    def decide(self, user_id: str, proposal_id: str, decision: str) -> dict:
        raise AgentRuntimeError(_LEGACY_WRITE_MESSAGE, code="AGENT_INVALID_STATE", http_status=409)


__all__ = ["FinalReviewService"]
