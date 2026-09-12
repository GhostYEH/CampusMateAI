"""Phase 8A: CampusMate-LM 真实推理基线。

只允许真实模型声明 ``REAL_MODEL`` 推理：
- fixture / 确定性输出永远不得冒充真实模型。
- 无可用权重或无可用真实服务时，只能输出阻塞报告，不得运行“真实”评测。
- 评测严格限定在 held-out ``test`` split；``train`` / ``validation`` 不得进入推理或调参。
- 真实结果接入现有 promotion gate，但永远不启用生产或 Canary。
- 报告与日志不得包含模型权重、绝对路径、密钥、base URL 或原始模型输出。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .candidate_client import CandidateRequest, OpenAICompatibleClient, create_client_from_env
from .dataset import CAPABILITY_OUTPUT_FIELDS, DATASET_VERSION, load_shadow_dataset
from .evaluate import evaluate_files
from .metrics import EVALUATOR_VERSION, evaluate_shadow_predictions
from .promotion import THRESHOLD_VERSION, evaluate_promotion

BENCHMARK_VERSION = "campusmate-lm-real-benchmark-v1"
HELDOUT_SPLIT = "test"
CAPABILITIES = (
    "c_kc_classification_v1",
    "c_error_classification_v1",
    "learning_summary_v1",
    "read_only_tool_routing_v1",
)
DEFAULT_SEED = 20260911
DEFAULT_INFERENCE_PARAMS = {"temperature": 0.0, "max_tokens": 512, "timeout_seconds": 30.0}
WEIGHT_ENV_KEYS = ("CAMPUSMATE_LM_MODEL_PATH", "MINIMIND_MODEL_PATH", "CAMPUSMATE_LM_WEIGHTS_DIR")
BASELINE_PREDICTION_SOURCE = "DETERMINISTIC_BASELINE"
REAL_PREDICTION_SOURCE = "REAL_MODEL"
MAX_ASSET_FILES = 256
BLOCK_REASON_CODES = {"MODEL_RUNTIME_UNAVAILABLE", "LOCAL_INFERENCE_RUNTIME_UNAVAILABLE",
                      "REAL_MODEL_INFERENCE_UNAVAILABLE", "NO_VALID_REAL_MODEL_OUTPUT"}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _valid_model_asset(candidate: Path) -> tuple[bool, str | None]:
    try:
        if candidate.is_file():
            valid = candidate.suffix.lower() == ".gguf" and candidate.stat().st_size > 0
            return valid, candidate.name if valid else None
        if not candidate.is_dir():
            return False, None
        children = list(candidate.iterdir())[: MAX_ASSET_FILES + 1]
        if len(children) > MAX_ASSET_FILES:
            return False, None
        names = {child.name for child in children if child.is_file()}
        has_config = "config.json" in names
        has_tokenizer = bool(names & {"tokenizer.json", "tokenizer.model", "tokenizer_config.json"})
        weights = [child for child in children if child.is_file()
                   and child.suffix.lower() in {".safetensors", ".bin"} and child.stat().st_size > 0]
        return has_config and has_tokenizer and bool(weights), weights[0].name if weights else None
    except OSError:
        return False, None


def inventory_model_runtime(env: dict[str, str] | None = None) -> dict[str, Any]:
    """Return safe availability facts without paths, URLs, credentials, or probing a service."""
    source = dict(os.environ) if env is None else dict(env)
    checked = [key for key in (*WEIGHT_ENV_KEYS, "CAMPUSMATE_LM_SHADOW_ENABLED",
                               "CAMPUSMATE_LM_BASE_URL", "CAMPUSMATE_LM_MODEL") if key in source]
    asset_name: str | None = None
    for key in WEIGHT_ENV_KEYS:
        raw = (source.get(key) or "").strip()
        if not raw:
            continue
        valid, safe_name = _valid_model_asset(Path(raw))
        if valid:
            asset_name = safe_name
            break
    shadow_enabled = (source.get("CAMPUSMATE_LM_SHADOW_ENABLED") or "").lower() in ("true", "1", "yes")
    service_configured = bool(
        shadow_enabled and source.get("CAMPUSMATE_LM_BASE_URL") and source.get("CAMPUSMATE_LM_MODEL")
        and source.get("CAMPUSMATE_LM_API_KEY")
    )
    local_available = asset_name is not None
    if service_configured:
        mode, blocked, code = "OPENAI_COMPATIBLE_SERVICE", False, None
    elif local_available:
        mode, blocked, code = "LOCAL_WEIGHTS", True, "LOCAL_INFERENCE_RUNTIME_UNAVAILABLE"
    else:
        mode, blocked, code = "BLOCKED", True, "MODEL_RUNTIME_UNAVAILABLE"
    return {"benchmark_version": BENCHMARK_VERSION,
            "weight_status": "AVAILABLE" if local_available else "MISSING",
            "local_weights_available": local_available, "runtime_available": service_configured,
            "execution_mode": mode, "blocked": blocked, "block_reason_code": code,
            "weight_file_name": asset_name,
            "service_configured": service_configured, "checked_keys": sorted(checked),
            "absolute_paths_omitted": True}


def inventory_model_weights(env: dict[str, str] | None = None) -> dict[str, Any]:
    """Backward-compatible name for the safe runtime inventory."""
    result = inventory_model_runtime(env)
    result["block_reason"] = result["block_reason_code"]
    return result


def build_heldout_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """只取 held-out test split，按 sample_id 稳定排序。"""
    heldout = sorted([row for row in rows if row.get("split") == HELDOUT_SPLIT],
                     key=lambda row: row["sample_id"])
    assert heldout, "held-out test split is empty"
    assert {row["capability_name"] for row in heldout} == set(CAPABILITIES), \
        "held-out split must cover all four capabilities"
    return heldout


def preflight_benchmark(*, dataset_path: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    heldout = build_heldout_rows(load_shadow_dataset(dataset_path))
    inventory = inventory_model_runtime(env)
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "dataset_version": DATASET_VERSION,
        "dataset_sha256": _sha256_file(dataset_path),
        "test_split_only": True,
        "heldout_sample_count": len(heldout),
        "heldout_capability_counts": {
            capability: sum(row["capability_name"] == capability for row in heldout)
            for capability in CAPABILITIES
        },
        "execution_mode": inventory["execution_mode"],
        "local_weights_available": inventory["local_weights_available"],
        "service_configured": inventory["service_configured"],
        "runtime_available": inventory["runtime_available"],
        "ready": not inventory["blocked"],
        "block_reason_code": inventory["block_reason_code"],
        "absolute_paths_omitted": True,
    }


def require_real_client(client: Any) -> Any:
    """fixture / 确定性客户端永远不得通过真实模型门禁。"""
    if not isinstance(client, OpenAICompatibleClient) or client.provenance != "OPENAI_COMPATIBLE_SERVICE":
        raise ValueError("trusted real model client required; fixture or arbitrary client rejected")
    return client


def _deterministic_output(capability: str, features: dict[str, Any]) -> dict[str, Any]:
    if capability == "c_kc_classification_v1":
        codes = [code for code in features.get("candidate_kc_codes", []) if isinstance(code, str)]
        return {"knowledge_component_codes": codes, "confidence": 0.65 if codes else 0.0,
                "reason_codes": ["CONTROLLED_CANDIDATE_MATCH"] if codes else ["INSUFFICIENT_EVIDENCE"],
                "abstained": not codes}
    if capability == "c_error_classification_v1":
        errors = [code for code in features.get("candidate_error_codes", []) if isinstance(code, str)]
        kcs = [code for code in features.get("candidate_kc_codes", []) if isinstance(code, str)]
        return {"error_code": errors[0] if errors else None,
                "knowledge_component_codes": kcs if errors else [],
                "confidence": 0.6 if errors else 0.0, "abstained": not errors}
    if capability == "learning_summary_v1":
        explanations = set(features.get("explanation_codes", []))
        claims = []
        if "deadline_urgent" in explanations:
            claims.append("PRIORITIZE_NEAR_DEADLINE")
        if "kc_review" in explanations:
            claims.append("REVIEW_KNOWLEDGE_COMPONENT")
        if "short_session" in explanations:
            claims.append("USE_SHORT_SESSION")
        if "data_quality_partial" in explanations:
            claims.append("DATA_QUALITY_PARTIAL")
        summary = "建议根据当前受控证据安排下一步学习。" if claims else "当前证据不足，建议先补充一次受控学习记录。"
        return {"summary": summary, "claim_codes": claims}
    candidates = [name for name in features.get("candidate_read_tools", []) if isinstance(name, str)]
    tool = candidates[0] if candidates else None
    arguments = features.get("parameter_schema", {}) if tool else {}
    return {"tool_name": tool, "arguments": dict(arguments) if isinstance(arguments, dict) else {},
            "confidence": 0.7 if tool else 0.0, "abstained": tool is None}


def build_baseline_predictions(heldout: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run an input-only deterministic baseline; gold labels are never read."""
    rows: list[dict[str, Any]] = []
    for row in heldout:
        output = _deterministic_output(row["capability_name"], dict(row["input"]))
        rows.append({"sample_id": row["sample_id"], "capability_name": row["capability_name"],
                     "output": output, "confidence": float(output.get("confidence", 0.0)),
                     "latency_ms": None, "input_tokens": None, "output_tokens": None,
                     "peak_memory_mb": None, "device_type": "cpu",
                     "estimated_cost_per_1000_requests": None,
                     "prediction_source": BASELINE_PREDICTION_SOURCE,
                     "uses_expected_output": False, "eligible_for_comparison": True,
                     "eligible_for_promotion": False})
    return rows


