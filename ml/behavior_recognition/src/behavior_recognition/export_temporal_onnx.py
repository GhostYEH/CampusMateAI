from __future__ import annotations

import hashlib
import json
import os
import tempfile
import warnings
from collections.abc import Mapping
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


def _artifact_set_digest(directory: Path, filenames: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for filename in sorted(filenames):
        digest.update(filename.encode("utf-8"))
        digest.update(b"\0")
        with (directory / filename).open("rb") as handle:
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
    if len(model.graph.input) != 1:
        raise ValueError("Source ONNX must have exactly one input")
    source_input = model.graph.input[0]
    if source_input.type.tensor_type.elem_type != TensorProto.FLOAT:
        raise ValueError("Source ONNX input must be float32")
    dimensions = source_input.type.tensor_type.shape.dim
    source_shape = [int(dimension.dim_value) for dimension in dimensions]
    if source_shape != [1, 3, 224, 224]:
        raise ValueError("Source ONNX input must be fixed [1, 3, 224, 224]")
    _, channels, height, width = source_shape
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


def _shape(value: onnx.ValueInfoProto) -> list[int]:
    return [int(dimension.dim_value) for dimension in value.type.tensor_type.shape.dim]


def _validate_fused_contract(model: onnx.ModelProto) -> None:
    if len(model.graph.input) != 1 or model.graph.input[0].name != "frames":
        raise ValueError("Fused ONNX must expose only the frames input")
    if _shape(model.graph.input[0]) != [1, 16, 3, 224, 224]:
        raise ValueError("Fused ONNX input must be [1, 16, 3, 224, 224]")
    if len(model.graph.output) != 1 or model.graph.output[0].name != "logits":
        raise ValueError("Fused ONNX must expose only the logits output")
    if _shape(model.graph.output[0]) != [1, 4]:
        raise ValueError("Fused ONNX output must be [1, 4]")


def _load_temporal_checkpoint(path: Path) -> dict:
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(checkpoint, dict):
        raise ValueError("Temporal checkpoint must be a mapping")
    required = {
        "epoch", "architecture", "model_state", "config", "class_names",
        "source_onnx_sha256",
    }
    missing = required - set(checkpoint)
    if missing:
        raise ValueError(f"Temporal checkpoint is missing fields: {sorted(missing)}")
    if not isinstance(checkpoint["config"], Mapping):
        raise ValueError("Temporal checkpoint config must be a mapping")
    if not isinstance(checkpoint["model_state"], Mapping):
        raise ValueError("Temporal checkpoint model_state must be a mapping")
    if tuple(checkpoint["class_names"]) != tuple(CLASS_NAMES):
        raise ValueError("Temporal checkpoint class order does not match the product contract")
    return checkpoint


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
    if parity_samples < 1:
        raise ValueError("parity_samples must be at least 1")
    checkpoint = _load_temporal_checkpoint(checkpoint_path)
    if checkpoint.get("architecture") != "mobilenet_v3_small_onnx_gru":
        raise ValueError("Checkpoint is not a frozen-ONNX temporal candidate")
    source_hash = _sha256(source_onnx_path)
    if source_hash != checkpoint.get("source_onnx_sha256"):
        raise ValueError("Source ONNX hash does not match the temporal checkpoint")
    config = checkpoint["config"]
    sequence_length = int(config.get("sequence_length", 16))
    if sequence_length != 16:
        raise ValueError("Temporal checkpoint sequence_length must be 16")
    feature_size = int(config["onnx_feature_size"])
    feature_output = str(config["onnx_feature_output"])
    hidden_size = int(config.get("hidden_size", 256))
    head = TemporalGRUHead(feature_size, hidden_size, len(CLASS_NAMES))
    head.load_state_dict(checkpoint["model_state"])
    head.eval()

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="temporal-export-", dir=output_dir.parent
    ) as temporary_directory:
        temporary_dir = Path(temporary_directory)
        staged_dir = temporary_dir / "generation"
        work_dir = temporary_dir / "work"
        staged_dir.mkdir()
        work_dir.mkdir()
        frame_model, image_shape = _prepare_frame_graph(
            source_onnx_path, feature_output, feature_size, sequence_length
        )
        head_path = work_dir / "temporal_head.onnx"
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
        _validate_fused_contract(fused)
        onnx.checker.check_model(fused)
        temporary_fused_path = staged_dir / "campusmate_behavior_gru_candidate.onnx"
        onnx.save(fused, temporary_fused_path)

        feature_model_path = work_dir / "parity_frame_features.onnx"
        create_feature_model(
            source_onnx_path,
            feature_model_path,
            feature_output,
            feature_size=feature_size,
        )
        encoder = OnnxFrameFeatureEncoder(feature_model_path, feature_output)
        fused_session = ort.InferenceSession(
            str(temporary_fused_path), providers=["CPUExecutionProvider"]
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
        if not parity["top1_match"] or maximum_error > 1e-4:
            raise RuntimeError(f"Fused temporal ONNX parity failed: {parity}")
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
            "fused_onnx_sha256": _sha256(temporary_fused_path),
            "file_size_bytes": temporary_fused_path.stat().st_size,
            "parity": parity,
            "limitations": [
                "Validated on only three independent source videos.",
                "No real-device front-camera evaluation has been completed.",
                "This artifact must not replace the Android production model without promotion checks.",
            ],
        }
        sidecars = {
            "parity.json": parity,
            "labels.json": {"classes": list(CLASS_NAMES)},
            "model_card.json": model_card,
        }
        for filename, contents in sidecars.items():
            (staged_dir / filename).write_text(
                json.dumps(contents, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        artifact_filenames = (
            "campusmate_behavior_gru_candidate.onnx",
            "parity.json",
            "labels.json",
            "model_card.json",
        )
        generation_digest = _artifact_set_digest(staged_dir, artifact_filenames)
        generation_id = generation_digest[:20]
        output_dir.mkdir(parents=True, exist_ok=True)
        generations_dir = output_dir / "generations"
        generations_dir.mkdir(exist_ok=True)
        generation_dir = generations_dir / generation_id
        if generation_dir.exists():
            if _artifact_set_digest(generation_dir, artifact_filenames) != generation_digest:
                raise RuntimeError(f"Generation directory collision: {generation_id}")
        else:
            os.replace(staged_dir, generation_dir)

        pointer = {
            "generation": generation_id,
            "model": (
                f"generations/{generation_id}/campusmate_behavior_gru_candidate.onnx"
            ),
            "fused_onnx_sha256": model_card["fused_onnx_sha256"],
        }
        pointer_path = output_dir / "current.json"
        pointer_temporary_path = output_dir / f".current-{os.getpid()}.json.tmp"
        pointer_temporary_path.write_text(
            json.dumps(pointer, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(pointer_temporary_path, pointer_path)

        legacy_names = (
            *artifact_filenames,
            "temporal_head.onnx",
            "parity_frame_features.onnx",
        )
        for legacy_name in legacy_names:
            legacy_path = output_dir / legacy_name
            if legacy_path.is_file():
                legacy_path.unlink()
    return generation_dir / "campusmate_behavior_gru_candidate.onnx"
