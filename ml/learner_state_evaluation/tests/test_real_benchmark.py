from __future__ import annotations

from learner_state_evaluation.model_shadow.dataset import build_shadow_dataset


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


def test_phase8a_real_run_stays_blocked_without_weights(tmp_path) -> None:
    from learner_state_evaluation.model_shadow import real_benchmark as rb
    from learner_state_evaluation.model_shadow.candidate_client import OpenAICompatibleClient
    from learner_state_evaluation.model_shadow.dataset import write_shadow_dataset

    source = write_shadow_dataset(tmp_path / "source")
    client = OpenAICompatibleClient(
        base_url="http://127.0.0.1:1", model="phase8a-probe", api_key="probe-key", timeout_seconds=0.1)
    try:
        rb.run_real_benchmark(
            dataset_path=source.data_path,
            output_dir=tmp_path / "real",
            client=client,
            model_version="phase8a-probe",
        )
    except RuntimeError as exc:
        assert "blocked" in str(exc).lower()
    else:
        raise AssertionError("real benchmark must stay blocked without authorized weights")
