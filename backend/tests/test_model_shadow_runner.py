from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.models.model_capability import ModelCapabilityRequest
from app.services.llm.base import LLMResponse
from app.services.model_capability_registry import ModelCapabilityRegistry
from app.services.model_shadow_runner import ModelShadowRunner


def _request(name: str, payload: dict) -> ModelCapabilityRequest:
    return ModelCapabilityRequest(
        capability_name=name, capability_version="v1", subject_user_id=None,
        input_payload=payload, request_id=f"request-{name}", id_mode=True,
    )


class FakeLLM:
    name = "campusmate-lm:test"
    available = True

    def __init__(self, content: str, delay: float = 0) -> None:
        self.content = content
        self.delay = delay
        self.calls = 0

    async def chat(self, messages, *, temperature=0.0, max_tokens=None, timeout=None):
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        return LLMResponse(self.content)


def test_disabled_candidate_returns_deterministic_fallback_without_calling_model() -> None:
    candidate = FakeLLM("{}"); runner = ModelShadowRunner(registry=ModelCapabilityRegistry(), candidate_llm=candidate, enabled=False)
    result = asyncio.run(runner.run(_request("learning_summary_v1", { "warning_codes": [], "explanation_codes": ["deadline_urgent"],
        "item_type": "TASK_FOCUS", "estimated_minutes": 30, "data_quality": "verified",
        "evidence_count": 1, "deadline_bucket": "DUE_24H", "state_band": None, "confidence_bucket": "HIGH",
    })))
    assert result.used_fallback is True
    assert result.failure_code == "MODEL_DISABLED"
    assert result.schema_valid and result.policy_valid
    assert candidate.calls == 0


def test_timeout_and_invalid_output_are_safe_fallbacks() -> None:
    registry = ModelCapabilityRegistry()
    request = _request("learning_summary_v1", { "warning_codes": [], "explanation_codes": ["deadline_urgent"],
        "item_type": "TASK_FOCUS", "estimated_minutes": 30, "data_quality": "verified",
        "evidence_count": 1, "deadline_bucket": "DUE_24H", "state_band": None, "confidence_bucket": "HIGH",
    })
    timeout_runner = ModelShadowRunner(registry=registry, candidate_llm=FakeLLM("{}", delay=0.05),
                                       enabled=True, sample_rate=1.0, timeout_ms=1)
    timed = asyncio.run(timeout_runner.run(request))
    assert timed.failure_code == "MODEL_TIMEOUT" and timed.used_fallback
    invalid_runner = ModelShadowRunner(registry=registry, candidate_llm=FakeLLM("not-json"),
                                       enabled=True, sample_rate=1.0, timeout_ms=100)
    invalid = asyncio.run(invalid_runner.run(request))
    assert invalid.failure_code == "MODEL_SCHEMA_INVALID" and invalid.used_fallback
    assert invalid.output_payload is not None


def test_candidate_write_tool_response_is_rejected_and_never_invoked() -> None:
    candidate = FakeLLM('{"tool_name":"create_personal_task","arguments":{},"confidence":1,"abstained":false}')
    runner = ModelShadowRunner(registry=ModelCapabilityRegistry(), candidate_llm=candidate, enabled=True, sample_rate=1.0)
    result = asyncio.run(runner.run(_request("read_only_tool_routing_v1", {
        "intent_code": "read_state", "authorized_resource_type": "learner_state",
        "candidate_read_tools": ["read_core_state"], "parameter_schema": {"projection_kind": "CORE"},
        "resource_ownership": "current_user",
    })))
    assert result.failure_code == "MODEL_POLICY_VIOLATION"
    assert result.used_fallback and result.output_payload["abstained"] is True
    assert candidate.calls == 1


def test_circuit_breaker_opens_after_repeated_failures_and_recovers_after_cooldown() -> None:
    candidate = FakeLLM("not-json")
    runner = ModelShadowRunner(registry=ModelCapabilityRegistry(), candidate_llm=candidate, enabled=True,
                               sample_rate=1.0, circuit_breaker_threshold=2, circuit_breaker_cooldown_seconds=0.01)
    request = _request("learning_summary_v1", { "warning_codes": [], "explanation_codes": ["deadline_urgent"],
        "item_type": "TASK_FOCUS", "estimated_minutes": 30, "data_quality": "verified",
        "evidence_count": 1, "deadline_bucket": "DUE_24H", "state_band": None, "confidence_bucket": "HIGH",
    })
    asyncio.run(runner.run(request)); asyncio.run(runner.run(request))
    opened = asyncio.run(runner.run(request))
    assert opened.failure_code == "MODEL_CIRCUIT_OPEN"
    import time; time.sleep(0.02)
    recovered = asyncio.run(runner.run(request))
    assert recovered.failure_code == "MODEL_SCHEMA_INVALID"


