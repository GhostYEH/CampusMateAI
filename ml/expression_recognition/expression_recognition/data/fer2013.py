"""FER2013 数据解析与 torch Dataset 包装。

支持两种数据格式：
1. fer2013_csv：官方 CSV，列为 emotion / pixels / Usage。
   - emotion: 0..6，对应 constants.EXPRESSION_LABELS。
   - pixels: 2304 个空格分隔的整数（48*48 灰度）。
   - Usage: "Training" / "PublicTest" / "PrivateTest"。
2. image_dir：按 split/label 组织的图像目录。
   - 推荐结构：dataset_root/{train,val,test}/{label}/*.png
   - 也支持未划分结构：dataset_root/{label}/*.png，由 split.py 划分。

解析函数（parse_fer2013_csv / scan_image_dir）只依赖 numpy/pandas/PIL，
不依赖 torch，便于在无 torch 环境运行单元测试。
torch Dataset 包装放在本文件末尾，需要 torch 时才导入。

重要：数据集缺失时抛出 DatasetNotFoundError，给出明确错误信息，
绝不自动下载来历不明的数据。
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

from ..constants import (
    EXPRESSION_LABELS,
    FER2013_NATIVE_SIZE,
    LABEL_TO_INDEX,
)


class DatasetNotFoundError(FileNotFoundError):
    """数据集不存在或格式不匹配时抛出。

    本工程不自动下载来历不明的数据，缺失时必须由用户手动放置并重试。
    """


@dataclass
class FER2013Sample:
    """一条样本（解析后的中间表示，与 torch 解耦）。

    对于 CSV 格式，pixels 是 48x48 uint8 numpy 数组，usage 来自 Usage 列。
    对于 image_dir 格式，pixels 为 None，path 为图像路径，usage 取自目录名
    （train/val/test）或 None（未划分）。
    """

    label: int
    usage: str | None  # "Training" / "PublicTest" / "PrivateTest" / "train"/"val"/"test" / None
    pixels: np.ndarray | None  # uint8, shape (H, W) 或 (H, W, C)
    path: str | None  # image_dir 格式下的图像路径
    source: str  # "csv" 或 "image_dir"

    @property
    def label_name(self) -> str:
        return EXPRESSION_LABELS[self.label]


def _parse_pixels(pixels_str: str) -> np.ndarray:
    """把 FER2013 CSV 的 pixels 字段解析为 48x48 uint8 数组。"""
    values = pixels_str.split()
    expected = FER2013_NATIVE_SIZE * FER2013_NATIVE_SIZE
    if len(values) != expected:
        raise ValueError(
            f"FER2013 pixels 数量错误：期望 {expected}，得到 {len(values)}。"
            "请确认 CSV 为官方格式。"
        )
    arr = np.asarray(values, dtype=np.uint8).reshape(
        FER2013_NATIVE_SIZE, FER2013_NATIVE_SIZE
    )
    return arr


def parse_fer2013_csv(csv_path: str | Path) -> list[FER2013Sample]:
    """解析 FER2013 官方 CSV。

    Args:
        csv_path: CSV 文件路径。

    Returns:
        样本列表。

    Raises:
        DatasetNotFoundError: 文件不存在。
        ValueError: 文件格式不合法（列缺失、pixels 数量错误、标签越界）。
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise DatasetNotFoundError(
            f"FER2013 CSV 不存在: {csv_path}\n"
            "本工程不自动下载数据集。请从合法来源获取 fer2013.csv 并放到\n"
            f"{csv_path.parent} 目录后重试。"
        )

    samples: list[FER2013Sample] = []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "emotion" not in reader.fieldnames \
                or "pixels" not in reader.fieldnames:
            raise ValueError(
                f"CSV 列不合法，期望包含 emotion/pixels，得到 {reader.fieldnames}。"
            )
        has_usage = "Usage" in reader.fieldnames
        for row_idx, row in enumerate(reader):
            try:
                emotion = int(row["emotion"])
            except (ValueError, TypeError) as e:
                raise ValueError(f"第 {row_idx} 行 emotion 非整数: {row['emotion']!r}") from e
            if emotion < 0 or emotion >= len(EXPRESSION_LABELS):
                raise ValueError(
                    f"第 {row_idx} 行 emotion 越界: {emotion}，"
                    f"合法范围 0..{len(EXPRESSION_LABELS) - 1}。"
                )
            pixels = _parse_pixels(row["pixels"])
            usage = row.get("Usage") if has_usage else None
            samples.append(
                FER2013Sample(
                    label=emotion,
                    usage=usage,
                    pixels=pixels,
                    path=None,
                    source="csv",
                )
            )
    if not samples:
        raise DatasetNotFoundError(f"CSV 解析后样本数为 0: {csv_path}")
    return samples


