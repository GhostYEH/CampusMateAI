"""期末复习服务包(§8.1)。

完整闭环: Campaign → 不可变 Plan Version → Daily Agenda → Evidence →
Analyzer → Adjustment Proposal → Risk/Approval → 新版本。

复用现有 runtime 服务:
- container.agent_run_manager
- container.agent_model_router
- container.agent_risk_engine
- container.agent_approval_gate
- container.agent_artifact_manager
"""
from __future__ import annotations

__all__: list[str] = []