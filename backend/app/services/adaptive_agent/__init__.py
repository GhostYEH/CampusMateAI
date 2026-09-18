"""状态驱动干预子系统。

只包含三块职责单一的组件：

- `StudentStateAnalyzer` —— 把服务端状态投影 + 预测 + 当前目标，确定性、可解释地
  归纳成 `StudentStateAssessment`。
- `StrategyPolicy` —— 从有限策略目录里按稳定优先级选出一条 `StrategyDecision`。
- `AdaptiveInterventionService` —— 唯一编排入口：投影 → 分析 → 策略 → 干预记录 → 差异化计划。

边界：不新建平行的学生画像 / 任务系统 / Agent Runtime；不把逻辑堆回
`learner_state_service.py` 或 `learning_planner_service.py`。
"""
from .intervention_service import AdaptiveInterventionService
from .state_analyzer import StudentStateAnalyzer
from .strategy_policy import StrategyPolicy

__all__ = ["AdaptiveInterventionService", "StudentStateAnalyzer", "StrategyPolicy"]
