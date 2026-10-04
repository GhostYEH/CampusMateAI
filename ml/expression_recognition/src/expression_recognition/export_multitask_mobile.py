"""Export a calibrated multitask checkpoint to mobile raw-logit formats.

Input is one 96x96 grayscale face replicated into NHWC RGB channels and
normalized with the checkpoint's ImageNet mean/std. The model returns ten raw
logits in the declared label order. Temporal averaging and calibration remain
in the mobile clients so the same single-frame model serves both platforms.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn

from .constants import CLASS_NAMES
from .data import create_loader
from .export_litert import create_interpreter, create_tensorflow_resnet18, run_interpreter
from .learning_state_experiment import file_digest
from .metrics import calibrate_class_thresholds
from .multitask_confidence import LABEL_NAMES, confidence_probabilities
from .multitask_model import MultiTaskExpressionModel, validate_multitask_checkpoint
from .utils import save_json

STATE_WINDOW_FRAMES = 4
STATE_WINDOW_MAX_AGE_MS = 5000
MINIMUM_ACCEPTED_FOR_THRESHOLDS = 20
DEPLOYMENT_FLOOR = {
    "angry": 0.81,
    "disgust": 0.91,
    "fear": 0.80,
    "happy": 0.30,
    "neutral": 0.83,
    "sad": 0.68,
    "surprise": 0.78,
}


class NhwcMultitaskLogits(nn.Module):
    """Keep one NHWC mobile input while calling the NCHW PyTorch model."""

    def __init__(self, model: MultiTaskExpressionModel):
        super().__init__()
        self.model = model

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        output = self.model(inputs.permute(0, 3, 1, 2).contiguous())
        return torch.cat((output["expression_logits"], output["state_logits"]), dim=1)


class NchwMultitaskLogits(nn.Module):
    """NCHW variant for MindSpore Lite 2.1's ONNX Conv parser."""

    def __init__(self, model: MultiTaskExpressionModel):
        super().__init__()
        self.model = model

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        output = self.model(inputs)
        return torch.cat((output["expression_logits"], output["state_logits"]), dim=1)


def validate_mobile_export_checkpoint(checkpoint: dict) -> None:
    if checkpoint.get("selection_split") != "validation":
        raise ValueError("Mobile export requires a checkpoint selected on validation")
    if checkpoint.get("candidate_only") is not False:
        raise ValueError("Mobile export requires an explicitly selected checkpoint")
    if checkpoint.get("expression_guard_passed") is not True:
        raise ValueError("Mobile export requires a checkpoint that passed the expression guard")


def calibrate_validation_thresholds(checkpoint: dict, predictions_path: Path) -> tuple[dict, dict]:
    """Derive seven-class abstention thresholds from this checkpoint's validation logits."""
    calibration = checkpoint.get("confidence_calibration")
    if not isinstance(calibration, dict):
        raise ValueError("A validation-calibrated checkpoint is required for mobile export")
    if calibration.get("fitted_on") != "validation":
        raise ValueError("Confidence calibration must explicitly identify validation as its fit split")
    if calibration.get("label_order") != LABEL_NAMES:
        raise ValueError("Checkpoint calibration has an incompatible output order")
    if calibration.get("positive_definition") != "DAiSEE level >= 2":
        raise ValueError("Checkpoint calibration has an incompatible state definition")
    if file_digest(predictions_path) != calibration.get("predictions_sha256"):
        raise ValueError("Validation predictions do not match the checkpoint calibration")
    with np.load(predictions_path, allow_pickle=False) as data:
        if str(data["split"].item()) != "validation":
            raise ValueError("Mobile thresholds can only be derived from validation predictions")
        if str(data["checkpoint_sha256"].item()) != calibration.get("source_checkpoint_sha256"):
            raise ValueError("Validation predictions belong to a different source checkpoint")
        logits = torch.as_tensor(data["expression_logits"], dtype=torch.float64)
        targets = np.asarray(data["expression_targets"], dtype=np.int64)
    if logits.ndim != 2 or logits.shape[1] != 7 or targets.shape != (len(logits),):
        raise ValueError("Validation expression predictions have an invalid shape")
    probs = confidence_probabilities(
        {"expression_logits": logits, "state_logits": torch.zeros((len(logits), 3), dtype=logits.dtype)},
        calibration,
    )[:, :7].numpy()
    thresholds, diagnostics = {}, {}
    grid = [round(value, 2) for value in np.arange(0.30, 0.961, 0.01)]
    for name in CLASS_NAMES:
        eligible = [value for value in grid if value >= DEPLOYMENT_FLOOR[name]] + [1.01]
        label_thresholds, label_diagnostics = calibrate_class_thresholds(
            probs,
            targets,
            target_precision=0.80,
            thresholds=eligible,
            minimum_accepted=MINIMUM_ACCEPTED_FOR_THRESHOLDS,
        )
        thresholds[name] = label_thresholds[name]
        diagnostics[name] = label_diagnostics[name]
    return thresholds, diagnostics


