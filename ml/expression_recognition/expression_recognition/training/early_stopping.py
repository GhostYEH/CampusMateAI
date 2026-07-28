"""早停：监控验证指标，连续 patience 轮无改善则停止。

支持两种模式：
- maximize：监控 val_macro_f1，越大越好。
- minimize：监控 val_loss，越小越好。
"""

from __future__ import annotations


class EarlyStopping:
    """早停控制器。"""

    def __init__(self, patience: int = 8, mode: str = "maximize", min_delta: float = 1e-4):
        if mode not in ("maximize", "minimize"):
            raise ValueError("mode 必须为 'maximize' 或 'minimize'")
        self.patience = max(0, patience)
        self.mode = mode
        self.min_delta = float(min_delta)
        self.best: float | None = None
        self.wait = 0
        self.stopped = False

    def step(self, value: float) -> bool:
        """更新一次监控值。

        Returns:
            True 表示产生了新的最佳值。
        """
        improved = False
        if self.best is None:
            self.best = value
            improved = True
            self.wait = 0
        else:
            if self.mode == "maximize":
                improved = value > self.best + self.min_delta
            else:
                improved = value < self.best - self.min_delta
            if improved:
                self.best = value
                self.wait = 0
            else:
                self.wait += 1
        if self.patience > 0 and self.wait >= self.patience:
            self.stopped = True
        return improved

    @property
    def should_stop(self) -> bool:
        return self.stopped
