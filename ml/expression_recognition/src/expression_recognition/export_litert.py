from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

from .constants import CLASS_NAMES, LABEL_TO_ANDROID
from .data import create_loader
from .metrics import compute_classification_metrics
from .models import build_model
from .utils import save_json


class NhwcInputWrapper(nn.Module):
    """Expose a mobile-friendly NHWC input while preserving PyTorch NCHW math."""

    def __init__(self, model: nn.Module):
        super().__init__()
        self.model = model

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.model(inputs.permute(0, 3, 1, 2).contiguous())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def create_interpreter(model_path: Path):
    try:
        from ai_edge_litert.interpreter import Interpreter
    except ImportError:
        try:
            from tensorflow.lite import Interpreter
        except ImportError:
            # TensorFlow 2.20 removed the public tensorflow.lite.Interpreter
            # alias, while retaining the implementation used by the desktop
            # verifier. Keep this fallback local to export/verification so the
            # Android runtime contract remains unchanged.
            from tensorflow.lite.python.interpreter import Interpreter

    interpreter = Interpreter(model_path=str(model_path), num_threads=4)
    interpreter.allocate_tensors()
    return interpreter


def run_interpreter(interpreter, inputs: np.ndarray) -> np.ndarray:
    input_detail = interpreter.get_input_details()[0]
    output_detail = interpreter.get_output_details()[0]
    input_values = inputs.astype(np.float32, copy=False)
    if np.issubdtype(input_detail["dtype"], np.integer):
        scale, zero_point = input_detail["quantization"]
        input_values = np.round(input_values / scale + zero_point).clip(
            np.iinfo(input_detail["dtype"]).min,
            np.iinfo(input_detail["dtype"]).max,
        )
    interpreter.set_tensor(input_detail["index"], input_values.astype(input_detail["dtype"], copy=False))
    interpreter.invoke()
    output = interpreter.get_tensor(output_detail["index"]).copy()
    if np.issubdtype(output_detail["dtype"], np.integer):
        scale, zero_point = output_detail["quantization"]
        output = (output.astype(np.float32) - zero_point) * scale
    return output


def benchmark_litert(model_path: Path, sample: np.ndarray) -> dict:
    interpreter = create_interpreter(model_path)
    for _ in range(20):
        run_interpreter(interpreter, sample)
    timings = []
    for _ in range(150):
        started = time.perf_counter()
        run_interpreter(interpreter, sample)
        timings.append((time.perf_counter() - started) * 1000)
    return {
        "runtime": "ai-edge-litert desktop CPU",
        "mean_latency_ms": float(np.mean(timings)),
        "p50_latency_ms": float(np.percentile(timings, 50)),
        "p95_latency_ms": float(np.percentile(timings, 95)),
        "throughput_samples_per_second": float(1000.0 / np.mean(timings)),
    }


def evaluate_litert(
    model_path: Path,
    manifest: Path,
    config: dict,
    split: str,
) -> dict:
    eval_config = dict(config)
    eval_config["num_workers"] = 0
    _, loader = create_loader(
        manifest,
        split,
        eval_config,
        training=False,
        batch_size_override=1,
    )
    interpreter = create_interpreter(model_path)
    probabilities = []
    targets = []
    for inputs, labels in loader:
        nhwc = inputs.permute(0, 2, 3, 1).numpy().astype(np.float32)
        logits = run_interpreter(interpreter, nhwc)
        shifted = logits - logits.max(axis=1, keepdims=True)
        exp_values = np.exp(shifted)
        probabilities.append(exp_values / exp_values.sum(axis=1, keepdims=True))
        targets.append(labels.numpy())
    metrics = compute_classification_metrics(
        np.concatenate(probabilities),
        np.concatenate(targets),
    )
    return metrics


def alignment_check(
    wrapper: nn.Module,
    model_path: Path,
    manifest: Path,
    config: dict,
    sample_count: int = 64,
) -> dict:
    eval_config = dict(config)
    eval_config["num_workers"] = 0
    _, loader = create_loader(
        manifest,
        "validation",
        eval_config,
        training=False,
        batch_size_override=1,
    )
    interpreter = create_interpreter(model_path)
    absolute_differences = []
    matches = []
    wrapper.eval()
    with torch.no_grad():
        for index, (inputs, _) in enumerate(loader):
            if index >= sample_count:
                break
            nhwc = inputs.permute(0, 2, 3, 1).contiguous()
            torch_output = wrapper(nhwc).numpy()
            litert_output = run_interpreter(interpreter, nhwc.numpy())
            absolute_differences.append(np.abs(torch_output - litert_output))
            matches.append(int(torch_output.argmax(1)[0] == litert_output.argmax(1)[0]))
    differences = np.concatenate(absolute_differences)
    return {
        "sample_count": len(matches),
        "maximum_absolute_logit_error": float(differences.max()),
        "mean_absolute_logit_error": float(differences.mean()),
        "top1_agreement": float(np.mean(matches)),
    }


