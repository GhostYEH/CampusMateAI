from __future__ import annotations

import hashlib
import json
import warnings
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import torch
from onnx import TensorProto, compose, helper, numpy_helper

from .constants import CLASS_NAMES, IMAGENET_MEAN, IMAGENET_STD
from .onnx_features import OnnxFrameFeatureEncoder, create_feature_model
from .temporal_models import TemporalGRUHead


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _rename_value(model: onnx.ModelProto, old: str, new: str) -> None:
    for node in model.graph.node:
        node.input[:] = [new if value == old else value for value in node.input]
        node.output[:] = [new if value == old else value for value in node.output]
    for collection in (model.graph.input, model.graph.output, model.graph.value_info):
        for value in collection:
            if value.name == old:
                value.name = new


def _prepare_frame_graph(
    source_path: Path,
    feature_output: str,
    feature_size: int,
    sequence_length: int,
) -> tuple[onnx.ModelProto, tuple[int, int, int]]:
    model = onnx.load(source_path)
    source_input = model.graph.input[0]
    dimensions = source_input.type.tensor_type.shape.dim
    channels, height, width = (int(dimensions[index].dim_value) for index in (1, 2, 3))
    if min(channels, height, width) < 1:
        raise ValueError("Source ONNX must have fixed channel and spatial dimensions")
    available = {name for node in model.graph.node for name in node.output}
    if feature_output not in available:
        raise ValueError(f"ONNX intermediate output not found: {feature_output}")

    for original_output in list(model.graph.output):
        if original_output.name != feature_output:
            _rename_value(
                model,
                original_output.name,
                f"frame_encoder_unused/{original_output.name}",
            )

    original_input_name = source_input.name
    model.graph.input.remove(source_input)
    model.graph.input.append(
        helper.make_tensor_value_info(
            "frames",
            TensorProto.FLOAT,
            [1, sequence_length, channels, height, width],
        )
    )
    frame_shape_name = "temporal_frame_shape"
    model.graph.initializer.append(
        numpy_helper.from_array(
            np.asarray([sequence_length, channels, height, width], dtype=np.int64),
            name=frame_shape_name,
        )
    )
    model.graph.node.insert(
        0,
        helper.make_node(
            "Reshape", ["frames", frame_shape_name], [original_input_name], name="FlattenFrames"
        ),
    )
    sequence_shape_name = "temporal_sequence_shape"
    model.graph.initializer.append(
        numpy_helper.from_array(
            np.asarray([1, sequence_length, feature_size], dtype=np.int64),
            name=sequence_shape_name,
        )
    )
    model.graph.node.append(
        helper.make_node(
            "Reshape",
            [feature_output, sequence_shape_name],
            ["sequence_features"],
            name="RestoreSequence",
        )
    )
    del model.graph.output[:]
    model.graph.output.append(
        helper.make_tensor_value_info(
            "sequence_features", TensorProto.FLOAT, [1, sequence_length, feature_size]
        )
    )
    onnx.checker.check_model(model)
    return model, (channels, height, width)


def _export_head(
    head: TemporalGRUHead,
    path: Path,
    sequence_length: int,
    feature_size: int,
    ir_version: int,
) -> onnx.ModelProto:
    dummy = torch.zeros(1, sequence_length, feature_size, dtype=torch.float32)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        warnings.filterwarnings("ignore", category=torch.jit.TracerWarning)
        warnings.filterwarnings(
            "ignore", message=r"Exporting a model to ONNX with a batch_size.*"
        )
        torch.onnx.export(
            head,
            dummy,
            path,
            input_names=["sequence_features"],
            output_names=["head_logits"],
            opset_version=17,
            do_constant_folding=True,
            dynamo=False,
        )
    model = onnx.load(path)
    model.ir_version = ir_version
    return model


