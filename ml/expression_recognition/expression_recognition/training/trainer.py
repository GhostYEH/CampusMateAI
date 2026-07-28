"""训练循环：串联模型、损失、优化器、调度器、早停、检查点、冻结/解冻。

设计要点：
- 每轮训练后评估验证集，计算 Macro-F1 等，按 monitor 指标保存最佳检查点。
- 支持 backbone 冻结 + 逐步解冻（达到 unfreeze_at_epoch 后解冻并切换到 unfreeze_lr）。
- 支持梯度裁剪、AMP（CUDA 时）。
- 每轮写一行 training_history.csv，便于后续绘图与复现。
- 完成后保存 last 检查点与训练历史 CSV。

注意：本模块只在有 torch 时可用。
"""

from __future__ import annotations

import csv
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader

from ..config import ExperimentConfig
from ..constants import EXPRESSION_LABELS, NUM_CLASSES
from ..evaluation.metrics import compute_metrics
from ..models.build import (
    build_model,
    count_parameters,
    freeze_model_backbone,
    unfreeze_model_backbone,
)
from ..utils.io import write_json, ensure_dir
from ..utils.seed import set_seed
from .checkpoint import (
    BEST_FILENAME,
    LAST_FILENAME,
    save_checkpoint,
)
from .early_stopping import EarlyStopping
from .losses import build_loss, compute_class_weights
from .scheduler import build_scheduler


def _move(batch, device):
    x, y = batch
    return x.to(device, non_blocking=True), y.to(device, non_blocking=True)


@torch.no_grad()
def evaluate_model(
    model: torch.nn.Module,
    loader: DataLoader,
    device: torch.device,
) -> dict[str, Any]:
    """在给定 loader 上评估，返回指标字典。"""
    model.eval()
    all_preds: list[np.ndarray] = []
    all_targets: list[np.ndarray] = []
    total_loss = 0.0
    n = 0
    # 评估时损失用普通 CE（无权重/平滑），便于横向比较。
    ce = torch.nn.CrossEntropyLoss()
    for batch in loader:
        x, y = _move(batch, device)
        logits = model(x)
        loss = ce(logits, y)
        bs = y.size(0)
        total_loss += float(loss.item()) * bs
        n += bs
        preds = logits.argmax(dim=1).cpu().numpy()
        all_preds.append(preds)
        all_targets.append(y.cpu().numpy())
    preds = np.concatenate(all_preds)
    targets = np.concatenate(all_targets)
    metrics = compute_metrics(targets, preds, label_names=list(EXPRESSION_LABELS))
    metrics["loss"] = total_loss / max(1, n)
    return metrics


def _build_optimizer(cfg: ExperimentConfig, model: torch.nn.Module, lr: float) -> torch.optim.Optimizer:
    """根据配置构造优化器。"""
    params = [p for p in model.parameters() if p.requires_grad]
    if cfg.optimizer.type == "adamw":
        return torch.optim.AdamW(params, lr=lr, weight_decay=cfg.optimizer.weight_decay)
    if cfg.optimizer.type == "sgd":
        return torch.optim.SGD(
            params, lr=lr, momentum=cfg.optimizer.momentum,
            weight_decay=cfg.optimizer.weight_decay,
        )
    raise ValueError(f"未知 optimizer.type: {cfg.optimizer.type}")