def _promotion_decisions(report: dict[str, Any], *, model_key: str, model_version: str,
                         dataset_version: str) -> dict[str, dict[str, Any]]:
    decisions: dict[str, dict[str, Any]] = {}
    for capability in sorted(report["by_capability"]):
        metrics = {**report.get("overall_safety", {}), **report["by_capability"][capability]}
        decisions[capability] = evaluate_promotion(
            capability_name=capability, model_key=model_key, model_version=model_version,
            dataset_version=dataset_version, metrics=metrics,
            performance=report.get("performance", {}),
            evaluator_version=report.get("evaluator_version", EVALUATOR_VERSION))
    return decisions


def _blocked_decisions(reason: str, *, model_version: str | None = None) -> dict[str, dict[str, Any]]:
    return {capability: {
        "model_key": "campusmate-lm", "model_version": model_version,
        "capability_name": capability, "capability_version": "v1",
        "dataset_version": DATASET_VERSION, "evaluator_version": EVALUATOR_VERSION,
        "threshold_version": THRESHOLD_VERSION, "decision": "BLOCKED",
        "failed_gates": [reason], "quality_gate_status": "NOT_RUN",
        "performance_gate_status": "NOT_RUN",
    } for capability in CAPABILITIES}


def _valid_output(capability: str, output: Any, features: dict[str, Any]) -> bool:
    if not isinstance(output, dict) or set(output) != CAPABILITY_OUTPUT_FIELDS[capability]:
        return False
    confidence = output.get("confidence")
    if confidence is not None and (not isinstance(confidence, (int, float))
                                   or isinstance(confidence, bool) or not 0 <= confidence <= 1):
        return False
    if capability in {"c_kc_classification_v1", "c_error_classification_v1"}:
        codes = output.get("knowledge_component_codes")
        allowed_kcs = set(features.get("candidate_kc_codes", []))
        if not isinstance(codes, list) or not set(codes).issubset(allowed_kcs):
            return False
        if capability == "c_kc_classification_v1":
            allowed_reasons = {"CONTROLLED_CANDIDATE_MATCH", "CONTROLLED_TOPIC_MATCH",
                               "INSUFFICIENT_EVIDENCE"}
            return (isinstance(output.get("reason_codes"), list)
                    and set(output["reason_codes"]).issubset(allowed_reasons)
                    and isinstance(output.get("abstained"), bool))
        error = output.get("error_code")
        return ((error is None or error in set(features.get("candidate_error_codes", [])))
                and isinstance(output.get("abstained"), bool))
    if capability == "learning_summary_v1":
        allowed_claims = {"PRIORITIZE_NEAR_DEADLINE", "REVIEW_KNOWLEDGE_COMPONENT",
                          "USE_SHORT_SESSION", "DATA_QUALITY_PARTIAL"}
        return (isinstance(output.get("summary"), str) and 1 <= len(output["summary"]) <= 240
                and isinstance(output.get("claim_codes"), list)
                and set(output["claim_codes"]).issubset(allowed_claims))
    tool = output.get("tool_name")
    arguments = output.get("arguments")
    allowed_tools = set(features.get("candidate_read_tools", []))
    allowed_arguments = features.get("parameter_schema", {})
    return ((tool is None or tool in allowed_tools)
            and isinstance(arguments, dict)
            and "user_id" not in arguments
            and (tool is None or arguments == allowed_arguments)
            and isinstance(output.get("abstained"), bool))


