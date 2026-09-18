"""LearningPlannerService 的状态驱动策略接入。

覆盖四件事：

1. 不传 `strategy_context` 时行为与历史完全一致（不追加解释码、不写策略绑定）；
2. 不同策略产生结构上可观测的差异（条目上限、预算、单项时长）；
3. 策略永远不能突破 `available_minutes`；
4. 策略版本进入 input digest / knowledge_bindings，旧版本计划会被判为 STALE。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from adaptive_intervention_helpers import sample_strategy
from app.core.config import Settings
from app.core.exceptions import LearningPlanStale
from app.core.security import hash_password
from app.schemas.adaptive_intervention import PlanningStrategyContext, StrategyPlanningParameters
from app.services.container import reset_container_for_tests

AVAILABLE_MINUTES = 120


def _setup():
    container = reset_container_for_tests(Settings(app_env="test", database_url="sqlite:///:memory:"))
    student = container.user_repository.create_user(
        username="adaptive_plan_student", password_hash=hash_password("Demo123456"), role="student"
    )
    return container, student


def _seed_tasks(container, user_id: str, count: int = 6) -> list[str]:
    now = datetime.now(timezone.utc)
    return [
        container.personal_task_repository.create_task(
            user_id=user_id,
            title=f"复习第 {index + 1} 章",
            deadline=(now + timedelta(hours=6 * (index + 1))).isoformat(),
        ).id
        for index in range(count)
    ]


def _context(
    letter: str, *, intervention_id: str = "intv_test_1", version: str | None = None,
    available_minutes: int = AVAILABLE_MINUTES,
):
    """把策略层真实产出的决策包成规划器可消费的上下文。

    `available_minutes` 必须与规划时的取值一致：策略层会据此收紧单项时长，
    否则会造出"预算 15 分钟但单项 20 分钟"的虚假输入。
    """
    assessment, strategy = sample_strategy(letter, available_minutes=available_minutes)
    return PlanningStrategyContext(
        strategy_code=strategy.strategy_code,
        strategy_version=version or strategy.strategy_version,
        planning_parameters=strategy.planning_parameters,
        intervention_id=intervention_id,
        baseline_core_run_id=assessment.core_run_id,
        baseline_academic_run_id=assessment.academic_run_id,
        baseline_world_run_id=assessment.world_run_id,
        rationale_codes=list(strategy.rationale_codes),
    )


def _generate(container, user_id: str, *, key: str, context=None):
    return container.learning_planner_service.generate(
        user_id=user_id, available_minutes=AVAILABLE_MINUTES, force_new=True,
        idempotency_key=key, strategy_context=context,
    )


def test_without_strategy_context_keeps_legacy_behaviour() -> None:
    container, student = _setup()
    _seed_tasks(container, student.id)
    plan = _generate(container, student.id, key="no-strategy")
    assert plan.items
    bindings = plan.run.knowledge_bindings or {}
    # 没有策略上下文时不能凭空写入策略绑定，否则旧调用方会被"看起来有策略"。
    assert "strategy_code" not in bindings
    assert "strategy_version" not in bindings
    assert "intervention_id" not in bindings
    assert all(
        not code.startswith("strategy_") for item in plan.items for code in item.explanation_codes
    )


def test_strategy_changes_item_cap_budget_and_explanation_codes() -> None:
    container, student = _setup()
    _seed_tasks(container, student.id)
    reduced = _generate(container, student.id, key="reduced", context=_context("a"))
    upsifted = _generate(container, student.id, key="upsifted", context=_context("b"))

    assert reduced.items and upsifted.items
    # A：max_plan_items=3，单项 20 分钟；B：max_plan_items=10，单项 30 分钟。
    assert len(reduced.items) <= 3
    assert reduced.run.allocated_minutes < upsifted.run.allocated_minutes
    assert max(item.estimated_minutes for item in reduced.items) < max(
        item.estimated_minutes for item in upsifted.items
    )
    assert "strategy_workload_reduction" in {
        code for item in reduced.items for code in item.explanation_codes
    }
    assert "strategy_challenge_upshift" in {
        code for item in upsifted.items for code in item.explanation_codes
    }
    # 两种策略的输入摘要必须不同，否则幂等复用会把 A 的计划当成 B 的。
    assert reduced.run.input_digest != upsifted.run.input_digest


@pytest.mark.parametrize("minutes", [15, 30, 60, 120, 240])
@pytest.mark.parametrize("letter", ["a", "b", "c"])
def test_allocated_minutes_never_exceeds_available(minutes: int, letter: str) -> None:
    container, student = _setup()
    _seed_tasks(container, student.id, count=3)
    plan = container.learning_planner_service.generate(
        user_id=student.id, available_minutes=minutes, force_new=True,
        idempotency_key=f"budget-{minutes}-{letter}",
        strategy_context=_context(letter, available_minutes=minutes),
    )
    assert plan.run.allocated_minutes <= minutes
    assert sum(item.estimated_minutes for item in plan.items) == plan.run.allocated_minutes


def test_strategy_parameters_are_schema_checked_before_planning() -> None:
    """越界参数必须在进入规划前被拦下，而不是产出超预算计划。"""
    container, student = _setup()
    _seed_tasks(container, student.id)
    context = _context("a").model_dump(mode="json")
    context["planning_parameters"]["max_plan_items"] = 999
    with pytest.raises(ValidationError):
        _generate(container, student.id, key="bad-params", context=context)
    _plans, total = container.learning_plan_repository.list_plans(
        user_id=student.id, page=1, page_size=20
    )
    assert total == 0


def test_strategy_version_enters_input_digest() -> None:
    container, student = _setup()
    _seed_tasks(container, student.id)
    current = _generate(container, student.id, key="v1", context=_context("a"))
    future = _generate(
        container, student.id, key="v9", context=_context("a", version="adaptive-strategy-v9")
    )
    plain = _generate(container, student.id, key="plain")
    assert current.run.input_digest != future.run.input_digest
    assert current.run.input_digest != plain.run.input_digest


def test_identical_strategy_context_is_reusable() -> None:
    container, student = _setup()
    _seed_tasks(container, student.id)
    first = _generate(container, student.id, key="reuse-1", context=_context("a"))
    second = container.learning_planner_service.generate(
        user_id=student.id, available_minutes=AVAILABLE_MINUTES, force_new=False,
        idempotency_key="reuse-2", strategy_context=_context("a"),
    )
    assert second.plan_id == first.plan_id


def test_plan_records_safe_strategy_and_intervention_bindings() -> None:
    container, student = _setup()
    _seed_tasks(container, student.id)
    context = _context("a", intervention_id="intv_binding_1")
    plan = _generate(container, student.id, key="binding", context=context)
    bindings = plan.run.knowledge_bindings or {}
    assert bindings["intervention_id"] == "intv_binding_1"
    assert bindings["strategy_code"] == "WORKLOAD_REDUCTION"
    assert bindings["strategy_version"] == context.strategy_version
    assert bindings["baseline_state_runs"] == {
        "core": "lrun_a_core", "academic": "lrun_a_academic", "world": "lrun_a_world",
    }
    # 只保存安全引用：不能把评估 JSON、理由正文或学生原始内容写进绑定。
    serialized = str(bindings)
    for forbidden in ("assessment_json", "strategy_json", "raw_content", "chat"):
        assert forbidden not in serialized


def test_bound_strategy_version_invalidates_plan_on_execute() -> None:
    container, student = _setup()
    _seed_tasks(container, student.id)
    planner = container.learning_planner_service
    plan = _generate(
        container, student.id, key="stale-strategy",
        context=_context("a", version="adaptive-strategy-v0"),
    )
    assert plan.run.knowledge_bindings["strategy_version"] == "adaptive-strategy-v0"
    planner.decide(user_id=student.id, plan_id=plan.plan_id, decision="ACCEPT")
    with pytest.raises(LearningPlanStale):
        planner.execute(user_id=student.id, plan_id=plan.plan_id)
    stored = planner.repository.get_plan(plan.plan_id, user_id=student.id)
    assert stored is not None and stored.status == "STALE"


def _foundation_context(available_minutes: int = AVAILABLE_MINUTES) -> PlanningStrategyContext:
    """与策略目录中 FOUNDATION_REINFORCEMENT 一致的参数（foundation_emphasis 高于阈值）。"""
    return _context("a", available_minutes=available_minutes).model_copy(
        update={
            "strategy_code": "FOUNDATION_REINFORCEMENT",
            "planning_parameters": StrategyPlanningParameters(
                max_plan_items=5, target_item_minutes=25, workload_scale=1.0,
                foundation_emphasis=0.7, challenge_level="BASELINE", pacing_mode="STEADY",
            ),
        }
    )


def test_foundation_emphasis_appends_review_item_with_academic_evidence() -> None:
    """高基础强调时追加基础复习项；证据必须指向真实的知识掌握观测快照。"""
    container, student = _setup()
    planner = container.learning_planner_service
    context = _foundation_context()
    knowledge = _knowledge_snapshot()
    items = planner._apply_strategy(  # noqa: SLF001 - 直接验证策略落到条目上的规则
        [
            {
                "item_type": "TASK_FOCUS", "course_id": "course-1", "task_id": "task-1",
                "estimated_minutes": 30, "priority_score": 1.0, "priority_components": {},
                "explanation_codes": ["deadline_soon"], "evidence": [],
            }
        ],
        context, {"course-1": [object()]}, [knowledge],
    )
    review = [item for item in items if item["item_type"] == "REVIEW_AND_REFLECT"]
    assert len(review) == 1
    assert review[0]["course_id"] == "course-1"
    assert "strategy_foundation_reinforcement" in review[0]["explanation_codes"]
    assert review[0]["evidence"][0]["evidence_type"] == "ACADEMIC_SNAPSHOT"
    assert review[0]["evidence"][0]["reference_id"] == knowledge.snapshot_id


def test_workload_reduction_does_not_add_extra_items() -> None:
    """减负策略不追加基础复习项：它已经通过更少更短的条目减负，薄弱信号留在 rationale 里。"""
    container, student = _setup()
    planner = container.learning_planner_service
    context = _context("a")
    assert context.planning_parameters.foundation_emphasis < 0.5
    items = planner._apply_strategy(  # noqa: SLF001
        [
            {
                "item_type": "TASK_FOCUS", "course_id": "course-1", "task_id": "task-1",
                "estimated_minutes": 30, "priority_score": 1.0, "priority_components": {},
                "explanation_codes": [], "evidence": [],
            }
        ],
        context, {"course-1": [object()]}, [_knowledge_snapshot()],
    )
    assert [item for item in items if item["item_type"] == "REVIEW_AND_REFLECT"] == []


def test_foundation_review_item_requires_usable_knowledge_observation() -> None:
    container, student = _setup()
    planner = container.learning_planner_service
    context = _foundation_context()
    base_item = {
        "item_type": "TASK_FOCUS", "course_id": "course-1", "task_id": "task-1",
        "estimated_minutes": 30, "priority_score": 1.0, "priority_components": {},
        "explanation_codes": [], "evidence": [],
    }
    # 没有知识观测 / 观测不可用 / 没有课程内容证据时都不能凭空造复习项。
    for snapshots, course_data in (
        ([], {"course-1": [object()]}),
        ([_knowledge_snapshot(quality="unavailable")], {"course-1": [object()]}),
        ([_knowledge_snapshot()], {}),
    ):
        items = planner._apply_strategy([dict(base_item)], context, course_data, snapshots)  # noqa: SLF001
        assert [item for item in items if item["item_type"] == "REVIEW_AND_REFLECT"] == []


def _knowledge_snapshot(quality: str = "verified"):
    from adaptive_intervention_helpers import snapshot

    return snapshot(
        "lrun_knowledge", "knowledge_mastery_observation",
        {"knowledge_point_count": 12, "own_mastery_rate": 48.0, "data_completeness": quality},
        quality, index=1,
    )
