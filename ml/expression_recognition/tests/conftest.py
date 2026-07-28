"""pytest 公共 fixture。

提供：
- 合成 FER2013 CSV（小规模，用于测试解析与划分）。
- 合成 image_dir（小规模）。
- 合成 torch 模型与输入（用于测试前向/导出）。

合成数据全部在内存或 tmp_path 中生成，不依赖真实 FER2013。
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest

from expression_recognition.constants import EXPRESSION_LABELS, FER2013_NATIVE_SIZE


def _make_pixels(seed: int) -> str:
    """生成 48*48 个 0-255 整数（空格分隔），模拟 FER2013 pixels。"""
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 256, size=FER2013_NATIVE_SIZE * FER2013_NATIVE_SIZE, dtype=np.uint8)
    return " ".join(str(int(v)) for v in arr)


@pytest.fixture
def synthetic_csv(tmp_path: Path) -> Path:
    """合成 FER2013 CSV：7 类，每类 12 条，带 Usage 列。"""
    csv_path = tmp_path / "fer2013.csv"
    usages = ["Training"] * 8 + ["PublicTest"] * 2 + ["PrivateTest"] * 2
    rows = []
    for label_idx in range(len(EXPRESSION_LABELS)):
        for i, usage in enumerate(usages):
            seed = label_idx * 100 + i
            rows.append({"emotion": label_idx, "pixels": _make_pixels(seed), "Usage": usage})
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["emotion", "pixels", "Usage"])
        writer.writeheader()
        writer.writerows(rows)
    return csv_path


@pytest.fixture
def synthetic_csv_no_usage(tmp_path: Path) -> Path:
    """合成 FER2013 CSV（无 Usage 列），用于测试随机划分。"""
    csv_path = tmp_path / "fer2013_no_usage.csv"
    rows = []
    for label_idx in range(len(EXPRESSION_LABELS)):
        for i in range(10):
            rows.append({"emotion": label_idx, "pixels": _make_pixels(label_idx * 10 + i)})
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["emotion", "pixels"])
        writer.writeheader()
        writer.writerows(rows)
    return csv_path


@pytest.fixture
def synthetic_image_dir(tmp_path: Path) -> Path:
    """合成 image_dir 结构：{train,val,test}/{label}/*.png。"""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow 未安装，跳过 image_dir 测试。")
    root = tmp_path / "imgset"
    splits = {"train": 6, "val": 2, "test": 2}
    rng = np.random.default_rng(0)
    for split, n in splits.items():
        for label_idx, label in enumerate(EXPRESSION_LABELS):
            d = root / split / label
            d.mkdir(parents=True, exist_ok=True)
            for i in range(n):
                arr = rng.integers(0, 256, size=(FER2013_NATIVE_SIZE, FER2013_NATIVE_SIZE), dtype=np.uint8)
                Image.fromarray(arr, mode="L").save(d / f"{label}_{i}.png")
    return root


@pytest.fixture
def tiny_input_cfg():
    from expression_recognition.config import InputConfig

    return InputConfig(size=48, channels=1, mean=(0.5,), std=(0.5,))


@pytest.fixture
def tiny_model_cfg():
    from expression_recognition.config import ModelConfig

    return ModelConfig(name="custom_cnn", num_classes=7, pretrained=False,
                       freeze_backbone=False, dropout=0.1)
