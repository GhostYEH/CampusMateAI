"""CampusMate-LM 业务接线测试：影子观测 + 只读金丝雀展示。

这组用例回答三个问题，而不是"某个函数对不对"：

1. 已注册的只读能力有没有**真实业务调用点**？（`GET /learning-plans/{id}/summary`）
2. 门禁全过时，候选结果有没有以只读字段**进入一个真实生产响应**？
3. 超时 / 非法 JSON / 策略违规 / 熔断 / 采样未命中 / 未配置时，
   生产响应是否仍然是**完全确定性的**，并且没有任何候选输出进入业务表？

安全边界同时在这里钉死：响应与日志不得出现密钥、base URL、候选原文或用户自由文本。
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.models.model_capability import ModelCapabilityRequest
from app.services.container import reset_container_for_tests
from app.services.llm.base import LLMResponse

PASSWORD = "Demo123456"
API = "/api/v1"
CANDIDATE_API_KEY = "campusmate-lm-test-key-not-real"
CANDIDATE_BASE_URL = "http://candidate.invalid:8000"

# 与 `model_capability_registry.SUMMARY_CLAIM_EVIDENCE` 同源：候选只能声明
# 输入里真有证据的结论。这里让假模型表现得像一个守规矩的候选。
_CLAIM_EVIDENCE = {
    "PRIORITIZE_NEAR_DEADLINE": {"deadline_urgent", "PRIORITIZE_NEAR_DEADLINE"},
    "USE_SHORT_SESSION": {"short_session", "USE_SHORT_SESSION"},
    "DATA_QUALITY_PARTIAL": {"data_quality_partial", "DATA_QUALITY_PARTIAL"},
}
# 只读注解的标记串：用来在业务表里搜"候选输出有没有漏进去"。
MARKER_SUMMARY = "候选模型只读注解标记串，不得进入任何业务表。"


class GroundedFakeLLM:
    """守规矩的假候选：只声明输入里有证据的结论，并记录实际收到的 messages。"""

    name = "campusmate-lm:test"
    available = True

    def __init__(self, *, raw: str | None = None, delay: float = 0.0, summary: str = MARKER_SUMMARY) -> None:
        self.raw = raw
        self.delay = delay
        self.summary = summary
        self.calls = 0
        # 发送给候选模型的实际报文：用于验证"不外发任何稳定内部 ID"。
        self.messages_seen: list[list[dict[str, str]]] = []

    async def chat(self, messages, *, temperature=0.0, max_tokens=None, timeout=None):
        self.calls += 1
        self.messages_seen.append(messages)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.raw is not None:
            return LLMResponse(self.raw)
        payload = json.loads(messages[-1]["content"])
        codes = sorted(
            claim for claim, evidence in _CLAIM_EVIDENCE.items()
            if evidence & set(payload.get("explanation_codes") or [])
        )
        return LLMResponse(json.dumps({"summary": self.summary, "claim_codes": codes}))


class CancellingLLM:
    """在调用瞬间被取消的候选：验证 half-open 探测权不会因此卡死。"""

    name = "campusmate-lm:cancelled"
    available = True

    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, messages, *, temperature=0.0, max_tokens=None, timeout=None):
        self.calls += 1
        raise asyncio.CancelledError()


def _settings(**overrides) -> Settings:
    base = dict(
        app_env="test",
        database_url="sqlite:///:memory:",
        campusmate_lm_enabled=True,
        campusmate_lm_base_url=CANDIDATE_BASE_URL,
        campusmate_lm_api_key=CANDIDATE_API_KEY,
        campusmate_lm_model_name="test-model",
        campusmate_lm_shadow_sample_rate=1.0,
        campusmate_lm_canary_enabled=True,
        campusmate_lm_canary_sample_rate=1.0,
        campusmate_lm_timeout_ms=500,
    )
    base.update(overrides)
    return Settings(**base)


def _setup(*, candidate=None, username="canary_student", **overrides):
    container = reset_container_for_tests(_settings(**overrides))
    if candidate is not None:
        container.model_shadow_runner.candidate_llm = candidate
    student = container.user_repository.create_user(
        username=username, password_hash=hash_password(PASSWORD), role="student"
    )
    client = TestClient(create_app())
    response = client.post(f"{API}/auth/login", json={"username": username, "password": PASSWORD})
    assert response.status_code == 200, response.text
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    return container, student, client, headers


def _insert_promotion_decision(container, capability_name="learning_summary_v1",
                               decision="ELIGIBLE_FOR_CANARY", failed_gates=None):
    now = datetime.now(timezone.utc).isoformat()
    with container.db.transaction() as conn:
        conn.execute(
            """INSERT INTO model_promotion_decisions
               (decision_id, model_key, model_version, capability_name, capability_version,
                dataset_version, evaluator_version, threshold_version, metrics_digest,
                decision, failed_gates_json, created_at)
               VALUES (?, 'campusmate-lm', 'candidate-v1', ?, 'v1',
                'ds-v1', 'eval-v1', 'th-v1', 'digest-placeholder', ?, ?, ?)""",
            (f"promo_{capability_name}_{now}", capability_name, decision,
             json.dumps(failed_gates or []), now),
        )


def _urgent_task(container, user_id: str, *, hours: int = 2):
    """期限 24h 内的待办 → 计划条目必然带 `deadline_urgent` 解释码。"""
    return container.personal_task_repository.create_task(
        user_id=user_id,
        title="候选接线验证任务",
        deadline=(datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(),
    )


def _generate_plan(client, headers, *, key: str) -> dict:
    response = client.post(
        f"{API}/learning-plans/generate",
        json={"available_minutes": 60, "idempotency_key": key},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _summary(client, headers, plan_id: str) -> dict:
    response = client.get(f"{API}/learning-plans/{plan_id}/summary", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _business_counts(client, headers) -> dict:
    response = client.get(f"{API}/learner-state/data-summary", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    # shadow_run_count 是影子表计数，本来就应该变；业务计数必须不变。
    return {key: value for key, value in body.items() if key != "shadow_run_count"}


def _shadow_rows(container, capability_name="learning_summary_v1") -> list[dict]:
    with container.db.query() as conn:
        return [
            dict(row) for row in conn.execute(
                "SELECT r.*, x.used_fallback, x.failure_code, x.schema_valid, x.policy_valid "
                "FROM model_shadow_runs r JOIN model_shadow_results x ON x.shadow_run_id = r.shadow_run_id "
                "WHERE r.capability_name = ? ORDER BY r.created_at, r.shadow_run_id",
                (capability_name,),
            ).fetchall()
        ]


def _assert_business_tables_clean(container, marker: str = MARKER_SUMMARY) -> None:
    """候选输出不得出现在任何业务表里。

    逐表逐列扫标记串：拼错表名会先炸在 PRAGMA 上，而不是静默通过。
    """
    tables = (
        "learning_plans", "learning_plan_runs", "learning_plan_items", "learner_events",
        "adaptive_interventions", "learner_state_snapshots", "learner_state_projection_runs",
        "personal_tasks",
    )
    with container.db.query() as conn:
        for table in tables:
            columns = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            assert columns, f"业务表 {table} 不存在（拼写错误会让这个断言失效）"
            for column in columns:
                found = conn.execute(
                    f"SELECT COUNT(*) AS c FROM {table} WHERE CAST({column} AS TEXT) LIKE ?",
                    (f"%{marker}%",),
                ).fetchone()
                assert found["c"] == 0, f"候选输出泄漏进业务表 {table}.{column}"


# ===== 1. 影子观测：真实业务调用点，结果只落影子表 =====


def test_plain_plan_summary_is_a_real_shadow_call_site():
    candidate = GroundedFakeLLM()
    container, student, client, headers = _setup(candidate=candidate)
    _urgent_task(container, student.id)
    plan = _generate_plan(client, headers, key="canary-shadow-1")

    before = _business_counts(client, headers)
    body = _summary(client, headers, plan["plan_id"])
    after = _business_counts(client, headers)

    assert candidate.calls == 1, "影子观测必须真的调用了一次候选模型"
    rows = _shadow_rows(container)
    assert len(rows) == 1, f"应当产生且只产生一条影子观测记录：{rows}"
    assert rows[0]["user_id"] == student.id
    assert after == before, "影子观测不得改变任何业务计数"
    # 门禁未过（本用例没有 promotion decision）→ 注解安全降级
    assert body["candidate_annotation"]["available"] is False
    assert body["candidate_annotation"]["reason"] == "no_promotion_decision"


def test_shadow_observation_is_idempotent_for_the_same_plan_input():
    candidate = GroundedFakeLLM()
    container, student, client, headers = _setup(candidate=candidate)
    _urgent_task(container, student.id)
    plan = _generate_plan(client, headers, key="canary-shadow-idem")

    _summary(client, headers, plan["plan_id"])
    _summary(client, headers, plan["plan_id"])
    _summary(client, headers, plan["plan_id"])

    assert len(_shadow_rows(container)) == 1, "同一份输入重复查看不得让影子表膨胀"


def test_candidate_never_touches_business_tables_in_shadow_mode():
    candidate = GroundedFakeLLM()
    container, student, client, headers = _setup(candidate=candidate)
    _urgent_task(container, student.id)
    plan = _generate_plan(client, headers, key="canary-shadow-clean")

    _summary(client, headers, plan["plan_id"])

    assert candidate.calls == 1
    _assert_business_tables_clean(container)


# ===== 2. 金丝雀展示：门禁通过后进入真实生产响应 =====


def test_canary_result_enters_production_response_as_read_only_field():
    candidate = GroundedFakeLLM()
    container, student, client, headers = _setup(candidate=candidate)
    _urgent_task(container, student.id)
    _insert_promotion_decision(container)
    plan = _generate_plan(client, headers, key="canary-hit")

    before = _business_counts(client, headers)
    body = _summary(client, headers, plan["plan_id"])
    after = _business_counts(client, headers)
    annotation = body["candidate_annotation"]

    assert annotation["available"] is True, annotation
    assert annotation["inference_source"] == "REAL_MODEL"
    assert annotation["read_only"] is True
    assert annotation["affects_production"] is False
    assert annotation["used_fallback"] is False
    assert annotation["model_key"] == "campusmate-lm:test"
    assert annotation["shadow_run_id"], "必须能追溯到影子表里的那一次观测"
    assert annotation["input_digest"]
    assert annotation["summary"] == MARKER_SUMMARY
    assert "PRIORITIZE_NEAR_DEADLINE" in annotation["claim_codes"], (
        "结论必须被输入里的真实解释码支撑"
    )
    assert set(annotation["claim_codes"]) <= set(_CLAIM_EVIDENCE)

    # 确定性字段照常返回，候选注解只是附加字段。
    assert body["headline"] and body["next_action"] and body["status"] == "PROPOSED"
    assert after == before, "金丝雀展示不得改变任何业务计数"
    assert candidate.calls == 1, "门禁通过时只调用一次候选模型（不是影子+金丝雀各一次）"
    assert len(_shadow_rows(container)) == 1


def test_canary_display_never_writes_candidate_output_into_business_tables():
    candidate = GroundedFakeLLM()
    container, student, client, headers = _setup(candidate=candidate)
    _urgent_task(container, student.id)
    _insert_promotion_decision(container)
    plan = _generate_plan(client, headers, key="canary-clean")

    body = _summary(client, headers, plan["plan_id"])
    assert body["candidate_annotation"]["available"] is True

    _assert_business_tables_clean(container)


# ===== 3. 门禁失败 → 安全降级 =====


def test_canary_degrades_when_feature_flag_disabled():
    candidate = GroundedFakeLLM()
    container, student, client, headers = _setup(candidate=candidate, campusmate_lm_canary_enabled=False)
    _urgent_task(container, student.id)
    _insert_promotion_decision(container)
    plan = _generate_plan(client, headers, key="canary-flag-off")

    annotation = _summary(client, headers, plan["plan_id"])["candidate_annotation"]
    assert annotation["available"] is False
    assert annotation["reason"] == "canary_feature_flag_disabled"
    assert annotation["summary"] is None
    # 门禁未过 → 改走影子观测，模型仍然只被调用一次
    assert candidate.calls == 1


def test_canary_degrades_when_candidate_model_not_configured():
    candidate = GroundedFakeLLM()
    container, student, client, headers = _setup(
        candidate=candidate, campusmate_lm_enabled=False,
    )
    _urgent_task(container, student.id)
    _insert_promotion_decision(container)
    plan = _generate_plan(client, headers, key="canary-unconfigured")

    annotation = _summary(client, headers, plan["plan_id"])["candidate_annotation"]
    assert annotation["available"] is False
    assert annotation["reason"] == "candidate_model_not_configured"
    assert candidate.calls == 0, "未配置时不得调用候选模型"


def test_canary_degrades_when_user_paused_model_shadow_source():
    candidate = GroundedFakeLLM()
    container, student, client, headers = _setup(candidate=candidate)
    _urgent_task(container, student.id)
    _insert_promotion_decision(container)
    container.learner_control_service.update_source_control(
        user_id=student.id, source_key="MODEL_SHADOW", status="PAUSED"
    )
    plan = _generate_plan(client, headers, key="canary-paused")

    annotation = _summary(client, headers, plan["plan_id"])["candidate_annotation"]
    assert annotation["available"] is False
    assert annotation["reason"] == "model_shadow_paused_for_user"


def test_canary_degrades_when_quality_gates_failed():
    candidate = GroundedFakeLLM()
    container, student, client, headers = _setup(candidate=candidate)
    _urgent_task(container, student.id)
    _insert_promotion_decision(container, failed_gates=["PERFORMANCE_NOT_MEASURED"])
    plan = _generate_plan(client, headers, key="canary-gate-failed")

    annotation = _summary(client, headers, plan["plan_id"])["candidate_annotation"]
    assert annotation["available"] is False
    assert annotation["reason"] == "quality_gates_failed"


# ===== 4. 模型失败 → 安全回退到确定性结果 =====


def test_canary_degrades_on_sampling_miss():
    candidate = GroundedFakeLLM()
    container, student, client, headers = _setup(candidate=candidate, campusmate_lm_canary_sample_rate=0.0)
    _urgent_task(container, student.id)
    _insert_promotion_decision(container)
    plan = _generate_plan(client, headers, key="canary-sampling-miss")

    body = _summary(client, headers, plan["plan_id"])
    annotation = body["candidate_annotation"]
    assert annotation["available"] is False
    assert annotation["reason"] == "MODEL_RATE_LIMITED"
    assert body["headline"], "确定性结果必须照常返回"


def test_canary_degrades_on_timeout():
    candidate = GroundedFakeLLM(delay=0.2)
    container, student, client, headers = _setup(candidate=candidate, campusmate_lm_timeout_ms=1)
    _urgent_task(container, student.id)
    _insert_promotion_decision(container)
    plan = _generate_plan(client, headers, key="canary-timeout")

    annotation = _summary(client, headers, plan["plan_id"])["candidate_annotation"]
    assert annotation["available"] is False
    assert annotation["reason"] == "MODEL_TIMEOUT"
    assert annotation["used_fallback"] is True


def test_canary_degrades_on_invalid_json():
    candidate = GroundedFakeLLM(raw="这不是 JSON")
    container, student, client, headers = _setup(candidate=candidate)
    _urgent_task(container, student.id)
    _insert_promotion_decision(container)
    plan = _generate_plan(client, headers, key="canary-invalid-json")

    annotation = _summary(client, headers, plan["plan_id"])["candidate_annotation"]
    assert annotation["available"] is False
    assert annotation["reason"] == "MODEL_SCHEMA_INVALID"


def test_canary_degrades_on_policy_violation():
    candidate = GroundedFakeLLM(
        raw=json.dumps({"summary": "该生姓名已知，成绩必然提升", "claim_codes": ["PRIORITIZE_NEAR_DEADLINE"]})
    )
    container, student, client, headers = _setup(candidate=candidate)
    _urgent_task(container, student.id)
    _insert_promotion_decision(container)
    plan = _generate_plan(client, headers, key="canary-policy")

    body = _summary(client, headers, plan["plan_id"])
    annotation = body["candidate_annotation"]
    assert annotation["available"] is False
    assert annotation["reason"] == "MODEL_POLICY_VIOLATION"
    assert "该生姓名" not in json.dumps(body, ensure_ascii=False), "违规原文不得进入响应"


def test_canary_degrades_on_open_circuit():
    candidate = GroundedFakeLLM()
    container, student, client, headers = _setup(candidate=candidate)
    _urgent_task(container, student.id)
    _insert_promotion_decision(container)
    runner = container.model_shadow_runner
    for _ in range(runner.circuit_breaker_threshold):
        runner._record_failure("learning_summary_v1")
    plan = _generate_plan(client, headers, key="canary-circuit")

    annotation = _summary(client, headers, plan["plan_id"])["candidate_annotation"]
    assert annotation["available"] is False
    # 门禁在调用模型之前就拦住了（stable reason code 由 canary_gate 给出）
    assert annotation["reason"] == "circuit_breaker_open"
    assert candidate.calls == 0, "熔断打开时不得调用候选模型"


# ===== 5. 隐私与权限 =====


def test_canary_response_never_leaks_credentials_or_prompt():
    candidate = GroundedFakeLLM()
    container, student, client, headers = _setup(candidate=candidate)
    _urgent_task(container, student.id)
    _insert_promotion_decision(container)
    plan = _generate_plan(client, headers, key="canary-privacy")

    raw = _summary(client, headers, plan["plan_id"])
    serialized = json.dumps(raw, ensure_ascii=False)

    for secret in (CANDIDATE_API_KEY, CANDIDATE_BASE_URL, "candidate.invalid", "test-model",
                   "只返回严格 JSON"):
        assert secret not in serialized, f"响应不得包含 {secret}"
    # `prompt_version` 是合法的可追溯元数据；被禁的是内部字段与原始 prompt 正文。
    for forbidden in ("user_id", "source_id", "api_key", "candidate_read_tools", "messages"):
        assert forbidden not in serialized, f"响应不得包含内部字段名 {forbidden}"
    # 受控输入本身也不能出网：只有枚举/桶/计数。
    assert student.id not in serialized


def test_canary_annotation_is_isolated_between_users():
    candidate = GroundedFakeLLM()
    container, student, client, headers = _setup(candidate=candidate)
    outsider = container.user_repository.create_user(
        username="canary_outsider", password_hash=hash_password(PASSWORD), role="student"
    )
    _urgent_task(container, student.id)
    _insert_promotion_decision(container)
    container.learner_control_service.update_source_control(
        user_id=student.id, source_key="MODEL_SHADOW", status="PAUSED"
    )
    plan = _generate_plan(client, headers, key="canary-isolation")

    mine = _summary(client, headers, plan["plan_id"])["candidate_annotation"]
    assert mine["available"] is False
    assert mine["reason"] == "model_shadow_paused_for_user"

    login = client.post(f"{API}/auth/login", json={"username": "canary_outsider", "password": PASSWORD})
    outsider_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    theirs = client.get(f"{API}/learning-plans/{plan['plan_id']}/summary", headers=outsider_headers)
    assert theirs.status_code == 404, "跨用户读取计划摘要必须 404"
    assert outsider.id not in theirs.text


def test_canary_requires_authentication():
    candidate = GroundedFakeLLM()
    container, student, client, headers = _setup(candidate=candidate)
    _urgent_task(container, student.id)
    plan = _generate_plan(client, headers, key="canary-anon")

    assert client.get(f"{API}/learning-plans/{plan['plan_id']}/summary").status_code in {401, 403}


# ===== 6. 未接入真实模型时的诚实标记 =====


def test_no_real_inference_is_reported_honestly_when_candidate_absent():
    """候选模型未配置时，透明度接口必须明说"没有真实推理"，不得伪造通过。"""
    container, student, client, headers = _setup(campusmate_lm_enabled=False)
    _urgent_task(container, student.id)
    plan = _generate_plan(client, headers, key="canary-honest")
    _summary(client, headers, plan["plan_id"])

    transparency = client.get(f"{API}/learner-state/model-transparency", headers=headers).json()
    assert transparency["uses_real_model_inference"] is False
    assert transparency["real_inference_observed"] is False
    assert transparency["uses_fixed_prediction_file"] is True
    assert transparency["campusmate_lm_affects_production"] is False
    assert transparency["shadow_results_modify_plans"] is False
    assert transparency["read_only_canary_active"] is False


# ===== 7. half-open 熔断恢复：探测权只能由 runner 占用 =====


def test_canary_gate_never_consumes_the_half_open_probe():
    """门禁是**只读**预检查：反复查询不得占用 half-open 探测权。

    回归点：门禁曾经调用会占用探测权的 `_circuit_allows`。那样一来，
    门禁自己把探测权吃掉，真正调用候选模型的 `run()` 反而被判
    MODEL_CIRCUIT_OPEN —— 真实候选永远收不到这次探测，熔断再也关不上。
    """
    candidate = GroundedFakeLLM()
    container, student, _client, _headers = _setup(
        candidate=candidate, campusmate_lm_circuit_breaker_cooldown_seconds=0.0,
    )
    # 门禁必须真的走到熔断那一项检查（前面的门禁项都要先满足）。
    _insert_promotion_decision(container)
    runner = container.model_shadow_runner
    for _ in range(runner.circuit_breaker_threshold):
        runner._record_failure("learning_summary_v1")

    for _ in range(5):
        gate = container.learner_control_service.canary_gate(
            capability_name="learning_summary_v1", user_id=student.id
        )
        assert gate == {"allowed": True, "reason": None}, gate
        runner.circuit_status("learning_summary_v1")

    assert runner.circuit_status("learning_summary_v1")["probe_in_flight"] is False, (
        "门禁/状态查询不得占用探测权"
    )
    # 只有 runner 能占用；占用后其他调用必须被拒。
    assert runner._circuit_allows("learning_summary_v1").allowed is True
    assert runner.circuit_status("learning_summary_v1")["probe_in_flight"] is True
    assert runner.canary_allowed("learning_summary_v1") is False
    assert runner._circuit_allows("learning_summary_v1").allowed is False
    # 释放后回到可探测状态，且失败计数不被释放动作改写。
    runner._release_probe("learning_summary_v1")
    status = runner.circuit_status("learning_summary_v1")
    assert status["probe_in_flight"] is False
    assert status["failures"] == runner.circuit_breaker_threshold
    assert status["state"] == "HALF_OPEN"


def test_half_open_probe_reaches_candidate_and_closes_the_circuit():
    """失败熔断 → 冷却 → 探测真实候选调用成功 → 熔断关闭。

    这是端到端的回归：门禁通过必须真的把这次调用送到候选模型，
    而不是在门禁里就把探测权消耗掉、让熔断永远停在 HALF_OPEN。
    """
    candidate = GroundedFakeLLM()
    container, student, client, headers = _setup(
        candidate=candidate, campusmate_lm_circuit_breaker_cooldown_seconds=0.15,
    )
    _urgent_task(container, student.id)
    _insert_promotion_decision(container)
    plan = _generate_plan(client, headers, key="canary-half-open")
    runner = container.model_shadow_runner

    # 1. 连续失败 → 熔断打开，门禁拒绝
    for _ in range(runner.circuit_breaker_threshold):
        runner._record_failure("learning_summary_v1")
    assert runner.circuit_status("learning_summary_v1")["state"] == "OPEN"
    gate = container.learner_control_service.canary_gate(
        capability_name="learning_summary_v1", user_id=student.id
    )
    assert gate == {"allowed": False, "reason": "circuit_breaker_open"}
    assert runner.circuit_status("learning_summary_v1")["probe_in_flight"] is False, (
        "被熔断拒绝的门禁查询不得占用探测权"
    )

    # 2. 冷却结束 → HALF_OPEN，且探测权仍然空闲
    time.sleep(0.2)
    assert runner.circuit_status("learning_summary_v1")["state"] == "HALF_OPEN"
    assert runner.circuit_status("learning_summary_v1")["probe_in_flight"] is False

    # 3. 门禁放行，但仍然不占探测权
    gate = container.learner_control_service.canary_gate(
        capability_name="learning_summary_v1", user_id=student.id
    )
    assert gate == {"allowed": True, "reason": None}
    assert runner.circuit_status("learning_summary_v1")["probe_in_flight"] is False

    # 4. 真实调用 → 候选被真的调用一次 → 熔断关闭
    calls_before = candidate.calls
    annotation = _summary(client, headers, plan["plan_id"])["candidate_annotation"]
    assert candidate.calls == calls_before + 1, "half-open 探测必须真的打到候选模型"
    assert annotation["available"] is True, annotation
    assert annotation["inference_source"] == "REAL_MODEL"
    status = runner.circuit_status("learning_summary_v1")
    assert status["state"] == "CLOSED"
    assert status["failures"] == 0
    assert status["probe_in_flight"] is False


def test_cancelled_probe_is_released_and_cannot_wedge_the_circuit():
    """调用被取消（CancelledError 是 BaseException）时，探测权也必须被释放。"""
    from app.models.model_capability import ModelCapabilityRequest
    from app.services.model_capability_registry import ModelCapabilityRegistry
    from app.services.model_shadow_runner import ModelShadowRunner

    runner = ModelShadowRunner(
        registry=ModelCapabilityRegistry(), candidate_llm=CancellingLLM(),
        enabled=True, sample_rate=1.0, circuit_breaker_threshold=1,
        circuit_breaker_cooldown_seconds=0.0,
    )
    runner._record_failure("learning_summary_v1")
    assert runner.circuit_status("learning_summary_v1")["state"] == "HALF_OPEN"

    request = ModelCapabilityRequest(
        capability_name="learning_summary_v1", capability_version="v1", subject_user_id="user-1",
        input_payload={
            "warning_codes": [], "explanation_codes": ["deadline_urgent"], "item_type": "TASK_FOCUS",
            "estimated_minutes": 30, "data_quality": "verified", "evidence_count": 1,
            "deadline_bucket": "TODAY", "state_band": None, "confidence_bucket": "HIGH",
        },
        request_id="cancel-probe", id_mode=True,
    )
    try:
        asyncio.run(runner.run(request))
    except asyncio.CancelledError:
        pass

    status = runner.circuit_status("learning_summary_v1")
    assert status["probe_in_flight"] is False, "取消后探测权必须被释放，否则熔断永久卡在 HALF_OPEN"
    assert status["state"] == "HALF_OPEN", "失败计数与开启时刻不应被释放动作改写"


# ===== 8. 外发报文不含稳定内部 ID =====

_FORBIDDEN_PAYLOAD_KEYS = (
    "plan_id", "user_id", "task_id", "goal_id", "run_id",
    "snapshot_id", "intervention_id", "subject_user_id", "request_id",
)


def test_candidate_messages_carry_no_stable_internal_ids():
    """发给候选模型的 messages 不得含 plan / user / task / goal 等稳定内部 ID。

    本地影子记录与生产响应的关联仍靠 request_id + input_digest 完成 ——
    两者都在请求信封与落库侧，不进入 messages。
    """
    candidate = GroundedFakeLLM()
    container, student, client, headers = _setup(candidate=candidate)
    task = _urgent_task(container, student.id)
    goal = container.student_goal_repository.create_goal(
        user_id=student.id, name="接线验证目标", category="ACADEMIC",
        target_date=(datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat(),
        idempotency_key="canary-payload-goal",
    )[0]
    _insert_promotion_decision(container)
    response = client.post(
        f"{API}/learning-plans/generate",
        json={"available_minutes": 60, "goal_id": goal.goal_id, "idempotency_key": "canary-payload"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    plan = response.json()

    annotation = _summary(client, headers, plan["plan_id"])["candidate_annotation"]
    assert annotation["available"] is True, annotation
    assert candidate.messages_seen, "必须真的调用过候选模型"

    for messages in candidate.messages_seen:
        assert len(messages) == 2, messages
        payload = json.loads(messages[-1]["content"])
        for key in _FORBIDDEN_PAYLOAD_KEYS:
            assert key not in payload, f"外发报文不得含字段 {key}: {payload}"
        assert set(payload) == {
            "warning_codes", "explanation_codes", "item_type", "estimated_minutes",
            "data_quality", "evidence_count", "deadline_bucket", "state_band", "confidence_bucket",
        }, f"外发字段集合必须恰好是受控结构化特征：{sorted(payload)}"
        serialized = messages[-1]["content"]
        for identifier in (plan["plan_id"], student.id, goal.goal_id, task.id):
            assert identifier not in serialized, f"外发报文泄漏了内部标识 {identifier}"

    # 本地关联不受影响：影子记录的 request_id 仍然指向这份计划，input_digest 可对账。
    rows = _shadow_rows(container)
    assert rows, "影子观测记录必须存在"
    assert any(plan["plan_id"] in row["request_id"] for row in rows), (
        f"本地关联必须仍可由 request_id 完成：{rows}"
    )
    assert annotation["input_digest"], "本地关联必须仍可由 input_digest 完成"


# ===== 9. 上线适配：默认关闭 + 配置入口可发现 =====

_ENV_EXAMPLE = Path(__file__).resolve().parents[1] / ".env.example"


def _documented_candidate_keys() -> set[str]:
    keys = set()
    for line in _ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("CAMPUSMATE_LM_"):
            keys.add(line.split("=", 1)[0])
    return keys


def test_env_example_documents_exactly_the_real_candidate_settings():
    """`.env.example` 与真实 Settings 字段必须双向一致。

    运维只能从模板发现配置入口：模板里写了一个不存在的键 → 配了没效果；
    新增了配置却忘了写模板 → 没人知道要配。两个方向都要钉住。
    """
    documented = _documented_candidate_keys()
    fields = {name.upper() for name in Settings.model_fields if name.startswith("campusmate_lm_")}
    assert documented, "候选模型的配置入口必须写进 .env.example"
    assert documented - fields == set(), f"模板里有不存在的配置项：{sorted(documented - fields)}"
    assert fields - documented == set(), f"未写进 .env.example 的配置项：{sorted(fields - documented)}"


def test_env_example_never_carries_a_real_credential():
    """模板必须保持脱敏：候选模型的凭据键一律留空。"""
    for line in _ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("CAMPUSMATE_LM_"):
            continue
        key, _, value = stripped.partition("=")
        if key.endswith(("API_KEY", "SECRET", "TOKEN")):
            assert value == "", f"模板里的凭据键必须留空：{key}"


def test_candidate_model_defaults_to_fully_off_and_never_calls_out():
    """默认配置下候选模型完全关闭：不构造客户端、不发起任何真实调用。"""
    settings = Settings(app_env="test", database_url="sqlite:///:memory:")
    assert settings.campusmate_lm_enabled is False
    assert settings.campusmate_lm_available is False
    assert settings.campusmate_lm_canary_enabled is False
    assert settings.campusmate_lm_shadow_sample_rate == 0.0

    container = reset_container_for_tests(settings)
    runner = container.model_shadow_runner
    assert runner.candidate_llm is None, "默认不得构造候选客户端"
    assert runner.enabled is False

    result = asyncio.run(runner.run(ModelCapabilityRequest(
        capability_name="learning_summary_v1", capability_version="v1", subject_user_id="user-default",
        input_payload={
            "warning_codes": [], "explanation_codes": ["deadline_urgent"], "item_type": "TASK_FOCUS",
            "estimated_minutes": 30, "data_quality": "verified", "evidence_count": 1,
            "deadline_bucket": "TODAY", "state_band": None, "confidence_bucket": "HIGH",
        },
        request_id="defaults-off", id_mode=True,
    )))
    assert result.failure_code == "MODEL_DISABLED"
    assert result.used_fallback is True
    assert result.inference_source == "DETERMINISTIC_FALLBACK"


def test_candidate_config_requires_all_three_of_url_key_and_model():
    """三要素缺任意一个都不算"已配置"：宁可判定未配置，也不发起半配置的调用。

    另外：开启开关却给了一个不合法的 base_url 会**启动即失败**（fail fast），
    而不是静默地"以为配好了、其实从没调用过"。
    """
    import pytest

    base = dict(app_env="test", database_url="sqlite:///:memory:", campusmate_lm_enabled=True)
    # 开了开关却没给可用 origin → 直接拒绝启动
    with pytest.raises(ValueError):
        Settings(**base)

    url = dict(base, campusmate_lm_base_url="http://candidate.invalid:8000")
    assert Settings(**url).campusmate_lm_available is False, "只有 URL 不算已配置"
    assert Settings(**url, campusmate_lm_api_key="k").campusmate_lm_available is False, "缺 model 不算已配置"
    assert Settings(**url, campusmate_lm_model_name="m").campusmate_lm_available is False, "缺 key 不算已配置"
    assert Settings(**url, campusmate_lm_api_key="k",
                    campusmate_lm_model_name="m").campusmate_lm_available is True


def test_candidate_base_url_must_be_a_safe_origin():
    """凭据不能藏在 URL 里，也不能带 query/fragment：这些都会被拒绝。"""
    import pytest

    for bad in ("ftp://candidate.invalid", "http://user:pass@candidate.invalid",
                "http://candidate.invalid?token=x", "http://candidate.invalid#frag", "not-a-url"):
        with pytest.raises(ValueError):
            Settings(app_env="test", database_url="sqlite:///:memory:", campusmate_lm_enabled=True,
                     campusmate_lm_base_url=bad, campusmate_lm_api_key="k", campusmate_lm_model_name="m")


# ===== 10. 线程安全：同步路由跑在 threadpool 里 =====


def test_canary_gate_is_read_only_even_when_called_from_a_worker_thread():
    """同步路由（FastAPI 会放进 threadpool）调用门禁时，不得改动熔断状态。

    `GET /learner-state/canary-gate/{capability}` 是 **`def`** 而非 `async def`，
    所以 FastAPI 会把它丢进线程池执行。门禁曾经调用会**写入** `probe_in_flight`
    的 `_circuit_allows` —— 也就是说那次写入来自 worker 线程，与事件循环上
    真实进行的 half-open 探测并发。修复后门禁只用只读查询，这个跨线程写入消失。
    """
    from concurrent.futures import ThreadPoolExecutor

    candidate = GroundedFakeLLM()
    container, student, _client, _headers = _setup(
        candidate=candidate, campusmate_lm_circuit_breaker_cooldown_seconds=0.0,
    )
    _insert_promotion_decision(container)
    runner = container.model_shadow_runner
    for _ in range(runner.circuit_breaker_threshold):
        runner._record_failure("learning_summary_v1")
    before = dict(runner.circuit_status("learning_summary_v1"))

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(
            lambda _: container.learner_control_service.canary_gate(
                capability_name="learning_summary_v1", user_id=student.id),
            range(8),
        ))

    assert all(item == {"allowed": True, "reason": None} for item in results), results
    after = dict(runner.circuit_status("learning_summary_v1"))
    assert after["probe_in_flight"] is False, "多线程调用门禁也不得占用探测权"
    assert after["failures"] == before["failures"], "只读查询不得改写失败计数"
    assert after["generation"] == before["generation"], "只读查询不得推进熔断代次"


def test_sync_canary_gate_route_stays_read_only_over_http():
    """同一结论走真实 HTTP：同步路由连续调用后熔断状态逐字段不变。"""
    candidate = GroundedFakeLLM()
    container, _student, client, headers = _setup(
        candidate=candidate, campusmate_lm_circuit_breaker_cooldown_seconds=0.0,
    )
    _insert_promotion_decision(container)
    runner = container.model_shadow_runner
    for _ in range(runner.circuit_breaker_threshold):
        runner._record_failure("learning_summary_v1")
    before = dict(runner.circuit_status("learning_summary_v1"))

    for _ in range(5):
        response = client.get(f"{API}/learner-state/canary-gate/learning_summary_v1", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json() == {"allowed": True, "reason": None}

    assert dict(runner.circuit_status("learning_summary_v1")) == before
