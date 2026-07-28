"""基准测试：单张 CPU 推理延迟、参数量、模型文件大小、ONNX/TFLite 延迟。

延迟测量：单张输入，warmup 后重复多次取均值/中位数/标准差。
所有测量在 CPU 上进行（与端侧部署一致）。

输出 benchmark.json。
"""

from __future__ import annotations

import statistics
import time
from pathlib import Path
from typing import Any

import numpy as np

from ..config import BenchmarkConfig, ExperimentConfig
from ..constants import EXPRESSION_LABELS
from ..models.build import build_model, count_parameters, get_input_shape, dummy_input
from ..utils.io import ensure_dir, write_json, sha256_of_file, file_size_bytes, format_size


def _measure(fn, warmup: int, repeats: int) -> dict[str, float]:
    """测量 fn 单次调用耗时（毫秒）。"""
    for _ in range(warmup):
        fn()
    times_ms: list[float] = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        t1 = time.perf_counter()
        times_ms.append((t1 - t0) * 1000.0)
    return {
        "mean_ms": float(statistics.mean(times_ms)),
        "median_ms": float(statistics.median(times_ms)),
        "std_ms": float(statistics.pstdev(times_ms)) if len(times_ms) > 1 else 0.0,
        "min_ms": float(min(times_ms)),
        "max_ms": float(max(times_ms)),
        "repeats": repeats,
        "warmup": warmup,
    }


def run_benchmark(
    cfg: ExperimentConfig,
    checkpoint_path: str | Path,
    onnx_path: str | Path | None = None,
    tflite_path: str | Path | None = None,
) -> dict[str, Any]:
    """运行基准测试。

    Returns:
        benchmark 结果字典，写入 benchmark.json。
    """
    import torch

    out_dir = ensure_dir(cfg.output_dir)
    device = torch.device("cpu")
    bcfg: BenchmarkConfig = cfg.benchmark

    # 重建模型。
    model = build_model(cfg.model, cfg.input).to(device)
    state = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(state["model_state"])
    model.eval()

    x = dummy_input(cfg.input).to(device)
    input_shape = get_input_shape(cfg.input)

    result: dict[str, Any] = {
        "experiment_name": cfg.experiment_name,
        "model_name": cfg.model.name,
        "device": "cpu",
        "input_shape": list(input_shape),
        "label_order": list(EXPRESSION_LABELS),
        "param_counts": count_parameters(model),
        "checkpoint": {
            "path": str(checkpoint_path),
            "sha256": sha256_of_file(checkpoint_path),
            "size": format_size(file_size_bytes(checkpoint_path)),
            "size_bytes": file_size_bytes(checkpoint_path),
        },
    }

    # PyTorch CPU 延迟。
    with torch.no_grad():
        result["pytorch_latency_ms"] = _measure(
            lambda: model(x), bcfg.warmup, bcfg.repeats
        )

    # ONNX 延迟。
    if onnx_path and Path(onnx_path).exists():
        try:
            import onnxruntime as ort

            sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
            x_np = x.numpy()
            result["onnx_latency_ms"] = _measure(
                lambda: sess.run(["logits"], {"input": x_np}), bcfg.warmup, bcfg.repeats
            )
            result["onnx_file"] = {
                "path": str(onnx_path),
                "sha256": sha256_of_file(onnx_path),
                "size": format_size(file_size_bytes(onnx_path)),
                "size_bytes": file_size_bytes(onnx_path),
            }
        except Exception as e:  # pragma: no cover
            result["onnx_error"] = f"{type(e).__name__}: {e}"

    # TFLite 延迟。
    if tflite_path and Path(tflite_path).exists():
        try:
            try:
                from ai_edge_litert.interpreter import Interpreter
            except ImportError:  # pragma: no cover
                from tflite_runtime.interpreter import Interpreter  # type: ignore

            interp = Interpreter(model_path=str(tflite_path))
            interp.allocate_tensors()
            in_det = interp.get_input_details()[0]
            single = x.numpy()
            # 兼容 NHWC。
            shape = list(in_det["shape"])
            if len(shape) == 4 and shape[1] in (1, 3) and shape[3] not in (1, 3):
                single_nhwc = np.transpose(single, (0, 2, 3, 1))
            else:
                single_nhwc = single

            def _tflite_call():
                interp.set_tensor(in_det["index"], single_nhwc.astype(np.float32))
                interp.invoke()

            result["tflite_latency_ms"] = _measure(_tflite_call, bcfg.warmup, bcfg.repeats)
            result["tflite_file"] = {
                "path": str(tflite_path),
                "sha256": sha256_of_file(tflite_path),
                "size": format_size(file_size_bytes(tflite_path)),
                "size_bytes": file_size_bytes(tflite_path),
            }
        except Exception as e:  # pragma: no cover
            result["tflite_error"] = f"{type(e).__name__}: {e}"

    write_json(out_dir / "benchmark.json", result)
    return result