def test_circuit_status_is_read_only_and_does_not_consume_half_open_probe() -> None:
    runner = ModelShadowRunner(registry=ModelCapabilityRegistry(), enabled=False,
                               circuit_breaker_threshold=1, circuit_breaker_cooldown_seconds=0.01)
    assert runner.circuit_status("learning_summary_v1")["state"] == "CLOSED"
    assert runner.canary_allowed("learning_summary_v1") is True
    runner._record_failure("learning_summary_v1")
    assert runner.circuit_status("learning_summary_v1")["state"] == "OPEN"
    assert runner.canary_allowed("learning_summary_v1") is False
    import time; time.sleep(0.02)
    assert runner.circuit_status("learning_summary_v1")["state"] == "HALF_OPEN"
    assert runner.canary_allowed("learning_summary_v1") is True
    assert runner.circuit_status("learning_summary_v1")["state"] == "HALF_OPEN"
    assert runner.circuit_status("learning_summary_v1")["probe_in_flight"] is False
    assert runner.canary_allowed("learning_summary_v1") is True
    assert runner._circuit_allows("learning_summary_v1").allowed is True
    assert runner.canary_allowed("learning_summary_v1") is False
    runner._record_success("learning_summary_v1")
    assert runner.circuit_status("learning_summary_v1")["state"] == "CLOSED"
    assert runner.canary_allowed("learning_summary_v1") is True


def test_canary_gate_uses_read_only_circuit_query_without_side_effects() -> None:
    from app.core.config import Settings
    from app.core.security import hash_password
    from app.main import create_app
    from app.services.container import reset_container_for_tests
    from fastapi.testclient import TestClient
    import json as jsonlib
    from datetime import datetime, timezone

    settings = Settings(
        app_env="test", database_url="sqlite:///:memory:", campusmate_lm_canary_enabled=True,
        campusmate_lm_enabled=True, campusmate_lm_base_url="http://test-candidate:8000",
        campusmate_lm_api_key="test-key", campusmate_lm_model_name="test-model",
        campusmate_lm_circuit_breaker_cooldown_seconds=60.0,
    )
    container = reset_container_for_tests(settings)
    container.user_repository.create_user(
        username="canary_gate_probe", password_hash=hash_password("Demo123456"), role="student", display_name="P")
    TestClient(create_app())
    uid = container.user_repository.get_user_by_username("canary_gate_probe").id
    now = datetime.now(timezone.utc).isoformat()
    with container.db.transaction() as conn:
        conn.execute(
            """INSERT INTO model_promotion_decisions
               (decision_id, model_key, model_version, capability_name, capability_version,
                dataset_version, evaluator_version, threshold_version, metrics_digest,
                decision, failed_gates_json, created_at)
               VALUES (?, 'campusmate-lm', 'candidate-v1', 'learning_summary_v1', 'v1',
                'ds-v1', 'eval-v1', 'th-v1', 'digest', 'ELIGIBLE_FOR_CANARY', '[]', ?)""",
            ("promo_probe", now),
        )
    runner = container.model_shadow_runner
    for _ in range(runner.circuit_breaker_threshold):
        runner._record_failure("learning_summary_v1")
    first = container.learner_control_service.canary_gate(capability_name="learning_summary_v1", user_id=uid)
    second = container.learner_control_service.canary_gate(capability_name="learning_summary_v1", user_id=uid)
    assert first["allowed"] is False and first["reason"] == "circuit_breaker_open"
    assert second["allowed"] is False and second["reason"] == "circuit_breaker_open"
    assert jsonlib.dumps(first, sort_keys=True) == jsonlib.dumps(second, sort_keys=True)


