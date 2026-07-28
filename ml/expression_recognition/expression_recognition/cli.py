"""命令行入口。

子命令：
- prepare_data：解析并划分数据集，输出 split 摘要。
- train：训练模型。
- evaluate：在测试集上评估，输出指标/CSV/混淆矩阵。
- export：导出 PyTorch/ONNX/TFLite + labels.json + preprocess.json + 一致性测试。
- benchmark：单张 CPU 推理延迟、参数量、模型大小。
- run_all：依次执行上述全流程。

用法示例：
    python -m expression_recognition.cli --config experiment_config.yaml prepare_data
    python -m expression_recognition.cli --config experiment_config.yaml train
    python -m expression_recognition.cli --config experiment_config.yaml run_all

注意：数据集缺失时给出明确错误，不自动下载。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .config import ExperimentConfig
from .constants import EXPRESSION_LABELS
from .data import load_samples, split_samples
from .data.transforms import build_train_transform, build_eval_transform
from .data.fer2013 import build_torch_datasets
from .utils.io import write_json, ensure_dir


def _load_config(args) -> ExperimentConfig:
    cfg = ExperimentConfig.from_yaml(args.config)
    cfg.validate()
    # 命令行参数覆盖配置。
    if getattr(args, "dataset_root", None):
        cfg.data.dataset_root = args.dataset_root
    if getattr(args, "output_dir", None):
        cfg.output_dir = args.output_dir
    return cfg


def _prepare_splits(cfg: ExperimentConfig) -> dict[str, Any]:
    """加载数据并划分，返回 torch Dataset 字典 + 原始 split 结果。"""
    if not cfg.data.dataset_root:
        raise SystemExit(
            "未配置 data.dataset_root。请在 experiment_config.yaml 中设置，\n"
            "或通过 --dataset-root 传入。本工程不自动下载数据集。"
        )
    samples = load_samples(cfg.data.dataset_root, cfg.data.format, cfg.data.csv_name)
    split_result = split_samples(
        samples,
        train_ratio=cfg.data.train_ratio,
        val_ratio=cfg.data.val_ratio,
        test_ratio=cfg.data.test_ratio,
        stratified=cfg.data.stratified,
        split_seed=cfg.data.split_seed,
    )
    # 构造变换。
    train_tfm = build_train_transform(cfg.augmentation, cfg.input, seed=cfg.train.seed)
    eval_tfm = build_eval_transform(cfg.input)
    datasets = build_torch_datasets(split_result.as_dict(), train_tfm, eval_tfm, cfg.input.channels)
    return {"datasets": datasets, "split_result": split_result}


def cmd_prepare_data(cfg: ExperimentConfig) -> dict[str, Any]:
    """解析并划分数据集，输出 split 摘要（不训练）。"""
    out_dir = ensure_dir(cfg.output_dir)
    if not cfg.data.dataset_root:
        raise SystemExit(
            "未配置 data.dataset_root。本工程不自动下载数据集，请手动放置 FER2013。"
        )
    samples = load_samples(cfg.data.dataset_root, cfg.data.format, cfg.data.csv_name)
    split_result = split_samples(
        samples,
        train_ratio=cfg.data.train_ratio,
        val_ratio=cfg.data.val_ratio,
        test_ratio=cfg.data.test_ratio,
        stratified=cfg.data.stratified,
        split_seed=cfg.data.split_seed,
    )
    counts = split_result.counts_by_split_label()
    summary = {
        "dataset_root": cfg.data.dataset_root,
        "format": cfg.data.format,
        "method": split_result.method,
        "note": split_result.note,
        "label_order": list(EXPRESSION_LABELS),
        "counts": {
            split: {
                "total": len(getattr(split_result, split)),
                "per_class": {EXPRESSION_LABELS[i]: counts[split].get(i, 0)
                              for i in range(len(EXPRESSION_LABELS))},
            }
            for split in ("train", "val", "test")
        },
    }
    write_json(out_dir / "data_split_summary.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def cmd_train(cfg: ExperimentConfig) -> dict[str, Any]:
    from .training.trainer import train

    prepared = _prepare_splits(cfg)
    summary = train(cfg, prepared["datasets"])
    # 附带数据划分信息。
    sr = prepared["split_result"]
    summary["split_method"] = sr.method
    summary["split_note"] = sr.note
    write_json(Path(cfg.output_dir) / "training_summary.json", summary)
    return summary


def cmd_evaluate(cfg: ExperimentConfig, split: str = "test") -> dict[str, Any]:
    from .evaluation.evaluate import run_evaluation

    prepared = _prepare_splits(cfg)
    ckpt = Path(cfg.output_dir) / "best_model.pt"
    if not ckpt.exists():
        raise SystemExit(f"检查点不存在: {ckpt}，请先训练。")
    return run_evaluation(cfg, ckpt, prepared["datasets"], split=split)


def cmd_export(cfg: ExperimentConfig) -> dict[str, Any]:
    from .export.onnx_export import export_onnx
    from .export.tflite_export import export_tflite
    from .export.labels import export_labels_json
    from .export.preprocess import export_preprocess_json
    from .export.consistency import run_consistency_test

    out_dir = ensure_dir(cfg.output_dir)
    ckpt = out_dir / "best_model.pt"
    if not ckpt.exists():
        raise SystemExit(f"检查点不存在: {ckpt}，请先训练。")

    # labels / preprocess 总是导出（不需要训练）。
    labels_info = export_labels_json(out_dir / "labels.json")
    preprocess_info = export_preprocess_json(out_dir / "preprocess.json", cfg.input)

    result: dict[str, Any] = {
        "labels": labels_info,
        "preprocess": preprocess_info,
        "checkpoint": str(ckpt),
    }

    # ONNX。
    onnx_path = out_dir / "model.onnx"
    if cfg.export.onnx:
        result["onnx"] = export_onnx(cfg, ckpt, onnx_path)

    # TFLite。
    tflite_path = out_dir / "model.tflite"
    if cfg.export.tflite:
        result["tflite"] = export_tflite(onnx_path, tflite_path)

    # 一致性测试（需要 ONNX；TFLite 可选）。
    if cfg.export.onnx:
        tfl_arg = tflite_path if result.get("tflite", {}).get("status") == "ok" else None
        result["consistency"] = run_consistency_test(cfg, ckpt, onnx_path, tfl_arg)

    write_json(out_dir / "export_summary.json", result)
    return result


def cmd_benchmark(cfg: ExperimentConfig) -> dict[str, Any]:
    from .benchmark.benchmark import run_benchmark

    out_dir = ensure_dir(cfg.output_dir)
    ckpt = out_dir / "best_model.pt"
    if not ckpt.exists():
        raise SystemExit(f"检查点不存在: {ckpt}，请先训练。")
    onnx_path = out_dir / "model.onnx" if (out_dir / "model.onnx").exists() else None
    tflite_path = out_dir / "model.tflite" if (out_dir / "model.tflite").exists() else None
    return run_benchmark(cfg, ckpt, onnx_path, tflite_path)


def cmd_run_all(cfg: ExperimentConfig) -> dict[str, Any]:
    """依次执行：prepare_data -> train -> evaluate -> export -> benchmark。"""
    out: dict[str, Any] = {}
    print("=== [1/5] prepare_data ===")
    out["prepare_data"] = cmd_prepare_data(cfg)
    print("=== [2/5] train ===")
    out["train"] = cmd_train(cfg)
    print("=== [3/5] evaluate ===")
    out["evaluate"] = cmd_evaluate(cfg, split="test")
    print("=== [4/5] export ===")
    out["export"] = cmd_export(cfg)
    print("=== [5/5] benchmark ===")
    out["benchmark"] = cmd_benchmark(cfg)
    write_json(Path(cfg.output_dir) / "run_all_summary.json", out)
    print(f"\n全流程完成。结果目录: {cfg.output_dir}")
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="expression_recognition",
        description="CampusMateAI CNN 面部表情识别训练与评估工程。",
    )
    p.add_argument(
        "--config", default="experiment_config.yaml",
        help="实验配置 YAML 路径（默认 experiment_config.yaml）。",
    )
    p.add_argument("--dataset-root", default=None, help="覆盖 data.dataset_root。")
    p.add_argument("--output-dir", default=None, help="覆盖 output_dir。")

    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("prepare_data", help="解析并划分数据集，输出 split 摘要。")
    sub.add_parser("train", help="训练模型。")

    p_eval = sub.add_parser("evaluate", help="在 split 上评估。")
    p_eval.add_argument("--split", default="test", choices=["train", "val", "test"],
                        help="评估的 split（默认 test）。")

    sub.add_parser("export", help="导出 PyTorch/ONNX/TFLite + labels/preprocess + 一致性。")
    sub.add_parser("benchmark", help="单张 CPU 推理延迟、参数量、大小。")
    sub.add_parser("run_all", help="依次执行全流程。")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = _load_config(args)

    if args.command == "prepare_data":
        cmd_prepare_data(cfg)
    elif args.command == "train":
        cmd_train(cfg)
    elif args.command == "evaluate":
        cmd_evaluate(cfg, split=args.split)
    elif args.command == "export":
        cmd_export(cfg)
    elif args.command == "benchmark":
        cmd_benchmark(cfg)
    elif args.command == "run_all":
        cmd_run_all(cfg)
    else:  # pragma: no cover
        parser.print_help()
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
