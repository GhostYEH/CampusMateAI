"""检查点保存与加载测试（需要 torch）。"""

import pytest

torch = pytest.importorskip("torch")

from expression_recognition.config import InputConfig, ModelConfig
from expression_recognition.constants import NUM_CLASSES, EXPRESSION_LABELS
from expression_recognition.models.build import build_model
from expression_recognition.training.checkpoint import save_checkpoint, load_checkpoint
from expression_recognition.training.early_stopping import EarlyStopping


def _build():
    cfg = ModelConfig(name="custom_cnn", num_classes=NUM_CLASSES, pretrained=False,
                      freeze_backbone=False, dropout=0.0)
    inp = InputConfig(size=48, channels=1, mean=(0.5,), std=(0.5,))
    return build_model(cfg, inp)


def test_save_load_roundtrip(tmp_path):
    model = _build()
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
    ckpt = tmp_path / "ckpt.pt"
    save_checkpoint(ckpt, model=model, optimizer=opt, epoch=5,
                    best_metric=0.42, metric_name="val_macro_f1")

    model2 = _build()
    opt2 = torch.optim.AdamW(model2.parameters(), lr=1e-3)
    meta = load_checkpoint(ckpt, model=model2, optimizer=opt2)
    assert meta["epoch"] == 5
    assert meta["best_metric"] == pytest.approx(0.42)
    assert meta["metric_name"] == "val_macro_f1"

    # 权重应一致。
    for p1, p2 in zip(model.parameters(), model2.parameters()):
        assert torch.allclose(p1, p2)


def test_checkpoint_label_order_guarded(tmp_path):
    """模拟标签顺序不一致，应拒绝加载。"""
    model = _build()
    ckpt = tmp_path / "ckpt.pt"
    save_checkpoint(ckpt, model=model, epoch=1)
    # 篡改 label_order。
    state = torch.load(ckpt, map_location="cpu", weights_only=False)
    bad = list(EXPRESSION_LABELS)
    bad[0], bad[1] = bad[1], bad[0]
    state["label_order"] = bad
    torch.save(state, ckpt)
    model2 = _build()
    with pytest.raises(ValueError, match="标签顺序"):
        load_checkpoint(ckpt, model=model2)


def test_checkpoint_num_classes_guarded(tmp_path):
    model = _build()
    ckpt = tmp_path / "ckpt.pt"
    save_checkpoint(ckpt, model=model, epoch=1)
    state = torch.load(ckpt, map_location="cpu", weights_only=False)
    state["num_classes"] = 99
    torch.save(state, ckpt)
    model2 = _build()
    with pytest.raises(ValueError, match="num_classes"):
        load_checkpoint(ckpt, model=model2)


def test_early_stopping_maximize():
    es = EarlyStopping(patience=2, mode="maximize")
    assert es.step(0.5)        # best
    assert es.step(0.6)        # best
    assert not es.step(0.55)   # wait 1
    assert not es.step(0.55)   # wait 2 -> stop
    assert es.should_stop


def test_early_stopping_minimize():
    es = EarlyStopping(patience=1, mode="minimize")
    assert es.step(1.0)
    assert es.step(0.8)
    assert not es.step(0.9)   # wait 1 -> stop
    assert es.should_stop


def test_early_stopping_disabled():
    es = EarlyStopping(patience=0)
    es.step(0.1)
    es.step(0.1)
    assert not es.should_stop
