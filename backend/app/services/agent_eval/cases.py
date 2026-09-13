"""Agent Runtime 评测用例规格(SSOT)。

分层(参考通用评测金字塔,并贴合本项目的验证范围):
  L0 组件级确定性检查(不需要模型、不需要网络)
  L1 单模块集成(注册表/路由/状态机)
  L2 跨模块业务流程(期末复习 / 通知事务 / 课程研究的关键不变量)

优先级:P0 发布门禁 · P1 场景包 · P2 探索性
流程类型:happy · alt · negative · boundary · state_machine

新增用例请在 _REGISTRY 里登记 check 名称,并在 checks.py 实现同名函数。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Level = Literal["L0", "L1", "L2"]
Priority = Literal["P0", "P1", "P2"]
Flow = Literal["happy", "alt", "negative", "boundary", "state_machine"]


@dataclass(frozen=True)
class EvalCase:
    """一条评测用例的声明。"""

    case_id: str
    level: Level
    priority: Priority
    flow: Flow
    title: str
    check: str
    description: str = ""


_REGISTRY: tuple[EvalCase, ...] = (
    # ===== L0 组件级 =====
    EvalCase(
        "L0-context-budget-keeps-scalars",
        "L0",
        "P0",
        "boundary",
        "上下文超预算时仍保留容量等标量事实",
        "check_context_budget_keeps_scalars",
    ),
    EvalCase(
        "L0-hard-deny-payment",
        "L0",
        "P0",
        "negative",
        "支付类动作被不可覆盖地拒绝",
        "check_hard_deny_payment",
    ),
    EvalCase(
        "L0-risk-grading",
        "L0",
        "P0",
        "happy",
        "风险分级给出 MANUAL_ONLY / CONFIRM_REQUIRED 正确档位",
        "check_risk_grading",
    ),
    EvalCase(
        "L0-usage-extraction",
        "L0",
        "P1",
        "happy",
        "provider 用量字段可被解析为 token 计数",
        "check_usage_extraction",
    ),
    # ===== L1 单模块集成 =====
    EvalCase(
        "L1-role-manifest",
        "L1",
        "P0",
        "happy",
        "角色可由清单声明并支持工具白名单校验",
        "check_role_manifest",
    ),
    EvalCase(
        "L1-primary-provider-fallback",
        "L1",
        "P0",
        "alt",
        "未配智谱/讯飞时 primary 兜底并可真实路由",
        "check_primary_provider_fallback",
    ),
    EvalCase(
        "L1-dual-review-degrades",
        "L1",
        "P1",
        "boundary",
        "单 provider 时 dual_review 降级并显式标记",
        "check_dual_review_degrades",
    ),
    EvalCase(
        "L1-cancel-terminal-guard",
        "L1",
        "P0",
        "state_machine",
        "取消后不再推进,终态不可再转换",
        "check_cancel_terminal_guard",
    ),
    EvalCase(
        "L1-stale-run-sweep",
        "L1",
        "P1",
        "negative",
        "长期未推进的 run 被兜底置为失败",
        "check_stale_run_sweep",
    ),
    # ===== L2 业务流程不变量 =====
    EvalCase(
        "L2-notice-manual-action-blocked",
        "L2",
        "P0",
        "negative",
        "通知事务:外部提交/支付类动作不会被自动执行",
        "check_notice_action_not_auto_executed",
    ),
    EvalCase(
        "L2-research-academic-policy",
        "L2",
        "P0",
        "negative",
        "课程研究:考试限制下不返回完整代答",
        "check_research_policy_restriction",
    ),
    EvalCase(
        "L2-final-review-version-immutable",
        "L2",
        "P0",
        "state_machine",
        "期末复习:计划版本不可变,调整需批准后产生新版本",
        "check_final_review_version_immutable",
    ),
)


def all_cases() -> tuple[EvalCase, ...]:
    return _REGISTRY


def cases_by_level(level: Level) -> tuple[EvalCase, ...]:
    return tuple(case for case in _REGISTRY if case.level == level)


def case_ids() -> tuple[str, ...]:
    return tuple(case.case_id for case in _REGISTRY)


__all__ = ["EvalCase", "all_cases", "case_ids", "cases_by_level"]
