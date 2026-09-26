"""Validation-only comparison for the offline local-cue behavior ablation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import average_precision_score, confusion_matrix, f1_score
from torch.utils.data import DataLoader

from .constants import CLASS_NAMES, PRODUCT_CLASS_NAMES
from .data import BehaviorDataset
from .metrics import project_product_probabilities, softmax
from .models import build_experiment_model


def collect_logits(model, dataset, device: torch.device) -> tuple[np.ndarray, np.ndarray]:
    logits = []
    labels = []
    with torch.inference_mode():
        for images, targets in DataLoader(dataset, batch_size=32, shuffle=False, num_workers=0):
            logits.append(model(images.to(device)).cpu().numpy())
            labels.append(targets.numpy())
    return np.concatenate(logits), np.concatenate(labels)


def validation_metrics(checkpoint_path: Path, manifest: Path, device: torch.device) -> dict:
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    config = checkpoint["config"]
    if config.get("input_mode", "roi") != "roi":
        raise ValueError("Local-cue comparison requires ROI-trained checkpoints")
    model = build_experiment_model({**config, "pretrained": False}, len(CLASS_NAMES))
    model.load_state_dict(checkpoint["model_state"])
    model.to(device).eval()
    dataset = BehaviorDataset(manifest, mode="roi", training=False)
    logits, labels = collect_logits(model, dataset, device)
    probabilities = softmax(logits)
    predictions = probabilities.argmax(axis=1)
    product_labels, product_probabilities = project_product_probabilities(labels, probabilities, CLASS_NAMES)
    phone_index = CLASS_NAMES.index("PHONE_INTERACTION")
    phone_truth = labels == phone_index
    return {
        "checkpoint": str(checkpoint_path.resolve()),
        "model_variant": config.get("model_variant", "mobilenet_v3_small"),
        "sample_count": int(len(labels)),
        "macro_f1": float(f1_score(labels, predictions, labels=list(range(len(CLASS_NAMES))), average="macro", zero_division=0)),
        "phone_auprc": float(average_precision_score(phone_truth, probabilities[:, phone_index])) if phone_truth.any() else None,
        "phone_precision": float(np.sum((predictions == phone_index) & phone_truth) / max(1, np.sum(predictions == phone_index))),
        "phone_recall": float(np.sum((predictions == phone_index) & phone_truth) / max(1, np.sum(phone_truth))),
        "product_macro_f1": float(f1_score(product_labels, product_probabilities.argmax(axis=1), labels=list(range(len(PRODUCT_CLASS_NAMES))), average="macro", zero_division=0)),
        "confusion_matrix": confusion_matrix(labels, predictions, labels=list(range(len(CLASS_NAMES)))).tolist(),
    }


def compare(baseline: Path, local_cue: Path, manifest_dir: Path, output: Path, *, cpu: bool = False) -> dict:
    if output.resolve() in {baseline.resolve(), local_cue.resolve(), (manifest_dir / "val.csv").resolve()}:
        raise ValueError("Output cannot overwrite an input")
    manifest = manifest_dir / "val.csv"
    if not manifest.is_file():
        raise FileNotFoundError(f"Missing validation manifest: {manifest}")
    baseline_config = torch.load(baseline, map_location="cpu", weights_only=False)["config"]
    local_config = torch.load(local_cue, map_location="cpu", weights_only=False)["config"]
    baseline_settings = {key: value for key, value in baseline_config.items() if key != "model_variant"}
    local_settings = {key: value for key, value in local_config.items() if key != "model_variant"}
    if baseline_settings != local_settings:
        raise ValueError("Baseline and local-cue checkpoints must use matching training settings")
    device = torch.device("cpu" if cpu or not torch.cuda.is_available() else "cuda")
    before = validation_metrics(baseline, manifest, device)
    after = validation_metrics(local_cue, manifest, device)
    if before["model_variant"] != "mobilenet_v3_small" or after["model_variant"] != "local_cue":
        raise ValueError("Expected a baseline checkpoint followed by a local-cue checkpoint")
    report = {
        "scope": "validation_only_offline_ablation",
        "production_approved": False,
        "baseline": before,
        "local_cue": after,
        "delta": {
            key: after[key] - before[key]
            for key in ("macro_f1", "phone_auprc", "phone_precision", "phone_recall", "product_macro_f1")
            if after[key] is not None and before[key] is not None
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare full-ROI and local-cue behavior checkpoints on validation only.")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--local-cue", type=Path, required=True)
    parser.add_argument("--manifests", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cpu", action="store_true")
    args = parser.parse_args()
    print(json.dumps(compare(args.baseline, args.local_cue, args.manifests, args.output, cpu=args.cpu), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