def export_dynamic_range_ai_edge(float_model_path: Path, output_path: Path) -> None:
    from ai_edge_quantizer import quantizer, recipe

    qt = quantizer.Quantizer(float_model_path)
    qt.load_quantization_recipe(recipe.dynamic_wi8_afp32())
    result = qt.quantize()
    result.export_model(output_path, overwrite=True)


def _set_conv_weights(keras_layer, torch_layer: nn.Conv2d) -> None:
    weights = torch_layer.weight.detach().cpu().numpy().transpose(2, 3, 1, 0)
    values = [weights]
    if torch_layer.bias is not None:
        values.append(torch_layer.bias.detach().cpu().numpy())
    keras_layer.set_weights(values)


def _set_batch_norm_weights(keras_layer, torch_layer: nn.BatchNorm2d) -> None:
    keras_layer.set_weights(
        [
            torch_layer.weight.detach().cpu().numpy(),
            torch_layer.bias.detach().cpu().numpy(),
            torch_layer.running_mean.detach().cpu().numpy(),
            torch_layer.running_var.detach().cpu().numpy(),
        ]
    )


def create_tensorflow_resnet18(torch_model: nn.Module, input_size: int):
    """Create an inference-only NHWC Keras ResNet18 and transfer torchvision weights."""
    import tensorflow as tf

    layers = tf.keras.layers
    inputs = tf.keras.Input(
        shape=(input_size, input_size, 3),
        batch_size=1,
        dtype=tf.float32,
        name="expression_input",
    )
    x = layers.ZeroPadding2D(3, name="stem_pad")(inputs)
    x = layers.Conv2D(
        64,
        7,
        strides=2,
        padding="valid",
        use_bias=False,
        name="conv1",
    )(x)
    x = layers.BatchNormalization(epsilon=1e-5, name="bn1")(x)
    x = layers.ReLU(name="stem_relu")(x)
    x = layers.ZeroPadding2D(1, name="pool_pad")(x)
    x = layers.MaxPool2D(3, strides=2, padding="valid", name="maxpool")(x)

    stage_filters = (64, 128, 256, 512)
    for stage_index, (torch_stage, filters) in enumerate(
        zip(
            (
                torch_model.layer1,
                torch_model.layer2,
                torch_model.layer3,
                torch_model.layer4,
            ),
            stage_filters,
        ),
        start=1,
    ):
        for block_index, torch_block in enumerate(torch_stage):
            prefix = f"layer{stage_index}_block{block_index}"
            stride = int(torch_block.conv1.stride[0])
            residual = x
            x = layers.ZeroPadding2D(1, name=f"{prefix}_pad1")(x)
            x = layers.Conv2D(
                filters,
                3,
                strides=stride,
                padding="valid",
                use_bias=False,
                name=f"{prefix}_conv1",
            )(x)
            x = layers.BatchNormalization(
                epsilon=1e-5,
                name=f"{prefix}_bn1",
            )(x)
            x = layers.ReLU(name=f"{prefix}_relu1")(x)
            x = layers.ZeroPadding2D(1, name=f"{prefix}_pad2")(x)
            x = layers.Conv2D(
                filters,
                3,
                padding="valid",
                use_bias=False,
                name=f"{prefix}_conv2",
            )(x)
            x = layers.BatchNormalization(
                epsilon=1e-5,
                name=f"{prefix}_bn2",
            )(x)
            if torch_block.downsample is not None:
                residual = layers.Conv2D(
                    filters,
                    1,
                    strides=stride,
                    padding="valid",
                    use_bias=False,
                    name=f"{prefix}_downsample_conv",
                )(residual)
                residual = layers.BatchNormalization(
                    epsilon=1e-5,
                    name=f"{prefix}_downsample_bn",
                )(residual)
            x = layers.Add(name=f"{prefix}_add")([x, residual])
            x = layers.ReLU(name=f"{prefix}_relu2")(x)

    x = layers.GlobalAveragePooling2D(name="avgpool")(x)
    outputs = layers.Dense(7, name="fc")(x)
    keras_model = tf.keras.Model(inputs, outputs, name="expression_resnet18")

    _set_conv_weights(keras_model.get_layer("conv1"), torch_model.conv1)
    _set_batch_norm_weights(keras_model.get_layer("bn1"), torch_model.bn1)
    for stage_index, torch_stage in enumerate(
        (
            torch_model.layer1,
            torch_model.layer2,
            torch_model.layer3,
            torch_model.layer4,
        ),
        start=1,
    ):
        for block_index, torch_block in enumerate(torch_stage):
            prefix = f"layer{stage_index}_block{block_index}"
            _set_conv_weights(
                keras_model.get_layer(f"{prefix}_conv1"),
                torch_block.conv1,
            )
            _set_batch_norm_weights(
                keras_model.get_layer(f"{prefix}_bn1"),
                torch_block.bn1,
            )
            _set_conv_weights(
                keras_model.get_layer(f"{prefix}_conv2"),
                torch_block.conv2,
            )
            _set_batch_norm_weights(
                keras_model.get_layer(f"{prefix}_bn2"),
                torch_block.bn2,
            )
            if torch_block.downsample is not None:
                _set_conv_weights(
                    keras_model.get_layer(f"{prefix}_downsample_conv"),
                    torch_block.downsample[0],
                )
                _set_batch_norm_weights(
                    keras_model.get_layer(f"{prefix}_downsample_bn"),
                    torch_block.downsample[1],
                )
    keras_model.get_layer("fc").set_weights(
        [
            torch_model.fc.weight.detach().cpu().numpy().T,
            torch_model.fc.bias.detach().cpu().numpy(),
        ]
    )
    return keras_model


