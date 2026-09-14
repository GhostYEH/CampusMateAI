"""期末复习服务包(§8.1)。

完整闭环: Campaign → 不可变 Plan Version → Daily Agenda → Evidence →
Analyzer → Adjustment Proposal → Risk/Approval → 新版本。

复用现有 runtime 服务:
- container.agent_run_manager
- container.agent_model_router
- container.agent_risk_engine
- container.agent_approval_gate
- container.agent_artifact_manager
- container.agent_tool_gateway(审批后写操作的唯一执行入口)

审批后的高风险写操作(激活计划版本、应用调整提案)不再由路由直接执行,
而是由 `services/agent_runtime/handlers/final_review.py` 经
`ToolInvocationGateway` 完成;路由只创建命令或解析用户审批。
"""
from __future__ import annotations

__all__: list[str] = []