"""FER2013 正式训练驱动脚本（一次性执行：smoke → 正式训练 → 评估 → 导出 → 模型卡片）。

执行流程：
1. 加载/生成数据划分清单（split_manifest.json），保证三个模型用同一固定划分。
2. 对三个模型分别跑 1 epoch smoke training（小量数据），验证训练链路正常。
3. smoke 全部通过后，依次正式训练 custom_cnn → mobilenet_v3_small → resnet18。
   - 不会同时启动多个 GPU 训练进程。
4. 每个模型训练完成后立即：
   - 在 test 上评估一次（用 best_checkpoint）
   - 导出 .pt / .onnx / labels.json / preprocess.json / model_card.json / SHA-256
   - 写 model_card.json
5. 汇总三个模型的真实指标到 artifacts/fer2013_training_summary.json。

使用：
    cd ml/expression_recognition
    conda run -n campusmate-cnn python run_fer2013_training.py

产物根目录：artifacts/
- artifacts/split_manifest.json
- artifacts/smoke/<model>/...
- artifacts/<model>/best_model.pt, model.onnx, labels.json, preprocess.json,
                            model_card.json, metrics.json, evaluate_summary.json,
                            training_summary.json, training_history.csv,
                            confusion_matrix.png, consistency.json
- artifacts/fer2013_training_summary.json
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
import time
import traceback
from dataclasses import replace
from pathlib import Path
from typing import Any

# 让脚本可独立运行：把当前目录加入 sys.path。
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from expression_recognition.config import ExperimentConfig
from expression_recognition.constants import EXPRESSION_LABELS
from expression_recognition.data import (
    load_samples,
    split_samples,
    save_manifest,
    load_manifest,
    reconstruct_samples_from_manifest,
    verify_manifest_against_samples,
)
from expression_recognition.data.fer2013 import build_torch_datasets, FER2013Sample
from expression_recognition.data.transforms import build_train_transform, build_eval_transform
from expression_recognition.training.trainer import train as run_train
from expression_recognition.evaluation.evaluate import run_evaluation
from expression_recognition.export.onnx_export import export_onnx
from expression_recognition.export.labels import export_labels_json
from expression_recognition.export.preprocess import export_preprocess_json
from expression_recognition.export.consistency import run_consistency_test
from expression_recognition.export.tflite_export import export_tflite
from expression_recognition.export.model_card import export_model_card
from expression_recognition.utils.io import write_json, read_json, ensure_dir


# ============================================================================
# 配置：三个模型的配置文件路径与训练顺序
# ============================================================================
CONFIGS_DIR = HERE / "configs"
MODEL_CONFIGS = [
    ("custom_cnn", CONFIGS_DIR / "custom_cnn.yaml"),
    ("mobilenet_v3_small", CONFIGS_DIR / "mobilenet_v3_small.yaml"),
    ("resnet18", CONFIGS_DIR / "resnet18.yaml"),
]

ARTIFACTS_DIR = HERE / "artifacts"
MANIFEST_PATH = ARTIFACTS_DIR / "split_manifest.json"
SMOKE_DIR = ARTIFACTS_DIR / "smoke"
SUMMARY_PATH = ARTIFACTS_DIR / "fer2013_training_summary.json"

# Smoke 训练参数：每类取 N 张训练样本，跑 1 epoch。
SMOKE_PER_CLASS = 30
SMOKE_EPOCHS = 1


# ============================================================================
# 工具函数
# ============================================================================
def _log(msg: str) -> None:
    """带时间戳的日志输出。"""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _load_cfg(config_path: Path) -> ExperimentConfig:
    cfg = ExperimentConfig.from_yaml(config_path)
    cfg.validate()
    return cfg


def _build_datasets_from_samples(
    samples_by_split: dict[str, list[FER2013Sample]],
    cfg: ExperimentConfig,
) -> dict[str, Any]:
    """根据配置构造 torch Dataset 字典。"""
    train_tfm = build_train_transform(cfg.augmentation, cfg.input, seed=cfg.train.seed)
    eval_tfm = build_eval_transform(cfg.input)
    return build_torch_datasets(samples_by_split, train_tfm, eval_tfm, cfg.input.channels)


def _subset_per_class(
    samples: list[FER2013Sample],
    per_class: int,
    seed: int = 42,
) -> list[FER2013Sample]:
    """按类别分层抽取子集（每类 per_class 张），用于 smoke training。"""
    import random
    rng = random.Random(seed)
    by_label: dict[int, list[FER2013Sample]] = {}
    for s in samples:
        by_label.setdefault(s.label, []).append(s)
    out: list[FER2013Sample] = []
    for label in sorted(by_label.keys()):
        group = by_label[label][:]
        rng.shuffle(group)
        out.extend(group[:per_class])
    rng.shuffle(out)
    return out


# ============================================================================
# Step 1: 数据划分清单
# ============================================================================
def prepare_split_manifest(reference_cfg: ExperimentConfig) -> dict[str, Any]:
    """生成或加载 split_manifest.json。

    用 reference_cfg 的 data 配置（三个模型 data 配置相同）。
    """
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    if MANIFEST_PATH.exists():
        _log(f"数据划分清单已存在，加载: {MANIFEST_PATH}")
        manifest = load_manifest(MANIFEST_PATH)
        # 校验清单与当前数据集是否一致。
        samples = load_samples(
            reference_cfg.data.dataset_root,
            reference_cfg.data.format,
            reference_cfg.data.csv_name,
        )
        ok, msg = verify_manifest_against_samples(manifest, samples)
        if ok:
            _log(f"清单与当前数据集一致（{len(samples)} 样本）。复用固定划分。")
            return manifest
        _log(f"清单与当前数据集不一致: {msg} 重新生成清单。")
        # 不一致则重新生成（继续走下面的逻辑）。

    _log("首次运行，生成数据划分清单...")
    samples = load_samples(
        reference_cfg.data.dataset_root,
        reference_cfg.data.format,
        reference_cfg.data.csv_name,
    )
    _log(f"原始样本总数: {len(samples)}")

    split_result = split_samples(
        samples,
        train_ratio=reference_cfg.data.train_ratio,
        val_ratio=reference_cfg.data.val_ratio,
        test_ratio=reference_cfg.data.test_ratio,
        stratified=reference_cfg.data.stratified,
        split_seed=reference_cfg.data.split_seed,
    )
    counts = split_result.counts_by_split_label()
    _log(
        f"划分完成: train={len(split_result.train)}, "
        f"val={len(split_result.val)}, test={len(split_result.test)}"
    )
    for split_name in ("train", "val", "test"):
        per_class_str = ", ".join(
            f"{EXPRESSION_LABELS[i]}={counts[split_name].get(i, 0)}"
            for i in range(len(EXPRESSION_LABELS))
        )
        _log(f"  {split_name}: {per_class_str}")

    manifest = save_manifest(
        MANIFEST_PATH,
        samples,
        split_result,
        dataset_root=reference_cfg.data.dataset_root,
        fmt=reference_cfg.data.format,
        split_seed=reference_cfg.data.split_seed,
    )
    _log(f"清单已保存: {MANIFEST_PATH}")
    return manifest


def load_splits_from_manifest(manifest: dict[str, Any]) -> dict[str, list[FER2013Sample]]:
    """从清单重建 splits 字典。"""
    return reconstruct_samples_from_manifest(manifest)


# ============================================================================
# Step 2: Smoke training（1 epoch，小量子集）
# ============================================================================
def run_smoke_training(
    model_name: str,
    cfg: ExperimentConfig,
    full_splits: dict[str, list[FER2013Sample]],
) -> dict[str, Any]:
    """对单个模型跑 1 epoch smoke training。

    smoke 用 train 的子集（每类 SMOKE_PER_CLASS 张）+ val 的子集（同上）。
    产物写到 artifacts/smoke/<model>/。
    """
    _log(f"=== SMOKE 训练: {model_name} ===")
    smoke_out_dir = SMOKE_DIR / model_name
    if smoke_out_dir.exists():
        shutil.rmtree(smoke_out_dir, ignore_errors=True)
    ensure_dir(smoke_out_dir)

    # 构造 smoke 子集。
    smoke_train = _subset_per_class(full_splits["train"], SMOKE_PER_CLASS, seed=42)
    smoke_val = _subset_per_class(full_splits["val"], max(5, SMOKE_PER_CLASS // 3), seed=43)
    smoke_splits = {"train": smoke_train, "val": smoke_val, "test": []}
    _log(
        f"  smoke 子集: train={len(smoke_train)}, val={len(smoke_val)}"
    )

    # 复制 cfg 并覆盖训练参数：1 epoch，小 batch，无早停，无 AMP（smoke 只验证链路）。
    smoke_cfg = copy.deepcopy(cfg)
    smoke_cfg.experiment_name = f"{model_name}_smoke"
    smoke_cfg.output_dir = str(smoke_out_dir)
    smoke_cfg.train.epochs = SMOKE_EPOCHS
    smoke_cfg.train.batch_size = min(cfg.train.batch_size, 32)
    smoke_cfg.train.early_stopping_patience = 0  # 关闭早停
    smoke_cfg.train.amp = False  # smoke 用纯 fp32 验证
    smoke_cfg.train.num_workers = 0  # Windows 下 smoke 用主进程更稳

    datasets = _build_datasets_from_samples(smoke_splits, smoke_cfg)
    # run_train 内部会写 training_summary.json / training_history.csv / best_model.pt
    t0 = time.time()
    summary = run_train(smoke_cfg, datasets)
    elapsed = time.time() - t0

    ok = (
        summary.get("best_metric") is not None
        and (smoke_out_dir / "best_model.pt").exists()
    )
    result = {
        "model_name": model_name,
        "ok": ok,
        "elapsed_sec": elapsed,
        "best_metric": summary.get("best_metric"),
        "best_epoch": summary.get("best_epoch"),
        "epochs_run": summary.get("epochs_run"),
        "output_dir": str(smoke_out_dir),
    }
    write_json(smoke_out_dir / "smoke_result.json", result)
    _log(
        f"  smoke 完成: ok={ok}, best_metric={summary.get('best_metric')}, "
        f"elapsed={elapsed:.1f}s"
    )
    return result


# ============================================================================
# Step 3: 正式训练 + 评估 + 导出 + 模型卡片
# ============================================================================
def run_formal_pipeline(
    model_name: str,
    cfg: ExperimentConfig,
    full_splits: dict[str, list[FER2013Sample]],
) -> dict[str, Any]:
    """对单个模型跑正式训练 + 评估 + 导出 + 模型卡片。"""
    _log(f"=== 正式训练: {model_name} ===")
    out_dir = Path(cfg.output_dir)
    if out_dir.exists():
        # 保留已有产物？为避免混淆，正式训练前清空目标目录。
        # 但如果用户中断后重跑，可能会丢失已有产物；这里选择清空以保证干净。
        _log(f"  清空已有产物目录: {out_dir}")
        shutil.rmtree(out_dir, ignore_errors=True)
    ensure_dir(out_dir)

    datasets = _build_datasets_from_samples(full_splits, cfg)

    # ---- 训练 ----
    t0 = time.time()
    training_summary = run_train(cfg, datasets)
    train_elapsed = time.time() - t0
    _log(
        f"  训练完成: epochs_run={training_summary.get('epochs_run')}, "
        f"best_epoch={training_summary.get('best_epoch')}, "
        f"best_metric={training_summary.get('best_metric')}, "
        f"elapsed={train_elapsed:.1f}s"
    )

    # 附带划分信息到 training_summary.json
    training_summary["split_method"] = "official_usage"
    training_summary["split_note"] = (
        "FER2013 image_dir 格式：train 目录 90% 划为 train、10% 划为 val（分层随机，"
        "seed=42），test 目录完全不参与训练/调参/模型选择。三个模型复用同一固定划分"
        "（见 artifacts/split_manifest.json）。"
    )
    write_json(out_dir / "training_summary.json", training_summary)

    # ---- 评估（test 上只评估一次）----
    _log(f"  在 test 上评估 best_checkpoint...")
    eval_summary = run_evaluation(cfg, out_dir / "best_model.pt", datasets, split="test")
    metrics = read_json(out_dir / "metrics.json")
    _log(
        f"  评估完成: accuracy={eval_summary.get('accuracy'):.4f}, "
        f"macro_f1={eval_summary.get('macro_f1'):.4f}, "
        f"num_samples={eval_summary.get('num_samples')}"
    )

    # ---- 导出 ----
    _log(f"  导出 ONNX / labels / preprocess...")
    labels_info = export_labels_json(out_dir / "labels.json")
    preprocess_info = export_preprocess_json(out_dir / "preprocess.json", cfg.input)
    onnx_path = out_dir / "model.onnx"
    onnx_info = export_onnx(cfg, out_dir / "best_model.pt", onnx_path)
    _log(f"  ONNX 导出完成: {onnx_info.get('size')}")

    # TFLite（环境不支持时跳过并记录）。
    tflite_path = out_dir / "model.tflite"
    tflite_info = export_tflite(onnx_path, tflite_path)
    if tflite_info.get("status") != "ok":
        _log(f"  TFLite 跳过: {tflite_info.get('error', 'unknown')}")

    # 一致性测试。
    tfl_arg = tflite_path if tflite_info.get("status") == "ok" else None
    consistency = run_consistency_test(cfg, out_dir / "best_model.pt", onnx_path, tfl_arg)
    _log(
        f"  一致性测试: passed={consistency.get('passed')}, "
        f"mismatch={consistency.get('total_top1_mismatch')}"
    )

    export_summary = {
        "labels": labels_info,
        "preprocess": preprocess_info,
        "checkpoint": str(out_dir / "best_model.pt"),
        "onnx": onnx_info,
        "tflite": tflite_info,
        "consistency": consistency,
    }
    write_json(out_dir / "export_summary.json", export_summary)

    # ---- 模型卡片 ----
    _log(f"  生成 model_card.json...")
    extra = {
        "train_elapsed_sec": train_elapsed,
        "smoke_per_class": SMOKE_PER_CLASS,
        "split_manifest_path": str(MANIFEST_PATH),
    }
    card = export_model_card(
        cfg=cfg,
        card_path=out_dir / "model_card.json",
        training_summary=training_summary,
        evaluate_summary=eval_summary,
        metrics=metrics,
        export_summary=export_summary,
        consistency=consistency,
        extra=extra,
    )
    _log(f"  模型卡片已保存: {out_dir / 'model_card.json'}")

    return {
        "model_name": model_name,
        "ok": True,
        "train_elapsed_sec": train_elapsed,
        "training_summary": training_summary,
        "evaluate_summary": eval_summary,
        "metrics": metrics,
        "export_summary": export_summary,
        "consistency": consistency,
        "model_card": card,
        "output_dir": str(out_dir),
    }


# ============================================================================
# 主流程
# ============================================================================
def main() -> int:
    parser = argparse.ArgumentParser(
        description="FER2013 正式训练驱动脚本（smoke + 正式训练 + 评估 + 导出 + 模型卡片）"
    )
    parser.add_argument(
        "--skip-smoke", action="store_true",
        help="跳过 smoke 阶段（默认 False）。仅在已确认链路正常时使用。",
    )
    parser.add_argument(
        "--only", default=None,
        help="只训练指定模型（custom_cnn / mobilenet_v3_small / resnet18），默认全部。",
    )
    args = parser.parse_args()

    _log("=" * 70)
    _log("FER2013 正式训练流程启动")
    _log(f"  产物根目录: {ARTIFACTS_DIR}")
    _log(f"  模型顺序: {[m for m, _ in MODEL_CONFIGS]}")
    _log("=" * 70)

    # 加载所有配置。
    configs: dict[str, ExperimentConfig] = {}
    for name, path in MODEL_CONFIGS:
        if not path.exists():
            _log(f"ERROR: 配置文件不存在: {path}")
            return 2
        configs[name] = _load_cfg(path)
        _log(f"已加载配置: {name} <- {path}")

    # 选择要训练的模型。
    target_models = list(configs.keys())
    if args.only:
        if args.only not in configs:
            _log(f"ERROR: --only={args.only} 不在可用模型中: {list(configs.keys())}")
            return 2
        target_models = [args.only]

    # Step 1: 数据划分清单（用第一个模型配置作为参考，data 配置都相同）。
    reference_cfg = configs[target_models[0]]
    manifest = prepare_split_manifest(reference_cfg)
    full_splits = load_splits_from_manifest(manifest)

    # Step 2: Smoke training（除非 --skip-smoke）。
    if not args.skip_smoke:
        smoke_results: dict[str, Any] = {}
        for name in target_models:
            try:
                smoke_results[name] = run_smoke_training(name, configs[name], full_splits)
            except Exception as e:
                _log(f"ERROR: smoke 训练失败 [{name}]: {type(e).__name__}: {e}")
                traceback.print_exc()
                # smoke 失败属于硬错误，停止后续训练。
                return 3
            if not smoke_results[name].get("ok"):
                _log(f"ERROR: smoke 训练未产生 best_metric [{name}]")
                return 3
        write_json(ARTIFACTS_DIR / "smoke_summary.json", smoke_results)
        _log("所有模型 smoke 训练通过，进入正式训练阶段。")
    else:
        _log("已跳过 smoke 阶段（--skip-smoke）。")

    # Step 3: 正式训练（按顺序，不同时启动多个）。
    formal_results: dict[str, Any] = {}
    for name in target_models:
        try:
            formal_results[name] = run_formal_pipeline(name, configs[name], full_splits)
        except Exception as e:
            _log(f"ERROR: 正式训练失败 [{name}]: {type(e).__name__}: {e}")
            traceback.print_exc()
            formal_results[name] = {
                "model_name": name,
                "ok": False,
                "error": f"{type(e).__name__}: {e}",
                "traceback": traceback.format_exc(),
            }
            # 单个模型失败不阻塞其他模型，继续训练下一个（但记录失败）。

    # 汇总。
    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "artifacts_dir": str(ARTIFACTS_DIR),
        "split_manifest": str(MANIFEST_PATH),
        "smoke_per_class": SMOKE_PER_CLASS,
        "smoke_skipped": bool(args.skip_smoke),
        "models": {},
    }
    for name in target_models:
        r = formal_results.get(name, {})
        if r.get("ok"):
            ts = r.get("training_summary", {}) or {}
            es = r.get("evaluate_summary", {}) or {}
            summary["models"][name] = {
                "ok": True,
                "output_dir": r.get("output_dir"),
                "best_epoch": ts.get("best_epoch"),
                "best_val_macro_f1": ts.get("best_metric"),
                "test_accuracy": es.get("accuracy"),
                "test_macro_f1": es.get("macro_f1"),
                "test_num_samples": es.get("num_samples"),
                "train_elapsed_sec": r.get("train_elapsed_sec"),
                "param_counts": ts.get("param_counts"),
                "checkpoint_sha256": es.get("checkpoint_sha256"),
                "checkpoint_size": es.get("checkpoint_size"),
            }
        else:
            summary["models"][name] = {
                "ok": False,
                "error": r.get("error"),
            }
    write_json(SUMMARY_PATH, summary)
    _log(f"\n汇总已保存: {SUMMARY_PATH}")
    _log("\n=== 训练结果汇总 ===")
    for name in target_models:
        m = summary["models"].get(name, {})
        if m.get("ok"):
            _log(
                f"  {name}: best_epoch={m['best_epoch']}, "
                f"val_f1={m['best_val_macro_f1']:.4f}, "
                f"test_acc={m['test_accuracy']:.4f}, "
                f"test_f1={m['test_macro_f1']:.4f}"
            )
        else:
            _log(f"  {name}: FAILED ({m.get('error')})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
