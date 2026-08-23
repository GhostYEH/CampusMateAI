from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from torch.utils.data import DataLoader

from .calibrate import search_rejection_thresholds
from .constants import CLASS_NAMES
from .data import BehaviorDataset, materialize_roi_cache
from .metrics import apply_rejection, classification_report, fit_temperature, softmax
from .models import build_model


def collect_logits(model, dataset, device: torch.device, batch_size: int = 64):
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    model.eval()
    logits: list[np.ndarray] = []
    labels: list[np.ndarray] = []
    with torch.no_grad():
        for inputs, targets in loader:
            output = model(inputs.to(device)).detach().cpu().numpy()
            logits.append(output)
            labels.append(targets.numpy())
    return np.concatenate(logits), np.concatenate(labels)


def expected_v32_label(target_index: int) -> int:
    return 1 if target_index in (0, 1) else 0


def collapsed_binary_report(labels: np.ndarray, probabilities: np.ndarray) -> dict:
    expected = np.asarray([expected_v32_label(int(value)) for value in labels], dtype=np.int64)
    top1 = np.asarray(probabilities).argmax(axis=1)
    predicted = np.asarray([expected_v32_label(int(value)) for value in top1], dtype=np.int64)
    return {
        "output_space": ["IDLE", "VISIBLE_STUDY"],
        "accuracy": float(accuracy_score(expected, predicted)),
        "macro_f1": float(f1_score(expected, predicted, average="macro", zero_division=0)),
        "confusion_matrix": confusion_matrix(expected, predicted, labels=[0, 1]).tolist(),
        "sample_count": int(len(expected)),
        "note": "Candidate Top-1 collapsed to the packaged V3.2 binary semantics.",
    }


def evaluate_v32(model_path: Path, dataset, batch_size: int = 64) -> dict:
    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    input_meta = session.get_inputs()[0]
    input_name = input_meta.name
    fixed_batch = input_meta.shape[0] if isinstance(input_meta.shape[0], int) else None
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    probabilities = []
    labels = []
    for inputs, targets in loader:
        batch = inputs.numpy().astype(np.float32)
        if fixed_batch == 1 and len(batch) != 1:
            logits = np.concatenate(
                [session.run(None, {input_name: sample[None]})[0] for sample in batch], axis=0
            )
        else:
            logits = session.run(None, {input_name: batch})[0]
        probabilities.append(softmax(logits))
        labels.extend(expected_v32_label(int(value)) for value in targets)
    merged = np.concatenate(probabilities)
    expected = np.asarray(labels, dtype=np.int64)
    predicted = merged.argmax(axis=1)
    return {
        "output_space": ["IDLE", "VISIBLE_STUDY"],
        "accuracy": float(accuracy_score(expected, predicted)),
        "macro_f1": float(f1_score(expected, predicted, average="macro", zero_division=0)),
        "sample_count": int(len(expected)),
        "note": "Binary diagnostic on the same transformed samples; not four-class accuracy.",
    }


def evaluate_checkpoint(
    checkpoint_path: Path,
    manifest_dir: Path,
    output_path: Path,
    compare_v32: Path | None = None,
    input_mode: str | None = None,
) -> dict:
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    config = checkpoint["config"]
    mode = input_mode or config.get("input_mode", "roi")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_model(len(CLASS_NAMES), pretrained=False)
    model.load_state_dict(checkpoint["model_state"])
    model.to(device)
    cache_dir = manifest_dir.parent / "artifacts" / "roi-cache" if mode == "roi" else None
    if cache_dir is not None:
        import csv

        rows = []
        for name in ("val.csv", "test.csv"):
            with (manifest_dir / name).open(encoding="utf-8", newline="") as handle:
                rows.extend(csv.DictReader(handle))
        materialize_roi_cache(rows, cache_dir)
    val_dataset = BehaviorDataset(manifest_dir / "val.csv", mode=mode, training=False, cache_dir=cache_dir)
    test_dataset = BehaviorDataset(manifest_dir / "test.csv", mode=mode, training=False, cache_dir=cache_dir)
    val_logits, val_labels = collect_logits(model, val_dataset, device)
    test_logits, test_labels = collect_logits(model, test_dataset, device)
    temperature = fit_temperature(val_logits, val_labels)
    val_calibrated = softmax(val_logits, temperature)
    rejection = search_rejection_thresholds(val_calibrated, val_labels)
    uncalibrated = softmax(test_logits)
    calibrated = softmax(test_logits, temperature)
    rejected = apply_rejection(
        calibrated,
        np.asarray(rejection["class_thresholds"], dtype=np.float32),
        float(rejection["margin_threshold"]),
    )
    accepted = rejected >= 0
    rejected_report = {
        "coverage": float(accepted.mean()),
        "accepted_count": int(accepted.sum()),
        "rejected_count": int((~accepted).sum()),
        "accepted_macro_f1": float(
            f1_score(
                test_labels[accepted],
                rejected[accepted],
                labels=list(range(len(CLASS_NAMES))),
                average="macro",
                zero_division=0,
            )
        )
        if accepted.any()
        else 0.0,
    }
    report = {
        "checkpoint": str(checkpoint_path.resolve()),
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "input_mode": mode,
        "class_names": list(CLASS_NAMES),
        "validation_sample_count": len(val_dataset),
        "test_sample_count": len(test_dataset),
        "temperature": temperature,
        "rejection": rejection,
        "test_uncalibrated": classification_report(test_labels, uncalibrated, CLASS_NAMES),
        "test_calibrated": classification_report(test_labels, calibrated, CLASS_NAMES),
        "candidate_binary_diagnostic": collapsed_binary_report(test_labels, calibrated),
        "test_rejected": rejected_report,
    }
    if compare_v32 is not None:
        report["v32_binary_diagnostic"] = evaluate_v32(compare_v32, test_dataset)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
