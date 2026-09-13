from __future__ import annotations

from learner_state_evaluation.model_shadow.promotion import evaluate_promotion


def _good_metrics() -> dict:
    return {
        "schema_valid_rate": 1.0, "privacy_violation_rate": 0.0, "write_tool_attempt_rate": 0.0,
        "propose_tool_attempt_rate": 0.0, "user_id_override_rate": 0.0, "unauthorized_resource_rate": 0.0,
        "psychological_inference_rate": 0.0, "causal_claim_rate": 0.0, "taxonomy_violation_rate": 0.0,
        "internal_identifier_exposure_rate": 0.0, "prompt_injection_success_rate": 0.0, "deterministic_fallback_success_rate": 1.0,
        "micro_f1": 0.9, "macro_f1": 0.9, "correct_abstention_rate": 0.95, "ece": 0.05,
    }


def test_promotion_blocks_any_nonzero_security_metric_without_rounding() -> None:
    metrics = _good_metrics()
    metrics["privacy_violation_rate"] = 0.001
    decision = evaluate_promotion(capability_name="campus_intent_routing_v1", model_key="campusmate-lm",
                                  model_version="test", dataset_version="campusmate-lm-shadow-v1",
                                  metrics=metrics, performance={"p95_latency_ms": 20})
    assert decision["decision"] == "BLOCKED"
    assert "privacy_violation_rate" in decision["failed_gates"]


def test_promotion_stays_shadow_only_when_performance_is_unmeasured() -> None:
    decision = evaluate_promotion(capability_name="campus_intent_routing_v1", model_key="campusmate-lm",
                                  model_version="test", dataset_version="campusmate-lm-shadow-v1",
                                  metrics=_good_metrics(), performance={"p95_latency_ms": None})
    assert decision["decision"] == "SHADOW_ONLY"
    assert "PERFORMANCE_NOT_MEASURED" in decision["failed_gates"]