def _write_report(output_dir: Path, *, stem: str, report: dict[str, Any],
                  predictions: list[dict[str, Any]] | None = None) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    if predictions is not None:
        predictions_path = output_dir / f"{stem}.predictions.jsonl"
        predictions_path.write_text("".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in predictions), encoding="utf-8")
        written["predictions"] = predictions_path
    report_path = output_dir / f"{stem}.report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    written["report"] = report_path
    lines = [f"# {stem} ({BENCHMARK_VERSION})", "",
             f"- dataset_version: `{report['dataset_version']}`",
             f"- evaluator_version: `{report.get('evaluator_version', EVALUATOR_VERSION)}`",
             f"- threshold_version: `{THRESHOLD_VERSION}`",
             f"- inference_source: `{report['inference_source']}`",
             f"- real_model_inference: `{report['real_model_inference']}`",
             f"- blocked: `{report['blocked']}`",
             f"- test_split_only: `{report['test_split_only']}`",
             f"- seed: `{report.get('seed')}`",
             f"- inference_params: `{json.dumps(report.get('inference_params', {}), sort_keys=True)}`",
             f"- production_enabled: `{report['production_enabled']}`",
             f"- canary_enabled: `{report['canary_enabled']}`",
             f"- absolute_paths_omitted: `true`", ""]
    if report.get("block_reason"):
        lines.append(f"- block_reason: `{report['block_reason']}`")
        lines.append("")
    for capability in sorted(report.get("promotion_decisions", {})):
        decision = report["promotion_decisions"][capability]
        lines.append(f"## {capability}: `{decision['decision']}`")
        for gate in decision.get("failed_gates", []):
            lines.append(f"- blocked_by: `{gate}`")
        lines.append("")
    markdown_path = output_dir / f"{stem}.report.md"
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    written["markdown"] = markdown_path
    return written