def verify_torch_tensorflow(torch_wrapper: nn.Module, keras_model, sample: np.ndarray) -> dict:
    torch_wrapper.eval()
    torch_logits = []
    tf_logits = []
    with torch.inference_mode():
        for frame in sample:
            batch = frame[None, ...]
            torch_logits.append(torch_wrapper(torch.from_numpy(batch)).cpu().numpy())
            tf_logits.append(keras_model(batch, training=False).numpy())
    torch_logits = np.concatenate(torch_logits, axis=0)
    tf_logits = np.concatenate(tf_logits, axis=0)
    difference = np.abs(torch_logits - tf_logits)
    return {
        "sample_count": int(len(sample)),
        "maximum_absolute_logit_error": float(difference.max()),
        "mean_absolute_logit_error": float(difference.mean()),
        "top1_expression_agreement": float(np.mean(torch_logits[:, :7].argmax(1) == tf_logits[:, :7].argmax(1))),
        "maximum_accepted_error": 1e-3,
    }


def validation_samples(manifest: Path, config: dict, count: int = 64) -> np.ndarray:
    eval_config = dict(config)
    eval_config["num_workers"] = 0
    _, loader = create_loader(manifest, "validation", eval_config, training=False, batch_size_override=1)
    values = []
    for inputs, _ in loader:
        values.append(inputs.permute(0, 2, 3, 1).numpy().astype(np.float32))
        if len(values) >= count:
            break
    if not values:
        raise ValueError("Validation manifest produced no samples")
    return np.concatenate(values, axis=0)


def _write_onnx(wrapper: nn.Module, path: Path) -> None:
    sample = torch.zeros(1, 3, 96, 96, dtype=torch.float32)
    torch.onnx.export(
        wrapper.eval(), sample, str(path), input_names=["input"], output_names=["raw_logits"],
        opset_version=17, dynamo=False, do_constant_folding=True,
    )
    # MindSpore Lite 2.1's ONNX parser rejects MaxPool dilations even when
    # they are the ONNX default [1, 1]. Removing that redundant attribute is
    # semantics-preserving and keeps the graph compatible with the repository
    # converter already used for Harmony assets.
    import onnx
    graph = onnx.load(str(path))
    for node in graph.graph.node:
        if node.op_type != "MaxPool":
            continue
        retained = []
        for attribute in node.attribute:
            if attribute.name == "dilations":
                if list(attribute.ints) != [1, 1]:
                    raise ValueError("Only identity MaxPool dilations can be removed for MindSpore Lite 2.1")
                continue
            retained.append(attribute)
        del node.attribute[:]
        node.attribute.extend(retained)
    onnx.checker.check_model(graph)
    onnx.save(graph, str(path))


