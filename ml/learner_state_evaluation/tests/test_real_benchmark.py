from __future__ import annotations

import json

import pytest

from learner_state_evaluation.model_shadow.dataset import build_shadow_dataset


def test_phase8a_baseline_never_reads_expected_output() -> None:
    from learner_state_evaluation.model_shadow import real_benchmark as rb

    heldout = rb.build_heldout_rows(build_shadow_dataset())
    without_gold = [{key: value for key, value in row.items() if key != "expected_output"} for row in heldout]
    poisoned = [dict(row, expected_output={"poison": row["sample_id"]}) for row in heldout]

    expected = rb.build_baseline_predictions(without_gold)
    actual = rb.build_baseline_predictions(poisoned)

    assert actual == expected
    assert all(row["prediction_source"] == "DETERMINISTIC_BASELINE" for row in actual)
    assert all(row["uses_expected_output"] is False for row in actual)
    assert all(row["eligible_for_promotion"] is False for row in actual)


def test_phase8a_inventory_distinguishes_service_and_model_assets(tmp_path) -> None:
    from learner_state_evaluation.model_shadow import real_benchmark as rb

    hf_dir = tmp_path / "model"
    hf_dir.mkdir()
    (hf_dir / "config.json").write_text("{}", encoding="utf-8")
    (hf_dir / "tokenizer.json").write_text("{}", encoding="utf-8")
    (hf_dir / "model.safetensors").write_bytes(b"weights")
    local = rb.inventory_model_runtime(env={"CAMPUSMATE_LM_WEIGHTS_DIR": str(hf_dir)})
    assert local["local_weights_available"] is True
    assert local["execution_mode"] == "LOCAL_WEIGHTS"
    assert str(tmp_path) not in json.dumps(local)

    service = rb.inventory_model_runtime(env={
        "CAMPUSMATE_LM_SHADOW_ENABLED": "true",
        "CAMPUSMATE_LM_BASE_URL": "http://service.invalid",
        "CAMPUSMATE_LM_MODEL": "campusmate-lm-v1",
        "CAMPUSMATE_LM_API_KEY": "secret",
    })
    assert service["service_configured"] is True
    assert service["execution_mode"] == "OPENAI_COMPATIBLE_SERVICE"
    assert service["blocked"] is False
    assert "secret" not in json.dumps(service)
    assert "service.invalid" not in json.dumps(service)


def test_phase8a_inventory_rejects_unrelated_or_incomplete_assets(tmp_path) -> None:
    from learner_state_evaluation.model_shadow import real_benchmark as rb

    vision_dir = tmp_path / "vision"
    vision_dir.mkdir()
    (vision_dir / "expression_recognition.onnx").write_bytes(b"vision")
    assert rb.inventory_model_runtime(env={"CAMPUSMATE_LM_WEIGHTS_DIR": str(vision_dir)})["blocked"] is True

    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    (incomplete / "tokenizer.json").write_text("{}", encoding="utf-8")
    assert rb.inventory_model_runtime(env={"CAMPUSMATE_LM_WEIGHTS_DIR": str(incomplete)})["blocked"] is True


def test_phase8b_preflight_is_blocked_without_runtime_and_ready_for_service(tmp_path) -> None:
    from learner_state_evaluation.model_shadow import real_benchmark as rb
    from learner_state_evaluation.model_shadow.dataset import write_shadow_dataset

    source = write_shadow_dataset(tmp_path / "source")
    blocked = rb.preflight_benchmark(dataset_path=source.data_path, env={})
    assert blocked["ready"] is False
    assert blocked["block_reason_code"] == "MODEL_RUNTIME_UNAVAILABLE"
    assert blocked["heldout_sample_count"] == 52

    ready = rb.preflight_benchmark(dataset_path=source.data_path, env={
        "CAMPUSMATE_LM_SHADOW_ENABLED": "true",
        "CAMPUSMATE_LM_BASE_URL": "http://service.invalid",
        "CAMPUSMATE_LM_MODEL": "campusmate-lm-v1",
        "CAMPUSMATE_LM_API_KEY": "secret",
    })
    assert ready["ready"] is True
    assert ready["execution_mode"] == "OPENAI_COMPATIBLE_SERVICE"
    assert "secret" not in json.dumps(ready)
    assert "service.invalid" not in json.dumps(ready)


def test_phase8b_baseline_report_is_never_promotion_eligible(tmp_path) -> None:
    from learner_state_evaluation.model_shadow import real_benchmark as rb
    from learner_state_evaluation.model_shadow.dataset import write_shadow_dataset

    source = write_shadow_dataset(tmp_path / "source")
    report = rb.run_baseline_benchmark(dataset_path=source.data_path, output_dir=tmp_path / "out")
    assert report["inference_source"] == "DETERMINISTIC_BASELINE"
    assert report["uses_expected_output"] is False
    assert report["eligible_for_promotion"] is False
    assert report["performance"]["p95_latency_ms"] is None
    assert all(decision["decision"] == "BLOCKED" for decision in report["promotion_decisions"].values())


def test_phase8a_arbitrary_real_flag_cannot_bypass_provenance() -> None:
    from learner_state_evaluation.model_shadow import real_benchmark as rb

    class Pretender:
        is_real_model = True
        provenance = "OPENAI_COMPATIBLE_SERVICE"

    with pytest.raises(ValueError, match="trusted"):
        rb.require_real_client(Pretender())


