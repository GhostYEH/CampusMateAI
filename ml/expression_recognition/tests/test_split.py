"""划分测试：分层随机、计数、防泄漏说明。"""

import pytest

from expression_recognition.data import parse_fer2013_csv, split_samples, LEAKAGE_NOTE
from expression_recognition.constants import NUM_CLASSES


def test_split_uses_official_usage(synthetic_csv):
    samples = parse_fer2013_csv(synthetic_csv)
    sr = split_samples(samples)
    assert sr.method == "official_usage"
    # 每类 8 train + 2 val + 2 test。
    assert len(sr.train) == 7 * 8
    assert len(sr.val) == 7 * 2
    assert len(sr.test) == 7 * 2


def test_split_stratified_random(synthetic_csv_no_usage):
    samples = parse_fer2013_csv(synthetic_csv_no_usage)
    sr = split_samples(
        samples, train_ratio=0.8, val_ratio=0.1, test_ratio=0.1,
        stratified=True, split_seed=42,
    )
    assert sr.method == "stratified_random"
    # 每类 10 条 -> 8/1/1。
    counts = sr.counts_by_split_label()
    for i in range(NUM_CLASSES):
        assert counts["train"][i] == 8
        assert counts["val"][i] == 1
        assert counts["test"][i] == 1


def test_split_reproducible(synthetic_csv_no_usage):
    samples = parse_fer2013_csv(synthetic_csv_no_usage)
    sr1 = split_samples(samples, split_seed=123)
    sr2 = split_samples(samples, split_seed=123)
    assert [s.label for s in sr1.train] == [s.label for s in sr2.train]
    assert [s.label for s in sr1.val] == [s.label for s in sr2.val]


def test_split_different_seed_differs(synthetic_csv_no_usage):
    samples = parse_fer2013_csv(synthetic_csv_no_usage)
    sr1 = split_samples(samples, split_seed=1)
    sr2 = split_samples(samples, split_seed=2)
    # 标签序列应不同（极小概率相同）。
    assert [s.label for s in sr1.train] != [s.label for s in sr2.train]


def test_split_preserves_all_samples(synthetic_csv_no_usage):
    samples = parse_fer2013_csv(synthetic_csv_no_usage)
    n = len(samples)
    sr = split_samples(samples)
    assert len(sr.train) + len(sr.val) + len(sr.test) == n


def test_leakage_note_present():
    assert "受试者" in LEAKAGE_NOTE or "subject" in LEAKAGE_NOTE.lower()
    assert "FER2013" in LEAKAGE_NOTE


def test_split_empty_rejected():
    with pytest.raises(ValueError):
        split_samples([])