def export_fused_temporal_candidate(
    checkpoint_path: Path,
    source_onnx_path: Path,
    output_dir: Path,
    *,
    parity_samples: int = 4,
) -> Path:
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if checkpoint.get("architecture") != "mobilenet_v3_small_onnx_gru":
        raise ValueError("Checkpoint is not a frozen-ONNX temporal candidate")
    source_hash = _sha256(source_onnx_path)
    if source_hash != checkpoint.get("source_onnx_sha256"):
        raise ValueError("Source ONNX hash does not match the temporal checkpoint")
    config = checkpoint["config"]
    sequence_length = int(config.get("sequence_length", 16))
    feature_size = int(config["onnx_feature_size"])
    feature_output = str(config["onnx_feature_output"])
    hidden_size = int(config.get("hidden_size", 256))
    head = TemporalGRUHead(feature_size, hidden_size, len(CLASS_NAMES))
    head.load_state_dict(checkpoint["model_state"])
    head.eval()

    output_dir.mkdir(parents=True, exist_ok=True)
    frame_model, image_shape = _prepare_frame_graph(
        source_onnx_path, feature_output, feature_size, sequence_length
    )
    head_path = output_dir / "temporal_head.onnx"
    head_model = _export_head(
        head, head_path, sequence_length, feature_size, frame_model.ir_version
    )
    fused = compose.merge_models(
        frame_model,
        head_model,
        io_map=[("sequence_features", "sequence_features")],
        prefix2="temporal/",
        name="CampusMateTemporalBehavior",
    )
    _rename_value(fused, "temporal/head_logits", "logits")
    fused = onnx.shape_inference.infer_shapes(fused)
    onnx.checker.check_model(fused)
    fused_path = output_dir / "campusmate_behavior_gru_candidate.onnx"
    onnx.save(fused, fused_path)

    feature_model_path = output_dir / "parity_frame_features.onnx"
    create_feature_model(
        source_onnx_path,
        feature_model_path,
        feature_output,
        feature_size=feature_size,
    )
    encoder = OnnxFrameFeatureEncoder(feature_model_path, feature_output)
    fused_session = ort.InferenceSession(
        str(fused_path), providers=["CPUExecutionProvider"]
    )
    rng = np.random.default_rng(int(config.get("seed", 20260827)))
    maximum_error = 0.0
    top1_matches = []
    channels, height, width = image_shape
    with torch.no_grad():
        for _ in range(parity_samples):
            sample = rng.normal(
                size=(1, sequence_length, channels, height, width)
            ).astype(np.float32)
            features = encoder.encode(sample.reshape(-1, channels, height, width))
            reference = head(
                torch.from_numpy(features.reshape(1, sequence_length, feature_size))
            ).numpy()
            actual = fused_session.run(["logits"], {"frames": sample})[0]
            maximum_error = max(
                maximum_error, float(np.max(np.abs(reference - actual)))
            )
            top1_matches.append(int(reference.argmax()) == int(actual.argmax()))
    parity = {
        "sample_count": parity_samples,
        "top1_match": bool(all(top1_matches)),
        "max_abs_error": maximum_error,
        "tolerance": 1e-4,
    }
    (output_dir / "parity.json").write_text(
        json.dumps(parity, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "labels.json").write_text(
        json.dumps({"classes": list(CLASS_NAMES)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    model_card = {
        "status": "offline_temporal_candidate_not_for_production",
        "architecture": "mobilenet_v3_small_gru",
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "input": {
            "name": "frames",
            "shape": [1, sequence_length, channels, height, width],
            "dtype": "float32",
            "color": "RGB",
        },
        "normalization": {"mean": IMAGENET_MEAN, "std": IMAGENET_STD},
        "output": {"name": "logits", "classes": list(CLASS_NAMES)},
        "source_onnx_sha256": source_hash,
        "checkpoint_metrics": checkpoint.get("metrics", {}),
        "fused_onnx_sha256": _sha256(fused_path),
        "file_size_bytes": fused_path.stat().st_size,
        "parity": parity,
        "limitations": [
            "Validated on only three independent source videos.",
            "No real-device front-camera evaluation has been completed.",
            "This artifact must not replace the Android production model without promotion checks.",
        ],
    }
    (output_dir / "model_card.json").write_text(
        json.dumps(model_card, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not parity["top1_match"] or maximum_error > 1e-4:
        raise RuntimeError(f"Fused temporal ONNX parity failed: {parity}")
    return fused_path
