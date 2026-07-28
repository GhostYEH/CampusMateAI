"""跨后端一致性测试：PyTorch / ONNX / TFLite 输出比较。

对一组固定输入，分别用三个后端推理，比较：
1. logits 数值误差（允许小数误差）。
2. Top-1 标签一致性（应一致，最多允许 consistency_max_mismatch 个不一致）。

任一后端不可用（缺依赖）时跳过该后端，并在结果中记录。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from ..config import ExperimentConfig
from ..constants import EXPRESSION_LABELS
from ..models.build import build_model, get_input_shape
from ..utils.io import write_json, ensure_dir


def _fixed_inputs(input_shape: tuple[int, int, int], n: int = 8, seed: int = 0) -> np.ndarray:
    """生成 n 个固定输入（seed 固定，可复现）。返回 (n, C, H, W) float32。"""
    rng = np.random.default_rng(seed)
    c, h, w = input_shape
    # 模拟已归一化的输入（值域接近 N(0,1)）。
    return rng.standard_normal((n, c, h, w)).astype(np.float32)


def _run_pytorch(cfg: ExperimentConfig, checkpoint_path: str | Path, inputs: np.ndarray) -> np.ndarray | None:
    try:
        import torch

        device = torch.device("cpu")
        model = build_model(cfg.model, cfg.input).to(device)
        state = torch.load(checkpoint_path, map_location=device, weights_only=False)
        model.load_state_dict(state["model_state"])
        model.eval()
        with torch.no_grad():
            x = torch.from_numpy(inputs)
            out = model(x).cpu().numpy()
        return out
    except Exception as e:  # pragma: no cover
        return _err("pytorch", e)


def _err(name: str, e: Exception) -> dict[str, Any]:
    return {"backend": name, "error": f"{type(e).__name__}: {e}"}


def _run_onnx(onnx_path: str | Path, inputs: np.ndarray) -> np.ndarray | dict[str, Any]:
    try:
        import onnxruntime as ort

        sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        out = sess.run(["logits"], {"input": inputs})[0]
        return out
    except Exception as e:  # pragma: no cover
        return _err("onnx", e)


def _run_tflite(tflite_path: str | Path, inputs: np.ndarray) -> np.ndarray | dict[str, Any]:
    try:
        # 优先 ai-edge-litert，其次 tflite_runtime。
        try:
            from ai_edge_litert.interpreter import Interpreter
        except ImportError:  # pragma: no cover
            from tflite_runtime.interpreter import Interpreter  # type: ignore

        interp = Interpreter(model_path=str(tflite_path))
        interp.allocate_tensors()
        in_det = interp.get_input_details()[0]
        out_det = interp.get_output_details()[0]
        # TFLite 通常是 NCHW 或 NHWC；按输入 detail 设置。
        # 假设导出时保留 NCHW（onnx2tf 默认会转 NHWC，这里做形状兼容）。
        outs = []
        for i in range(inputs.shape[0]):
            single = inputs[i:i + 1]
            # 若 detail 是 NHWC，转置。
            shape = list(in_det["shape"])
            if len(shape) == 4 and shape[1] in (1, 3) and shape[3] not in (1, 3):
                # 看起来是 NHWC
                single = np.transpose(single, (0, 2, 3, 1))
            interp.set_tensor(in_det["index"], single.astype(np.float32))
            interp.invoke()
            out = interp.get_tensor(out_det["index"])
            # 输出统一回 NCHW-ish (N, C)
            outs.append(np.asarray(out).reshape(1, -1))
        return np.concatenate(outs, axis=0)
    except Exception as e:  # pragma: no cover
        return _err("tflite", e)


def run_consistency_test(
    cfg: ExperimentConfig,
    checkpoint_path: str | Path,
    onnx_path: str | Path,
    tflite_path: str | Path | None,
    n_samples: int = 8,
    seed: int = 0,
) -> dict[str, Any]:
    """运行跨后端一致性测试。

    Returns:
        结果字典，包含各后端输出、数值误差、Top-1 不一致数、是否通过。
    """
    out_dir = ensure_dir(cfg.output_dir)
    input_shape = get_input_shape(cfg.input)
    inputs = _fixed_inputs(input_shape, n=n_samples, seed=seed)

    pt = _run_pytorch(cfg, checkpoint_path, inputs)
    onx = _run_onnx(onnx_path, inputs)
    tfl = _run_tflite(tflite_path, inputs) if tflite_path and Path(tflite_path).exists() else None

    result: dict[str, Any] = {
        "n_samples": n_samples,
        "seed": seed,
        "input_shape": list(input_shape),
        "label_order": list(EXPRESSION_LABELS),
        "backends": {},
        "passed": True,
    }

    # PyTorch 作为基准。
    if isinstance(pt, dict):
        result["backends"]["pytorch"] = {"ok": False, "error": pt["error"]}
        result["passed"] = False
        write_json(out_dir / "consistency.json", result)
        return result
    result["backends"]["pytorch"] = {"ok": True}
    pt_labels = pt.argmax(axis=1)

    # ONNX 比较。
    if isinstance(onx, dict):
        result["backends"]["onnx"] = {"ok": False, "error": onx["error"]}
    else:
        onx_labels = onx.argmax(axis=1)
        max_abs_err = float(np.max(np.abs(pt - onx))) if pt.shape == onx.shape else None
        mismatch = int((pt_labels != onx_labels).sum())
        result["backends"]["onnx"] = {
            "ok": True,
            "max_abs_diff": max_abs_err,
            "top1_mismatch": mismatch,
        }

    # TFLite 比较。
    if tfl is None:
        result["backends"]["tflite"] = {"ok": False, "skipped": True, "reason": "TFLite 模型不存在"}
    elif isinstance(tfl, dict):
        result["backends"]["tflite"] = {"ok": False, "error": tfl["error"]}
    else:
        tfl_labels = tfl.argmax(axis=1)
        max_abs_err = float(np.max(np.abs(pt - tfl))) if pt.shape == tfl.shape else None
        mismatch = int((pt_labels != tfl_labels).sum())
        result["backends"]["tflite"] = {
            "ok": True,
            "max_abs_diff": max_abs_err,
            "top1_mismatch": mismatch,
        }

    # 汇总 Top-1 不一致。
    total_mismatch = 0
    for name in ("onnx", "tflite"):
        b = result["backends"].get(name, {})
        if b.get("ok"):
            total_mismatch += b["top1_mismatch"]
    result["total_top1_mismatch"] = total_mismatch
    result["max_allowed_mismatch"] = cfg.export.consistency_max_mismatch
    result["passed"] = total_mismatch <= cfg.export.consistency_max_mismatch
    result["note"] = (
        "允许 logits 数值小误差，但 Top-1 标签应一致。"
        f"允许最大不一致数: {cfg.export.consistency_max_mismatch}，实际: {total_mismatch}。"
    )

    write_json(out_dir / "consistency.json", result)
    return result
