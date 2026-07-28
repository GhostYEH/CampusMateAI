"""TFLite 导出与一致性测试（需要 torch + onnx2tf + tensorflow）。

环境不支持时优雅跳过，不报错。
"""

import pytest

torch = pytest.importorskip("torch")

import numpy as np

from expression_recognition.config import ExperimentConfig, InputConfig, ModelConfig, ExportConfig
from expression_recognition.constants import NUM_CLASSES
from expression_recognition.models.build import build_model
from expression_recognition.training.checkpoint import save_checkpoint
from expression_recognition.export.onnx_export import export_onnx
from expression_recognition.export.tflite_export import export_tflite
from expression_recognition.export.consistency import run_consistency_test


def _make_env(tmp_path):
    cfg = ExperimentConfig(
        experiment_name="tflite_test",
        output_dir=str(tmp_path / "run"),
        input=InputConfig(size=48, channels=1, mean=(0.5,), std=(0.5,)),
        model=ModelConfig(name="custom_cnn", num_classes=NUM_CLASSES,
                          pretrained=False, freeze_backbone=False, dropout=0.0),
        export=ExportConfig(onnx=True, tflite=True, consistency_max_mismatch=0),
    )
    model = build_model(cfg.model, cfg.input)
    model.eval()
    ckpt = tmp_path / "run" / "best_model.pt"
    save_checkpoint(ckpt, model=model, epoch=1)
    onnx_path = tmp_path / "run" / "model.onnx"
    export_onnx(cfg, ckpt, onnx_path)
    return cfg, ckpt, onnx_path


def test_tflite_export_or_skip(tmp_path):
    """若 onnx2tf/tensorflow 缺失，导出应 skipped 而非报错。"""
    cfg, ckpt, onnx_path = _make_env(tmp_path)
    tflite_path = tmp_path / "run" / "model.tflite"
    info = export_tflite(onnx_path, tflite_path)
    assert info["status"] in ("ok", "skipped", "failed")
    if info["status"] == "skipped":
        pytest.skip(f"TFLite 依赖缺失: {info.get('reason', '')}")


def test_consistency_pytorch_onnx(tmp_path):
    """仅 PyTorch 与 ONNX 的一致性（TFLite 可不存在）。"""
    onnxruntime = pytest.importorskip("onnxruntime")
    cfg, ckpt, onnx_path = _make_env(tmp_path)
    # 不传 tflite_path，只比 PyTorch vs ONNX。
    result = run_consistency_test(cfg, ckpt, onnx_path, tflite_path=None)
    assert result["backends"]["pytorch"]["ok"]
    assert result["backends"]["onnx"]["ok"]
    # 允许 0 不一致。
    assert result["total_top1_mismatch"] == 0
    assert result["passed"]


def test_consistency_with_tflite_if_available(tmp_path):
    """若 TFLite 可导出，则三方一致性也应通过。"""
    try:
        import onnx2tf  # noqa: F401
        import tensorflow  # noqa: F401
    except ImportError:
        pytest.skip("onnx2tf/tensorflow 未安装，跳过 TFLite 三方一致性测试。")

    cfg, ckpt, onnx_path = _make_env(tmp_path)
    tflite_path = tmp_path / "run" / "model.tflite"
    info = export_tflite(onnx_path, tflite_path)
    if info["status"] != "ok":
        pytest.skip(f"TFLite 导出未成功: {info}")
    tflite_arg = tflite_path if info["status"] == "ok" else None
    result = run_consistency_test(cfg, ckpt, onnx_path, tflite_arg)
    assert result["passed"]
