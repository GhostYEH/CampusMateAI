import json
from pathlib import Path

import torch
import yaml

from behavior_recognition.export_onnx import export_candidate
from behavior_recognition.models import build_model


def test_exported_onnx_matches_pytorch(tmp_path: Path):
    """Catches label/order or operator drift between PyTorch and ONNX Runtime."""
    model = build_model(num_classes=4, pretrained=False)
    checkpoint = tmp_path / "best.pt"
    config = {"input_mode": "roi", "seed": 20260823, "pretrained": False}
    torch.save(
        {"epoch": 1, "model_state": model.state_dict(), "config": config, "class_names": (
            "READ", "WRITE", "PHONE_INTERACTION", "NO_VISIBLE_STUDY"
        )},
        checkpoint,
    )
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    onnx_path = export_candidate(checkpoint, config_path, tmp_path / "export", parity_samples=2)
    parity = json.loads((tmp_path / "export" / "parity.json").read_text(encoding="utf-8"))
    assert onnx_path.exists()
    assert parity["top1_match"] is True
    assert parity["max_abs_error"] <= 1e-4
