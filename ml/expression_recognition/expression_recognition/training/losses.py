"""损失函数：带类别权重与标签平滑的 CrossEntropy，以及可选 Focal Loss。

类别权重按训练集频率逆倒数计算，缓解 FER2013 中 disgust 类极不平衡问题。
标签平滑通过 torch CrossEntropyLoss 的 label_smoothing 参数实现。
Focal Loss 自行实现（标准公式）。
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from ..config import LossConfig
from ..constants import NUM_CLASSES


def compute_class_weights(
    train_labels: Sequence[int],
    num_classes: int = NUM_CLASSES,
    strategy: str = "inverse",
) -> torch.Tensor:
    """根据训练集标签分布计算类别权重。

    Args:
        train_labels: 训练集每个样本的标签（0..num_classes-1）。
        num_classes: 类别数。
        strategy: "inverse"=按频率逆倒数；"effective_num"=有效数量（CB loss 思路）。

    Returns:
        长度 num_classes 的 float32 张量。
    """
    labels = np.asarray(train_labels, dtype=np.int64)
    counts = np.bincount(labels, minlength=num_classes).astype(np.float64)
    # 防止除零：未出现类给 1。
    counts = np.where(counts == 0, 1.0, counts)
    if strategy == "inverse":
        weights = counts.sum() / (num_classes * counts)
    elif strategy == "effective_num":
        beta = 0.9999
        effective = (1.0 - np.power(beta, counts)) / (1.0 - beta)
        weights = 1.0 / effective
        weights = weights / weights.sum() * num_classes
    else:
        raise ValueError(f"未知 class weight strategy: {strategy}")
    return torch.tensor(weights, dtype=torch.float32)


class CrossEntropyLoss(nn.Module):
    """带类别权重与标签平滑的交叉熵。"""

    def __init__(
        self,
        weight: torch.Tensor | None = None,
        label_smoothing: float = 0.0,
    ):
        super().__init__()
        self.ce = nn.CrossEntropyLoss(
            weight=weight,
            label_smoothing=label_smoothing,
        )

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        return self.ce(logits, targets)


class FocalLoss(nn.Module):
    """多分类 Focal Loss。

    FL(p_t) = -alpha * (1 - p_t)^gamma * log(p_t)

    支持 per-class alpha 与类别权重结合。
    """

    def __init__(
        self,
        gamma: float = 2.0,
        alpha: float | torch.Tensor | None = None,
        class_weight: torch.Tensor | None = None,
        label_smoothing: float = 0.0,
        num_classes: int = NUM_CLASSES,
    ):
        super().__init__()
        self.gamma = gamma
        self.label_smoothing = label_smoothing
        self.num_classes = num_classes
        # alpha 可以是标量，也可以是 per-class 张量。
        if alpha is None:
            self.register_buffer("alpha", None)
        elif isinstance(alpha, (int, float)):
            self.register_buffer("alpha", torch.full((num_classes,), float(alpha)))
        else:
            self.register_buffer("alpha", alpha.float())
        self.register_buffer("class_weight", class_weight.float() if class_weight is not None else None)

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        # 数值稳定的 log-softmax。
        log_probs = F.log_softmax(logits, dim=1)
        probs = log_probs.exp()
        # one-hot（带标签平滑）。
        with torch.no_grad():
            target_dist = torch.zeros_like(logits)
            target_dist.fill_(self.label_smoothing / (self.num_classes - 1))
            target_dist.scatter_(1, targets.unsqueeze(1), 1.0 - self.label_smoothing)
        # focal 调制：对每个类概率 p_t（target 概率）做 (1-p_t)^gamma。
        pt = (target_dist * probs).sum(dim=1).clamp(min=1e-8, max=1.0)
        focal_modulation = (1.0 - pt) ** self.gamma
        loss = -(target_dist * log_probs).sum(dim=1)
        loss = loss * focal_modulation
        # per-class alpha。
        if self.alpha is not None:
            loss = loss * self.alpha[targets]
        # class weight（按 target 类别）。
        if self.class_weight is not None:
            loss = loss * self.class_weight[targets]
        return loss.mean()


def build_loss(
    loss_cfg: LossConfig,
    class_weights: torch.Tensor | None = None,
) -> nn.Module:
    """根据配置构造损失函数。

    Args:
        loss_cfg: 损失配置。
        class_weights: 类别权重张量（use_class_weights=True 时使用）。
    """
    weight = class_weights if loss_cfg.use_class_weights else None
    if loss_cfg.type == "cross_entropy":
        return CrossEntropyLoss(
            weight=weight,
            label_smoothing=loss_cfg.label_smoothing,
        )
    if loss_cfg.type == "focal":
        return FocalLoss(
            gamma=loss_cfg.focal_gamma,
            alpha=loss_cfg.focal_alpha,
            class_weight=weight,
            label_smoothing=loss_cfg.label_smoothing,
        )
    raise ValueError(f"未知 loss.type: {loss_cfg.type}")
