from __future__ import annotations

import hashlib
import json
import warnings
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
import yaml

from .constants import CLASS_NAMES, IMAGE_SIZE, IMAGENET_MEAN, IMAGENET_STD
from .models import build_model, parameter_count


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_candidate(
    checkpoint_path: Path,
    config_path: Path,
    output_dir: Path,
    parity_samples: int = 32,
) -> Path:
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    model = build_model(len(CLASS_NAMES), pretrained=False)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    output_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = output_dir / "campusmate_behavior_v34_candidate.onnx"
    dummy = torch.zeros(1, 3, IMAGE_SIZE, IMAGE_SIZE, dtype=torch.float32)
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"You are using the legacy TorchScript-based ONNX export.*",
            category=DeprecationWarning,
        )
        warnings.filterwarnings("ignore", category=DeprecationWarning, module=r"torch\.onnx.*")
        torch.onnx.export(
            model,
            dummy,
            onnx_path,
            input_names=["input"],
            output_names=["logits"],
            opset_version=17,
            do_constant_folding=True,
            dynamo=False,
        )
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    rng = np.random.default_rng(int(config.get("seed", 20260823)))
    maximum_error = 0.0
    top1_matches = []
    with torch.no_grad():
        for _ in range(parity_samples):
            sample = rng.normal(size=(1, 3, IMAGE_SIZE, IMAGE_SIZE)).astype(np.float32)
            pytorch_logits = model(torch.from_numpy(sample)).numpy()
            onnx_logits = session.run(["logits"], {"input": sample})[0]
            maximum_error = max(maximum_error, float(np.max(np.abs(pytorch_logits - onnx_logits))))
            top1_matches.append(int(pytorch_logits.argmax()) == int(onnx_logits.argmax()))
    parity = {
        "sample_count": parity_samples,
        "top1_match": bool(all(top1_matches)),
        "max_abs_error": maximum_error,
        "tolerance": 1e-4,
    }
    (output_dir / "parity.json").write_text(
        json.dumps(parity, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    labels = {"classes": list(CLASS_NAMES), "uncertain_index": -1}
    (output_dir / "labels.json").write_text(
        json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    model_card = {
        "status": "offline_candidate_not_for_production",
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "input": {"shape": [1, 3, IMAGE_SIZE, IMAGE_SIZE], "dtype": "float32", "color": "RGB"},
        "normalization": {"mean": IMAGENET_MEAN, "std": IMAGENET_STD},
        "output_classes": list(CLASS_NAMES),
        "input_mode": config.get("input_mode", "roi"),
        "opset": 17,
        "parameter_count": parameter_count(model),
        "file_size_bytes": onnx_path.stat().st_size,
        "sha256": _sha256(onnx_path),
        "parity": parity,
        "limitations": [
            "Trained on distant multi-student classroom images.",
            "No real-device/front-camera validation has been completed.",
            "PHONE_INTERACTION does not establish non-learning intent.",
        ],
    }
    (output_dir / "model_card.json").write_text(
        json.dumps(model_card, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not parity["top1_match"] or maximum_error > 1e-4:
        raise RuntimeError(f"ONNX parity failed: {parity}")
    return onnx_path
