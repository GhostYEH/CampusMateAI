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
import time
from pathlib import Path
from typing import Any

from .candidate_client import CandidateRequest, create_client_from_env
from .dataset import DATASET_VERSION, load_shadow_dataset
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
WEIGHT_SUFFIXES = (".safetensors", ".gguf", ".pt", ".bin", ".onnx")
BASELINE_PREDICTION_SOURCE = "deterministic_baseline"
REAL_PREDICTION_SOURCE = "real_model_inference"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory_model_weights(env: dict[str, str] | None = None) -> dict[str, Any]:
    """盘点可用权重与真实推理入口，只返回存在性布尔值，不回显路径与密钥。"""
    source = dict(os.environ) if env is None else dict(env)
    checked = [key for key in (*WEIGHT_ENV_KEYS, "CAMPUSMATE_LM_SHADOW_ENABLED",
                               "CAMPUSMATE_LM_BASE_URL", "CAMPUSMATE_LM_MODEL") if key in source]
    weight_file: Path | None = None
    for key in WEIGHT_ENV_KEYS:
        raw = (source.get(key) or "").strip()
        if not raw:
            continue
        candidate = Path(raw)
        if candidate.suffix.lower() in WEIGHT_SUFFIXES and candidate.is_file():
            try:
                if candidate.stat().st_size > 0:
                    weight_file = candidate
                    break
            except OSError:
                continue
    shadow_enabled = (source.get("CAMPUSMATE_LM_SHADOW_ENABLED") or "").lower() in ("true", "1", "yes")
    service_configured = bool(
        shadow_enabled and source.get("CAMPUSMATE_LM_BASE_URL") and source.get("CAMPUSMATE_LM_MODEL")
        and source.get("CAMPUSMATE_LM_API_KEY")
    )
    if weight_file is not None:
        status, blocked, reason = "AVAILABLE", False, None
    else:
        status, blocked = "MISSING", True
        reason = "no authorized MiniMind/CampusMate-LM weights available"
    return {"benchmark_version": BENCHMARK_VERSION, "weight_status": status, "blocked": blocked,
            "block_reason": reason, "weight_file_name": weight_file.name if weight_file else None,
            "service_configured": service_configured, "checked_keys": sorted(checked),
            "absolute_paths_omitted": True}


def build_heldout_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """只取 held-out test split，按 sample_id 稳定排序。"""
    heldout = sorted([row for row in rows if row.get("split") == HELDOUT_SPLIT],
                     key=lambda row: row["sample_id"])
    assert heldout, "held-out test split is empty"
    assert {row["capability_name"] for row in heldout} == set(CAPABILITIES), \
        "held-out split must cover all four capabilities"
    return heldout


def require_real_client(client: Any) -> Any:
    """fixture / 确定性客户端永远不得通过真实模型门禁。"""
    if not getattr(client, "is_real_model", False):
        raise ValueError("fixture or deterministic client cannot claim REAL_MODEL inference")
    return client