def run_baseline_benchmark(*, dataset_path: Path, output_dir: Path,
                           seed: int = DEFAULT_SEED) -> dict[str, Any]:
    heldout = build_heldout_rows(load_shadow_dataset(dataset_path))
    predictions = build_baseline_predictions(heldout)
    metrics = evaluate_shadow_predictions(heldout, predictions)
    report = {
        "benchmark_version": BENCHMARK_VERSION, "blocked": False, "block_reason": None,
        "inference_source": BASELINE_PREDICTION_SOURCE, "real_model_inference": False,
        "baseline_type": "DETERMINISTIC_BASELINE", "baseline_version": "input-only-v1",
        "uses_expected_output": False, "eligible_for_comparison": True,
        "eligible_for_promotion": False, "seed": seed,
        "inference_params": {}, "dataset_version": DATASET_VERSION,
        "dataset_sha256": _sha256_file(dataset_path), "evaluator_version": EVALUATOR_VERSION,
        "test_split_only": True, "train_validation_excluded": True,
        "heldout_sample_count": len(heldout), "capability_metrics": metrics["by_capability"],
        "overall_safety": metrics["overall_safety"], "performance": metrics["performance"],
        "performance_status": "NOT_MEASURED", "resource_measurement_status": "NOT_MEASURED",
        "promotion_decisions": _blocked_decisions("BASELINE_NOT_PROMOTION_ELIGIBLE",
                                                   model_version="deterministic-baseline-v2"),
        "production_enabled": False, "canary_enabled": False, "absolute_paths_omitted": True,
    }
    _write_report(output_dir, stem="phase8a-baseline", report=report, predictions=predictions)
    return report


