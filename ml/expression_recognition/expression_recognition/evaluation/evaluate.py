"""评估脚本：加载检查点 -> 测试集预测 -> 写指标/CSV/混淆矩阵图。

输出文件（写到 cfg.output_dir）：
- metrics.json：完整指标（accuracy/macro_f1/per_class/confusion_matrix/...）
- per_class_metrics.csv：每类 P/R/F1/support
- confusion_matrix.png：混淆矩阵图（matplotlib 不可用时跳过并记录）
- evaluate_summary.json：评估元信息（数据集数量、检查点 SHA-256 等）

禁止：写死指标、用占位随机数、把训练集结果冒充测试集结果。
本脚本默认评估测试集；如评估训练集，会在 summary 中明确标注。
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader

from ..config import ExperimentConfig
from ..constants import EXPRESSION_LABELS
from ..models.build import build_model, count_parameters
from ..utils.io import ensure_dir, write_json, sha256_of_file, file_size_bytes, format_size
from .metrics import compute_metrics


@torch.no_grad()
def run_evaluation(
    cfg: ExperimentConfig,
    checkpoint_path: str | Path,
    datasets: dict[str, Any],
    split: str = "test",
) -> dict[str, Any]:
    """在指定 split 上评估模型并写出报告文件。

    Args:
        cfg: 实验配置。
        checkpoint_path: 检查点路径。
        datasets: torch Dataset 字典。
        split: 评估的 split 名（test / val / train）。

    Returns:
        评估结果字典。
    """
    if split not in datasets:
        raise ValueError(f"split={split} 不在 datasets 中，可用: {list(datasets)}")
    out_dir = ensure_dir(cfg.output_dir)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # 重建模型并加载权重。
    model = build_model(cfg.model, cfg.input).to(device)
    state = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(state["model_state"])
    model.eval()

    loader = DataLoader(
        datasets[split], batch_size=cfg.train.batch_size, shuffle=False,
        num_workers=cfg.train.num_workers,
    )

    all_preds: list[np.ndarray] = []
    all_targets: list[np.ndarray] = []
    for batch in loader:
        x, y = batch
        x = x.to(device, non_blocking=True)
        logits = model(x)
        preds = logits.argmax(dim=1).cpu().numpy()
        all_preds.append(preds)
        all_targets.append(np.asarray(y).ravel())
    preds = np.concatenate(all_preds)
    targets = np.concatenate(all_targets)

    # 真实计算指标。
    metrics = compute_metrics(targets, preds, label_names=list(EXPRESSION_LABELS))

    # 写 metrics.json。
    write_json(out_dir / "metrics.json", metrics)

    # 写 per_class_metrics.csv。
    per_class_path = out_dir / "per_class_metrics.csv"
    with per_class_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["label", "precision", "recall", "f1", "support"])
        for name in EXPRESSION_LABELS:
            pc = metrics["per_class"][name]
            writer.writerow([name, pc["precision"], pc["recall"], pc["f1"], pc["support"]])

    # 混淆矩阵图（matplotlib 不可用时跳过）。
    cm_path = out_dir / "confusion_matrix.png"
    cm_plot_error: str | None = None
    try:
        import matplotlib
        matplotlib.use("Agg")  # 非交互后端，无需显示。
        import matplotlib.pyplot as plt

        cm = np.asarray(metrics["confusion_matrix"])
        fig, ax = plt.subplots(figsize=(6, 6))
        im = ax.imshow(cm, cmap="Blues")
        ax.set_xticks(range(len(EXPRESSION_LABELS)))
        ax.set_yticks(range(len(EXPRESSION_LABELS)))
        ax.set_xticklabels(EXPRESSION_LABELS, rotation=45, ha="right")
        ax.set_yticklabels(EXPRESSION_LABELS)
        ax.set_xlabel("Predicted")
        ax.set_ylabel("True")
        ax.set_title(f"Confusion Matrix ({split})")
        # 在格子里写数字。
        thresh = cm.max() / 2.0 if cm.max() > 0 else 0.0
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                ax.text(j, i, str(int(cm[i, j])), ha="center", va="center",
                        color="white" if cm[i, j] > thresh else "black", fontsize=8)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        fig.tight_layout()
        fig.savefig(cm_path, dpi=150)
        plt.close(fig)
    except Exception as e:  # pragma: no cover - 视环境而定
        cm_plot_error = f"{type(e).__name__}: {e}"

    # 评估摘要。
    cp_sha = sha256_of_file(checkpoint_path)
    cp_size = file_size_bytes(checkpoint_path)
    summary = {
        "experiment_name": cfg.experiment_name,
        "model_name": cfg.model.name,
        "split": split,
        "checkpoint": str(checkpoint_path),
        "checkpoint_sha256": cp_sha,
        "checkpoint_size": format_size(cp_size),
        "checkpoint_size_bytes": cp_size,
        "num_samples": int(metrics["num_samples"]),
        "accuracy": metrics["accuracy"],
        "macro_f1": metrics["macro_f1"],
        "param_counts": count_parameters(model),
        "confusion_matrix_png": str(cm_path) if cm_plot_error is None else None,
        "confusion_matrix_plot_error": cm_plot_error,
        "per_class_csv": str(per_class_path),
        "metrics_json": str(out_dir / "metrics.json"),
        "label_order": list(EXPRESSION_LABELS),
        "note": (
            "所有指标基于真实模型预测与真实标签计算，未写死、未用占位随机数。"
            f"评估 split: {split}。"
            + ("（注意：评估的是训练集，不能作为泛化指标。）" if split == "train" else "")
        ),
    }
    write_json(out_dir / "evaluate_summary.json", summary)
    return summary