def test_phase8a_real_benchmark_harness_exists() -> None:
    from learner_state_evaluation.model_shadow import real_benchmark as rb

    assert rb.BENCHMARK_VERSION == "campusmate-lm-real-benchmark-v1"
    assert rb.HELDOUT_SPLIT == "test"

    inventory = rb.inventory_model_weights(env={})
    assert inventory["weight_status"] == "MISSING"
    assert inventory["blocked"] is True
    assert inventory["absolute_paths_omitted"] is True

    rows = build_shadow_dataset()
    heldout = rb.build_heldout_rows(rows)
    assert heldout
    assert {row["split"] for row in heldout} == {"test"}
    assert {row["capability_name"] for row in heldout} == {
        "c_kc_classification_v1",
        "c_error_classification_v1",
        "learning_summary_v1",
        "read_only_tool_routing_v1",
    }


def test_phase8a_fixture_can_never_claim_real_model() -> None:
    from learner_state_evaluation.model_shadow import real_benchmark as rb
    from learner_state_evaluation.model_shadow.candidate_client import DeterministicFixtureClient

    fixture = DeterministicFixtureClient()
    try:
        rb.require_real_client(fixture)
    except ValueError as exc:
        assert "fixture" in str(exc).lower() or "real" in str(exc).lower()
    else:
        raise AssertionError("fixture client must not pass as real model")


def test_phase8a_blocked_report_never_claims_real_inference(tmp_path) -> None:
    from learner_state_evaluation.model_shadow import real_benchmark as rb
    from learner_state_evaluation.model_shadow.dataset import write_shadow_dataset

    source = write_shadow_dataset(tmp_path / "source")
    report = rb.run_blocked_benchmark(
        dataset_path=source.data_path,
        output_dir=tmp_path / "reports",
        reason="no authorized weights available",
    )
    assert report["inference_source"] != "REAL_MODEL"
    assert report["real_model_inference"] is False
    assert report["blocked"] is True
    assert report["test_split_only"] is True
    assert report["production_enabled"] is False
    assert report["canary_enabled"] is False
    assert report["absolute_paths_omitted"] is True
    assert report["heldout_sample_count"] == 52
    assert report["heldout_capability_counts"] == {
        "c_kc_classification_v1": 18,
        "c_error_classification_v1": 14,
        "learning_summary_v1": 10,
        "read_only_tool_routing_v1": 10,
    }
    assert report["train_validation_excluded"] is True
    assert report["seed"] == 20260911
    assert report["inference_params"] == {"temperature": 0.0, "max_tokens": 512, "timeout_seconds": 30.0}
    assert (tmp_path / "reports" / "phase8a-blocked.report.json").is_file()
    assert (tmp_path / "reports" / "phase8a-blocked.report.md").is_file()
    assert (tmp_path / "reports" / "phase8a-blocked.predictions.jsonl").is_file()
    for decision in report["promotion_decisions"].values():
        assert decision["decision"] in ("BLOCKED", "SHADOW_ONLY")


def test_phase8a_compare_keeps_quality_safety_latency_resource_context(tmp_path) -> None:
    from learner_state_evaluation.model_shadow import real_benchmark as rb
    from learner_state_evaluation.model_shadow.dataset import write_shadow_dataset

    source = write_shadow_dataset(tmp_path / "source")
    baseline = rb.run_blocked_benchmark(
        dataset_path=source.data_path,
        output_dir=tmp_path / "baseline",
        reason="no authorized weights available",
    )
    baseline_path = tmp_path / "baseline" / "phase8a-blocked.report.json"
    comparison = rb.compare_benchmarks(
        baseline_report_path=baseline_path,
        candidate_report_path=baseline_path,
        output_path=tmp_path / "comparison.json",
    )
    assert comparison["baseline_inference_source"] == baseline["inference_source"]
    assert comparison["candidate_inference_source"] == baseline["inference_source"]
    assert "baseline_performance" in comparison
    assert "candidate_performance" in comparison
    assert set(comparison["by_capability"]) == {
        "c_kc_classification_v1",
        "c_error_classification_v1",
        "learning_summary_v1",
        "read_only_tool_routing_v1",
    }


def test_phase8a_configured_service_runs_without_local_weights_but_failures_stay_blocked(tmp_path) -> None:
    from learner_state_evaluation.model_shadow import real_benchmark as rb
    from learner_state_evaluation.model_shadow.candidate_client import OpenAICompatibleClient
    from learner_state_evaluation.model_shadow.dataset import write_shadow_dataset

    source = write_shadow_dataset(tmp_path / "source")
    client = OpenAICompatibleClient(
        base_url="http://127.0.0.1:1", model="phase8a-probe", api_key="probe-key", timeout_seconds=0.1)
    report = rb.run_real_benchmark(
        dataset_path=source.data_path,
        output_dir=tmp_path / "real",
        client=client,
        model_version="phase8a-probe",
    )
    assert report["execution_mode"] == "OPENAI_COMPATIBLE_SERVICE"
    assert report["inference_source"] == "MIXED_REAL_AND_FALLBACK"
    assert report["source_counts"] == {"REAL_MODEL": 0, "DETERMINISTIC_FALLBACK": 52}
    assert all(item["decision"] == "BLOCKED" for item in report["promotion_decisions"].values())
