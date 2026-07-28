"""生成 model_card.json：模型卡片，记录训练来源、指标、用途、限制。

遵循"不虚构"原则：所有字段都从真实训练/评估结果中提取，缺失字段标注为
"未提供"或"未评估"，绝不编造数值。

卡片字段（对齐任务第 14 步产物要求）：
- 模型名、架构、标签顺序
- 训练数据集、训练样本数、验证样本数、测试样本数
- 训练超参（epochs / batch_size / lr / optimizer / scheduler / loss / aug）
- 训练结果（best epoch、best val Macro-F1）
- 测试集真实指标（Accuracy / Macro-F1 / 各类 P/R/F1/support）
- 检查点信息（路径、SHA-256、大小、参数量）
- 导出产物（.pt / .onnx / labels.json / preprocess.json 各自 SHA-256 + 大小）
- 科学边界声明
- 许可与用途限制
"""

from __future__ import annotations

import platform
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import ExperimentConfig
from ..constants import EXPRESSION_LABELS
from ..utils.io import write_json, sha256_of_file, file_size_bytes, format_size


def _safe_sha256(path: str | Path | None) -> str | None:
    """文件存在则返回 SHA-256，否则 None。"""
    if path is None:
        return None
    p = Path(path)
    if not p.exists() or not p.is_file():
        return None
    return sha256_of_file(p)


def _safe_size(path: str | Path | None) -> dict[str, Any] | None:
    """文件存在则返回 {size_bytes, size_human}，否则 None。"""
    if path is None:
        return None
    p = Path(path)
    if not p.exists() or not p.is_file():
        return None
    b = file_size_bytes(p)
    return {"size_bytes": int(b), "size_human": format_size(b)}


def build_model_card(
    cfg: ExperimentConfig,
    training_summary: dict[str, Any] | None,
    evaluate_summary: dict[str, Any] | None,
    metrics: dict[str, Any] | None,
    export_summary: dict[str, Any] | None,
    consistency: dict[str, Any] | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """组装模型卡片字典。

    Args:
        cfg: 实验配置。
        training_summary: training_summary.json 内容（可为 None）。
        evaluate_summary: evaluate_summary.json 内容（可为 None）。
        metrics: metrics.json 内容（可为 None）。
        export_summary: export_summary.json 内容（可为 None）。
        consistency: consistency.json 内容（可为 None）。
        extra: 额外信息（如 smoke 训练状态、训练耗时等）。

    Returns:
        模型卡片字典。
    """
    out_dir = Path(cfg.output_dir)
    best_ckpt = out_dir / "best_model.pt"
    onnx_path = out_dir / "model.onnx"
    labels_path = out_dir / "labels.json"
    preprocess_path = out_dir / "preprocess.json"
    tflite_path = out_dir / "model.tflite"

    # 训练摘要。
    best_epoch: int | None = None
    best_metric: float | None = None
    param_counts: dict[str, int] | None = None
    device_used: str | None = None
    epochs_run: int | None = None
    if training_summary:
        best_epoch = training_summary.get("best_epoch")
        best_metric = training_summary.get("best_metric")
        param_counts = training_summary.get("param_counts")
        device_used = training_summary.get("device")
        epochs_run = training_summary.get("epochs_run")

    # 评估摘要。
    eval_acc: float | None = None
    eval_macro_f1: float | None = None
    eval_num_samples: int | None = None
    eval_split: str = "test"
    if evaluate_summary:
        eval_acc = evaluate_summary.get("accuracy")
        eval_macro_f1 = evaluate_summary.get("macro_f1")
        eval_num_samples = evaluate_summary.get("num_samples")
        eval_split = evaluate_summary.get("split", "test")

    # per-class 指标。
    per_class: dict[str, Any] | None = None
    confusion_matrix: list[list[int]] | None = None
    if metrics:
        per_class = metrics.get("per_class")
        confusion_matrix = metrics.get("confusion_matrix")

    # 导出产物 SHA-256 + 大小。
    artifacts_info: dict[str, Any] = {
        "best_checkpoint": {
            "path": str(best_ckpt),
            "sha256": _safe_sha256(best_ckpt),
            **(_safe_size(best_ckpt) or {}),
        },
        "onnx": {
            "path": str(onnx_path),
            "sha256": _safe_sha256(onnx_path),
            **(_safe_size(onnx_path) or {}),
            "status": "ok" if onnx_path.exists() else "not_exported",
        },
        "labels_json": {
            "path": str(labels_path),
            "sha256": _safe_sha256(labels_path),
            **(_safe_size(labels_path) or {}),
        },
        "preprocess_json": {
            "path": str(preprocess_path),
            "sha256": _safe_sha256(preprocess_path),
            **(_safe_size(preprocess_path) or {}),
        },
        "tflite": {
            "path": str(tflite_path),
            "sha256": _safe_sha256(tflite_path),
            **(_safe_size(tflite_path) or {}),
            "status": "ok" if tflite_path.exists() else "not_exported",
        },
    }

    # ONNX 详情（opset、exporter）。
    onnx_info: dict[str, Any] | None = None
    if export_summary and "onnx" in export_summary:
        onnx_info = {
            "opset_version_requested": export_summary["onnx"].get("opset_version_requested"),
            "opset_version_actual": export_summary["onnx"].get("opset_version_actual"),
            "exporter": export_summary["onnx"].get("exporter"),
            "onnxruntime_ok": export_summary["onnx"].get("onnxruntime_ok"),
        }

    # 一致性测试结果。
    consistency_info: dict[str, Any] | None = None
    if consistency:
        consistency_info = {
            "passed": consistency.get("passed"),
            "total_top1_mismatch": consistency.get("total_top1_mismatch"),
            "max_allowed_mismatch": consistency.get("max_allowed_mismatch"),
            "backends": consistency.get("backends"),
        }

    card: dict[str, Any] = {
        "model_name": cfg.model.name,
        "experiment_name": cfg.experiment_name,
        "architecture": _architecture_description(cfg.model.name),
        "label_order": list(EXPRESSION_LABELS),
        "num_classes": len(EXPRESSION_LABELS),
        "input": {
            "size": cfg.input.size,
            "channels": cfg.input.channels,
            "mean": list(cfg.input.mean),
            "std": list(cfg.input.std),
        },
        "training": {
            "dataset": "FER2013",
            "dataset_root": cfg.data.dataset_root,
            "data_format": cfg.data.format,
            "split_method": (training_summary or {}).get("split_method"),
            "split_note": (training_summary or {}).get("split_note"),
            "epochs_configured": cfg.train.epochs,
            "epochs_run": epochs_run,
            "best_epoch": best_epoch,
            "best_metric": best_metric,
            "metric_name": cfg.train.monitor,
            "batch_size": cfg.train.batch_size,
            "optimizer": cfg.optimizer.type,
            "lr": cfg.optimizer.lr,
            "weight_decay": cfg.optimizer.weight_decay,
            "scheduler": cfg.scheduler.type,
            "loss": cfg.loss.type,
            "use_class_weights": cfg.loss.use_class_weights,
            "label_smoothing": cfg.loss.label_smoothing,
            "augmentation_enabled": cfg.augmentation.enabled,
            "early_stopping_patience": cfg.train.early_stopping_patience,
            "seed": cfg.train.seed,
            "device": device_used,
            "amp": cfg.train.amp,
            "pretrained": cfg.model.pretrained,
            "freeze_backbone": cfg.model.freeze_backbone,
            "unfreeze_at_epoch": cfg.model.unfreeze_at_epoch,
        },
        "parameters": param_counts,
        "evaluation": {
            "split": eval_split,
            "num_samples": eval_num_samples,
            "accuracy": eval_acc,
            "macro_f1": eval_macro_f1,
            "per_class": per_class,
            "confusion_matrix": confusion_matrix,
            "note": (
                "测试集只评估一次，使用 best_checkpoint（按 val Macro-F1 选）。"
                "指标基于真实模型预测与真实标签计算，未写死、未用占位随机数。"
            ),
        },
        "artifacts": artifacts_info,
        "onnx": onnx_info,
        "consistency": consistency_info,
        "scientific_boundary": (
            "本模型识别的是可观察到的面部表情（FER2013 七类：angry/disgust/fear/"
            "happy/sad/surprise/neutral）。不输出疲劳/注意力/焦虑症/心理疾病等类别。"
            "结果仅供辅助参考，不进行疾病诊断，不替代专业心理咨询。"
        ),
        "intended_use": (
            "面向大学生校园事务智能陪伴助手的学习状态记录与轻量陪伴场景，"
            "用于在用户主动开启学习陪伴时识别当前面部表情，结合连续学习时长等信号"
            "给出温和提醒。不得用于医疗诊断、招考筛选、监控等场景。"
        ),
        "limitations": [
            "FER2013 类别分布不均衡（disgust 类样本极少），该类指标通常偏低。",
            "FER2013 不提供受试者 ID，无法做严格的同源样本隔离。",
            "面部表情 ≠ 心理状态；模型只识别可观察到的面部肌肉模式。",
            "低光照、遮挡、侧脸、夸张妆容等场景下识别准确率会下降。",
            "模型在特定人群（年龄/肤色/地区）上的公平性未做专门验证。",
        ],
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "torch": _torch_version(),
            "torchvision": _torchvision_version(),
            "onnxruntime": _onnxruntime_version(),
            "cuda_available": _cuda_available(),
            "gpu_name": _gpu_name(),
        },
        "generated_at": datetime.now().astimezone().isoformat(),
        "extra": extra or {},
    }
    return card