def tensorflow_alignment_check(
    wrapper: nn.Module,
    keras_model,
    manifest: Path,
    config: dict,
    sample_count: int = 64,
) -> dict:
    eval_config = dict(config)
    eval_config["num_workers"] = 0
    _, loader = create_loader(
        manifest,
        "validation",
        eval_config,
        training=False,
        batch_size_override=1,
    )
    absolute_differences = []
    matches = []
    wrapper.eval()
    with torch.no_grad():
        for index, (inputs, _) in enumerate(loader):
            if index >= sample_count:
                break
            nhwc = inputs.permute(0, 2, 3, 1).contiguous()
            torch_output = wrapper(nhwc).numpy()
            tensorflow_output = keras_model(nhwc.numpy(), training=False).numpy()
            absolute_differences.append(np.abs(torch_output - tensorflow_output))
            matches.append(
                int(torch_output.argmax(1)[0] == tensorflow_output.argmax(1)[0])
            )
    differences = np.concatenate(absolute_differences)
    return {
        "sample_count": len(matches),
        "maximum_absolute_logit_error": float(differences.max()),
        "mean_absolute_logit_error": float(differences.mean()),
        "top1_agreement": float(np.mean(matches)),
    }


def export_with_tensorflow(
    torch_model: nn.Module,
    wrapper: nn.Module,
    manifest: Path,
    config: dict,
    float_path: Path,
    dynamic_path: Path,
    float16_path: Path,
    full_int8_path: Path,
) -> dict:
    import tensorflow as tf

    keras_model = create_tensorflow_resnet18(
        torch_model,
        int(config["input_size"]),
    )
    source_alignment = tensorflow_alignment_check(
        wrapper,
        keras_model,
        manifest,
        config,
    )
    if (
        source_alignment["top1_agreement"] < 1.0
        or source_alignment["maximum_absolute_logit_error"] > 1e-3
    ):
        raise RuntimeError(
            "TensorFlow weight transfer failed alignment acceptance criteria: "
            f"{source_alignment}"
        )

    float_converter = tf.lite.TFLiteConverter.from_keras_model(keras_model)
    float_path.write_bytes(float_converter.convert())

    dynamic_converter = tf.lite.TFLiteConverter.from_keras_model(keras_model)
    dynamic_converter.optimizations = [tf.lite.Optimize.DEFAULT]
    dynamic_path.write_bytes(dynamic_converter.convert())

    float16_converter = tf.lite.TFLiteConverter.from_keras_model(keras_model)
    float16_converter.optimizations = [tf.lite.Optimize.DEFAULT]
    float16_converter.target_spec.supported_types = [tf.float16]
    float16_path.write_bytes(float16_converter.convert())

    def representative_dataset():
        eval_config = dict(config)
        eval_config["num_workers"] = 0
        _, loader = create_loader(manifest, "validation", eval_config, training=False, batch_size_override=1)
        for index, (inputs, _) in enumerate(loader):
            if index >= 256:
                break
            yield [inputs.permute(0, 2, 3, 1).numpy().astype(np.float32)]

    full_int8_converter = tf.lite.TFLiteConverter.from_keras_model(keras_model)
    full_int8_converter.optimizations = [tf.lite.Optimize.DEFAULT]
    full_int8_converter.representative_dataset = representative_dataset
    full_int8_converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    full_int8_converter.inference_input_type = tf.int8
    full_int8_converter.inference_output_type = tf.int8
    full_int8_path.write_bytes(full_int8_converter.convert())
    return {"source_alignment": source_alignment, "representative_sample_limit": 256}


