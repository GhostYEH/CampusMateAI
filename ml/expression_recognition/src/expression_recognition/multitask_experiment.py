"""Jointly fine-tune expression and binary co-occurring state outputs offline."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sklearn.metrics import (accuracy_score, average_precision_score,
                             balanced_accuracy_score, brier_score_loss, f1_score)
from torch.nn import functional as F
from torch.utils.data import DataLoader

from .constants import CLASS_NAMES
from .data import ManifestDataset, build_transforms
from .models import build_model
from .utils import save_json, seed_everything
from .multitask_model import (MULTITASK_CLASS_ORDER, MULTITASK_VERSION,
                              STATE_NAMES, STATE_POSITIVE_DEFINITION,
                              MultitaskExpressionStateModel, validate_multitask_checkpoint)

EXPRESSION_GUARD = "validation expression macro-F1 degradation <= configured maximum"


def file_digest(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def binary_state_targets(levels: torch.Tensor | np.ndarray) -> torch.Tensor | np.ndarray:
    """Map each DAiSEE ordinal label independently: 0/1 absent, 2/3 present."""
    if isinstance(levels, torch.Tensor):
        if levels.ndim != 2 or levels.shape[1] != 3 or levels.dtype != torch.long:
            raise ValueError("DAiSEE levels must be an integer [N,3] array")
        if torch.any((levels < 0) | (levels > 3)):
            raise ValueError("DAiSEE levels must be in 0..3")
        return (levels >= 2).to(torch.float32)
    values = np.asarray(levels)
    if values.ndim != 2 or values.shape[1] != 3 or not np.issubdtype(values.dtype, np.integer):
        raise ValueError("DAiSEE levels must be an integer [N,3] array")
    if (values < 0).any() or (values > 3).any():
        raise ValueError("DAiSEE levels must be in 0..3")
    return (values >= 2).astype(np.float32)


def binary_positive_weights(targets: torch.Tensor, cap: float = 10.0) -> torch.Tensor:
    """Training-split negative/positive ratios, capped to bound rare-label loss."""
    if targets.ndim != 2 or targets.shape[1] != 3 or targets.numel() == 0:
        raise ValueError("Expected nonempty [N,3] binary training targets")
    if not torch.all((targets == 0) | (targets == 1)):
        raise ValueError("Binary training targets must contain only zero and one")
    positive = targets.sum(dim=0).float()
    negative = len(targets) - positive
    return (negative / positive.clamp_min(1)).clamp(min=1e-6, max=cap)


def _expression_metrics(targets: np.ndarray, logits: np.ndarray) -> dict[str, Any]:
    predicted = logits.argmax(axis=1)
    return {"accuracy": float(accuracy_score(targets, predicted)),
            "macro_f1": float(f1_score(targets, predicted, labels=list(range(7)), average="macro", zero_division=0)),
            "balanced_accuracy": float(balanced_accuracy_score(targets, predicted))}


def _state_metrics(targets: np.ndarray, logits: np.ndarray) -> dict[str, Any]:
    probabilities = 1 / (1 + np.exp(-np.clip(logits, -50, 50)))
    predictions = probabilities >= 0.5
    per_state = {}
    for index, name in enumerate(STATE_NAMES):
        target, predicted, probability = targets[:, index].astype(int), predictions[:, index], probabilities[:, index]
        per_state[name] = {
            "support_negative": int((target == 0).sum()),
            "support_positive": int((target == 1).sum()),
            "accuracy": float(accuracy_score(target, predicted)),
            "macro_f1": float(f1_score(target, predicted, labels=[0, 1], average="macro", zero_division=0)),
            "balanced_accuracy": float(balanced_accuracy_score(target, predicted)),
            "brier_score": float(brier_score_loss(target, probability)),
            "average_precision": (float(average_precision_score(target, probability)) if len(np.unique(target)) == 2 else None),
        }
    return {"per_state": per_state,
            "mean_macro_f1": float(np.mean([row["macro_f1"] for row in per_state.values()]))}


def _majority_state_logits(positive_counts: list[int] | np.ndarray, sample_count: int, rows: int) -> np.ndarray:
    counts = np.asarray(positive_counts, dtype=np.int64)
    if counts.shape != (3,) or sample_count < 1:
        raise ValueError("Training majority baseline needs three counts and a positive sample count")
    positive_majority = counts * 2 >= sample_count
    return np.broadcast_to(np.where(positive_majority, 20.0, -20.0), (rows, 3)).copy()


def _loader(manifest: Path, split: str, config: dict, training: bool, batch: int, workers: int):
    dataset = ManifestDataset(manifest, split, build_transforms(config, training=training))
    return dataset, DataLoader(dataset, batch_size=batch, shuffle=training, num_workers=workers,
                               pin_memory=torch.cuda.is_available(), drop_last=False)


def _state_loader(manifest: Path, split: str, config: dict, training: bool, batch: int, workers: int):
    from .daisee_data import DAiSEEVideoDataset
    dataset = DAiSEEVideoDataset(manifest, split, build_transforms(config, training=training), frames_per_clip=4)
    return dataset, DataLoader(dataset, batch_size=batch, shuffle=training, num_workers=workers,
                               pin_memory=torch.cuda.is_available(), drop_last=False)


@torch.inference_mode()
def _predict_expression(model, loader, device):
    model.eval()
    logits, targets = [], []
    for images, labels in loader:
        output = model(images.to(device))
        if isinstance(output, dict):
            output = output["expression_logits"]
        logits.append(output.cpu().numpy())
        targets.append(labels.numpy())
    return np.concatenate(logits), np.concatenate(targets).astype(np.int64)


@torch.inference_mode()
def _predict_states(model, loader, device):
    model.eval()
    logits, levels = [], []
    for clips, labels in loader:
        logits.append(model(clips.to(device))["state_logits"].cpu().numpy())
        levels.append(labels.numpy())
    return np.concatenate(logits), binary_state_targets(np.concatenate(levels)).astype(np.int64)


def _make_checkpoint(model, args, source, expression_manifest, state_manifest, train_counts, metrics, epoch, settings):
    return {
        "checkpoint_version": MULTITASK_VERSION,
        "config": model.config,
        "model_state": {key: value.detach().cpu().clone() for key, value in model.state_dict().items()},
        "class_order": list(MULTITASK_CLASS_ORDER),
        "expression_class_order": list(CLASS_NAMES),
        "state_order": list(STATE_NAMES),
        "state_positive_definition": STATE_POSITIVE_DEFINITION,
        "source_checkpoint_sha256": file_digest(source),
        "expression_manifest_sha256": file_digest(expression_manifest),
        "daisee_manifest_sha256": file_digest(state_manifest),
        "training_state_counts": train_counts.tolist(),
        "training_state_sample_count": int(args.training_state_sample_count),
        "selection_validation": metrics,
        "epoch": epoch,
        "seed": args.seed,
        "training_settings": settings,
        "selection_split": "validation",
        "deployment_ready": False,
        "confidence_semantics": "uncalibrated_model_probability",
    }


def train_multitask(args) -> dict[str, Any]:
    if args.epochs < 1 or args.batch_size < 1 or args.state_batch_size < 1 or args.workers < 0:
        raise ValueError("epochs and batch sizes must be positive; workers must be nonnegative")
    if (not all(math.isfinite(value) for value in (args.learning_rate, args.state_learning_rate,
                                                    args.max_expression_f1_drop, args.teacher_kl_weight,
                                                    args.teacher_temperature)) or
            args.learning_rate <= 0 or args.state_learning_rate <= 0 or args.max_expression_f1_drop < 0 or
            args.teacher_kl_weight < 0 or args.teacher_temperature <= 0):
        raise ValueError("Learning rates must be positive and the expression guard nonnegative")
    if args.output_dir.exists():
        raise FileExistsError("Choose a new output directory; existing experiments are never overwritten")
    if not torch.cuda.is_available() and not args.allow_cpu:
        raise RuntimeError("CUDA unavailable; --allow-cpu is required for intentional CPU runs")
    seed_everything(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = MultitaskExpressionStateModel.from_expression_checkpoint(args.checkpoint).to(device)
    teacher = build_model(model.config, allow_download=False).to(device)
    source = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    teacher.load_state_dict(source["model_state"], strict=True)
    teacher.eval().requires_grad_(False)
    expression_train, expression_train_loader = _loader(args.expression_manifest, "train", model.config, True,
                                                        args.batch_size, args.workers)
    state_train, state_train_loader = _state_loader(args.daisee_manifest, "train", model.config, True,
                                                    args.state_batch_size, args.workers)
    _, expression_val_loader = _loader(args.expression_manifest, "validation", model.config, False,
                                       args.batch_size, args.workers)
    _, state_val_loader = _state_loader(args.daisee_manifest, "validation", model.config, False,
                                        args.state_batch_size, args.workers)
    baseline_expression_logits, expression_val_targets = _predict_expression(teacher, expression_val_loader, device)
    baseline_expression = _expression_metrics(expression_val_targets, baseline_expression_logits)
    level_array = np.asarray([row[1] for row in state_train.rows], dtype=np.int64)
    train_counts = binary_state_targets(level_array).sum(axis=0).astype(np.int64)
    args.training_state_sample_count = len(state_train)
    train_binary = torch.from_numpy(binary_state_targets(level_array))
    positive_weights = binary_positive_weights(train_binary).to(device)
    args.output_dir.mkdir(parents=True)
    settings = {"epochs": args.epochs, "batch_size": args.batch_size, "state_batch_size": args.state_batch_size,
                "learning_rate": args.learning_rate, "state_learning_rate": args.state_learning_rate,
                "steps_per_epoch": len(state_train_loader), "optimizer": "AdamW", "weight_decay": 0.0001,
                "expression_loss": "cross_entropy", "state_loss": "binary_cross_entropy_with_logits",
                "state_pos_weight": positive_weights.cpu().tolist(), "teacher_kl_weight": args.teacher_kl_weight,
                "teacher_temperature": args.teacher_temperature, "seed": args.seed, "workers": args.workers,
                "amp": False, "frames_per_clip": 4, "expression_guard": EXPRESSION_GUARD,
                "max_expression_f1_drop": args.max_expression_f1_drop}
    optimizer = torch.optim.AdamW([
        {"params": list(model.backbone.layer4.parameters()) + list(model.backbone.fc.parameters()), "lr": args.learning_rate},
        {"params": model.state_head.parameters(), "lr": args.state_learning_rate},
    ], weight_decay=0.0001)
    best_score, best_epoch = -1.0, None
    unrestricted_score = -1.0
    best_path = args.output_dir / "best.pt"
    history = []
    for epoch in range(1, args.epochs + 1):
        model.train()
        exp_iter = iter(expression_train_loader)
        loss_total = 0.0
        for step, (state_images, state_levels) in enumerate(state_train_loader, start=1):
            try:
                exp_images, exp_labels = next(exp_iter)
            except StopIteration:
                exp_iter = iter(expression_train_loader)
                exp_images, exp_labels = next(exp_iter)
            exp_images, exp_labels = exp_images.to(device), exp_labels.to(device)
            state_images = state_images.to(device)
            state_targets = binary_state_targets(state_levels).to(device)
            optimizer.zero_grad(set_to_none=True)
            expression_logits = model(exp_images)["expression_logits"]
            state_logits = model(state_images)["state_logits"]
            with torch.no_grad():
                teacher_logits = teacher(exp_images)
            expression_loss = F.cross_entropy(expression_logits, exp_labels)
            temperature = args.teacher_temperature
            distillation = F.kl_div(F.log_softmax(expression_logits / temperature, dim=1),
                                    F.softmax(teacher_logits / temperature, dim=1), reduction="batchmean") * temperature ** 2
            state_loss = F.binary_cross_entropy_with_logits(state_logits, state_targets, pos_weight=positive_weights)
            loss = expression_loss + state_loss + args.teacher_kl_weight * distillation
            loss.backward()
            optimizer.step()
            loss_total += float(loss.detach())
            if step % 50 == 0:
                print(f"epoch={epoch} step={step}/{len(state_train_loader)} loss={float(loss.detach()):.4f}", flush=True)
        val_expression_logits, val_expression_targets = _predict_expression(model, expression_val_loader, device)
        val_state_logits, val_state_targets = _predict_states(model, state_val_loader, device)
        expr_metrics = _expression_metrics(val_expression_targets, val_expression_logits)
        state_metrics = _state_metrics(val_state_targets, val_state_logits)
        drop = baseline_expression["macro_f1"] - expr_metrics["macro_f1"]
        guarded = drop <= args.max_expression_f1_drop + 1e-12
        row = {"epoch": epoch, "mean_train_loss_per_step": loss_total / max(1, len(state_train_loader)),
               "validation_expression": expr_metrics, "validation_expression_macro_f1_drop": drop,
               "expression_guard_passed": guarded, "validation_states": state_metrics,
               "selection_score": state_metrics["mean_macro_f1"] if guarded else None}
        history.append(row)
        print(json.dumps(row), flush=True)
        # Keep the actual best unrestricted validation candidate as a separate artifact.
        if state_metrics["mean_macro_f1"] > unrestricted_score:
            unrestricted_score = state_metrics["mean_macro_f1"]
            candidate = _make_checkpoint(model, args, args.checkpoint, args.expression_manifest,
                                          args.daisee_manifest, train_counts, row, epoch, settings)
            candidate["candidate_only"] = True
            torch.save(candidate, args.output_dir / "candidate.pt")
        if guarded and state_metrics["mean_macro_f1"] > best_score:
            best_score, best_epoch = state_metrics["mean_macro_f1"], epoch
            checkpoint = _make_checkpoint(model, args, args.checkpoint, args.expression_manifest,
                                          args.daisee_manifest, train_counts, row, epoch, settings)
            checkpoint["expression_guard_passed"] = True
            checkpoint["candidate_only"] = False
            torch.save(checkpoint, best_path)
    selected = best_epoch is not None
    if not selected:
        checkpoint_path = args.output_dir / "candidate.pt"
    else:
        checkpoint_path = best_path
    locked = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    model.load_state_dict(locked["model_state"], strict=True)
    val_expression_logits, val_expression_targets = _predict_expression(model, expression_val_loader, device)
    val_state_logits, val_state_targets = _predict_states(model, state_val_loader, device)
    prediction_metadata = {"checkpoint_sha256": np.array(file_digest(checkpoint_path)),
                           "split": np.array("validation"),
                           "state_positive_definition": np.array(STATE_POSITIVE_DEFINITION)}
    np.savez_compressed(args.output_dir / "validation_predictions.npz",
                        expression_logits=val_expression_logits, expression_targets=val_expression_targets,
                        state_logits=val_state_logits, state_targets=val_state_targets, **prediction_metadata)
    report = {"checkpoint": checkpoint_path.name, "checkpoint_sha256": file_digest(checkpoint_path),
              "checkpoint_version": MULTITASK_VERSION, "class_order": list(MULTITASK_CLASS_ORDER),
              "state_positive_definition": STATE_POSITIVE_DEFINITION, "source_checkpoint_sha256": file_digest(args.checkpoint),
              "expression_manifest_sha256": file_digest(args.expression_manifest),
              "daisee_manifest_sha256": file_digest(args.daisee_manifest), "training_state_positive_counts": train_counts.tolist(),
              "training_state_sample_count": len(state_train),
              "training_state_majority_baseline": _state_metrics(
                  val_state_targets, _majority_state_logits(train_counts, len(state_train), len(val_state_targets))),
              "train_expression_samples": len(expression_train), "train_state_clips": len(state_train),
              "validation_expression_samples": len(val_expression_targets),
              "validation_state_clips": len(val_state_targets),
              "baseline_expression": baseline_expression, "selected_epoch": best_epoch,
              "expression_guard_passed": selected, "candidate_only": not selected,
              "validation_expression": _expression_metrics(val_expression_targets, val_expression_logits),
              "validation_states": _state_metrics(val_state_targets, val_state_logits),
              "training_settings": settings, "history": history, "selection_split": "validation",
              "deployment_ready": False,
              "limitations": ["State probabilities are uncalibrated and binary outputs are independent; the ten values do not sum to one.",
                              "DAiSEE 0/1 levels are grouped absent and 2/3 present for each state.",
                              "The model was trained and evaluated offline; no mobile or serving deployment is included."]}
    save_json(args.output_dir / "training_report.json", report)
    return report


def evaluate_multitask(args) -> dict[str, Any]:
    if args.output_dir.exists():
        raise FileExistsError("Choose a new evaluation output directory")
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    validate_multitask_checkpoint(checkpoint)
    model = MultitaskExpressionStateModel.from_checkpoint(args.checkpoint)
    if checkpoint.get("candidate_only"):
        raise ValueError("A candidate that failed the validation expression guard cannot be test-evaluated")
    if checkpoint.get("selection_split") != "validation" or checkpoint.get("expression_guard_passed") is not True:
        raise ValueError("Checkpoint did not pass its validation expression guard")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    _, expression_loader = _loader(args.expression_manifest, "test", model.config, False, args.batch_size, args.workers)
    _, state_loader = _state_loader(args.daisee_manifest, "test", model.config, False, args.state_batch_size, args.workers)
    expression_logits, expression_targets = _predict_expression(model, expression_loader, device)
    state_logits, state_targets = _predict_states(model, state_loader, device)
    calibration = checkpoint.get("confidence_calibration")
    if calibration is not None:
        if calibration.get("label_order") != list(MULTITASK_CLASS_ORDER):
            raise ValueError("Calibration label_order differs from the ten-label contract")
        scales = np.asarray(calibration.get("state_scales"), dtype=np.float64)
        biases = np.asarray(calibration.get("state_biases"), dtype=np.float64)
        temperature = float(calibration.get("expression_temperature", float("nan")))
        if (scales.shape != (3,) or biases.shape != (3,) or not np.isfinite(scales).all()
                or not np.isfinite(biases).all() or np.any(scales < 0)
                or not math.isfinite(temperature) or temperature <= 0):
            raise ValueError("Calibration has invalid temperature, state scales, or state biases")
        report_state_logits = state_logits * scales[None, :] + biases[None, :]
        confidence_semantics = "validation_calibrated_model_probability"
    else:
        report_state_logits = state_logits
        confidence_semantics = "uncalibrated_model_probability"
    args.output_dir.mkdir(parents=True)
    checkpoint_sha = file_digest(args.checkpoint)
    np.savez_compressed(args.output_dir / "test_predictions.npz", expression_logits=expression_logits,
                        expression_targets=expression_targets, state_logits=state_logits,
                        state_targets=state_targets, checkpoint_sha256=np.array(checkpoint_sha),
                        split=np.array("test"), state_positive_definition=np.array(STATE_POSITIVE_DEFINITION))
    report = {"split": "test", "checkpoint_sha256": checkpoint_sha,
              "expression_manifest_sha256": file_digest(args.expression_manifest),
              "daisee_manifest_sha256": file_digest(args.daisee_manifest),
              "expression": _expression_metrics(expression_targets, expression_logits),
              "states": _state_metrics(state_targets, report_state_logits),
              "training_state_majority_baseline": _state_metrics(
                  state_targets, _majority_state_logits(checkpoint["training_state_counts"],
                                                        checkpoint["training_state_sample_count"], len(state_targets))),
              "training_state_sample_count": checkpoint["training_state_sample_count"],
              "class_order": list(MULTITASK_CLASS_ORDER),
              "state_positive_definition": STATE_POSITIVE_DEFINITION,
              "confidence_semantics": confidence_semantics,
              "calibration_applied": calibration is not None,
              "deployment_ready": False}
    if calibration is not None:
        report["raw_states"] = _state_metrics(state_targets, state_logits)
    save_json(args.output_dir / "test_report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    train = commands.add_parser("train")
    evaluate = commands.add_parser("evaluate")
    for command in (train, evaluate):
        command.add_argument("--checkpoint", type=Path, required=True)
        command.add_argument("--expression-manifest", type=Path, required=True)
        command.add_argument("--daisee-manifest", type=Path, required=True)
        command.add_argument("--output-dir", type=Path, required=True)
        command.add_argument("--batch-size", type=int, default=64)
        command.add_argument("--state-batch-size", type=int, default=16)
        command.add_argument("--workers", type=int, default=0)
    train.add_argument("--epochs", type=int, default=3)
    train.add_argument("--learning-rate", type=float, default=1e-4)
    train.add_argument("--state-learning-rate", type=float, default=1e-3)
    train.add_argument("--teacher-kl-weight", type=float, default=0.5)
    train.add_argument("--teacher-temperature", type=float, default=2.0)
    train.add_argument("--max-expression-f1-drop", type=float, default=0.01)
    train.add_argument("--seed", type=int, default=20261004)
    train.add_argument("--allow-cpu", action="store_true")
    args = parser.parse_args()
    result = train_multitask(args) if args.command == "train" else evaluate_multitask(args)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
