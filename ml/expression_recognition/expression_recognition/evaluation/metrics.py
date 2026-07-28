"""分类指标：用纯 numpy 实现，不依赖 sklearn。

实现：
- accuracy
- macro_f1（宏平均 F1）
- per_class_precision_recall（各类 Precision / Recall / F1 / Support）
- confusion_matrix（混淆矩阵）

禁止：写死指标、用占位随机数。所有指标必须基于真实预测与标签计算。
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from ..constants import EXPRESSION_LABELS, NUM_CLASSES


def _check_inputs(targets: Sequence[int], preds: Sequence[int]) -> tuple[np.ndarray, np.ndarray]:
    t = np.asarray(targets, dtype=np.int64).ravel()
    p = np.asarray(preds, dtype=np.int64).ravel()
    if t.shape != p.shape:
        raise ValueError(
            f"targets 与 preds 形状不一致: {t.shape} vs {p.shape}"
        )
    if t.size == 0:
        raise ValueError("targets/preds 为空，无法计算指标。")
    if t.min() < 0 or t.max() >= NUM_CLASSES:
        raise ValueError(
            f"target 标签越界: [{t.min()}, {t.max()}]，合法范围 0..{NUM_CLASSES - 1}"
        )
    if p.min() < 0 or p.max() >= NUM_CLASSES:
        raise ValueError(
            f"pred 标签越界: [{p.min()}, {p.max()}，合法范围 0..{NUM_CLASSES - 1}"
        )
    return t, p


def accuracy(targets: Sequence[int], preds: Sequence[int]) -> float:
    """准确率。"""
    t, p = _check_inputs(targets, preds)
    return float((t == p).mean())


def confusion_matrix(
    targets: Sequence[int], preds: Sequence[int], num_classes: int = NUM_CLASSES
) -> np.ndarray:
    """混淆矩阵，行=真实，列=预测。"""
    t, p = _check_inputs(targets, preds)
    cm = np.zeros((num_classes, num_classes), dtype=np.int64)
    for ti, pi in zip(t, p):
        cm[ti, pi] += 1
    return cm


def per_class_precision_recall(
    targets: Sequence[int], preds: Sequence[int], num_classes: int = NUM_CLASSES
) -> dict[int, dict[str, float]]:
    """各类 Precision / Recall / F1 / Support。

    Precision_i = TP_i / (TP_i + FP_i)
    Recall_i    = TP_i / (TP_i + FN_i)
    F1_i        = 2 * P * R / (P + R)  （P+R=0 时记 0）
    Support_i   = 真实为 i 的样本数
    """
    cm = confusion_matrix(targets, preds, num_classes)
    out: dict[int, dict[str, float]] = {}
    for i in range(num_classes):
        tp = int(cm[i, i])
        fp = int(cm[:, i].sum() - tp)
        fn = int(cm[i, :].sum() - tp)
        support = int(cm[i, :].sum())
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        out[i] = {
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "support": support,
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }
    return out


def macro_f1(targets: Sequence[int], preds: Sequence[int], num_classes: int = NUM_CLASSES) -> float:
    """宏平均 F1（各类 F1 的算术平均）。"""
    pc = per_class_precision_recall(targets, preds, num_classes)
    f1s = [pc[i]["f1"] for i in range(num_classes)]
    return float(np.mean(f1s))


def compute_metrics(
    targets: Sequence[int],
    preds: Sequence[int],
    label_names: Sequence[str] = EXPRESSION_LABELS,
    num_classes: int = NUM_CLASSES,
) -> dict[str, object]:
    """一次性计算全部指标，返回结构化字典。

    返回结构：
    {
        "accuracy": float,
        "macro_f1": float,
        "label_order": [...],
        "per_class": {label_name: {precision, recall, f1, support, tp, fp, fn}},
        "confusion_matrix": [[...], ...],  # 行=真实，列=预测
        "num_samples": int,
    }
    """
    if list(label_names) != list(EXPRESSION_LABELS):
        from ..constants import assert_label_order

        assert_label_order(list(label_names))

    t, p = _check_inputs(targets, preds)
    cm = confusion_matrix(t, p, num_classes)
    pc = per_class_precision_recall(t, p, num_classes)
    label_names = list(label_names)

    per_class_named: dict[str, dict[str, float]] = {}
    for i, name in enumerate(label_names):
        per_class_named[name] = pc[i]

    return {
        "accuracy": accuracy(t, p),
        "macro_f1": macro_f1(t, p, num_classes),
        "label_order": label_names,
        "per_class": per_class_named,
        "confusion_matrix": cm.tolist(),
        "num_samples": int(t.size),
    }