# ===== 并发 / 熔断状态机回归 =====
#
# 这组用例针对的是"旧请求晚返回"与"并发 half-open"两类只有真并发才暴露的问题：
# 单请求串行路径永远看不出这些缺陷。
#
# 关键不变量：
#   1. 一次调用的结果只能作用于**它放行时所在的那个熔断代次**；
#   2. 同一 capability 同时最多一个 half-open 探测；
#   3. 失败 / 取消 / 成功三种结束路径都必须把探测权还回去，且不误伤他人。

_SUMMARY_PAYLOAD = {
    "warning_codes": [], "explanation_codes": ["deadline_urgent"], "item_type": "TASK_FOCUS",
    "estimated_minutes": 30, "data_quality": "verified", "evidence_count": 1,
    "deadline_bucket": "TODAY", "state_band": None, "confidence_bucket": "HIGH",
}


def _summary_request(request_id: str = "request-summary") -> ModelCapabilityRequest:
    # 注意：request_id 是**请求信封**字段，绝不能塞进 input_payload ——
    # payload 是 extra="forbid" 的严格 schema，多一个键就会在调用模型之前失败。
    return ModelCapabilityRequest(
        capability_name="learning_summary_v1", capability_version="v1", subject_user_id="shadow-user",
        input_payload=dict(_SUMMARY_PAYLOAD), request_id=request_id, id_mode=True,
    )


class GatedLLM:
    """可外部控制何时返回的假候选，用来制造"在熔断打开之前发起、之后才返回"的旧请求。"""

    name = "campusmate-lm:gated"
    available = True

    def __init__(self, *, content: str = '{"summary":"按已提供的优先级安排。","claim_codes":[]}',
                 raise_on_release: bool = False) -> None:
        self.content = content
        self.raise_on_release = raise_on_release
        self.calls = 0
        self.gate = asyncio.Event()
        self.entered = asyncio.Event()

    async def chat(self, messages, *, temperature=0.0, max_tokens=None, timeout=None):
        self.calls += 1
        self.entered.set()
        await self.gate.wait()
        if self.raise_on_release:
            raise RuntimeError("candidate failed after the circuit had already opened")
        return LLMResponse(self.content)


def _open_circuit(runner: ModelShadowRunner, name: str = "learning_summary_v1") -> None:
    """把熔断推到打开状态（阈值次失败）。"""
    for _ in range(runner.circuit_breaker_threshold):
        runner._record_failure(name)


def _gated_runner(candidate, **overrides) -> ModelShadowRunner:
    kwargs = dict(registry=ModelCapabilityRegistry(), candidate_llm=candidate, enabled=True,
                  sample_rate=1.0, circuit_breaker_threshold=1, circuit_breaker_cooldown_seconds=0.0,
                  # 闸门会一直挂到测试主动放行：默认 1500ms 超时会把"挂起"变成"超时"。
                  timeout_ms=60_000, concurrency_limit=8)
    kwargs.update(overrides)
    return ModelShadowRunner(**kwargs)


def test_late_success_cannot_release_another_half_open_probe_or_close_the_circuit() -> None:
    """旧请求晚返回成功时：不得释放当前探测者的 probe，也不得关闭熔断。"""

    async def scenario() -> None:
        candidate = GatedLLM()
        runner = _gated_runner(candidate)

        # 1. 熔断关闭时发起一个"慢"请求（放行代次 = 0），它挂在 gate 上
        late = asyncio.create_task(runner.run(_summary_request("late-success")))
        await asyncio.wait_for(candidate.entered.wait(), timeout=5)

        # 2. 另一个请求失败 → 熔断打开（代次推进）
        _open_circuit(runner)
        opened = runner.circuit_status("learning_summary_v1")
        assert opened["state"] == "HALF_OPEN", opened  # cooldown=0，已进入半开
        assert opened["failures"] == 1

        # 3. half-open 探测者占用探测权
        admission = runner._circuit_allows("learning_summary_v1")
        assert admission.allowed is True
        assert runner.circuit_status("learning_summary_v1")["probe_in_flight"] is True

        # 4. 旧请求现在才返回
        candidate.gate.set()
        await late

        status = runner.circuit_status("learning_summary_v1")
        assert status["probe_in_flight"] is True, "旧请求晚结束不得释放他人 probe"
        assert status["state"] == "HALF_OPEN", "旧请求的陈旧成功不得关闭熔断"
        assert status["failures"] == 1, "陈旧结果不得改写失败计数"
        # 同一 capability 同时最多一个 half-open 探测
        assert runner._circuit_allows("learning_summary_v1").allowed is False

    asyncio.run(scenario())


