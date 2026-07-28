"""ONNX 导出。

用 torch.onnx.export 导出模型，固定动态 batch（可选动态轴）。
导出后用 onnxruntime 做一次推理验证可运行。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from ..config import ExperimentConfig, InputConfig
from ..constants import EXPRESSION_LABELS
from ..models.build import build_model, dummy_input
from ..utils.io import ensure_dir, write_json, sha256_of_file, file_size_bytes, format_size


def export_onnx(
    cfg: ExperimentConfig,
    checkpoint_path: str | Path,
    onnx_path: str | Path,
) -> dict[str, Any]:
    """导出 ONNX 模型。

    Args:
        cfg: 实验配置。
        checkpoint_path: PyTorch 检查点路径。
        onnx_path: 输出 ONNX 路径。

    Returns:
        导出信息字典（含 SHA-256、大小、是否可推理）。
    """
    import torch

    onnx_path = Path(onnx_path)
    ensure_dir(onnx_path.parent)
    device = torch.device("cpu")

    model = build_model(cfg.model, cfg.input).to(device)
    state = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(state["model_state"])
    model.eval()

    dummy = dummy_input(cfg.input).to(device)

    # 动态 batch 维度，便于端侧单张或批量推理。
    dynamic_axes = {"input": {0: "batch"}, "logits": {0: "batch"}}
    # torch 2.12 默认走 dynamo 导出器，但 dynamic_axes 在 dynamo 模式下不被推荐，
    # 且 dynamo 对部分模型（含 BatchNorm）图形捕获不稳定。这里显式用 legacy
    # 导出器（dynamo=False），它在 torch 2.12 仍是稳定路径，且 dynamic_axes 行为可靠。
    # 若未来 torch 移除 legacy 导出器，再迁移到 dynamo + Dim dynamic_shapes。
    effective_opset = max(cfg.export.onnx_opset, 13)
    try:
        torch.onnx.export(
            model,
            dummy,
            str(onnx_path),
            input_names=["input"],
            output_names=["logits"],
            dynamic_axes=dynamic_axes,
            opset_version=effective_opset,
            do_constant_folding=True,
            dynamo=False,
        )
        used_exporter = "legacy"
    except TypeError:
        # 旧版 torch 无 dynamo 参数。
        torch.onnx.export(
            model,
            dummy,
            str(onnx_path),
            input_names=["input"],
            output_names=["logits"],
            dynamic_axes=dynamic_axes,
            opset_version=effective_opset,
            do_constant_folding=True,
        )
        used_exporter = "legacy_no_dynamo_kw"

    # 读回实际 opset。
    actual_opset = effective_opset
    try:
        import onnx

        onnx_model = onnx.load(str(onnx_path))
        actual_opset = next(
            (op.version for op in onnx_model.opset_import if op.domain in ("", "ai.onnx")),
            effective_opset,
        )
    except Exception:
        pass

    info: dict[str, Any] = {
        "onnx_path": str(onnx_path),
        "opset_version_requested": cfg.export.onnx_opset,
        "opset_version_effective": effective_opset,
        "opset_version_actual": actual_opset,
        "input_name": "input",
        "output_name": "logits",
        "dynamic_axes": dynamic_axes,
        "exporter": used_exporter,
        "sha256": sha256_of_file(onnx_path),
        "size": format_size(file_size_bytes(onnx_path)),
        "size_bytes": file_size_bytes(onnx_path),
        "label_order": list(EXPRESSION_LABELS),
    }

    # 用 onnxruntime 验证可运行（可选依赖）。
    try:
        import onnxruntime as ort

        sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        x = dummy.numpy()
        out = sess.run(["logits"], {"input": x})[0]
        info["onnxruntime_ok"] = True
        info["onnxruntime_output_shape"] = list(out.shape)
        info["onnxruntime_version"] = ort.__version__
    except Exception as e:  # pragma: no cover - 视环境而定
        info["onnxruntime_ok"] = False
        info["onnxruntime_error"] = f"{type(e).__name__}: {e}"

    write_json(onnx_path.with_suffix(".onnx.json"), info)
    return info
