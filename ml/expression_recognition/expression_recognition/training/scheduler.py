"""学习率调度器构造：cosine / step。"""

from __future__ import annotations

import torch

from ..config import SchedulerConfig


def build_scheduler(
    scheduler_cfg: SchedulerConfig,
    optimizer: torch.optim.Optimizer,
    total_epochs: int,
) -> torch.optim.lr_scheduler.LRScheduler | None:
    """构造学习率调度器。

    Args:
        scheduler_cfg: 调度器配置。
        optimizer: 优化器。
        total_epochs: 总训练 epoch（cosine 调度用）。

    Returns:
        调度器实例；patience<=0 或未知类型返回 None。
    """
    if scheduler_cfg.type == "cosine":
        return torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer,
            T_max=max(1, total_epochs),
            eta_min=scheduler_cfg.cosine_eta_min,
        )
    if scheduler_cfg.type == "step":
        return torch.optim.lr_scheduler.StepLR(
            optimizer,
            step_size=max(1, scheduler_cfg.step_size),
            gamma=scheduler_cfg.step_gamma,
        )
    raise ValueError(f"未知 scheduler.type: {scheduler_cfg.type}")
