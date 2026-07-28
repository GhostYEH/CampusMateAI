"""数据划分清单（split manifest）持久化。

用途：
- 第一次划分数据时，把 train/val/test 中每个样本的路径（或来源标识）与标签
  写入 JSON 文件，作为后续所有模型训练的固定划分。
- 后续训练直接加载清单复用，保证三个模型使用完全相同的数据划分，
  消除"划分差异"导致的指标不可比。

清单结构：
{
    "version": 1,
    "label_order": [...],
    "method": "official_usage" | "stratified_random",
    "note": "...",
    "split_seed": 42,
    "dataset_root": "...",
    "format": "image_dir" | "fer2013_csv",
    "splits": {
        "train": [{"path": "...", "label": 0, "label_name": "angry"}, ...],
        "val":   [...],
        "test":  [...]
    },
    "counts": {"train": {...}, "val": {...}, "test": {...}}
}

对于 CSV 格式样本（pixels 非空、path 为空），用 sample 索引 + 像素哈希标识，
保证可复现；但由于 CSV 解析后样本顺序固定，索引即可唯一标识。
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ..constants import EXPRESSION_LABELS, LABEL_TO_INDEX
from ..utils.io import write_json, read_json, ensure_dir
from .fer2013 import FER2013Sample


MANIFEST_VERSION: int = 1


def _sample_fingerprint(sample: FER2013Sample, idx: int) -> dict[str, Any]:
    """把单条样本转成清单条目（可序列化）。

    Args:
        sample: FER2013Sample。
        idx: 样本在原始 samples 列表中的索引（用于 CSV 格式下的稳定标识）。

    Returns:
        {"path": str|None, "label": int, "label_name": str, "source": str,
         "csv_index": int|None, "pixels_sha256": str|None}
    """
    pixels_sha: str | None = None
    if sample.pixels is not None:
        # CSV 样本：用像素哈希作为辅助校验，避免索引错位。
        h = hashlib.sha256()
        h.update(sample.pixels.tobytes())
        pixels_sha = h.hexdigest()
    return {
        "path": sample.path,
        "label": int(sample.label),
        "label_name": EXPRESSION_LABELS[sample.label],
        "source": sample.source,
        "csv_index": idx if sample.source == "csv" else None,
        "pixels_sha256": pixels_sha,
    }


def save_manifest(
    manifest_path: str | Path,
    samples: list[FER2013Sample],
    split_result,
    dataset_root: str | Path,
    fmt: str,
    split_seed: int,
) -> dict[str, Any]:
    """把划分结果保存为 JSON 清单。

    Args:
        manifest_path: 输出 JSON 路径。
        samples: 原始完整样本列表（用于生成 csv_index）。
        split_result: SplitResult 对象。
        dataset_root: 数据集根目录。
        fmt: 数据格式 ("image_dir" / "fer2013_csv")。
        split_seed: 划分随机种子。

    Returns:
        写入的清单字典。
    """
    # 建立样本 -> 原始索引映射（用 id 标识，避免相同样本重复）。
    # 注意：FER2013Sample 是 dataclass，默认按值相等；用 id() 取对象标识更稳妥。
    id_to_idx = {id(s): i for i, s in enumerate(samples)}

    def _to_entries(split_samples: list[FER2013Sample]) -> list[dict[str, Any]]:
        out = []
        for s in split_samples:
            entry = _sample_fingerprint(s, id_to_idx.get(id(s), -1))
            out.append(entry)
        return out

    counts = split_result.counts_by_split_label()
    manifest = {
        "version": MANIFEST_VERSION,
        "label_order": list(EXPRESSION_LABELS),
        "label_to_index": LABEL_TO_INDEX,
        "method": split_result.method,
        "note": split_result.note,
        "split_seed": int(split_seed),
        "dataset_root": str(dataset_root),
        "format": fmt,
        "splits": {
            "train": _to_entries(split_result.train),
            "val": _to_entries(split_result.val),
            "test": _to_entries(split_result.test),
        },
        "counts": {
            split: {
                "total": len(getattr(split_result, split)),
                "per_class": {
                    EXPRESSION_LABELS[i]: counts[split].get(i, 0)
                    for i in range(len(EXPRESSION_LABELS))
                },
            }
            for split in ("train", "val", "test")
        },
    }
    write_json(manifest_path, manifest)
    return manifest


def load_manifest(manifest_path: str | Path) -> dict[str, Any]:
    """加载清单 JSON。"""
    return read_json(manifest_path)


def reconstruct_samples_from_manifest(
    manifest: dict[str, Any],
) -> dict[str, list[FER2013Sample]]:
    """从清单重建 FER2013Sample 列表。

    用于后续训练时复用固定划分：加载清单 -> 重建样本 -> 构造 torch Dataset。

    Args:
        manifest: load_manifest 返回的字典。

    Returns:
        {"train": [...], "val": [...], "test": [...]}，每个元素是 FER2013Sample。
    """
    fmt = manifest.get("format", "image_dir")
    out: dict[str, list[FER2013Sample]] = {}
    for split in ("train", "val", "test"):
        entries = manifest["splits"].get(split, [])
        samples: list[FER2013Sample] = []
        for e in entries:
            if fmt == "image_dir":
                # image_dir 格式：path 优先，pixels 留空（Dataset 加载时用 PIL 读）。
                samples.append(
                    FER2013Sample(
                        label=int(e["label"]),
                        usage=None,  # 重建时不带 usage，避免再次触发官方划分逻辑
                        pixels=None,
                        path=e["path"],
                        source="image_dir",
                    )
                )
            else:
                # fer2013_csv 格式：清单不保存像素，需要从 CSV 重新解析。
                # 这里只重建索引，调用方需配合 CSV 路径重建像素。
                raise NotImplementedError(
                    "CSV 格式的清单重建需要原始 CSV 路径，请在调用方重建。"
                )
        out[split] = samples
    return out


def verify_manifest_against_samples(
    manifest: dict[str, Any],
    samples: list[FER2013Sample],
) -> tuple[bool, str]:
    """校验清单与当前样本集是否一致（用于检测数据是否被改动）。

    Args:
        manifest: 清单字典。
        samples: 当前数据集样本列表。

    Returns:
        (ok, message)。ok=True 表示一致。
    """
    expected_total = (
        len(manifest["splits"]["train"])
        + len(manifest["splits"]["val"])
        + len(manifest["splits"]["test"])
    )
    if expected_total != len(samples):
        return False, (
            f"样本总数不一致：清单 {expected_total}，当前 {len(samples)}。"
            "数据集可能已被改动，请重新生成清单。"
        )
    # 校验 image_dir 格式下路径是否都存在。
    if manifest.get("format") == "image_dir":
        missing = 0
        for split in ("train", "val", "test"):
            for e in manifest["splits"][split]:
                if e.get("path") and not Path(e["path"]).exists():
                    missing += 1
        if missing > 0:
            return False, f"{missing} 个样本路径不存在，数据集可能已被移动或删除。"
    return True, "OK"