def scan_image_dir(root: str | Path) -> list[FER2013Sample]:
    """扫描按 split/label 组织的图像目录。

    支持两种结构：
    A) dataset_root/{train,val,test}/{label}/*.png|jpg|jpeg
    B) dataset_root/{label}/*.png|jpg|jpeg  （未划分，由 split.py 处理）

    label 目录名必须是 constants.EXPRESSION_LABELS 之一。
    """
    root = Path(root)
    if not root.exists():
        raise DatasetNotFoundError(
            f"图像目录不存在: {root}\n"
            "本工程不自动下载数据集。请手动放置数据后重试。"
        )

    valid_labels = set(EXPRESSION_LABELS)
    split_names = {"train", "val", "test", "training", "publictest", "privatetest"}
    image_exts = {".png", ".jpg", ".jpeg", ".bmp"}
    samples: list[FER2013Sample] = []

    # 判断是结构 A 还是 B：若 root 下第一级子目录名含 split_names 视为 A。
    top_dirs = [p for p in root.iterdir() if p.is_dir()]
    top_names = {p.name.lower() for p in top_dirs}
    is_structured = bool(top_names & split_names)

    def _normalize_usage(name: str) -> str | None:
        name = name.lower()
        if name in ("train", "training"):
            return "Training"
        if name in ("val", "valid", "validation", "publictest"):
            return "PublicTest"
        if name in ("test", "privatetest"):
            return "PrivateTest"
        return None

    if is_structured:
        for split_dir in top_dirs:
            usage = _normalize_usage(split_dir.name)
            for label_dir in split_dir.iterdir():
                if not label_dir.is_dir() or label_dir.name.lower() not in valid_labels:
                    continue
                label_idx = LABEL_TO_INDEX[label_dir.name.lower()]
                for img_path in sorted(label_dir.iterdir()):
                    if img_path.suffix.lower() in image_exts:
                        samples.append(
                            FER2013Sample(
                                label=label_idx,
                                usage=usage,
                                pixels=None,
                                path=str(img_path),
                                source="image_dir",
                            )
                        )
    else:
        # 结构 B：root/{label}/*
        for label_dir in top_dirs:
            if label_dir.name.lower() not in valid_labels:
                continue
            label_idx = LABEL_TO_INDEX[label_dir.name.lower()]
            for img_path in sorted(label_dir.iterdir()):
                if img_path.suffix.lower() in image_exts:
                    samples.append(
                        FER2013Sample(
                            label=label_idx,
                            usage=None,
                            pixels=None,
                            path=str(img_path),
                            source="image_dir",
                        )
                    )

    if not samples:
        raise DatasetNotFoundError(
            f"在 {root} 下未找到任何图像样本。请确认目录结构为\n"
            "  {root}/{{train,val,test}}/{{label}}/*.png 或 {root}/{{label}}/*.png\n"
            f"且 label 名属于 {list(EXPRESSION_LABELS)}。"
        )
    return samples


