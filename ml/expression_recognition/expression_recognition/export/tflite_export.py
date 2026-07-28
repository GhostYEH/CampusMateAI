"""TFLite 导出：ONNX -> TensorFlow SavedModel -> TFLite。

转换流程使用 onnx2tf（PINTO0309/onnx2tf），它是目前最可靠的
ONNX->TF 转换工具之一。若 onnx2tf 或 tensorflow 缺失，本函数会
优雅返回，并在结果中记录原因，不抛异常中断整个导出流程。

环境依赖（可选）：
    pip install onnx2tf tensorflow ai-edge-litert sng4onnx onnx_graphsurgeon

结果文件：
    {tflite_path}.json：导出信息（含 SHA-256、大小、是否成功、错误原因）。
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ..utils.io import ensure_dir, write_json, sha256_of_file, file_size_bytes, format_size


def export_tflite(
    onnx_path: str | Path,
    tflite_path: str | Path,
    tf_dir: str | Path | None = None,
) -> dict[str, Any]:
    """从 ONNX 导出 TFLite。

    Args:
        onnx_path: 输入 ONNX 路径。
        tflite_path: 输出 TFLite 路径。
        tf_dir: 中间 SavedModel 目录（默认 tflite_path 旁的 _tf_saved_model）。

    Returns:
        导出信息字典。若依赖缺失，status="skipped"。
    """
    onnx_path = Path(onnx_path)
    tflite_path = Path(tflite_path)
    ensure_dir(tflite_path.parent)
    if tf_dir is None:
        tf_dir = tflite_path.parent / (tflite_path.stem + "_tf_saved_model")
    else:
        tf_dir = Path(tf_dir)

    info: dict[str, Any] = {
        "onnx_path": str(onnx_path),
        "tflite_path": str(tflite_path),
        "tf_saved_model_dir": str(tf_dir),
        "status": "unknown",
    }

    # 1) 检查依赖。
    missing: list[str] = []
    try:
        import tensorflow  # noqa: F401
    except ImportError:
        missing.append("tensorflow")
    try:
        import onnx2tf  # noqa: F401
    except ImportError:
        missing.append("onnx2tf")
    if missing:
        info["status"] = "skipped"
        info["reason"] = (
            "缺少依赖: " + ", ".join(missing) + "。"
            "请安装: pip install onnx2tf tensorflow ai-edge-litert"
        )
        write_json(str(tflite_path) + ".json", info)
        return info

    # 2) ONNX -> TF SavedModel。
    try:
        import onnx2tf

        # 清理旧目录，避免 onnx2tf 报已存在。
        if tf_dir.exists():
            shutil.rmtree(tf_dir)
        onnx2tf.convert(
            input_onnx_file_path=str(onnx_path),
            output_folder_name=str(tf_dir),
            non_verbose=True,
            # 不替换为 ReLU/等简化，保持数值一致。
        )
        info["tf_saved_model_ok"] = True
    except Exception as e:  # pragma: no cover - 视环境而定
        info["status"] = "failed"
        info["stage"] = "onnx_to_tf"
        info["error"] = f"{type(e).__name__}: {e}"
        write_json(str(tflite_path) + ".json", info)
        return info

    # 3) TF SavedModel -> TFLite。
    try:
        import tensorflow as tf

        converter = tf.lite.TFLiteConverter.from_saved_model(str(tf_dir))
        converter.optimizations = []  # 不做默认量化，保持 fp32 一致性。
        tflite_bytes = converter.convert()
        with tflite_path.open("wb") as f:
            f.write(tflite_bytes)
        info["status"] = "ok"
        info["sha256"] = sha256_of_file(tflite_path)
        info["size"] = format_size(file_size_bytes(tflite_path))
        info["size_bytes"] = file_size_bytes(tflite_path)
    except Exception as e:  # pragma: no cover - 视环境而定
        info["status"] = "failed"
        info["stage"] = "tf_to_tflite"
        info["error"] = f"{type(e).__name__}: {e}"

    write_json(str(tflite_path) + ".json", info)
    return info
