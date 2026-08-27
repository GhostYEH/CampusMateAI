import hashlib
import json
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import torch
from onnx import TensorProto, helper

from behavior_recognition.export_temporal_onnx import export_fused_temporal_candidate
from behavior_recognition.temporal_models import TemporalGRUHead


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_frame_encoder(path: Path, input_shape=(1, 3, 224, 224)) -> None:
    input_info = helper.make_tensor_value_info("input", TensorProto.FLOAT, list(input_shape))
    output_info = helper.make_tensor_value_info("logits", TensorProto.FLOAT, [1, 3])
    graph = helper.make_graph(
        [
            helper.make_node("GlobalAveragePool", ["input"], ["pooled"]),
            helper.make_node("Flatten", ["pooled"], ["features"], axis=1),
            helper.make_node("Identity", ["features"], ["logits"]),
        ],
        "frame_encoder",
        [input_info],
        [output_info],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 10
    onnx.save(model, path)


def test_fused_temporal_onnx_matches_frame_encoder_plus_gru(tmp_path: Path):
    source = tmp_path / "frame_encoder.onnx"
    _write_frame_encoder(source)
    torch.manual_seed(7)
    head = TemporalGRUHead(input_size=3, hidden_size=4, num_classes=4)
    checkpoint = tmp_path / "best.pt"
    torch.save(
        {
            "epoch": 3,
            "phase": "frozen_encoder",
            "architecture": "mobilenet_v3_small_onnx_gru",
            "model_state": head.state_dict(),
            "config": {
                "hidden_size": 4,
                "onnx_feature_output": "features",
                "onnx_feature_size": 3,
                "sequence_length": 16,
            },
            "class_names": ("READ", "WRITE", "PHONE_INTERACTION", "NO_VISIBLE_STUDY"),
            "source_onnx_sha256": _sha256(source),
        },
        checkpoint,
    )

    fused_path = export_fused_temporal_candidate(
        checkpoint,
        source,
        tmp_path / "export",
        parity_samples=2,
    )

    model = onnx.load(fused_path)
    input_shape = [dimension.dim_value for dimension in model.graph.input[0].type.tensor_type.shape.dim]
    session = ort.InferenceSession(str(fused_path), providers=["CPUExecutionProvider"])
    output = session.run(
        ["logits"], {"frames": np.zeros((1, 16, 3, 224, 224), np.float32)}
    )[0]
    parity = json.loads((tmp_path / "export" / "parity.json").read_text(encoding="utf-8"))

    assert input_shape == [1, 16, 3, 224, 224]
    assert output.shape == (1, 4)
    assert parity["top1_match"] is True
    assert parity["max_abs_error"] <= 1e-4
    assert (tmp_path / "export" / "model_card.json").is_file()
    assert sorted(path.suffix for path in (tmp_path / "export").iterdir()) == [
        ".json", ".json", ".json", ".onnx"
    ]


def test_fused_export_rejects_disabled_parity(tmp_path: Path):
    with torch.no_grad():
        try:
            export_fused_temporal_candidate(
                tmp_path / "missing.pt",
                tmp_path / "missing.onnx",
                tmp_path / "export",
                parity_samples=0,
            )
        except ValueError as error:
            assert "parity_samples" in str(error)
        else:
            raise AssertionError("zero parity samples must be rejected")


def test_fused_export_rejects_nonproduction_frame_shape(tmp_path: Path):
    source = tmp_path / "wrong_shape.onnx"
    _write_frame_encoder(source, input_shape=(1, 3, 4, 4))
    head = TemporalGRUHead(input_size=3, hidden_size=4, num_classes=4)
    checkpoint = tmp_path / "best.pt"
    torch.save(
        {
            "epoch": 1,
            "phase": "frozen_encoder",
            "architecture": "mobilenet_v3_small_onnx_gru",
            "model_state": head.state_dict(),
            "config": {
                "hidden_size": 4,
                "onnx_feature_output": "features",
                "onnx_feature_size": 3,
                "sequence_length": 16,
            },
            "class_names": ("READ", "WRITE", "PHONE_INTERACTION", "NO_VISIBLE_STUDY"),
            "source_onnx_sha256": _sha256(source),
        },
        checkpoint,
    )

    try:
        export_fused_temporal_candidate(checkpoint, source, tmp_path / "export")
    except ValueError as error:
        assert "[1, 3, 224, 224]" in str(error)
    else:
        raise AssertionError("non-production source shape must be rejected")
