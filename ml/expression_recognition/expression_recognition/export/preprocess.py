"""导出 preprocess.json：预处理参数契约，供端侧推理复用。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import InputConfig
from ..constants import EXPRESSION_LABELS
from ..utils.io import write_json


def export_preprocess_json(path: str | Path, input_cfg: InputConfig) -> dict[str, Any]:
    """写出 preprocess.json。

    结构（字段对齐第七步要求）：
    {
        "input_size": [C, H, W],
        "channels": 1 | 3,
        "height": H,
        "width": W,
        "color_format": "GRAY" | "RGB",
        "input_dtype": "float32",
        "output_type": "logits",
        "normalization_mean": [...],
        "normalization_std": [...],
        "normalization": {"mean": [...], "std": [...]},  # 兼容旧字段
        "label_order": [...],
        "pixel_range": [0, 1],
        "pixel_scale": 1.0 / 255.0,
        "note": "..."
    }
    """
    color_format = "RGB" if input_cfg.channels == 3 else "GRAY"
    mean_list = list(input_cfg.mean)
    std_list = list(input_cfg.std)
    data = {
        "input_size": [input_cfg.channels, input_cfg.size, input_cfg.size],
        "channels": input_cfg.channels,
        "height": input_cfg.size,
        "width": input_cfg.size,
        "color_format": color_format,
        "input_dtype": "float32",
        "output_type": "logits",
        "normalization_mean": mean_list,
        "normalization_std": std_list,
        # 兼容旧字段名。
        "normalization": {"mean": mean_list, "std": std_list},
        "label_order": list(EXPRESSION_LABELS),
        # 像素归一化到 [0,1] 后再做 mean/std 归一化。
        "pixel_range": [0, 1],
        "pixel_scale": 1.0 / 255.0,
        "note": (
            "端侧推理预处理：灰度图 -> resize 到 (H,W) -> "
            "若 channels=3 复制到三通道 -> x/255.0 -> (x-mean)/std。"
            "输出为 7 类 logits，argmax 即预测类别索引，对齐 label_order。"
        ),
    }
    write_json(path, data)
    return data
