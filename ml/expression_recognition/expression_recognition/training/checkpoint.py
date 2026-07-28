"""检查点保存与加载。

保存内容：模型 state_dict、优化器 state_dict、调度器 state_dict、
epoch、最佳指标、配置快照、标签顺序。
加载时校验标签顺序与 num_classes 一致，防止模型与标签错位。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import torch

from ..constants import EXPRESSION_LABELS, NUM_CLASSES
from ..utils.io import write_json, read_json

BEST_FILENAME = "best_model.pt"
LAST_FILENAME = "last_model.pt"


def save_checkpoint(
    path: str | Path,
    model: torch.nn.Module,
    optimizer: torch.optim.Optimizer | None = None,
    scheduler: Any | None = None,
    epoch: int = 0,
    best_metric: float | None = None,
    metric_name: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """保存检查点。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "model_state": model.state_dict(),
        "epoch": int(epoch),
        "label_order": list(EXPRESSION_LABELS),
        "num_classes": NUM_CLASSES,
        "best_metric": best_metric,
        "metric_name": metric_name,
    }
    if optimizer is not None:
        state["optimizer_state"] = optimizer.state_dict()
    if scheduler is not None:
        state["scheduler_state"] = scheduler.state_dict()
    if extra:
        state["extra"] = extra
    torch.save(state, path)


def load_checkpoint(
    path: str | Path,
    model: torch.nn.Module,
    optimizer: torch.optim.Optimizer | None = None,
    scheduler: Any | None = None,
    map_location: Any = "cpu",
) -> dict[str, Any]:
    """加载检查点到模型/优化器/调度器。

    返回检查点中的元信息（epoch、best_metric 等）。
    会校验 label_order 与 num_classes，不一致则报错。
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"检查点不存在: {path}")
    state = torch.load(path, map_location=map_location, weights_only=False)

    saved_labels = state.get("label_order")
    if saved_labels is not None and list(saved_labels) != list(EXPRESSION_LABELS):
        raise ValueError(
            "检查点标签顺序与当前工程契约不一致，拒绝加载。\n"
            f"检查点: {saved_labels}\n当前契约: {list(EXPRESSION_LABELS)}"
        )
    saved_nc = state.get("num_classes")
    if saved_nc is not None and saved_nc != NUM_CLASSES:
        raise ValueError(
            f"检查点 num_classes={saved_nc}，与当前 {NUM_CLASSES} 不一致。"
        )

    model.load_state_dict(state["model_state"])
    if optimizer is not None and "optimizer_state" in state:
        optimizer.load_state_dict(state["optimizer_state"])
    if scheduler is not None and "scheduler_state" in state:
        scheduler.load_state_dict(state["scheduler_state"])
    return {
        "epoch": state.get("epoch", 0),
        "best_metric": state.get("best_metric"),
        "metric_name": state.get("metric_name"),
        "extra": state.get("extra"),
    }


def save_metrics_json(path: str | Path, metrics: dict[str, Any]) -> None:
    """保存指标为 JSON。"""
    write_json(path, metrics)


def load_metrics_json(path: str | Path) -> dict[str, Any]:
    """读取指标 JSON。"""
    return read_json(path)
