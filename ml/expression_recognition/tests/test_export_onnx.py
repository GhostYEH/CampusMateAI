"""ONNX 导出与推理测试（需要 torch + onnxruntime）。

torch 未安装时整文件跳过；onnxruntime 缺失则相应断言跳过。
"""

import pytest

torch = pytest.importorskip("torch")

import numpy as np

from expression_recognition.config import ExperimentConfig, InputConfig, ModelConfig
from expression_recognition.constants import NUM_CLASSES
from expression_recognition.models.build import build_model, dummy_input
from expression_recognition.training.checkpoint import save_checkpoint
from expression_recognition.export.onnx_export import export_onnx


def _make_cfg_and_ckpt(tmp_path):
    cfg = ExperimentConfig(
        experiment_name="onnx_test",
        output_dir=str(tmp_path / "run"),
        input=InputConfig(size=48, channels=1, mean=(0.5,), std=(0.5,)),
        model=ModelConfig(name="custom_cnn", num_classes=NUM_CLASSES,
                          pretrained=False, freeze_backbone=False, dropout=0.0),
    )
    model = build_model(cfg.model, cfg.input)
    model.eval()
    ckpt = tmp_path / "run" / "best_model.pt"
    save_checkpoint(ckpt, model=model, epoch=1)
    return cfg, ckpt, model


def test_onnx_export_and_inference(tmp_path):
    onnxruntime = pytest.importorskip("onnxruntime")
    cfg, ckpt, model = _make_cfg_and_ckpt(tmp_path)
    onnx_path = tmp_path / "run" / "model.onnx"
    info = export_onnx(cfg, ckpt, onnx_path)
    assert info["onnxruntime_ok"]
    assert info["onnxruntime_output_shape"] == [1, NUM_CLASSES]

    # 数值一致性：固定输入比较 PyTorch 与 ONNX 输出。
    import onnxruntime as ort

    torch.manual_seed(0)
    x = torch.randn(4, 1, 48, 48)
    with torch.no_grad():
        pt_out = model(x).numpy()
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    onx_out = sess.run(["logits"], {"input": x.numpy()})[0]
    # 数值允许小误差。
    assert np.allclose(pt_out, onx_out, atol=1e-4, rtol=1e-3)
    # Top-1 标签应完全一致。
    assert (pt_out.argmax(1) == onx_out.argmax(1)).all()


def test_onnx_dynamic_batch(tmp_path):
    onnxruntime = pytest.importorskip("onnxruntime")
    cfg, ckpt, _ = _make_cfg_and_ckpt(tmp_path)
    onnx_path = tmp_path / "run" / "model.onnx"
    export_onnx(cfg, ckpt, onnx_path)
    import onnxruntime as ort

    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    # batch=3 应可推理。
    x = np.zeros((3, 1, 48, 48), dtype=np.float32)
    out = sess.run(["logits"], {"input": x})[0]
    assert out.shape == (3, NUM_CLASSES)


def test_labels_and_preprocess_json(tmp_path):
    """导出 labels.json / preprocess.json 不需要 torch 训练，结构正确。"""
    from expression_recognition.export.labels import export_labels_json
    from expression_recognition.export.preprocess import export_preprocess_json

    labels = export_labels_json(tmp_path / "labels.json")
    assert labels["num_classes"] == 7
    assert labels["label_order"][0] == "angry"
    assert "科学边界" in labels["scientific_boundary"] or "表情" in labels["scientific_boundary"]

    inp = InputConfig(size=48, channels=1, mean=(0.5,), std=(0.5,))
    pp = export_preprocess_json(tmp_path / "preprocess.json", inp)
    assert pp["input_size"] == [1, 48, 48]
    assert pp["normalization"]["mean"] == [0.5]
    assert pp["label_order"] == labels["label_order"]
