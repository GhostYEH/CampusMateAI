"""评估子包：指标计算、评估脚本、混淆矩阵绘图。

metrics.py 只依赖 numpy，可在无 torch 环境运行单元测试。
"""

from .metrics import (
    compute_metrics,
    accuracy,
    macro_f1,
    per_class_precision_recall,
    confusion_matrix,
)

__all__ = [
    "compute_metrics",
    "accuracy",
    "macro_f1",
    "per_class_precision_recall",
    "confusion_matrix",
]
