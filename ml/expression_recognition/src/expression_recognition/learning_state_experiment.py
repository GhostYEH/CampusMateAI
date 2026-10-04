"""Offline DAiSEE extension: frozen seven-expression trunk, three state heads.

DAiSEE supplies clip-level ordinal labels, not additional mutually exclusive
expressions. This experiment never writes client assets or infers engagement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F
from torch.utils.data import DataLoader, TensorDataset

from .constants import CLASS_NAMES
from .data import build_transforms
from .models import build_model
from .utils import save_json, seed_everything

STATE_NAMES = ["boredom", "confusion", "frustration"]
LEVEL_NAMES = ["very_low", "low", "high", "very_high"]
EXTENSION_VERSION = "expression-learning-state-frozen-v1"


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def frozen_digest(model) -> str:
    """Include frozen weights and BN buffers; state heads are the only exclusion."""
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        if name.startswith("state_heads."):
            continue
        digest.update(name.encode("utf-8"))
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def state_class_weights(targets: torch.Tensor) -> torch.Tensor:
    if targets.ndim != 2 or targets.shape[1] != 3 or targets.numel() == 0:
        raise ValueError("Expected nonempty [clips, 3] training labels")
    if targets.dtype != torch.long or torch.any((targets < 0) | (targets > 3)):
        raise ValueError("DAiSEE levels must be integers in 0..3")
    weights = []
    for index in range(3):
        counts = torch.bincount(targets[:, index], minlength=4).float()
        values = (len(targets) / (4 * counts.clamp_min(1))).sqrt()
        weights.append(values / values.mean())
    return torch.stack(weights)


def state_loss(logits: torch.Tensor, targets: torch.Tensor, weights: torch.Tensor) -> torch.Tensor:
    if logits.shape != (len(targets), 3, 4) or weights.shape != (3, 4):
        raise ValueError("Expected three independent four-level classification heads")
    return torch.stack([
        F.cross_entropy(logits[:, index], targets[:, index], weight=weights[index], label_smoothing=0.05)
        for index in range(3)
    ]).mean()


def extract_clip_features(model, manifest: Path, split: str, device, batch_size: int, workers: int):
    from .daisee_data import DAiSEEVideoDataset

    dataset = DAiSEEVideoDataset(manifest, split, build_transforms(model.config, training=False))
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=workers)
    features, targets = [], []
    model.eval()
    with torch.inference_mode():
        for batch_index, (inputs, labels) in enumerate(loader):
            features.append(model.extract_features(inputs.to(device)).cpu().numpy())
            targets.append(labels.numpy())
            if batch_index % 20 == 0:
                print(f"{split}: extracted {sum(len(row) for row in targets)}/{len(dataset)} clips", flush=True)
    return np.concatenate(features), np.concatenate(targets).astype(np.int64)


def score_heads(model, features, targets, train_targets, device):
    from .learning_state_model import learning_state_metrics

    model.eval()
    with torch.no_grad():
        logits = model.state_logits_from_features(torch.as_tensor(features, device=device))
        probabilities = logits.softmax(-1).cpu().numpy()
    metrics = learning_state_metrics(targets, probabilities.argmax(-1), train_targets)
    return metrics, probabilities


def train_extension(args) -> dict:
    from .learning_state_model import FrozenExpressionLearningStateModel

    if args.epochs < 1 or args.learning_rate <= 0 or args.batch_size < 1:
        raise ValueError("epochs, learning_rate and batch_size must be positive")
    if args.output_dir.exists():
        raise FileExistsError("Choose a new output directory; existing experiments are never overwritten")
    if not torch.cuda.is_available() and not args.allow_cpu:
        raise RuntimeError("CUDA unavailable; --allow-cpu is required for intentional CPU runs")
    seed_everything(args.seed)
    settings = {"epochs": args.epochs, "learning_rate": args.learning_rate,
                "batch_size": args.batch_size, "feature_batch_size": args.feature_batch_size,
                "workers": args.workers, "seed": args.seed, "optimizer": "AdamW",
                "weight_decay": 1e-4, "label_smoothing": 0.05,
                "class_weighting": "normalized_sqrt_inverse_train_frequency"}
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = FrozenExpressionLearningStateModel.from_expression_checkpoint(args.checkpoint).to(device)
    before = frozen_digest(model)
    args.output_dir.mkdir(parents=True)
    # Only train and validation are decoded before the experiment is locked.
    train_features, train_targets = extract_clip_features(
        model, args.manifest, "train", device, args.feature_batch_size, args.workers,
    )
    val_features, val_targets = extract_clip_features(
        model, args.manifest, "validation", device, args.feature_batch_size, args.workers,
    )
    np.savez_compressed(args.output_dir / "features.npz", train_features=train_features,
                        train_targets=train_targets, validation_features=val_features, validation_targets=val_targets)
    labels = torch.as_tensor(train_targets, dtype=torch.long)
    weights = state_class_weights(labels).to(device)
    loader = DataLoader(TensorDataset(torch.from_numpy(train_features), labels),
                        batch_size=args.batch_size, shuffle=True,
                        generator=torch.Generator().manual_seed(args.seed))
    optimizer = torch.optim.AdamW(model.state_heads.parameters(), lr=args.learning_rate, weight_decay=1e-4)
    best_score = -1.0
    best_epoch = 0
    history = []
    for epoch in range(1, args.epochs + 1):
        model.train()
        loss_sum = 0.0
        for features, targets in loader:
            optimizer.zero_grad(set_to_none=True)
            logits = model.state_logits_from_features(features.to(device))
            loss = state_loss(logits, targets.to(device), weights)
            loss.backward()
            optimizer.step()
            loss_sum += float(loss.detach()) * len(targets)
        metrics, _ = score_heads(model, val_features, val_targets, train_targets, device)
        score = float(metrics["mean_macro_f1"])
        history.append({"epoch": epoch, "train_loss": loss_sum / len(train_targets),
                        "validation_mean_macro_f1": score})
        print(json.dumps(history[-1]), flush=True)
        if score > best_score:
            best_score, best_epoch = score, epoch
            torch.save({
                "extension_version": EXTENSION_VERSION, "config": model.config,
                "model_state": {key: value.detach().cpu().clone() for key, value in model.state_dict().items()},
                "expression_class_order": CLASS_NAMES, "state_order": STATE_NAMES, "level_order": LEVEL_NAMES,
                "source_checkpoint_sha256": file_digest(args.checkpoint),
                "manifest_sha256": file_digest(args.manifest), "frozen_state_sha256": before,
                "train_targets": train_targets, "epoch": epoch, "validation_mean_macro_f1": score,
                "seed": args.seed, "aggregation": "mean_frozen_face_features_per_clip",
                "training_settings": settings,
                "selection_split": "validation", "deployment_ready": False,
            }, args.output_dir / "best.pt")
    if frozen_digest(model) != before:
        raise RuntimeError("Frozen expression weights or BatchNorm state changed")
    checkpoint = torch.load(args.output_dir / "best.pt", map_location="cpu", weights_only=False)
    model.load_state_dict(checkpoint["model_state"], strict=True)
    metrics, probabilities = score_heads(model, val_features, val_targets, train_targets, device)
    np.savez_compressed(args.output_dir / "validation_predictions.npz", probabilities=probabilities, targets=val_targets)
    report = {"extension_version": EXTENSION_VERSION, "state_order": STATE_NAMES,
              "level_order": LEVEL_NAMES, "expression_class_order": CLASS_NAMES,
              "train_clips": len(train_targets), "validation_clips": len(val_targets),
              "train_class_weights": weights.cpu().tolist(), "best_epoch": best_epoch,
              "training_settings": settings,
              "source_checkpoint_sha256": checkpoint["source_checkpoint_sha256"],
              "manifest_sha256": checkpoint["manifest_sha256"],
              "frozen_expression_unchanged": frozen_digest(model) == before,
              "selection_split": "validation", "validation": metrics, "history": history,
              "deployment_ready": False,
              "limitations": ["Frozen visual features and clip mean pooling form a research baseline.",
                              "DAiSEE state labels are clip-level, not seven-expression ground truth.",
                              "No smartphone validation or probability threshold calibration performed."]}
    save_json(args.output_dir / "training_report.json", report)
    print(json.dumps({"best_epoch": best_epoch, "validation": metrics}, indent=2), flush=True)
    return report


def evaluate_extension(args) -> dict:
    from .learning_state_model import FrozenExpressionLearningStateModel

    if args.output_dir.exists():
        raise FileExistsError("Choose a new test report directory")
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    if (checkpoint.get("extension_version") != EXTENSION_VERSION or
            checkpoint.get("state_order") != STATE_NAMES or checkpoint.get("level_order") != LEVEL_NAMES or
            checkpoint.get("expression_class_order") != CLASS_NAMES or checkpoint.get("selection_split") != "validation"):
        raise ValueError("Checkpoint must be a validation-selected three-state extension")
    model = FrozenExpressionLearningStateModel(build_model(checkpoint["config"], allow_download=False), checkpoint["config"])
    model.load_state_dict(checkpoint["model_state"], strict=True)
    if frozen_digest(model) != checkpoint["frozen_state_sha256"]:
        raise ValueError("Expression backbone fingerprint differs from the locked checkpoint")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    features, targets = extract_clip_features(model, args.manifest, "test", device, args.feature_batch_size, args.workers)
    metrics, probabilities = score_heads(model, features, targets, checkpoint["train_targets"], device)
    report = {"split": "test", "locked_checkpoint_sha256": file_digest(args.checkpoint),
              "manifest_sha256": file_digest(args.manifest), "state_order": STATE_NAMES,
              "level_order": LEVEL_NAMES, "metrics": metrics, "deployment_ready": False}
    args.output_dir.mkdir(parents=True)
    np.savez_compressed(args.output_dir / "test_predictions.npz", probabilities=probabilities, targets=targets)
    save_json(args.output_dir / "test_report.json", report)
    print(json.dumps(report, indent=2), flush=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    train = commands.add_parser("train", help="Fit only new heads and select using validation")
    test = commands.add_parser("evaluate", help="Evaluate a locked extension on test without retraining")
    for command in (train, test):
        command.add_argument("--checkpoint", type=Path, required=True)
        command.add_argument("--manifest", type=Path, required=True)
        command.add_argument("--output-dir", type=Path, required=True)
        command.add_argument("--feature-batch-size", type=int, default=64)
        command.add_argument("--workers", type=int, default=0)
    train.add_argument("--epochs", type=int, default=40)
    train.add_argument("--learning-rate", type=float, default=1e-3)
    train.add_argument("--batch-size", type=int, default=256)
    train.add_argument("--seed", type=int, default=20261004)
    train.add_argument("--allow-cpu", action="store_true")
    args = parser.parse_args()
    (train_extension if args.command == "train" else evaluate_extension)(args)


if __name__ == "__main__":
    main()