def _baseline_predictions(heldout: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in heldout:
        start = time.perf_counter()
        output = dict(row["expected_output"])
        latency_ms = max(int((time.perf_counter() - start) * 1000), 0)
        rows.append({"sample_id": row["sample_id"], "capability_name": row["capability_name"],
                     "output": output, "confidence": float(output.get("confidence", 0.0)),
                     "latency_ms": latency_ms, "input_tokens": None, "output_tokens": None,
                     "peak_memory_mb": None, "device_type": "cpu",
                     "estimated_cost_per_1000_requests": 0.0,
                     "prediction_source": BASELINE_PREDICTION_SOURCE})
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


def run_blocked_benchmark(*, dataset_path: Path, output_dir: Path, reason: str,
                          seed: int = DEFAULT_SEED) -> dict[str, Any]:
    """无可用权重时的阻塞基线：只跑确定性基线做对照，真实侧保持阻塞。"""
    rows = load_shadow_dataset(dataset_path)
    heldout = build_heldout_rows(rows)
    predictions = _baseline_predictions(heldout)
    metrics_report = evaluate_shadow_predictions(heldout, predictions)
    baseline_decisions = _promotion_decisions(
        metrics_report, model_key="deterministic-baseline",
        model_version="deterministic-baseline-v1", dataset_version=DATASET_VERSION)
    blocked_decisions: dict[str, dict[str, Any]] = {}
    for capability in CAPABILITIES:
        blocked_decisions[capability] = {
            "model_key": "campusmate-lm", "model_version": None, "capability_name": capability,
            "capability_version": "v1", "dataset_version": DATASET_VERSION,
            "evaluator_version": EVALUATOR_VERSION, "threshold_version": THRESHOLD_VERSION,
            "decision": "BLOCKED", "failed_gates": ["REAL_MODEL_INFERENCE_UNAVAILABLE"],
            "quality_gate_status": "NOT_RUN", "performance_gate_status": "NOT_RUN"}
    report = {"benchmark_version": BENCHMARK_VERSION, "blocked": True, "block_reason": reason,
              "inference_source": "BLOCKED_NO_WEIGHTS", "real_model_inference": False,
              "prediction_source": BASELINE_PREDICTION_SOURCE, "model_path": None, "model_version": None,
              "seed": seed, "inference_params": dict(DEFAULT_INFERENCE_PARAMS),
              "dataset_version": DATASET_VERSION, "dataset_sha256": _sha256_file(dataset_path),
              "evaluator_version": EVALUATOR_VERSION, "test_split_only": True,
              "train_validation_excluded": True, "heldout_sample_count": len(heldout),
              "heldout_capability_counts": {cap: sum(r["capability_name"] == cap for r in heldout)
                                            for cap in CAPABILITIES},
              "baseline_metrics": metrics_report["by_capability"],
              "baseline_overall_safety": metrics_report["overall_safety"],
              "baseline_performance": metrics_report["performance"],
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
    inventory = inventory_model_weights()
    if inventory["blocked"]:
        raise RuntimeError(f"real benchmark is blocked: {inventory['block_reason']}")
    params = dict(DEFAULT_INFERENCE_PARAMS) if inference_params is None else dict(inference_params)
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
            run_id=f"{run_id}-{seed}-{row['sample_id']}")
        response = client.predict(request)
        output = dict(response.prediction) if isinstance(response.prediction, dict) else {}
        if response.used_fallback or not output:
            fallback_count += 1
            predictions.append({"sample_id": row["sample_id"], "capability_name": row["capability_name"],
                                "output": {}, "confidence": 0.0, "latency_ms": response.latency_ms,
                                "used_fallback": True, "error_code": response.error_code,
                                "prediction_source": "unavailable"})
            continue
        predictions.append({"sample_id": row["sample_id"], "capability_name": row["capability_name"],
                            "output": output, "confidence": float(output.get("confidence", 0.0)),
                            "latency_ms": response.latency_ms, "peak_memory_mb": None,
                            "device_type": None, "prediction_source": REAL_PREDICTION_SOURCE,
                            "model_version": response.model_version})
    metrics_report = evaluate_shadow_predictions(heldout, predictions)
    real_inference = fallback_count == 0
    report = {"benchmark_version": BENCHMARK_VERSION, "blocked": False, "block_reason": None,
              "inference_source": "REAL_MODEL" if real_inference else "MIXED_REAL_AND_FALLBACK",
              "real_model_inference": real_inference, "prediction_source": REAL_PREDICTION_SOURCE,
              "model_path": None, "model_weight_name": inventory.get("weight_file_name"),
              "model_version": model_version, "seed": seed,
              "inference_params": params, "fallback_count": fallback_count,
              "dataset_version": DATASET_VERSION, "dataset_sha256": _sha256_file(dataset_path),
              "evaluator_version": EVALUATOR_VERSION, "test_split_only": True,
              "train_validation_excluded": True, "heldout_sample_count": len(heldout),
              "capability_metrics": metrics_report["by_capability"],
              "overall_safety": metrics_report["overall_safety"],
              "performance": metrics_report["performance"],
              "promotion_decisions": _promotion_decisions(
                  metrics_report, model_key="campusmate-lm", model_version=model_version,
                  dataset_version=DATASET_VERSION),
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
    blocked = sub.add_parser("run-blocked")
    blocked.add_argument("--dataset", type=Path, required=True)
    blocked.add_argument("--output-dir", type=Path, required=True)
    blocked.add_argument("--reason", default="no authorized weights available")
    real = sub.add_parser("run-real")
    real.add_argument("--dataset", type=Path, required=True)
    real.add_argument("--output-dir", type=Path, required=True)
    real.add_argument("--model-version", required=True)
    real.add_argument("--seed", type=int, default=DEFAULT_SEED)
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
        print(json.dumps(inventory_model_weights(), ensure_ascii=False, indent=2, sort_keys=True))
    elif args.command == "run-blocked":
        report = run_blocked_benchmark(dataset_path=args.dataset, output_dir=args.output_dir,
                                       reason=args.reason)
        print(json.dumps({"blocked": report["blocked"], "inference_source": report["inference_source"],
                          "heldout_sample_count": report["heldout_sample_count"]},
                         ensure_ascii=False, sort_keys=True))
    elif args.command == "run-real":
        client = require_real_client(create_client_from_env())
        report = run_real_benchmark(dataset_path=args.dataset, output_dir=args.output_dir,
                                    client=client, model_version=args.model_version, seed=args.seed)
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
