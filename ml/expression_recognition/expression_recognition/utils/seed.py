"""随机种子控制，保证可复现。

固定 Python / NumPy / PyTorch（含 CUDA）的随机种子，并尽量关闭
非确定性算法。CUDA 完全确定性会带来性能损失，这里默认开启 cudnn
deterministic，可通过参数关闭。
"""

from __future__ import annotations

import os
import random


def set_seed(seed: int, deterministic: bool = True) -> None:
    """固定全局随机种子。

    Args:
        seed: 随机种子。
        deterministic: 是否强制 PyTorch cuDNN 使用确定性算法。
    """
    # Python 内置随机数。
    random.seed(seed)
    # 环境变量，部分库会读取。
    os.environ["PYTHONHASHSEED"] = str(seed)

    # NumPy（可能未安装时优雅跳过）。
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:  # pragma: no cover - numpy 通常存在
        pass

    # PyTorch（未安装时跳过，便于无 torch 环境运行部分测试）。
    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():  # pragma: no cover - 视环境而定
            torch.cuda.manual_seed_all(seed)
        if deterministic:
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
    except ImportError:  # pragma: no cover - 允许无 torch 环境
        pass
