from __future__ import annotations

from learner_state_evaluation.model_shadow.metrics import evaluate_shadow_predictions


def test_single_label_metrics_do_not_reduce_intent_to_single_class() -> None:
    rows = [
        {"sample_id": "intent-1", "capability_name": "campus_intent_routing_v1", "input": {},
         "expected_output": {"intent_code": "INTENT_VIEW_SCHEDULE", "abstained": False}},
        {"sample_id": "intent-2", "capability_name": "campus_intent_routing_v1", "input": {},
         "expected_output": {"intent_code": None, "abstained": True}},
    ]
    predictions = [
        {"sample_id": "intent-1", "output": {"intent_code": "INTENT_VIEW_SCHEDULE", "confidence": 0.8, "abstained": False}, "confidence": 0.8},
        {"sample_id": "intent-2", "output": {"intent_code": None, "confidence": 0.1, "abstained": True}, "confidence": 0.1},
    ]
    report = evaluate_shadow_predictions(rows, predictions)
    metrics = report["by_capability"]["campus_intent_routing_v1"]
    assert metrics["micro_recall"] == 1.0
    assert metrics["support_count"] == 2
    assert metrics["correct_abstention_rate"] == 1.0


def test_performance_metrics_are_null_when_prediction_file_has_no_measurements() -> None:
    rows = [{"sample_id": "tool-1", "capability_name": "read_only_tool_routing_v1", "input": {},
             "expected_output": {"tool_name": "read_core_state", "arguments": {}, "abstained": False}}]
    predictions = [{"sample_id": "tool-1", "output": {"tool_name": "read_core_state", "arguments": {}, "abstained": False}}]
    report = evaluate_shadow_predictions(rows, predictions)
    assert report["performance"]["p95_latency_ms"] is None
    assert report["performance"]["peak_memory_mb"] is None


def test_summary_supported_claims_use_controlled_evidence_mapping() -> None:
    rows = [{"sample_id": "summary-1", "capability_name": "student_state_summary_v1",
             "input": {"explanation_codes": ["deadline_urgent"]},
             "expected_output": {"summary": "建议先处理临近截止项。", "claim_codes": ["PRIORITIZE_NEAR_DEADLINE"]}}]
    predictions = [{"sample_id": "summary-1", "output": {"summary": "建议先处理临近截止项。", "claim_codes": ["PRIORITIZE_NEAR_DEADLINE"]}}]
    metrics = evaluate_shadow_predictions(rows, predictions)["by_capability"]["student_state_summary_v1"]
    assert metrics["supported_claim_rate"] == 1.0
    assert metrics["unsupported_claim_rate"] == 0.0