def test_late_failure_cannot_release_another_half_open_probe_or_inflate_failures() -> None:
    """旧请求晚返回失败时：同样不得释放他人 probe，也不得污染失败计数。"""

    async def scenario() -> None:
        candidate = GatedLLM(raise_on_release=True)
        runner = _gated_runner(candidate)

        late = asyncio.create_task(runner.run(_summary_request("late-failure")))
        await asyncio.wait_for(candidate.entered.wait(), timeout=5)

        _open_circuit(runner)
        assert runner.circuit_status("learning_summary_v1")["failures"] == 1
        admission = runner._circuit_allows("learning_summary_v1")
        assert admission.allowed is True

        candidate.gate.set()
        await late

        status = runner.circuit_status("learning_summary_v1")
        assert status["probe_in_flight"] is True, "旧请求晚结束不得释放他人 probe"
        assert status["failures"] == 1, "陈旧失败不得把失败计数继续推高"
        assert status["state"] == "HALF_OPEN"
        assert runner._circuit_allows("learning_summary_v1").allowed is False

    asyncio.run(scenario())


def test_concurrent_half_open_calls_produce_exactly_one_probe() -> None:
    """并发打进来的 half-open 请求只能有一个真的探测候选，其余必须被拒。"""

    async def scenario() -> None:
        # delay 必须 > 0：假模型若完全不 await，第一个协程会一口气跑完（含关闭熔断），
        # 后面的请求自然全部放行 —— 那样测的就不是并发，而是串行。
        candidate = FakeLLM('{"summary":"按已提供的优先级安排。","claim_codes":[]}', delay=0.01)
        runner = _gated_runner(candidate)
        _open_circuit(runner)

        results = await asyncio.gather(*[
            runner.run(_summary_request(f"concurrent-{index}")) for index in range(6)
        ])

        assert candidate.calls == 1, "同一 capability 同时最多一个 half-open 探测"
        assert sum(1 for item in results if item.inference_source == "REAL_MODEL") == 1
        assert sum(1 for item in results if item.failure_code == "MODEL_CIRCUIT_OPEN") == 5
        status = runner.circuit_status("learning_summary_v1")
        assert status["state"] == "CLOSED", "探测成功后熔断必须关闭"
        assert status["probe_in_flight"] is False

        # 熔断关闭后必须重新正常放行（并发拒绝不能把熔断卡在半开）
        after = await runner.run(_summary_request("concurrent-after"))
        assert after.inference_source == "REAL_MODEL"
        assert candidate.calls == 2

    asyncio.run(scenario())


def test_probe_failure_reopens_and_releases_the_probe() -> None:
    """探测失败：重新打开熔断、释放探测权、失败计数推进。"""

    async def scenario() -> None:
        candidate = FakeLLM("not-json")
        runner = _gated_runner(candidate)
        _open_circuit(runner)

        result = await runner.run(_summary_request("probe-failure"))
        assert result.failure_code == "MODEL_SCHEMA_INVALID"

        status = runner.circuit_status("learning_summary_v1")
        assert status["state"] == "HALF_OPEN", status
        assert status["probe_in_flight"] is False, "失败后必须释放探测权"
        assert status["failures"] == 2, "探测失败要计入失败计数"
        # 释放之后允许下一次探测
        assert runner._circuit_allows("learning_summary_v1").allowed is True

    asyncio.run(scenario())


def test_probe_cancellation_releases_the_probe_without_touching_failures() -> None:
    """探测被取消：必须释放探测权，但不得改动失败计数与开启时刻。"""

    async def scenario() -> None:
        candidate = GatedLLM()
        runner = _gated_runner(candidate)
        _open_circuit(runner)
        before = runner.circuit_status("learning_summary_v1")

        task = asyncio.create_task(runner.run(_summary_request("probe-cancel")))
        await asyncio.wait_for(candidate.entered.wait(), timeout=5)
        assert runner.circuit_status("learning_summary_v1")["probe_in_flight"] is True

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        after = runner.circuit_status("learning_summary_v1")
        assert after["probe_in_flight"] is False, "取消后探测权必须被释放，否则熔断永久卡在 HALF_OPEN"
        assert after["failures"] == before["failures"], "取消不是失败，不得改写失败计数"
        assert after["state"] == "HALF_OPEN"
        assert runner._circuit_allows("learning_summary_v1").allowed is True

    asyncio.run(scenario())