def load_samples(
    root: str | Path,
    fmt: str,
    csv_name: str = "fer2013.csv",
) -> list[FER2013Sample]:
    """根据格式加载样本（统一入口）。

    Args:
        root: 数据集根目录。
        fmt: "fer2013_csv" 或 "image_dir"。
        csv_name: CSV 文件名（仅 fer2013_csv 格式）。
    """
    root = Path(root)
    if fmt == "fer2013_csv":
        return parse_fer2013_csv(root / csv_name)
    if fmt == "image_dir":
        return scan_image_dir(root)
    raise ValueError(f"未知数据格式: {fmt}（支持 fer2013_csv / image_dir）")


# ---------------------------------------------------------------------------
# torch Dataset 包装（仅在有 torch 时可用）
# ---------------------------------------------------------------------------

# 注意：Dataset 类必须在模块顶层定义，否则在 Windows 上使用 multiprocessing
# spawn 启动 DataLoader worker 时无法 pickle（"Can't get local object" 错误）。
# 这里在模块顶层尝试导入 torch，若不可用则定义一个占位基类，保证模块可导入。

try:
    import torch as _torch
    from torch.utils.data import Dataset as _DatasetBase
    _TORCH_AVAILABLE = True
except ImportError:  # pragma: no cover - 允许无 torch 环境
    _torch = None
    _DatasetBase = object
    _TORCH_AVAILABLE = False


class FERDataset(_DatasetBase):
    """FER2013 torch Dataset（模块顶层类，可被 multiprocessing pickle）。

    支持两种样本来源：
    - CSV 格式（pixels 非空）：直接使用解析后的 numpy 数组。
    - image_dir 格式（pixels 为空、path 非空）：用 PIL 读取图像。

    通道处理：
    - channels=1：单通道灰度。
    - channels=3：灰度复制到三通道，适配 ImageNet 预训练骨干。
    """

    def __init__(self, samples, transform, channels):
        self.samples = list(samples)
        self.transform = transform
        self.channels = int(channels)

    def __len__(self) -> int:
        return len(self.samples)

    def _load_image(self, sample: "FER2013Sample") -> np.ndarray:
        if sample.pixels is not None:
            arr = sample.pixels
        else:
            # image_dir 格式：用 PIL 读取。
            from PIL import Image

            img = Image.open(sample.path)
            if img.mode != "L":
                img = img.convert("L")
            arr = np.asarray(img, dtype=np.uint8)
        # 统一成 (H, W) uint8。
        if arr.ndim == 3 and arr.shape[2] == 1:
            arr = arr[:, :, 0]
        return arr

    def __getitem__(self, idx: int):
        sample = self.samples[idx]
        arr = self._load_image(sample)
        if self.channels == 3:
            # 灰度复制到三通道，适配 ImageNet 预训练骨干。
            arr = np.stack([arr, arr, arr], axis=2)
        # 转 CHW float32。
        if arr.ndim == 2:
            arr = arr[:, :, None]
        arr = np.transpose(arr, (2, 0, 1)).astype(np.float32) / 255.0
        if self.transform is not None:
            arr = self.transform(arr)
        return _torch.from_numpy(np.ascontiguousarray(arr)), int(sample.label)


def _to_torch_dataset(samples: Sequence[FER2013Sample], transform, channels: int):
    """把样本列表包装成 torch Dataset。

    延迟导入 torch，便于无 torch 环境导入本模块的解析函数。
    """
    if not _TORCH_AVAILABLE:
        raise ImportError("构建 torch Dataset 需要 torch，请安装: pip install torch")
    return FERDataset(list(samples), transform, channels)


def build_torch_datasets(
    splits: dict[str, list[FER2013Sample]],
    train_transform,
    eval_transform,
    channels: int,
) -> dict[str, object]:
    """把划分后的样本字典构造成 torch Dataset 字典。

    Args:
        splits: {"train": [...], "val": [...], "test": [...]}。
        train_transform: 训练集增强。
        eval_transform: 验证/测试集变换（通常只做 resize+normalize）。
        channels: 1 或 3。
    """
    out = {}
    for name, samples in splits.items():
        tfm = train_transform if name == "train" else eval_transform
        out[name] = _to_torch_dataset(samples, tfm, channels)
    return out
