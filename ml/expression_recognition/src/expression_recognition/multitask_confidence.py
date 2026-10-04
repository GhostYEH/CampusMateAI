"""Validation-only confidence calibration and ten-label face inference."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from sklearn.linear_model import LogisticRegression

from .constants import CLASS_NAMES
from .data import build_transforms
from .learning_state_experiment import file_digest
from .learning_state_model import STATE_NAMES
from .utils import save_json

LABEL_NAMES = [*CLASS_NAMES, *STATE_NAMES]
POSITIVE_DEFINITION = "DAiSEE level >= 2"


def confidence_probabilities(outputs: dict, calibration: dict | None = None) -> torch.Tensor:
    """Seven competing expressions and three independent state probabilities."""
    expressions, states = outputs["expression_logits"], outputs["state_logits"]
    if expressions.ndim != 2 or expressions.shape[1] != 7 or states.shape != (len(expressions), 3):
        raise ValueError("Expected [N,7] expression logits and [N,3] state logits")
    temperature = 1.0
    if calibration is not None:
        if calibration.get("label_order") != LABEL_NAMES:
            raise ValueError("Calibration label order differs from the ten-label contract")
        temperature = float(calibration["expression_temperature"])
        scales = torch.as_tensor(calibration["state_scales"], device=states.device, dtype=states.dtype)
        biases = torch.as_tensor(calibration["state_biases"], device=states.device, dtype=states.dtype)
        if (scales.shape != (3,) or biases.shape != (3,) or not torch.isfinite(scales).all()
                or not torch.isfinite(biases).all() or torch.any(scales < 0)):
            raise ValueError("Calibration must contain three finite nonnegative scales and finite biases")
        states = states * scales + biases
    if not np.isfinite(temperature) or temperature <= 0:
        raise ValueError("Expression temperature must be finite and positive")
    return torch.cat([(expressions / temperature).softmax(-1), states.sigmoid()], dim=-1)


def fit_confidence_calibration(expression_logits, expression_targets, state_logits, state_targets) -> dict:
    """Fit temperature and monotone Platt maps on explicitly supplied validation."""
    expressions = np.asarray(expression_logits, dtype=np.float64)
    expr_labels = np.asarray(expression_targets)
    states = np.asarray(state_logits, dtype=np.float64)
    labels = np.asarray(state_targets)
    if (expressions.ndim != 2 or expressions.shape[1] != 7 or len(expressions) == 0
            or expr_labels.shape != (len(expressions),) or not np.issubdtype(expr_labels.dtype, np.integer)
            or np.any((expr_labels < 0) | (expr_labels > 6))):
        raise ValueError("Expected nonempty [N,7] validation logits and integer expression labels 0..6")
    if (states.ndim != 2 or states.shape[1] != 3 or len(states) == 0 or labels.shape != states.shape
            or not np.isin(labels, [0, 1]).all()):
        raise ValueError("Expected nonempty [M,3] validation state logits and binary labels")
    if not np.isfinite(expressions).all() or not np.isfinite(states).all():
        raise ValueError("Validation logits must be finite")
    temperatures = np.unique(np.r_[1.0, np.geomspace(0.1, 10.0, 201)])
    nlls = []
    for temperature in temperatures:
        scaled = expressions / temperature
        scaled -= scaled.max(axis=1, keepdims=True)
        nlls.append(float(np.mean(np.log(np.exp(scaled).sum(1)) - scaled[np.arange(len(scaled)), expr_labels])))
    scales, biases, notes = [], [], []
    for index, name in enumerate(STATE_NAMES):
        if len(np.unique(labels[:, index])) < 2:
            scales.append(1.0)
            biases.append(0.0)
            notes.append({"label": name, "fitted": False, "reason": "validation_has_only_one_binary_class"})
            continue
        fit = LogisticRegression(C=1.0, max_iter=1000).fit(states[:, index:index + 1], labels[:, index])
        scale, bias = float(fit.coef_[0, 0]), float(fit.intercept_[0])
        if scale < 0:
            # Preserve the meaning of a high state score; an inverted validation
            # relationship can only support a constant prevalence estimate.
            prevalence = float(labels[:, index].mean())
            scale, bias = 0.0, float(np.log(prevalence / (1 - prevalence)))
            reason = "nonpositive_relationship_uses_validation_prevalence"
        else:
            reason = "regularized_monotone_platt"
        scales.append(scale)
        biases.append(bias)
        notes.append({"label": name, "fitted": True, "reason": reason})
    return {"label_order": LABEL_NAMES, "expression_temperature": float(temperatures[np.argmin(nlls)]),
            "state_scales": scales, "state_biases": biases, "state_fit": notes,
            "fitted_on": "validation", "positive_definition": POSITIVE_DEFINITION,
            "expression_validation_samples": len(expressions), "state_validation_samples": len(states),
            "method": "expression_temperature_and_regularized_monotone_platt",
            "validation_nll_before": nlls[int(np.flatnonzero(temperatures == 1.0)[0])],
            "validation_nll_after": min(nlls),
            "guarantees_correctness": False}


def calibrate_checkpoint(checkpoint_path: Path, predictions_path: Path, output_path: Path) -> dict:
    from .multitask_model import MultitaskExpressionStateModel

    if output_path.exists():
        raise FileExistsError("Choose a new calibrated checkpoint path")
    MultitaskExpressionStateModel.from_checkpoint(checkpoint_path)  # Strict contract validation.
    digest = file_digest(checkpoint_path)
    with np.load(predictions_path, allow_pickle=False) as data:
        if str(data["split"].item()) != "validation":
            raise ValueError("Confidence calibration must use validation predictions, never test")
        if str(data["checkpoint_sha256"].item()) != digest:
            raise ValueError("Validation predictions belong to a different checkpoint")
        if str(data["state_positive_definition"].item()) != POSITIVE_DEFINITION:
            raise ValueError("Validation state labels use a different positive definition")
        calibration = fit_confidence_calibration(data["expression_logits"], data["expression_targets"],
                                                data["state_logits"], data["state_targets"])
    calibration.update({"source_checkpoint_sha256": digest, "predictions_sha256": file_digest(predictions_path)})
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    checkpoint["confidence_calibration"] = calibration
    checkpoint["confidence_semantics"] = "validation_calibrated_model_probability"
    checkpoint["deployment_ready"] = False
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, output_path)
    return calibration


def calibration_evaluation(checkpoint_path: Path, predictions_path: Path) -> dict:
    """Measure a locked calibrator without fitting or selecting on these labels."""
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    calibration = checkpoint["confidence_calibration"]
    with np.load(predictions_path, allow_pickle=False) as data:
        prediction_digest = str(data["checkpoint_sha256"].item())
        if prediction_digest not in {file_digest(checkpoint_path), calibration["source_checkpoint_sha256"]}:
            raise ValueError("Predictions do not belong to this model or its uncalibrated source")
        if str(data["state_positive_definition"].item()) != POSITIVE_DEFINITION:
            raise ValueError("State positive definition differs from the calibrator")
        expressions = torch.as_tensor(data["expression_logits"], dtype=torch.float64)
        states = torch.as_tensor(data["state_logits"], dtype=torch.float64)
        expr_labels = np.asarray(data["expression_targets"], dtype=np.int64)
        labels = np.asarray(data["state_targets"], dtype=np.int64)
        split = str(data["split"].item())
    # Prediction sets have separate expression/state populations, not paired labels.
    expr_probabilities = (expressions / calibration["expression_temperature"]).softmax(-1).numpy()
    state_probabilities = (states * torch.tensor(calibration["state_scales"])
                           + torch.tensor(calibration["state_biases"])).sigmoid().numpy()
    from sklearn.metrics import accuracy_score, average_precision_score, f1_score

    state_report = {}
    for index, name in enumerate(STATE_NAMES):
        targets, probabilities = labels[:, index], state_probabilities[:, index]
        raw_probabilities = states[:, index].sigmoid().numpy()
        state_report[name] = {"accuracy_at_0_5": float(accuracy_score(targets, probabilities >= .5)),
                              "macro_f1_at_0_5": float(f1_score(targets, probabilities >= .5,
                                                               labels=[0, 1], average="macro", zero_division=0)),
                              "positive_f1_at_0_5": float(f1_score(targets, probabilities >= .5, zero_division=0)),
                              "average_precision": (float(average_precision_score(targets, probabilities))
                                                    if len(np.unique(targets)) == 2 else None),
                              "brier_before": float(np.mean((raw_probabilities - targets) ** 2)),
                              "brier_after": float(np.mean((probabilities - targets) ** 2)),
                              "positive_support": int(targets.sum()), "samples": len(targets)}
    return {"split": split, "calibrated_checkpoint_sha256": file_digest(checkpoint_path),
            "predictions_sha256": file_digest(predictions_path), "calibrator_fitted_on": "validation",
            "expression_samples": len(expr_labels),
            "expression_accuracy": float(np.mean(expr_probabilities.argmax(-1) == expr_labels)),
            "expression_nll_after": float(-np.log(np.clip(expr_probabilities[np.arange(len(expr_labels)), expr_labels],
                                                          1e-15, 1)).mean()),
            "states": state_report, "decision_threshold": 0.5, "threshold_fitted_on_test": False,
            "note": "Threshold 0.5 measures decisions; the product returns all ten probabilities."}


def predict_faces(checkpoint_path: Path, face_images: list[Path], device_name: str = "cpu") -> dict:
    """Predict one face, supplied as a crop or several crops from the same clip."""
    from .multitask_model import MultitaskExpressionStateModel

    if not face_images:
        raise ValueError("Supply at least one cropped face image")
    model = MultitaskExpressionStateModel.from_checkpoint(checkpoint_path).to(device_name).eval()
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    transform = build_transforms(model.config, training=False)
    frames = []
    for path in face_images:
        with Image.open(path) as image:
            frames.append(transform(image.convert("RGB")))
    inputs = torch.stack(frames).unsqueeze(0).to(device_name)
    calibration = checkpoint.get("confidence_calibration")
    with torch.inference_mode():
        values = confidence_probabilities(model(inputs), calibration)[0].cpu().tolist()
    return {"confidences": dict(zip(LABEL_NAMES, values)),
            "confidence_percent": {label: round(value * 100, 2) for label, value in zip(LABEL_NAMES, values)},
            "expression_probability_sum": float(sum(values[:7])),
            "states_are_independent": True, "state_positive_definition": POSITIVE_DEFINITION,
            "calibration": "validation_fitted" if calibration else "uncalibrated_model_probability",
            "state_calibration": calibration.get("state_fit") if calibration else None,
            "frames_used": len(frames), "trained_state_frames_per_clip": 4,
            "single_frame_state_prediction_experimental": len(frames) != 4,
            "input_scope": "cropped_faces_of_one_person_from_one_clip",
            "confidence_is_not_measured_accuracy": True, "deployment_ready": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    calibrate = commands.add_parser("calibrate")
    calibrate.add_argument("--checkpoint", type=Path, required=True)
    calibrate.add_argument("--validation-predictions", type=Path, required=True)
    calibrate.add_argument("--output-checkpoint", type=Path, required=True)
    predict = commands.add_parser("predict")
    predict.add_argument("--checkpoint", type=Path, required=True)
    predict.add_argument("--face-images", type=Path, nargs="+", required=True)
    predict.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    predict.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    if args.command == "calibrate":
        result = calibrate_checkpoint(args.checkpoint, args.validation_predictions, args.output_checkpoint)
    else:
        if args.output_json and args.output_json.exists():
            raise FileExistsError("Choose a new prediction output path")
        result = predict_faces(args.checkpoint, args.face_images, args.device)
        if args.output_json:
            save_json(args.output_json, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