def test_probe_success_closes_the_circuit_and_resets_failures() -> None:
    """探测成功：熔断关闭、失败计数归零、探测权释放。"""

    async def scenario() -> None:
        candidate = FakeLLM('{"summary":"按已提供的优先级安排。","claim_codes":[]}')
        runner = _gated_runner(candidate)
        _open_circuit(runner)
        assert runner.circuit_status("learning_summary_v1")["failures"] == 1

        result = await runner.run(_summary_request("probe-success"))
        assert result.inference_source == "REAL_MODEL"
        assert candidate.calls == 1

        status = runner.circuit_status("learning_summary_v1")
        assert status["state"] == "CLOSED"
        assert status["failures"] == 0
        assert status["probe_in_flight"] is False

    asyncio.run(scenario())


def test_replanning_worker_thread_never_touches_the_circuit_breaker() -> None:
    """后台 Worker 跑在 `asyncio.to_thread` 里：它的调用图不得触及熔断器。

    `main.py` 与 `AdaptiveReplanningWorker` 都用 `asyncio.to_thread` 执行 tick，
    也就是说 tick 在 **worker 线程**里跑。熔断状态目前只在事件循环上被修改，
    这正是"不需要加锁"的前提。一旦 adaptive_agent 将来引用了熔断器，
    这个前提就失效了 —— 所以用源码级断言把它钉住。
    """
    package = Path(__file__).resolve().parents[1] / "app" / "services" / "adaptive_agent"
    assert package.is_dir(), f"找不到 adaptive_agent 包：{package}"
    offenders: list[tuple[str, str]] = []
    for path in sorted(package.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in ("model_shadow_runner", "ModelShadowRunner", "model_assist_service", "_circuits"):
            if token in text:
                offenders.append((path.name, token))
    assert offenders == [], (
        f"adaptive_agent 跑在 worker 线程，不得触及熔断器（否则需要加锁）：{offenders}"
    )


def _code_without_comments(text: str) -> str:
    """去掉 `#` 行内注释，避免注释里提到方法名造成假阳性。"""
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def test_circuit_mutations_are_confined_to_run() -> None:
    """只有 `run()` 可以改动熔断状态；其余调用点必须是只读的。

    这条不变量是"熔断状态只在事件循环上被修改"的静态证据。
    """
    root = Path(__file__).resolve().parents[1]
    runner_source = _code_without_comments(
        (root / "app" / "services" / "model_shadow_runner.py").read_text(encoding="utf-8"))
    gate_source = _code_without_comments(
        (root / "app" / "services" / "learner_control_service.py").read_text(encoding="utf-8"))
    # 门禁不得出现任何**调用**会写熔断状态的方法（注释里说明原因不算）。
    for token in ("_circuit_allows(", "_record_failure(", "_record_success(", "_release_probe("):
        assert token not in gate_source, f"门禁不得调用会写状态的 {token}"
    assert "canary_allowed(" in gate_source, "门禁必须使用只读查询"
    # runner 内部：申请放行只允许出现在 run() 里。
    assert runner_source.count("self._circuit_allows(") == 1, "只允许 run() 申请放行"
    # 三个记账/释放入口都必须带代次，漏一个等于没修。
    for token in ("self._record_failure(", "self._record_success(", "self._release_probe("):
        occurrences = runner_source.count(token)
        with_generation = runner_source.count(f"{token}request.capability_name, generation=generation")
        assert occurrences == with_generation, f"{token} 必须全部带 generation：{occurrences} vs {with_generation}"


# ===== CLOSED 状态下的并发成功 / 失败：generation 只能由真正的状态迁移推进 =====
#
# 回归背景：`_record_success` 曾经**无条件** `generation += 1`。于是 CLOSED 状态下
# 同一批并发请求（都持有 generation=0）里，只要有一个成功先返回，generation 就变成 1，
# 同批随后返回的失败全被判为"陈旧结果"丢弃 —— 候选服务部分故障时，
# 即使失败数足以达到阈值，熔断也永远打不开。
#
# 规则（本组用例即契约）：
#   - generation 只在真正的状态迁移时推进：CLOSED → OPEN、OPEN/HALF_OPEN → CLOSED；
#   - CLOSED 状态下的成功只清零失败计数，不推进 generation；
#   - CLOSED 状态下的失败正常累加，达到阈值即迁移为 OPEN。


class OrderedLLM:
    """按调用序号控制返回结果的假候选：用来构造确定性的并发交错。

    每次调用各有一个闸门，测试可以先让**所有**请求完成 admission
    （证明它们拿到同一个 generation），再按想要的顺序逐个放行。
    """

    name = "campusmate-lm:ordered"
    available = True

    def __init__(self, results: list[str]) -> None:
        # "ok" → 返回合法 JSON；"fail" → 抛异常，走 MODEL_UNAVAILABLE 分支
        self.results = list(results)
        self.calls = 0
        self.entered = [asyncio.Event() for _ in results]
        self.gates = [asyncio.Event() for _ in results]

    async def chat(self, messages, *, temperature=0.0, max_tokens=None, timeout=None):
        index = self.calls
        self.calls += 1
        self.entered[index].set()
        await self.gates[index].wait()
        if self.results[index] == "fail":
            raise RuntimeError("candidate failure (ordered)")
        return LLMResponse('{"summary":"按已提供的优先级安排。","claim_codes":[]}')


async def _run_ordered(
    results: list[str],
    *,
    threshold: int,
    cooldown: float = 60.0,
    request_prefix: str = "ordered",
):
    """让 `results` 里的每个请求都先完成 admission，再按给定顺序逐个放行。

    返回 `(放行后的熔断状态, admission 时的 generation, 真实候选调用次数)`。
    """
    candidate = OrderedLLM(results)
    runner = ModelShadowRunner(
        registry=ModelCapabilityRegistry(), candidate_llm=candidate, enabled=True,
        sample_rate=1.0, circuit_breaker_threshold=threshold,
        circuit_breaker_cooldown_seconds=cooldown,
        # 夹具必须让所有请求**同时**在途：默认 concurrency_limit=2 会让第 3 个请求
        # 卡在信号量上，默认 timeout_ms=1500 又会让先到的请求先超时 ——
        # 那样测的就不是"同一批并发"，而是"排队 + 超时"。
        concurrency_limit=len(results),
        timeout_ms=60_000,
    )
    tasks = [
        asyncio.create_task(runner.run(_summary_request(f"{request_prefix}-{index}")))
        for index in range(len(results))
    ]
    for event in candidate.entered:
        await asyncio.wait_for(event.wait(), timeout=5)
    generation_at_admission = runner.circuit_status("learning_summary_v1")["generation"]
    for index in range(len(results)):
        candidate.gates[index].set()
        await tasks[index]
    return runner.circuit_status("learning_summary_v1"), generation_at_admission, candidate.calls


def test_closed_concurrent_success_must_not_disable_later_failures() -> None:
    """CLOSED 并发：先成功、后失败 —— 失败必须仍然被计入并打开熔断。

    这是"部分故障"最典型的形状：一个请求恰好成功，其余都失败。
    如果成功把 generation 推进了，后面的失败会被当成陈旧结果丢掉，
    熔断永远不打开，流量继续打向已故障的候选服务。
    """

    async def scenario() -> None:
        status, generation_at_admission, calls = await _run_ordered(
            ["ok", "fail", "fail"], threshold=2, request_prefix="closed-partial-failure",
        )

        assert calls == 3, "三个请求都必须真的调用过候选（否则测的不是并发）"
        assert generation_at_admission == 0, "CLOSED 状态下三个请求应当拿到同一个 generation"

        assert status["state"] == "OPEN", f"失败数已达阈值，熔断必须打开：{status}"
        assert status["failures"] >= 2, f"失败必须被计入：{status}"
        assert status["probe_in_flight"] is False

    asyncio.run(scenario())


def test_closed_success_does_not_advance_generation() -> None:
    """CLOSED 状态下的成功不是状态迁移：只清零失败计数，generation 不动。"""

    async def scenario() -> None:
        status, generation_at_admission, calls = await _run_ordered(
            ["ok", "ok", "ok"], threshold=2, request_prefix="closed-all-success",
        )
        assert calls == 3
        assert generation_at_admission == 0
        assert status["state"] == "CLOSED"
        assert status["failures"] == 0
        assert status["generation"] == 0, "CLOSED 阶段没有任何状态迁移，generation 必须保持 0"

    asyncio.run(scenario())


def test_interleaved_closed_success_and_failure_follow_a_defined_rule() -> None:
    """CLOSED 并发成功/失败交错：成功清零、失败累加、generation 只在迁移时推进。

    与上一个用例互补 —— 那个证明"一个成功不会让后续失败失效"，
    这个钉住"成功确实会清零计数"，两条一起才把 CLOSED 阶段的语义说清楚。
    """

    async def scenario() -> None:
        # (a) 失败 → 成功 → 失败：成功把计数清零，因此只有 1 次连续失败，熔断保持关闭
        status, generation_at_admission, calls = await _run_ordered(
            ["fail", "ok", "fail"], threshold=2, request_prefix="interleave-a",
        )
        assert calls == 3
        assert generation_at_admission == 0
        assert status["state"] == "CLOSED", f"成功清零后未达阈值：{status}"
        assert status["failures"] == 1, f"成功清零后只应累计到 1 次失败：{status}"
        assert status["generation"] == 0, "CLOSED 阶段的成功/失败都不是迁移，generation 必须保持 0"

        # (b) 失败 → 失败：达到阈值 → 唯一一次迁移 CLOSED → OPEN
        status, _generation, calls = await _run_ordered(
            ["fail", "fail"], threshold=2, request_prefix="interleave-b",
        )
        assert calls == 2
        assert status["state"] == "OPEN", status
        assert status["failures"] >= 2, status
        assert status["generation"] == 1, f"只应有 CLOSED → OPEN 一次迁移：{status}"

        # (c) 成功 → 失败 → 失败：成功清零后仍能累计到阈值并打开
        status, _generation, calls = await _run_ordered(
            ["ok", "fail", "fail"], threshold=2, request_prefix="interleave-c",
        )
        assert calls == 3
        assert status["state"] == "OPEN", status
        assert status["failures"] >= 2, status

    asyncio.run(scenario())


def test_generation_advances_once_per_real_state_transition() -> None:
    """代次 = **状态迁移计数**：三次真实迁移之后 generation 恰好为 3。

    前面两个用例只钉住了 CLOSED 阶段与 CLOSED → OPEN；这里把"其他明确状态迁移"
    也逐一钉住数值（HALF_OPEN → OPEN、OPEN/HALF_OPEN → CLOSED），
    否则"代次只在迁移时推进"这句话在第三种迁移上仍然只是注释里的承诺。
    顺带证明陈旧代次既不能推进代次，也不能改动状态。
    """

    async def scenario() -> None:
        name = "learning_summary_v1"
        candidate = FakeLLM("not-json")
        # threshold=1、cooldown=0：打开后立刻进入半开，迁移序列完全确定，无需 sleep。
        runner = _gated_runner(candidate)

        assert runner.circuit_status(name)["generation"] == 0

        # 迁移 1：CLOSED → OPEN（失败数达到阈值）
        await runner.run(_summary_request("migration-open"))
        assert runner.circuit_status(name)["generation"] == 1, "CLOSED → OPEN 必须推进一次代次"
        assert runner.circuit_status(name)["state"] == "HALF_OPEN", "cooldown=0 时冷却已过，应为 HALF_OPEN"

        # 迁移 2：HALF_OPEN → OPEN（探测失败后重新打开）
        await runner.run(_summary_request("migration-reopen"))
        assert runner.circuit_status(name)["generation"] == 2, "HALF_OPEN → OPEN 必须推进一次代次"

        # 迁移 3：OPEN/HALF_OPEN → CLOSED（探测成功）
        candidate.content = '{"summary":"按已提供的优先级安排。","claim_codes":[]}'
        result = await runner.run(_summary_request("migration-close"))
        assert result.inference_source == "REAL_MODEL"
        status = runner.circuit_status(name)
        assert status["state"] == "CLOSED"
        assert status["failures"] == 0
        assert status["generation"] == 3, "OPEN/HALF_OPEN → CLOSED 必须推进一次代次"

        # 陈旧代次：既不能推进代次，也不能关闭熔断 / 改写失败计数
        runner._record_success(name, generation=0)
        runner._record_failure(name, generation=1)
        after = runner.circuit_status(name)
        assert after["generation"] == 3, f"陈旧代次必须被丢弃：{after}"
        assert after["state"] == "CLOSED" and after["failures"] == 0, after

    asyncio.run(scenario())