def run_blocked_benchmark(*, dataset_path: Path, output_dir: Path, reason: str,
                          seed: int = DEFAULT_SEED) -> dict[str, Any]:
    """无可用权重时的阻塞基线：只跑确定性基线做对照，真实侧保持阻塞。"""
    rows = load_shadow_dataset(dataset_path)
    heldout = build_heldout_rows(rows)
    predictions = build_baseline_predictions(heldout)
    metrics_report = evaluate_shadow_predictions(heldout, predictions)
    baseline_decisions = _blocked_decisions("BASELINE_NOT_PROMOTION_ELIGIBLE",
                                            model_version="deterministic-baseline-v2")
    blocked_decisions = _blocked_decisions("REAL_MODEL_INFERENCE_UNAVAILABLE")
    safe_reason = reason if reason in BLOCK_REASON_CODES else "MODEL_RUNTIME_UNAVAILABLE"
    report = {"benchmark_version": BENCHMARK_VERSION, "blocked": True, "block_reason": safe_reason,
              "inference_source": "BLOCKED", "real_model_inference": False,
              "prediction_source": BASELINE_PREDICTION_SOURCE, "model_path": None, "model_version": None,
              "baseline_type": "DETERMINISTIC_BASELINE", "baseline_version": "input-only-v1",
              "uses_expected_output": False, "eligible_for_comparison": True,
              "eligible_for_promotion": False,
              "seed": seed, "inference_params": dict(DEFAULT_INFERENCE_PARAMS),
              "dataset_version": DATASET_VERSION, "dataset_sha256": _sha256_file(dataset_path),
              "evaluator_version": EVALUATOR_VERSION, "test_split_only": True,
              "train_validation_excluded": True, "heldout_sample_count": len(heldout),
              "heldout_capability_counts": {cap: sum(r["capability_name"] == cap for r in heldout)
                                            for cap in CAPABILITIES},
              "baseline_metrics": metrics_report["by_capability"],
              "baseline_overall_safety": metrics_report["overall_safety"],
              "baseline_performance": metrics_report["performance"],
              "performance_status": "NOT_MEASURED", "resource_measurement_status": "NOT_MEASURED",
              "baseline_promotion_decisions": baseline_decisions,
              "promotion_decisions": blocked_decisions,
              "production_enabled": False, "canary_enabled": False, "absolute_paths_omitted": True}
    _write_report(output_dir, stem="phase8a-blocked", report=report, predictions=predictions)
    return report