def tensor_contract(model_path: Path) -> dict:
    interpreter = create_interpreter(model_path)
    input_detail = interpreter.get_input_details()[0]
    output_detail = interpreter.get_output_details()[0]
    return {
        "input_shape": input_detail["shape"].tolist(),
        "input_dtype": str(np.dtype(input_detail["dtype"])),
        "input_quantization": [float(value) for value in input_detail["quantization"]],
        "output_shape": output_detail["shape"].tolist(),
        "output_dtype": str(np.dtype(output_detail["dtype"])),
        "output_quantization": [float(value) for value in output_detail["quantization"]],
    }


def choose_variant(results: dict[str, dict]) -> str:
    float_f1 = results["float32"]["validation_metrics"]["macro_f1"]
    dynamic_f1 = results["dynamic_int8"]["validation_metrics"]["macro_f1"]
    if dynamic_f1 >= float_f1 - 0.01:
        return "dynamic_int8"
    return "float32"


def write_deployment_files(
    output_dir: Path,
    android_assets: Path,
    checkpoint: Path,
    config: dict,
    results: dict,
    chosen_variant: str,
    confidence_threshold: float,
    model_version: str,
    export_details: dict,
) -> None:
    chosen_path = Path(results[chosen_variant]["path"])
    output_dir.mkdir(parents=True, exist_ok=True)
    android_assets.mkdir(parents=True, exist_ok=True)
    labels_path = output_dir / "labels.txt"
    labels_path.write_text(
        "\n".join(
            f"{index} {label} {LABEL_TO_ANDROID[label]}"
            for index, label in enumerate(CLASS_NAMES)
        ) + "\n",
        encoding="utf-8",
    )
    preprocessing = {
        "input_size": config["input_size"],
        "input_channels": config["input_channels"],
        "input_layout": "NHWC",
        "input_color_mode": "grayscale_replicated",
        "channel_order": "grayscale replicated to RGB channels",
        "source_camera_conversion": "YUV_420_888 -> upright mirrored RGB bitmap",
        "resize": "bilinear",
        "value_scale": "[0,255] -> [0,1]",
        "mean": config["normalization"]["mean"],
        "std": config["normalization"]["std"],
        "confidence_threshold": confidence_threshold,
        "class_thresholds": results[chosen_variant]["validation_metrics"].get("class_thresholds", {}),
        "threshold_basis": "per-class validation abstention calibration targeting 0.80 precision",
        "face_crop": {
            "padding_x_fraction": float(config.get("face_crop", {}).get("padding_x_fraction", 0.16)),
            "padding_y_fraction": float(config.get("face_crop", {}).get("padding_y_fraction", 0.20)),
        },
        "model_version": model_version,
    }
    save_json(output_dir / "preprocessing.json", preprocessing)
    model_metadata = {
        "model_version": model_version,
        "architecture": config["model"],
        "selected_variant": chosen_variant,
        "class_order": CLASS_NAMES,
        "android_mapping": LABEL_TO_ANDROID,
        "model_sha256": sha256(chosen_path),
        "model_size_bytes": chosen_path.stat().st_size,
        "confidence_threshold": confidence_threshold,
        "class_thresholds": results[chosen_variant]["validation_metrics"].get("class_thresholds", {}),
        "unknown_policy": "below threshold, diffuse probability, or unstable sequence",
        "no_face_policy": "produced by ML Kit face detection, not by classifier",
        "test_metrics": results[chosen_variant]["test_metrics"],
        "alignment": results[chosen_variant]["alignment"],
        "desktop_litert_benchmark": results[chosen_variant]["benchmark"],
        "export": export_details,
        "limitations": [
            "FER-style labels describe observable facial expressions, not mental health.",
            "The cleaned dataset still contains label noise and severe class imbalance.",
            "Campus lighting, pose, occlusion, demographics, and camera quality cause domain shift.",
            "No real Android device latency measurement is claimed.",
        ],
    }
    save_json(output_dir / "model_metadata.json", model_metadata)
    save_json(output_dir / "training_config.json", config)
    shutil.copy2(checkpoint, output_dir / "best_checkpoint.pt")
    shutil.copy2(chosen_path, android_assets / "expression_model.tflite")
    shutil.copy2(labels_path, android_assets / "labels.txt")
    shutil.copy2(output_dir / "preprocessing.json", android_assets / "preprocessing.json")
    shutil.copy2(output_dir / "model_metadata.json", android_assets / "model_metadata.json")
    (output_dir / "model.sha256").write_text(
        f"{sha256(chosen_path)}  {chosen_path.name}\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert, quantize and verify a model with LiteRT.")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--android-assets", type=Path, required=True)
    parser.add_argument("--confidence-threshold", type=float, default=0.70)
    parser.add_argument("--model-version", default="expression-resnet18-clean-v1")
    parser.add_argument(
        "--converter",
        choices=("auto", "ai-edge-torch", "tensorflow"),
        default="auto",
        help="Prefer AI Edge Torch; auto uses verified TensorFlow transfer if unavailable.",
    )
    args = parser.parse_args()

    checkpoint_data = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    config = checkpoint_data["config"]
    model = build_model(config, allow_download=False)
    model.load_state_dict(checkpoint_data["model_state"])
    model.eval()
    wrapper = NhwcInputWrapper(model).eval()
    sample = torch.randn(
        1,
        int(config["input_size"]),
        int(config["input_size"]),
        int(config["input_channels"]),
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    float_path = args.output_dir / "expression_resnet18_float32.tflite"
    dynamic_path = args.output_dir / "expression_resnet18_dynamic_int8.tflite"
    float16_path = args.output_dir / "expression_resnet18_float16.tflite"
    full_int8_path = args.output_dir / "expression_resnet18_full_int8.tflite"

    export_details = {
        "requested_converter": args.converter,
        "selected_converter": None,
        "fallback_reason": None,
        "source_framework_alignment": None,
    }
    if args.converter in ("auto", "ai-edge-torch"):
        try:
            import ai_edge_torch

            edge_model = ai_edge_torch.convert(wrapper, (sample,))
            edge_model.export(float_path)
            export_dynamic_range_ai_edge(float_path, dynamic_path)
            export_details["selected_converter"] = "ai-edge-torch"
            export_details["fallback_reason"] = "AI Edge Torch path does not provide the complete TensorFlow representative export set; TensorFlow export is required for float16/full-int8."
            source_alignment = export_with_tensorflow(model, wrapper, args.manifest, config, float_path, dynamic_path, float16_path, full_int8_path)
            export_details["source_framework_alignment"] = source_alignment
        except Exception as error:
            if args.converter == "ai-edge-torch":
                raise
            export_details["fallback_reason"] = (
                f"{type(error).__name__}: {error}"
            )
    if export_details["selected_converter"] is None:
        source_alignment = export_with_tensorflow(
            model,
            wrapper,
            args.manifest,
            config,
            float_path,
            dynamic_path,
            float16_path,
            full_int8_path,
        )
        export_details["selected_converter"] = "tensorflow-lite-converter"
        export_details["source_framework_alignment"] = source_alignment

    results = {}
    for variant, path in (("float32", float_path), ("dynamic_int8", dynamic_path), ("float16", float16_path), ("full_int8", full_int8_path)):
        results[variant] = {
            "path": str(path.resolve()),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
            "tensor_contract": tensor_contract(path),
            "alignment": alignment_check(wrapper, path, args.manifest, config),
            "validation_metrics": evaluate_litert(
                path,
                args.manifest,
                config,
                "validation",
            ),
            "benchmark": benchmark_litert(path, sample.numpy()),
        }
    chosen_variant = choose_variant(results)
    for variant in ("float32", "dynamic_int8", "float16", "full_int8"):
        results[variant]["test_metrics"] = evaluate_litert(
            Path(results[variant]["path"]),
            args.manifest,
            config,
            "test",
        )
    results["selected_variant"] = chosen_variant
    results["selection_rule"] = (
        "dynamic int8 selected if validation macro-F1 loss is <= 0.01; full int8 is compared but is not Android-compatible with the current float32 input contract; "
        "test metrics for both exports are regression evidence only and do not alter selection"
    )
    results["export"] = export_details
    save_json(args.output_dir / "litert_verification.json", results)
    write_deployment_files(
        args.output_dir,
        args.android_assets,
        args.checkpoint,
        config,
        results,
        chosen_variant,
        args.confidence_threshold,
        args.model_version,
        export_details,
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
