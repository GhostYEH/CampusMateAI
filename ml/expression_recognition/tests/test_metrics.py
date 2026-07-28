"""指标函数测试（纯 numpy，不依赖 torch）。

禁止写死指标、用占位随机数——这里用已知预测/标签验证指标公式正确。
"""

import numpy as np

from expression_recognition.evaluation.metrics import (
    accuracy,
    macro_f1,
    per_class_precision_recall,
    confusion_matrix,
    compute_metrics,
)
from expression_recognition.constants import EXPRESSION_LABELS, NUM_CLASSES


def test_accuracy_perfect():
    targets = [0, 1, 2, 3, 4, 5, 6]
    assert accuracy(targets, targets) == 1.0


def test_accuracy_known():
    # index: 0,1,2,3,5 命中（5 个对）；4,6 错（2 个错）-> 5/7
    targets = [0, 1, 2, 3, 4, 5, 6]
    preds = [0, 1, 2, 3, 5, 5, 5]
    assert abs(accuracy(targets, preds) - 5 / 7) < 1e-9


def test_confusion_matrix_shape_and_entries():
    targets = [0, 0, 1, 1, 2]
    preds = [0, 1, 1, 1, 2]
    cm = confusion_matrix(targets, preds, num_classes=NUM_CLASSES)
    assert cm.shape == (NUM_CLASSES, NUM_CLASSES)
    assert cm[0, 0] == 1 and cm[0, 1] == 1
    assert cm[1, 1] == 2
    assert cm[2, 2] == 1


def test_per_class_precision_recall():
    # 类 0: TP=2, FP=1, FN=1 -> P=2/3, R=2/3
    targets = [0, 0, 0, 1, 1, 1, 2, 2, 2]
    preds =   [0, 0, 1, 0, 1, 1, 2, 2, 2]
    pc = per_class_precision_recall(targets, preds, NUM_CLASSES)
    assert abs(pc[0]["precision"] - 2 / 3) < 1e-9
    assert abs(pc[0]["recall"] - 2 / 3) < 1e-9
    # 类 1: TP=2, FP=1, FN=1
    assert abs(pc[1]["precision"] - 2 / 3) < 1e-9
    assert abs(pc[1]["recall"] - 2 / 3) < 1e-9
    # 类 2: TP=3, FP=0, FN=0 -> P=1, R=1
    assert pc[2]["precision"] == 1.0
    assert pc[2]["recall"] == 1.0
    assert pc[2]["support"] == 3


def test_macro_f1_perfect():
    targets = [0, 1, 2, 3, 4, 5, 6]
    assert macro_f1(targets, targets, NUM_CLASSES) == 1.0


def test_compute_metrics_structure():
    rng = np.random.default_rng(0)
    targets = rng.integers(0, NUM_CLASSES, size=50).tolist()
    preds = rng.integers(0, NUM_CLASSES, size=50).tolist()
    m = compute_metrics(targets, preds, label_names=list(EXPRESSION_LABELS))
    assert set(m.keys()) >= {"accuracy", "macro_f1", "label_order", "per_class",
                              "confusion_matrix", "num_samples"}
    assert m["label_order"] == list(EXPRESSION_LABELS)
    assert len(m["confusion_matrix"]) == NUM_CLASSES
    assert m["num_samples"] == 50
    for name in EXPRESSION_LABELS:
        assert set(m["per_class"][name].keys()) >= {"precision", "recall", "f1", "support"}


def test_shape_mismatch_rejected():
    import pytest

    with pytest.raises(ValueError):
        accuracy([0, 1, 2], [0, 1])


def test_empty_rejected():
    import pytest

    with pytest.raises(ValueError):
        accuracy([], [])


def test_label_out_of_range_rejected():
    import pytest

    with pytest.raises(ValueError):
        accuracy([NUM_CLASSES], [0])
