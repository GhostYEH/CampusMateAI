import csv
import json
from pathlib import Path

import torch
import yaml
import onnx
from onnx import TensorProto, helper
from PIL import Image

from behavior_recognition.temporal_train import train_temporal_model


def _write_windows(path: Path, image_paths: list[str]) -> None:
    fields = [
        "window_id", "video_id", "track_id", "split", "target_name",
        "target_index", "frame_paths", "boxes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for label in range(4):
            writer.writerow(
                {
                    "window_id": f"w{label}", "video_id": f"400{label}",
                    "track_id": f"t{label}", "split": path.stem,
                    "target_name": str(label), "target_index": label,
                    "frame_paths": json.dumps(image_paths),
                    "boxes": json.dumps([[0.5, 0.5, 0.9, 0.9]] * len(image_paths)),
                }
            )


def test_tiny_temporal_training_saves_reloadable_checkpoint(tmp_path: Path):
    image_paths = []
    for index in range(2):
        image = tmp_path / f"frame{index}.jpg"
        Image.new("RGB", (40, 40), color=(30 + index * 50, 20, 10)).save(image)
        image_paths.append(str(image))
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    _write_windows(manifests / "train.csv", image_paths)
    _write_windows(manifests / "val.csv", image_paths)
    config = tmp_path / "config.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "seed": 7,
                "pretrained": False,
                "hidden_size": 8,
                "batch_size": 2,
                "num_workers": 0,
                "phase1_epochs": 1,
                "phase2_epochs": 0,
                "learning_rate": 0.001,
                "weight_decay": 0.0,
                "label_smoothing": 0.0,
                "amp": False,
            }
        ),
        encoding="utf-8",
    )

    checkpoint = train_temporal_model(
        config, manifests, tmp_path / "run", device_override="cpu"
    )

    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    assert checkpoint.name == "best.pt"
    assert payload["architecture"] == "mobilenet_v3_small_gru"
    assert payload["phase"] == "frozen_encoder"
    assert (tmp_path / "run" / "last.pt").is_file()
    assert (tmp_path / "run" / "history.csv").is_file()


def test_frozen_onnx_encoder_trains_gru_from_current_features(tmp_path: Path):
    image_paths = []
    for index in range(2):
        image = tmp_path / f"onnx_frame{index}.jpg"
        Image.new("RGB", (40, 40), color=(30 + index * 50, 20, 10)).save(image)
        image_paths.append(str(image))
    manifests = tmp_path / "onnx_manifests"
    manifests.mkdir()
    _write_windows(manifests / "train.csv", image_paths)
    _write_windows(manifests / "val.csv", image_paths)

    source_onnx = tmp_path / "source.onnx"
    input_info = helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 3, 224, 224])
    output_info = helper.make_tensor_value_info("logits", TensorProto.FLOAT, [1, 3])
    nodes = [
        helper.make_node("GlobalAveragePool", ["input"], ["pooled"]),
        helper.make_node("Flatten", ["pooled"], ["features"], axis=1),
        helper.make_node("Identity", ["features"], ["logits"]),
    ]
    model = helper.make_model(
        helper.make_graph(nodes, "tiny", [input_info], [output_info]),
        opset_imports=[helper.make_opsetid("", 17)],
    )
    model.ir_version = 10
    onnx.save(model, source_onnx)
    config = tmp_path / "onnx_config.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "seed": 7, "encoder_mode": "onnx_frozen", "hidden_size": 8,
                "onnx_feature_output": "features", "onnx_feature_size": 3,
                "batch_size": 2, "num_workers": 0, "phase1_epochs": 1,
                "phase2_epochs": 0, "learning_rate": 0.001,
                "weight_decay": 0.0, "label_smoothing": 0.0, "amp": False,
            }
        ),
        encoding="utf-8",
    )

    checkpoint = train_temporal_model(
        config,
        manifests,
        tmp_path / "onnx_run",
        source_onnx_override=source_onnx,
        device_override="cpu",
    )

    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    assert payload["architecture"] == "mobilenet_v3_small_onnx_gru"
    assert payload["source_onnx_sha256"]
    assert (tmp_path / "onnx_run" / "frame_features.onnx").is_file()