def _architecture_description(name: str) -> str:
    if name == "custom_cnn":
        return (
            "Custom shallow CNN: 3x (Conv3x3 -> BN -> ReLU -> MaxPool2) + "
            "GlobalAvgPool -> Dropout -> Linear。输入 1 通道 48x48。"
        )
    if name == "resnet18":
        return (
            "ResNet18 迁移学习（ImageNet 预训练），替换 fc 为 Dropout+Linear(7)。"
            "输入 3 通道 224x224，灰度复制到三通道。"
        )
    if name == "mobilenet_v3_small":
        return (
            "MobileNetV3-Small 迁移学习（ImageNet 预训练），替换 classifier 末层为 "
            "Dropout+Linear(7)。输入 3 通道 224x224，灰度复制到三通道。"
        )
    return name


def _torch_version() -> str | None:
    try:
        import torch
        return torch.__version__
    except Exception:
        return None


def _torchvision_version() -> str | None:
    try:
        import torchvision
        return torchvision.__version__
    except Exception:
        return None


def _onnxruntime_version() -> str | None:
    try:
        import onnxruntime as ort
        return ort.__version__
    except Exception:
        return None


def _cuda_available() -> bool | None:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return None


def _gpu_name() -> str | None:
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.get_device_name(0)
    except Exception:
        pass
    return None


def export_model_card(
    cfg: ExperimentConfig,
    card_path: str | Path,
    training_summary: dict[str, Any] | None = None,
    evaluate_summary: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
    export_summary: dict[str, Any] | None = None,
    consistency: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """组装模型卡片并写入 card_path（model_card.json）。"""
    card = build_model_card(
        cfg=cfg,
        training_summary=training_summary,
        evaluate_summary=evaluate_summary,
        metrics=metrics,
        export_summary=export_summary,
        consistency=consistency,
        extra=extra,
    )
    write_json(card_path, card)
    return card