def export_mobile(checkpoint_path: Path, validation_predictions: Path, manifest: Path, output_dir: Path) -> dict:
    if output_dir.exists():
        raise FileExistsError("Choose a new mobile export directory; existing artifacts are preserved")
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    validate_multitask_checkpoint(checkpoint)
    validate_mobile_export_checkpoint(checkpoint)
    calibration = checkpoint.get("confidence_calibration")
    if not isinstance(calibration, dict):
        raise ValueError("The calibrated multitask checkpoint is required")
    if checkpoint.get("candidate_only") is True or checkpoint.get("expression_guard_passed") is False:
        raise ValueError("Mobile export requires a selected checkpoint that passed the expression guard")
    model = MultiTaskExpressionModel.from_checkpoint(checkpoint_path).cpu().eval()
    if int(model.config["input_size"]) != 96 or int(model.config["input_channels"]) != 3:
        raise ValueError("Mobile export supports the existing 96x96 three-channel contract only")
    wrapper = NhwcMultitaskLogits(model).eval()
    thresholds, threshold_diagnostics = calibrate_validation_thresholds(checkpoint, validation_predictions)

    output_dir.mkdir(parents=True)
    try:
        samples = validation_samples(manifest, model.config)
        import tensorflow as tf

        keras_model = create_tensorflow_resnet18(model.backbone, 96, state_head=model.state_head)
        tf_alignment = verify_torch_tensorflow(wrapper, keras_model, samples[: min(8, len(samples))])
        if (tf_alignment["top1_expression_agreement"] != 1.0
                or tf_alignment["maximum_absolute_logit_error"] > tf_alignment["maximum_accepted_error"]):
            raise RuntimeError(f"PyTorch/TensorFlow weight alignment failed: {tf_alignment}")

        float_path = output_dir / "campusmate_multitask_expression_float32.tflite"
        float_converter = tf.lite.TFLiteConverter.from_keras_model(keras_model)
        float_path.write_bytes(float_converter.convert())
        dynamic_path = output_dir / "campusmate_multitask_expression_dynamic_int8.tflite"
        dynamic_converter = tf.lite.TFLiteConverter.from_keras_model(keras_model)
        dynamic_converter.optimizations = [tf.lite.Optimize.DEFAULT]
        dynamic_path.write_bytes(dynamic_converter.convert())

        interpreter_results = {}
        for name, path in (("float32", float_path), ("dynamic_int8", dynamic_path)):
            interpreter = create_interpreter(path)
            with torch.inference_mode():
                expected = wrapper(torch.from_numpy(samples)).numpy()
            output = np.concatenate([run_interpreter(interpreter, sample[None, ...]) for sample in samples], axis=0)
            difference = np.abs(output - expected)
            interpreter_results[name] = {
                "sample_count": int(len(samples)),
                "maximum_absolute_logit_error": float(difference.max()),
                "mean_absolute_logit_error": float(difference.mean()),
                "top1_expression_agreement": float(np.mean(output[:, :7].argmax(1) == expected[:, :7].argmax(1))),
                "expression_logits_maximum_absolute_error": float(np.abs(output[:, :7] - expected[:, :7]).max()),
                "state_logits_maximum_absolute_error": float(np.abs(output[:, 7:] - expected[:, 7:]).max()),
                "output_shape": list(output.shape),
            }
        float32_result = interpreter_results["float32"]
        if (float32_result["maximum_absolute_logit_error"] > 1e-3
                or float32_result["top1_expression_agreement"] != 1.0):
            raise RuntimeError(f"Float32 LiteRT parity failed: {float32_result}")
        dynamic_result = interpreter_results["dynamic_int8"]
        chosen = "dynamic_int8" if (
            dynamic_result["maximum_absolute_logit_error"] <= 0.02
            and dynamic_result["top1_expression_agreement"] == 1.0
        ) else "float32"

        onnx_wrapper = NchwMultitaskLogits(model).eval()
        onnx_path = output_dir / "campusmate_multitask_expression_mindspore.onnx"
        _write_onnx(onnx_wrapper, onnx_path)
        try:
            import onnxruntime as ort
            session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
            onnx_values = np.concatenate([
                session.run(["raw_logits"], {"input": sample.transpose(2, 0, 1)[None, ...]})[0]
                for sample in samples
            ], axis=0)
            with torch.inference_mode():
                expected = onnx_wrapper(torch.from_numpy(samples.transpose(0, 3, 1, 2).copy())).numpy()
            onnx_error = np.abs(onnx_values - expected)
        except ImportError:
            onnx_error = None
        if onnx_error is not None and float(onnx_error.max()) > 1e-4:
            raise RuntimeError(f"PyTorch/ONNX alignment failed: max error {float(onnx_error.max())}")
        if onnx_error is not None:
            expected = onnx_values[0].reshape(-1)
            samples[0].transpose(2, 0, 1).copy().tofile(output_dir / "mindspore_input.bin")
            fixture = "raw_logits 2 1 10\n" + " ".join(f"{float(value):.9g}" for value in expected) + "\n"
            (output_dir / "mindspore_expected.txt").write_text(fixture, encoding="ascii")

        preprocessing = {
            "input_size": 96,
            "input_channels": 3,
            "input_layout": "NHWC",
            "input_dtype": "float32",
            "input_color_mode": "grayscale_replicated",
            "channel_order": "grayscale replicated to RGB channels",
            "resize": "bilinear",
            "value_scale": "[0,255] -> [0,1]",
            "mean": model.config["normalization"]["mean"],
            "std": model.config["normalization"]["std"],
            "face_crop": model.config.get("face_crop", {}),
        }
        metadata = {
            "model_version": "expression-multitask-calibrated10-v1",
            "checkpoint_sha256": file_digest(checkpoint_path),
            "input_shape": [1, 96, 96, 3],
            "output_size": 10,
            "output_order": LABEL_NAMES,
            "output_type": "logits",
            "android_input_shape": [1, 96, 96, 3],
            "android_input_layout": "NHWC",
            "harmony_input_shape": [1, 3, 96, 96],
            "harmony_input_layout": "NCHW",
            "expression_output": "first 7 logits; temperature-scale, then softmax",
            "state_output": "last 3 logits; four-frame mean, then affine Platt calibration and sigmoid",
            "confidence_calibration": {
                "expression_temperature": calibration["expression_temperature"],
                "state_scales": calibration["state_scales"],
                "state_biases": calibration["state_biases"],
                "positive_definition": "DAiSEE level >= 2",
                "fitted_on": "validation",
            },
            "class_thresholds": thresholds,
            "class_threshold_diagnostics": threshold_diagnostics,
            "confidence_threshold": 0.70,
            "threshold_basis": "calibrated validation predictions; 0.80 precision target, minimum 20 accepted samples, searched only at/above each prior deployed per-class threshold",
            "state_window_frames": STATE_WINDOW_FRAMES,
            "state_window_max_age_ms": STATE_WINDOW_MAX_AGE_MS,
            "states_are_independent": True,
            "state_threshold": None,
            "state_reporting": "calibrated probabilities only; no binary state decision threshold",
            "calibration_validation_predictions_sha256": file_digest(validation_predictions),
            "conversion": {
                "tensorflow_alignment": tf_alignment,
                "litert_parity": interpreter_results,
                "selected_litert_variant": chosen,
                "onnx_maximum_absolute_logit_error": float(onnx_error.max()) if onnx_error is not None else None,
                "onnx_mindspore_compatibility": "removed identity MaxPool dilations attribute for MindSpore Lite 2.1 parser compatibility",
                "mindspore_input_layout": "NCHW",
                "mindspore_parity_fixture": "first fixed validation crop; output compared against ONNX reference",
            },
            "deployment_ready": False,
        }
        for name, path in (("float32", float_path), ("dynamic_int8", dynamic_path), ("onnx", onnx_path)):
            metadata.setdefault("artifacts", {})[name] = {"file": path.name, "sha256": file_digest(path), "size_bytes": path.stat().st_size}
        selected_artifact = metadata["artifacts"][chosen]
        metadata.update({
            "selected_variant": chosen,
            "model_file": selected_artifact["file"],
            "model_sha256": selected_artifact["sha256"],
            "model_size_bytes": selected_artifact["size_bytes"],
        })
        save_json(output_dir / "preprocessing.json", preprocessing)
        save_json(output_dir / "model_metadata.json", metadata)
        training = {
            "model": checkpoint["config"].get("model"),
            "checkpoint_sha256": metadata["checkpoint_sha256"],
            "checkpoint_version": checkpoint["checkpoint_version"],
            "trainable_blocks": checkpoint["config"].get("trainable_blocks"),
            "source_checkpoint_sha256": calibration.get("source_checkpoint_sha256"),
            "calibration_method": calibration.get("method"),
            "calibration_fitted_on": calibration.get("fitted_on"),
            "state_positive_definition": calibration.get("positive_definition"),
            "class_order": LABEL_NAMES,
            "exported_outputs": "seven expression raw logits and three independent state raw logits",
        }
        save_json(output_dir / "training_config.json", training)
        (output_dir / "labels.txt").write_text("\n".join(LABEL_NAMES) + "\n", encoding="utf-8")
        return metadata
    except Exception:
        # Keep failed converter output for diagnosis and never remove user artifacts.
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--validation-predictions", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export_mobile(args.checkpoint, args.validation_predictions, args.manifest, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