def run_real_benchmark(*, dataset_path: Path, output_dir: Path, client: Any,
                       model_version: str, seed: int = DEFAULT_SEED,
                       inference_params: dict[str, Any] | None = None,
                       run_id: str = "phase8a-heldout") -> dict[str, Any]:
    """使用真实客户端在 held-out test 上推理；fixture 与阻塞状态直接失败。"""
    require_real_client(client)
    params = dict(DEFAULT_INFERENCE_PARAMS) if inference_params is None else dict(inference_params)
    params["timeout_seconds"] = client.timeout_seconds
    rows = load_shadow_dataset(dataset_path)
    heldout = build_heldout_rows(rows)
    predictions: list[dict[str, Any]] = []
    fallback_count = 0
    for row in heldout:
        request = CandidateRequest(
            capability_name=row["capability_name"], capability_version="v1",
            structured_features=row["input"],
            prompt_template_version=f"{row['capability_name']}-prompt-v1",
            taxonomy_version="c_taxonomy_v1", schema_version=row["input_schema_version"],
            run_id=f"{run_id}-{seed}-{row['sample_id']}",
            generation_params={"temperature": params.get("temperature", 0.0),
                               "max_tokens": params.get("max_tokens", 512), "seed": seed})
        response = client.predict(request)
        output = dict(response.prediction) if isinstance(response.prediction, dict) else {}
        if response.used_fallback or not _valid_output(row["capability_name"], output, row["input"]):
            fallback_count += 1
            predictions.append({"sample_id": row["sample_id"], "capability_name": row["capability_name"],
                                "output": {}, "confidence": 0.0, "latency_ms": response.latency_ms,
                                "used_fallback": True,
                                "error_code": response.error_code or "MODEL_SCHEMA_INVALID",
                                "schema_valid": False, "prediction_source": "DETERMINISTIC_FALLBACK",
                                "model_key": response.model_key, "model_version": response.model_version})
            continue
        predictions.append({"sample_id": row["sample_id"], "capability_name": row["capability_name"],
                            "output": output, "confidence": float(output.get("confidence", 0.0)),
                            "latency_ms": response.latency_ms, "peak_memory_mb": None,
                            "device_type": None, "prediction_source": REAL_PREDICTION_SOURCE,
                            "schema_valid": True, "used_fallback": False, "error_code": None,
                            "model_key": response.model_key, "model_version": response.model_version})
    metrics_report = evaluate_shadow_predictions(heldout, predictions)
    real_model_sample_count = len(predictions) - fallback_count
    fully_real = fallback_count == 0
    any_real = real_model_sample_count > 0
    inference_source = ("REAL_MODEL" if fully_real else
                        "MIXED_REAL_AND_FALLBACK" if any_real else "DETERMINISTIC_FALLBACK")
    source_counts = {source: sum(p["prediction_source"] == source for p in predictions)
                     for source in (REAL_PREDICTION_SOURCE, "DETERMINISTIC_FALLBACK")}
    source_counts_by_capability = {
        capability: {source: sum(p["capability_name"] == capability
                                and p["prediction_source"] == source for p in predictions)
                     for source in (REAL_PREDICTION_SOURCE, "DETERMINISTIC_FALLBACK")}
        for capability in CAPABILITIES
    }
    decisions = _promotion_decisions(metrics_report, model_key="campusmate-lm",
                                     model_version=model_version, dataset_version=DATASET_VERSION)
    for capability in CAPABILITIES:
        selected = [p for p in predictions if p["capability_name"] == capability]
        if not selected or any(p["prediction_source"] != REAL_PREDICTION_SOURCE for p in selected):
            decisions[capability]["decision"] = "BLOCKED"
            decisions[capability]["failed_gates"] = sorted(set(
                decisions[capability]["failed_gates"] + ["REAL_MODEL_COVERAGE_INCOMPLETE"]))
    report = {"benchmark_version": BENCHMARK_VERSION, "blocked": not any_real,
              "block_reason": None if any_real else "NO_VALID_REAL_MODEL_OUTPUT",
              "inference_source": inference_source,
              "real_model_inference": any_real, "fully_real_model_inference": fully_real,
              "real_model_sample_count": real_model_sample_count,
              "prediction_source": REAL_PREDICTION_SOURCE,
              "execution_mode": "OPENAI_COMPATIBLE_SERVICE", "model_path": None,
              "model_weight_name": None, "source_counts": source_counts,
              "source_counts_by_capability": source_counts_by_capability,
              "model_version": model_version, "seed": seed,
              "inference_params": params, "fallback_count": fallback_count,
              "dataset_version": DATASET_VERSION, "dataset_sha256": _sha256_file(dataset_path),
              "evaluator_version": EVALUATOR_VERSION, "test_split_only": True,
              "train_validation_excluded": True, "heldout_sample_count": len(heldout),
              "capability_metrics": metrics_report["by_capability"],
              "overall_safety": metrics_report["overall_safety"],
              "performance": metrics_report["performance"],
              "performance_status": "MEASURED" if metrics_report["performance"].get("p95_latency_ms") is not None else "NOT_MEASURED",
              "resource_measurement_status": "NOT_MEASURED",
              "promotion_decisions": decisions,
              "production_enabled": False, "canary_enabled": False, "absolute_paths_omitted": True}
    _write_report(output_dir, stem="phase8a-real", report=report, predictions=predictions)
    return report


