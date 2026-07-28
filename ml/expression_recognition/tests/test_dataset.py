"""数据集解析测试（纯 Python，不依赖 torch）。

覆盖：
- FER2013 CSV 解析（带/不带 Usage）。
- image_dir 扫描（两种结构）。
- 标签顺序与索引一致。
- pixels 形状正确。
"""

import pytest

from expression_recognition.data import parse_fer2013_csv, scan_image_dir
from expression_recognition.constants import EXPRESSION_LABELS, FER2013_NATIVE_SIZE


def test_parse_csv_with_usage(synthetic_csv):
    samples = parse_fer2013_csv(synthetic_csv)
    # 7 类 * 12 条 = 84
    assert len(samples) == 7 * 12
    # pixels 形状 48x48。
    assert samples[0].pixels.shape == (FER2013_NATIVE_SIZE, FER2013_NATIVE_SIZE)
    assert samples[0].pixels.dtype.name == "uint8"
    # 每类都有样本。
    labels = {s.label for s in samples}
    assert labels == set(range(7))
    # usage 字段存在。
    assert samples[0].usage in ("Training", "PublicTest", "PrivateTest")


def test_parse_csv_label_indices_match_constant(synthetic_csv):
    samples = parse_fer2013_csv(synthetic_csv)
    # label_name 与 EXPRESSION_LABELS 一致。
    for s in samples:
        assert s.label_name == EXPRESSION_LABELS[s.label]


def test_parse_csv_without_usage(synthetic_csv_no_usage):
    samples = parse_fer2013_csv(synthetic_csv_no_usage)
    assert len(samples) == 70
    assert all(s.usage is None for s in samples)


def test_parse_csv_bad_pixels_count(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("emotion,pixels,Usage\n0,1 2 3,Training\n", encoding="utf-8")
    with pytest.raises(ValueError, match="pixels 数量错误"):
        parse_fer2013_csv(p)


def test_parse_csv_bad_label(tmp_path):
    p = tmp_path / "bad.csv"
    pixels = " ".join(["0"] * (FER2013_NATIVE_SIZE * FER2013_NATIVE_SIZE))
    p.write_text(f"emotion,pixels,Usage\n9,{pixels},Training\n", encoding="utf-8")
    with pytest.raises(ValueError, match="emotion 越界"):
        parse_fer2013_csv(p)


def test_scan_image_dir_structured(synthetic_image_dir):
    samples = scan_image_dir(synthetic_image_dir)
    # 3 split * 7 label * 2..6 张
    counts_by_split = {"Training": 0, "PublicTest": 0, "PrivateTest": 0, None: 0}
    for s in samples:
        counts_by_split[s.usage] = counts_by_split.get(s.usage, 0) + 1
    # train: 7*6=42, val: 7*2=14, test: 7*2=14
    assert counts_by_split.get("Training", 0) == 42
    assert counts_by_split.get("PublicTest", 0) == 14
    assert counts_by_split.get("PrivateTest", 0) == 14


def test_scan_image_dir_unstructured(tmp_path):
    """结构 B：root/{label}/*.png，无 split。"""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow 未安装。")
    import numpy as np

    root = tmp_path / "flat"
    rng = np.random.default_rng(0)
    for label in EXPRESSION_LABELS:
        d = root / label
        d.mkdir(parents=True)
        for i in range(3):
            arr = rng.integers(0, 256, size=(48, 48), dtype=np.uint8)
            Image.fromarray(arr, mode="L").save(d / f"{i}.png")
    samples = scan_image_dir(root)
    assert len(samples) == 7 * 3
    assert all(s.usage is None for s in samples)


def test_scan_image_dir_empty_rejected(tmp_path):
    from expression_recognition.data import DatasetNotFoundError

    (tmp_path / "empty").mkdir()
    with pytest.raises(DatasetNotFoundError):
        scan_image_dir(tmp_path / "empty")
