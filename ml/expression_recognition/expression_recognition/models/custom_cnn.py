"""自定义浅层 CNN（基线模型）。

设计目标：
- 参数量小、结构简单，便于 freshman 理解与在本机 CPU 训练。
- 输入 1 通道 48x48 灰度（FER2013 原生尺寸）。
- 输出 7 类 logits。

结构：3 个 Conv->BN->ReLU->MaxPool 块 + 全局平均池化 + 分类头。
"""

from __future__ import annotations

import torch
from torch import nn


class CustomCNN(nn.Module):
    """浅层 CNN 基线。"""

    def __init__(self, num_classes: int = 7, dropout: float = 0.3, in_channels: int = 1):
        super().__init__()
        # 48x48 -> 24x24 -> 12x12 -> 6x6
        self.features = nn.Sequential(
            self._conv_block(in_channels, 32, 3, padding=1),
            self._conv_block(32, 64, 3, padding=1),
            self._conv_block(64, 128, 3, padding=1),
        )
        self.pool = nn.AdaptiveAvgPool2d((1, 1))
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(dropout),
            nn.Linear(128, num_classes),
        )

    @staticmethod
    def _conv_block(in_c: int, out_c: int, k: int, padding: int) -> nn.Sequential:
        return nn.Sequential(
            nn.Conv2d(in_c, out_c, k, padding=padding, bias=False),
            nn.BatchNorm2d(out_c),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = self.pool(x)
        return self.classifier(x)