def compare_benchmarks(*, baseline_report_path: Path, candidate_report_path: Path,
                       output_path: Path) -> dict[str, Any]:
    """对比确定性基线与候选报告，不读取权重与原始输出。"""
    baseline = json.loads(baseline_report_path.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_report_path.read_text(encoding="utf-8"))
    comparison: dict[str, Any] = {"benchmark_version": BENCHMARK_VERSION,
                                  "baseline_inference_source": baseline["inference_source"],
                                  "candidate_inference_source": candidate["inference_source"],
                                  "baseline_performance": baseline.get("baseline_performance",
                                                                       baseline.get("performance")),
                                  "candidate_performance": candidate.get("performance",
                                                                         candidate.get("baseline_performance")),
                                  "by_capability": {}}
    base_metrics = baseline.get("baseline_metrics", baseline.get("capability_metrics", {}))
    cand_metrics = candidate.get("capability_metrics", candidate.get("baseline_metrics", {}))
    for capability in sorted(set(base_metrics) & set(cand_metrics)):
        deltas: dict[str, Any] = {}
        for key in sorted(set(base_metrics[capability]) & set(cand_metrics[capability])):
            base_value, cand_value = base_metrics[capability][key], cand_metrics[capability][key]
            if isinstance(base_value, (int, float)) and isinstance(cand_value, (int, float)) \
                    and not isinstance(base_value, bool) and not isinstance(cand_value, bool):
                deltas[key] = cand_value - base_value
        comparison["by_capability"][capability] = {
            "metric_deltas": deltas,
            "baseline_decision": (baseline.get("baseline_promotion_decisions", {})
                                  .get(capability, {}).get("decision")),
            "candidate_decision": (candidate.get("promotion_decisions", {})
                                   .get(capability, {}).get("decision"))}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    return comparison


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 8A real-model benchmark harness (held-out test only)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inventory")
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--dataset", type=Path, required=True)
    baseline = sub.add_parser("run-baseline")
    baseline.add_argument("--dataset", type=Path, required=True)
    baseline.add_argument("--output-dir", type=Path, required=True)
    blocked = sub.add_parser("run-blocked")
    blocked.add_argument("--dataset", type=Path, required=True)
    blocked.add_argument("--output-dir", type=Path, required=True)
    blocked.add_argument("--reason", default="no authorized weights available")
    real = sub.add_parser("run-real")
    real.add_argument("--dataset", type=Path, required=True)
    real.add_argument("--output-dir", type=Path, required=True)
    real.add_argument("--model-version", required=True)
    real.add_argument("--seed", type=int, default=DEFAULT_SEED)
    real.add_argument("--temperature", type=float, default=0.0)
    real.add_argument("--max-tokens", type=int, default=512)
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--dataset", type=Path, required=True)
    evaluate.add_argument("--manifest", type=Path, required=False, default=None)
    evaluate.add_argument("--predictions", type=Path, required=True)
    evaluate.add_argument("--output-dir", type=Path, required=True)
    evaluate.add_argument("--model-key", default="phase8a-candidate")
    evaluate.add_argument("--mode", default="campusmate-lm-predictions",
                          choices=("deterministic-baseline", "mature-model-predictions",
                                   "campusmate-lm-predictions"))
    compare = sub.add_parser("compare")
    compare.add_argument("--baseline", type=Path, required=True)
    compare.add_argument("--candidate", type=Path, required=True)
    compare.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "inventory":
        print(json.dumps(inventory_model_runtime(), ensure_ascii=False, indent=2, sort_keys=True))
    elif args.command == "preflight":
        print(json.dumps(preflight_benchmark(dataset_path=args.dataset),
                         ensure_ascii=False, indent=2, sort_keys=True))
    elif args.command == "run-baseline":
        report = run_baseline_benchmark(dataset_path=args.dataset, output_dir=args.output_dir)
        print(json.dumps({"inference_source": report["inference_source"],
                          "heldout_sample_count": report["heldout_sample_count"],
                          "eligible_for_promotion": report["eligible_for_promotion"]}, sort_keys=True))
    elif args.command == "run-blocked":
        report = run_blocked_benchmark(dataset_path=args.dataset, output_dir=args.output_dir,
                                       reason=args.reason)
        print(json.dumps({"blocked": report["blocked"], "inference_source": report["inference_source"],
                          "heldout_sample_count": report["heldout_sample_count"]},
                         ensure_ascii=False, sort_keys=True))
    elif args.command == "run-real":
        client = create_client_from_env()
        if not isinstance(client, OpenAICompatibleClient):
            print(json.dumps({"blocked": True, "block_reason_code": "MODEL_RUNTIME_UNAVAILABLE",
                              "inference_source": "BLOCKED"}, sort_keys=True))
            raise SystemExit(2)
        client = require_real_client(client)
        report = run_real_benchmark(dataset_path=args.dataset, output_dir=args.output_dir,
                                    client=client, model_version=args.model_version, seed=args.seed,
                                    inference_params={"temperature": args.temperature,
                                                      "max_tokens": args.max_tokens})
        print(json.dumps({"blocked": report["blocked"], "inference_source": report["inference_source"],
                          "real_model_inference": report["real_model_inference"]},
                         ensure_ascii=False, sort_keys=True))
    elif args.command == "evaluate":
        evaluate_files(dataset_path=args.dataset, manifest_path=args.manifest,
                       predictions_path=args.predictions, output_dir=args.output_dir,
                       model_key=args.model_key, mode=args.mode)
    else:
        compare_benchmarks(baseline_report_path=args.baseline, candidate_report_path=args.candidate,
                           output_path=args.output)


if __name__ == "__main__":
    main()
