"""数据缺失时错误信息测试。

工程不自动下载来历不明的数据；缺失时必须给出明确错误。
"""

import pytest

from expression_recognition.data import (
    load_samples,
    parse_fer2013_csv,
    scan_image_dir,
    DatasetNotFoundError,
)


def test_csv_missing_raises(tmp_path):
    with pytest.raises(DatasetNotFoundError, match="不自动下载"):
        parse_fer2013_csv(tmp_path / "nonexistent.csv")


def test_image_dir_missing_raises(tmp_path):
    with pytest.raises(DatasetNotFoundError, match="不自动下载"):
        scan_image_dir(tmp_path / "nonexistent")


def test_load_samples_unknown_format(tmp_path):
    with pytest.raises(ValueError):
        load_samples(tmp_path, "unknown_format")


def test_load_samples_csv_missing_message(tmp_path):
    """错误信息应包含放置数据的提示。"""
    try:
        load_samples(tmp_path, "fer2013_csv", "fer2013.csv")
    except DatasetNotFoundError as e:
        msg = str(e)
        assert "fer2013.csv" in msg or "CSV" in msg
        assert "不自动下载" in msg
    else:
        pytest.fail("应抛出 DatasetNotFoundError")
