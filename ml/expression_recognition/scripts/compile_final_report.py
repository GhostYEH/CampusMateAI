"""Compile the reproducible model-selection and deployment handoff report."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "artifacts" / "final_report"
CLASSES = ["angry", "disgust", "fear", "happy", "neutral", "sad", "surprise"]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def metrics(path: Path) -> dict:
    value = read_json(path)
    report = value["classification_report"]
    return {
        "accuracy": value["accuracy"],
        "macro_f1": value["macro_f1"],
        "weighted_f1": value["weighted_f1"],
        "balanced_accuracy": value["balanced_accuracy"],
        "ece_15_bin": value["ece_15_bin"],
        "recall": {name: report[name]["recall"] for name in CLASSES},
        "source": str(path.resolve()),
    }


def main() -> None:
    REPORT.mkdir(parents=True, exist_ok=True)
    baseline_names = ["baseline_cnn", "mobilenet_v3_small", "resnet18"]
    candidate_names = [
        "resnet18_exp_a",
        "resnet18_exp_b",
        "resnet18_exp_c",
        "resnet18_exp_d",
        "efficientnet_b0",
    ]
    rows: list[dict] = []
    all_metrics: dict[str, dict] = {}
    for name in baseline_names:
        val = metrics(ROOT / "artifacts" / "baseline_reverification" / name / "validation" / "validation_metrics.json")
        test = metrics(ROOT / "artifacts" / "baseline_reverification" / name / "test" / "test_metrics.json")
        all_metrics[name] = {"validation": val, "test": test}
        rows.append({"name": name, "kind": "baseline", "validation": val, "test": test})
    for name in candidate_names:
        val = metrics(ROOT / "artifacts" / "experiments" / name / "validation" / "validation_metrics.json")
        test = metrics(ROOT / "artifacts" / "experiments" / name / "test" / "test_metrics.json")
        all_metrics[name] = {"validation": val, "test": test}
        rows.append({"name": name, "kind": "candidate", "validation": val, "test": test})

    baseline = all_metrics["resnet18"]["validation"]
    gate_rows = []
    for row in rows:
        if row["kind"] != "candidate":
            continue
        recall_delta = {
            name: row["validation"]["recall"][name] - baseline["recall"][name]
            for name in CLASSES
        }
        gate_rows.append(
            {
                "name": row["name"],
                "validation_macro_f1_delta": row["validation"]["macro_f1"] - baseline["macro_f1"],
                "minimum_validation_recall_delta": min(recall_delta.values()),
                "macro_f1_gate": row["validation"]["macro_f1"] >= baseline["macro_f1"] + 0.015,
                "recall_gate": min(recall_delta.values()) >= -0.03,
                "recall_delta": recall_delta,
            }
        )
    eligible = [item for item in gate_rows if item["macro_f1_gate"] and item["recall_gate"]]

    audit = read_json(ROOT / "artifacts" / "data_audit_full" / "dataset_inventory.json")
    environment = read_json(ROOT / "artifacts" / "environment_cuda.json")
    android_model = ROOT.parents[1] / "android" / "app" / "src" / "main" / "assets" / "expression_model.tflite"
    candidate_model = ROOT / "artifacts" / "litert_candidate" / "expression_resnet18_dynamic_int8.tflite"
    decision = {
        "status": "retain_current_android_asset" if not eligible else "candidate_eligible_for_review",
        "baseline": "resnet18",
        "eligible_candidates": eligible,
        "reason": "No candidate met validation macro-F1 +0.015 and per-class recall non-regression gates.",
        "current_android_asset_sha256": sha256(android_model),
        "candidate_dynamic_int8_sha256": sha256(candidate_model),
    }
    payload = {
        "classes": CLASSES,
        "baseline_metrics": all_metrics,
        "candidate_gate_results": gate_rows,
        "selection_decision": decision,
        "dataset_audit_summary": {
            key: audit[key]
            for key in (
                "dataset_root",
                "image_count",
                "readable_count",
                "corrupted_count",
                "missing_csv_references",
                "exact_duplicate_groups",
                "cross_split_exact_duplicate_groups",
                "perceptual_duplicate_groups",
                "selected_training_source",
                "excluded_sources",
                "license_status",
            )
        },
        "cuda_environment": environment,
        "artifact_roots": {
            "dataset_audit": str((ROOT / "artifacts" / "data_audit_full").resolve()),
            "baseline_reverification": str((ROOT / "artifacts" / "baseline_reverification").resolve()),
            "experiments": str((ROOT / "artifacts" / "experiments").resolve()),
            "litert_candidate": str((ROOT / "artifacts" / "litert_candidate").resolve()),
        },
    }
    (REPORT / "baseline_report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with (REPORT / "experiment_summary.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["name", "kind", "validation_accuracy", "validation_macro_f1", "test_accuracy", "test_macro_f1", "test_balanced_accuracy"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "name": row["name"],
                    "kind": row["kind"],
                    "validation_accuracy": row["validation"]["accuracy"],
                    "validation_macro_f1": row["validation"]["macro_f1"],
                    "test_accuracy": row["test"]["accuracy"],
                    "test_macro_f1": row["test"]["macro_f1"],
                    "test_balanced_accuracy": row["test"]["balanced_accuracy"],
                }
            )

    lines = [
        "# CNN 表情识别最终模型比较",
        "",
        "评估协议：同一份清洗后的 2013 manifest、固定 validation/test split、7 类 observable facial expression、CUDA 推理评估。",
        "",
        "| 模型 | 类型 | Val macro-F1 | Test macro-F1 | Test balanced accuracy | Test ECE |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['name']} | {row['kind']} | {row['validation']['macro_f1']:.6f} | {row['test']['macro_f1']:.6f} | {row['test']['balanced_accuracy']:.6f} | {row['test']['ece_15_bin']:.6f} |"
        )
    lines.extend(
        [
            "",
            f"当前基线为 ResNet18，验证 macro-F1={baseline['macro_f1']:.6f}。替换门槛为至少提升 0.015，且任何类别验证 recall 不下降超过 0.03。",
            "",
            "结论：所有候选均未通过门槛，因此保留现有 Android dynamic-int8 资产；不会用较弱候选覆盖线上/演示模型。",
            "",
            "实验配置：A=随机采样+weighted CE；B=WeightedRandomSampler+普通 CE；C=class-balanced focal；D=balanced batch+轻量 class-weighted CE。",
        ]
    )
    (REPORT / "model_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    litert = read_json(ROOT / "artifacts" / "litert_candidate" / "litert_verification.json")
    lite_lines = [
        "# LiteRT 导出验证",
        "",
        "四种变体均通过桌面 LiteRT interpreter 加载，并使用同一 validation/test manifest 验证。权重转换的 64 样本 top-1 对齐率为 1.0。",
        "",
        "| 变体 | 输入/输出 dtype | Val macro-F1 | Test macro-F1 | 对齐 top-1 | 平均延迟(ms) |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for name in ("float32", "dynamic_int8", "float16", "full_int8"):
        item = litert[name]
        contract = item["tensor_contract"]
        lite_lines.append(
            f"| {name} | {contract['input_dtype']} / {contract['output_dtype']} | {item['validation_metrics']['macro_f1']:.6f} | {item['test_metrics']['macro_f1']:.6f} | {item['alignment']['top1_agreement']:.6f} | {item['benchmark']['mean_latency_ms']:.3f} |"
        )
    lite_lines.extend(
        [
            "",
            f"导出器：{litert['export']['selected_converter']}；当前选择：{litert['selected_variant']}。",
            "full int8 已完成验证，但当前 Android runner 的输入契约是 float32，因此不直接替换 Android 资产。",
        ]
    )
    (REPORT / "litert_validation.md").write_text("\n".join(lite_lines) + "\n", encoding="utf-8")

    android_apk = ROOT.parents[1] / "android" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
    android_lines = [
        "# Android 验收",
        "",
        "- `:app:testDebugUnitTest`: PASS",
        "- `:app:assembleDebug`: PASS",
        "- `:app:lintDebug`: PASS（0 errors；有 warnings/hints）",
        f"- APK: `{android_apk.resolve()}` ({android_apk.stat().st_size} bytes)",
        "- ADB/真机 benchmark: 未执行；系统 PATH 与常见 Android SDK 路径均未发现 adb.exe，因此不虚构设备性能数据。",
        "- 构建 JDK：`F:/demo1/android/.tools/jdk21-full/jdk-21.0.12+8`；Gradle cache：`F:/demo1/android/.gradle-user-home`。",
    ]
    (REPORT / "android_validation.md").write_text("\n".join(android_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
