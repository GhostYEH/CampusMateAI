"""训练/验证/测试划分，含防泄漏说明。

防泄漏说明（强制诚实声明）：
FER2013 官方数据集不提供受试者 ID（subject ID），因此无法做严格的
"同一人的样本只出现在一个 split"的同源隔离。本工程采用以下策略，
并在报告中明确此限制：

1. 优先使用官方 Usage 列（Training / PublicTest / PrivateTest），
   这是数据集发布者给出的标准划分，是社区公认的防泄漏基线。
2. 当数据未自带 Usage（如 image_dir 格式的未划分目录）时，按样本索引
   做分层随机划分（按类别比例），保证三类集合类别分布一致。
3. 划分使用独立随机种子（data.split_seed），可复现。
4. 不做任何跨 split 的样本复制或增强共享——增强只作用于训练集，
   验证/测试集不增强。

如未来获得带 subject ID 的数据集，应改为按 subject 划分以进一步防泄漏。
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass
from typing import Sequence

from .fer2013 import FER2013Sample

# 防泄漏限制说明，写入报告。
LEAKAGE_NOTE: str = (
    "FER2013 不提供受试者 ID，无法做严格的同源样本隔离。"
    "本工程优先使用官方 Usage 划分（Training/PublicTest/PrivateTest）；"
    "当数据未自带 Usage 时，按分层随机索引划分（按类别比例，独立种子，可复现）。"
    "增强仅作用于训练集，验证/测试集不增强。"
    "如未来获得带 subject ID 的数据，应改为按 subject 划分以进一步防泄漏。"
)

# 统一的 usage 归一化：把各种写法映射到 train/val/test。
_USAGE_MAP = {
    "training": "train",
    "train": "train",
    "publictest": "val",
    "public_test": "val",
    "publictestset": "val",
    "val": "val",
    "valid": "val",
    "validation": "val",
    "privatetest": "test",
    "private_test": "test",
    "privatetestset": "test",
    "test": "test",
}


def _normalize_usage(usage: str | None) -> str | None:
    if usage is None:
        return None
    return _USAGE_MAP.get(usage.strip().lower())


@dataclass
class SplitResult:
    """划分结果。"""

    train: list[FER2013Sample]
    val: list[FER2013Sample]
    test: list[FER2013Sample]
    method: str  # "official_usage" 或 "stratified_random"
    note: str  # 防泄漏说明

    def as_dict(self) -> dict[str, list[FER2013Sample]]:
        return {"train": self.train, "val": self.val, "test": self.test}

    def counts_by_split_label(self) -> dict[str, dict[int, int]]:
        """统计每个 split 每个类别的样本数，用于报告与泄漏检查。"""
        out: dict[str, dict[int, int]] = {}
        for name in ("train", "val", "test"):
            samples = getattr(self, name)
            counter: dict[int, int] = defaultdict(int)
            for s in samples:
                counter[s.label] += 1
            out[name] = dict(counter)
        return out


def split_samples(
    samples: Sequence[FER2013Sample],
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
    stratified: bool = True,
    split_seed: int = 42,
) -> SplitResult:
    """把样本列表划分为 train/val/test。

    优先使用样本自带的 usage（官方 Usage 列或 image_dir 的 split 目录名）。
    若所有样本 usage 都为 None，则按比例做分层随机划分。

    Args:
        samples: 样本列表。
        train_ratio / val_ratio / test_ratio: 划分比例（仅随机划分时使用）。
        stratified: 是否分层（按类别比例）。
        split_seed: 随机种子。
    """
    if not samples:
        raise ValueError("样本列表为空，无法划分。")

    # 1) 若样本自带 usage，优先使用官方划分。
    normalized = [_normalize_usage(s.usage) for s in samples]
    if all(u is not None for u in normalized) and any(u == "train" for u in normalized):
        train = [s for s, u in zip(samples, normalized) if u == "train"]
        val = [s for s, u in zip(samples, normalized) if u == "val"]
        test = [s for s, u in zip(samples, normalized) if u == "test"]
        if not train:
            raise ValueError("样本自带 usage 但无 Training/train 划分。")
        # 若只有 train/val 或 train/test，按比例从 train 补齐缺失集。
        if not val and not test:
            train, val, test = _random_split(train, train_ratio, val_ratio, test_ratio,
                                              stratified, split_seed)
        elif not val and test:
            # 已有 train + test 但缺 val：从 train 中按比例分层切出 val，
            # test 保持不变（test 完全不参与训练/调参/模型选择）。
            # 此时 train_ratio 视为 train 占 (train+val) 的比例，val_ratio=1-train_ratio。
            train, val, _ = _random_split(
                train, train_ratio, 1.0 - train_ratio, 0.0,
                stratified, split_seed,
            )
        return SplitResult(
            train=train, val=val, test=test,
            method="official_usage", note=LEAKAGE_NOTE,
        )

    # 2) 否则按比例分层随机划分。
    train, val, test = _random_split(
        list(samples), train_ratio, val_ratio, test_ratio, stratified, split_seed
    )
    return SplitResult(
        train=train, val=val, test=test,
        method="stratified_random", note=LEAKAGE_NOTE,
    )


def _random_split(
    samples: list[FER2013Sample],
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    stratified: bool,
    seed: int,
) -> tuple[list[FER2013Sample], list[FER2013Sample], list[FER2013Sample]]:
    """按比例（可选分层）随机划分。"""
    rng = random.Random(seed)
    if stratified:
        # 按类别分组，每个类别内部按比例切。
        by_label: dict[int, list[FER2013Sample]] = defaultdict(list)
        for s in samples:
            by_label[s.label].append(s)
        train, val, test = [], [], []
        for label in sorted(by_label.keys()):
            group = by_label[label][:]
            rng.shuffle(group)
            n = len(group)
            n_train = int(round(n * train_ratio))
            n_val = int(round(n * val_ratio))
            # 剩余全部给 test，避免舍入误差导致样本丢失。
            n_test = n - n_train - n_val
            if n_test < 0:  # 比例舍入修正
                n_train += n_test
                n_test = 0
            train.extend(group[:n_train])
            val.extend(group[n_train:n_train + n_val])
            test.extend(group[n_train + n_val:n_train + n_val + n_test])
        # 打乱各 split 内部顺序，便于训练时 shuffle。
        rng.shuffle(train)
        rng.shuffle(val)
        rng.shuffle(test)
        return train, val, test
    else:
        shuffled = samples[:]
        rng.shuffle(shuffled)
        n = len(shuffled)
        n_train = int(round(n * train_ratio))
        n_val = int(round(n * val_ratio))
        n_test = n - n_train - n_val
        if n_test < 0:
            n_train += n_test
            n_test = 0
        return (
            shuffled[:n_train],
            shuffled[n_train:n_train + n_val],
            shuffled[n_train + n_val:n_train + n_val + n_test],
        )