def train(cfg: ExperimentConfig, splits: dict[str, Any]) -> dict[str, Any]:
    """执行训练。

    Args:
        cfg: 实验配置。
        splits: torch Dataset 字典 {"train":..., "val":..., "test":...}。

    Returns:
        训练结果字典（含 best_metric、history 路径、检查点路径等）。
    """
    set_seed(cfg.train.seed)

    out_dir = ensure_dir(cfg.output_dir)
    # 始终优先使用 CUDA（若有），AMP 仅决定是否启用混合精度，不影响设备选择。
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # AMP 仅在 CUDA + 配置开启时启用。
    amp = cfg.train.amp and device.type == "cuda"

    # 数据加载器。
    train_loader = DataLoader(
        splits["train"], batch_size=cfg.train.batch_size, shuffle=True,
        num_workers=cfg.train.num_workers, pin_memory=(device.type == "cuda"),
        drop_last=False,
    )
    val_loader = DataLoader(
        splits["val"], batch_size=cfg.train.batch_size, shuffle=False,
        num_workers=cfg.train.num_workers, pin_memory=(device.type == "cuda"),
    )

    # 模型。
    model = build_model(cfg.model, cfg.input).to(device)

    # 类别权重（基于训练集标签）。
    train_labels = [int(s.label) for s in splits["train"].samples]
    class_weights = compute_class_weights(train_labels, NUM_CLASSES).to(device)
    criterion = build_loss(cfg.loss, class_weights=class_weights).to(device)

    # 优化器与调度器。
    optimizer = _build_optimizer(cfg, model, cfg.optimizer.lr)
    scheduler = build_scheduler(cfg.scheduler, optimizer, cfg.train.epochs)
    scaler = torch.cuda.amp.GradScaler(enabled=amp)

    # 早停。
    mode = "maximize" if cfg.train.monitor == "val_macro_f1" else "minimize"
    early = EarlyStopping(patience=cfg.train.early_stopping_patience, mode=mode)

    # 训练历史 CSV。
    history_path = out_dir / "training_history.csv"
    history_fields = [
        "epoch", "train_loss", "val_loss", "val_accuracy", "val_macro_f1",
        "lr", "backbone_frozen", "elapsed_sec",
    ]
    with history_path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(history_fields)

    best_metric: float | None = None
    best_epoch: int | None = None
    backbone_frozen = cfg.model.freeze_backbone and cfg.model.name != "custom_cnn"
    unfrozen = not backbone_frozen

    for epoch in range(1, cfg.train.epochs + 1):
        # 逐步解冻。
        if backbone_frozen and not unfrozen and epoch > cfg.model.unfreeze_at_epoch:
            unfreeze_model_backbone(model, cfg.model.name)
            unfrozen = True
            # 解冻后用更小学习率重建优化器与调度器。
            optimizer = _build_optimizer(cfg, model, cfg.optimizer.unfreeze_lr)
            scheduler = build_scheduler(cfg.scheduler, optimizer, cfg.train.epochs)
            scaler = torch.cuda.amp.GradScaler(enabled=amp)

        model.train()
        t0 = time.time()
        running_loss = 0.0
        n_seen = 0
        for batch in train_loader:
            x, y = _move(batch, device)
            optimizer.zero_grad(set_to_none=True)
            with torch.cuda.amp.autocast(enabled=amp):
                logits = model(x)
                loss = criterion(logits, y)
            scaler.scale(loss).backward()
            if cfg.train.grad_clip > 0:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(
                    [p for p in model.parameters() if p.requires_grad],
                    cfg.train.grad_clip,
                )
            scaler.step(optimizer)
            scaler.update()
            bs = y.size(0)
            running_loss += float(loss.item()) * bs
            n_seen += bs
        train_loss = running_loss / max(1, n_seen)

        # 验证。
        val_metrics = evaluate_model(model, val_loader, device)
        val_loss = val_metrics["loss"]
        val_acc = val_metrics["accuracy"]
        val_f1 = val_metrics["macro_f1"]
        monitor_value = val_f1 if cfg.train.monitor == "val_macro_f1" else val_loss

        # 调度器步进。
        if scheduler is not None:
            scheduler.step()
        cur_lr = float(optimizer.param_groups[0]["lr"])

        elapsed = time.time() - t0
        with history_path.open("a", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow([
                epoch, train_loss, val_loss, val_acc, val_f1,
                cur_lr, int(unfrozen is False and backbone_frozen), elapsed,
            ])

        improved = early.step(monitor_value)
        if improved:
            best_metric = monitor_value
            best_epoch = epoch
            save_checkpoint(
                out_dir / BEST_FILENAME,
                model=model, optimizer=optimizer, scheduler=scheduler,
                epoch=epoch, best_metric=best_metric,
                metric_name=cfg.train.monitor,
                extra={"model_name": cfg.model.name, "experiment": cfg.experiment_name},
            )

        print(
            f"[epoch {epoch:03d}] train_loss={train_loss:.4f} "
            f"val_loss={val_loss:.4f} val_acc={val_acc:.4f} val_f1={val_f1:.4f} "
            f"lr={cur_lr:.2e} frozen={'Y' if (backbone_frozen and not unfrozen) else 'N'} "
            f"elapsed={elapsed:.1f}s"
        )

        if early.should_stop:
            print(f"早停：{cfg.train.monitor} 已 {early.wait} 轮无改善。")
            break

    # 保存 last 检查点。
    save_checkpoint(
        out_dir / LAST_FILENAME,
        model=model, optimizer=optimizer, scheduler=scheduler,
        epoch=cfg.train.epochs, best_metric=best_metric,
        metric_name=cfg.train.monitor,
    )

    # 保存训练摘要。
    summary = {
        "experiment_name": cfg.experiment_name,
        "model_name": cfg.model.name,
        "device": str(device),
        "epochs_run": min(epoch, cfg.train.epochs),
        "best_metric": best_metric,
        "best_epoch": best_epoch,
        "metric_name": cfg.train.monitor,
        "param_counts": count_parameters(model),
        "best_checkpoint": str(out_dir / BEST_FILENAME),
        "last_checkpoint": str(out_dir / LAST_FILENAME),
        "history_csv": str(history_path),
        "class_weights": class_weights.cpu().tolist(),
        "label_order": list(EXPRESSION_LABELS),
    }
    write_json(out_dir / "training_summary.json", summary)
    return summary
