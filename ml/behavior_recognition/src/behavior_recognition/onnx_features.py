from __future__ import annotations

from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnx import TensorProto, helper


def create_feature_model(
    source_path: Path,
    destination_path: Path,
    output_name: str,
    *,
    feature_size: int,
) -> Path:
    model = onnx.load(source_path)
    available = {name for node in model.graph.node for name in node.output}
    if output_name not in available:
        raise ValueError(f"ONNX intermediate output not found: {output_name}")
    if output_name not in {output.name for output in model.graph.output}:
        model.graph.output.append(
            helper.make_tensor_value_info(
                output_name, TensorProto.FLOAT, [1, feature_size]
            )
        )
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, destination_path)
    return destination_path


class OnnxFrameFeatureEncoder:
    def __init__(self, model_path: Path, output_name: str):
        self.output_name = output_name
        self.session = ort.InferenceSession(
            str(model_path), providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name

    def encode(self, inputs: np.ndarray) -> np.ndarray:
        values = np.asarray(inputs, dtype=np.float32)
        if values.ndim != 4:
            raise ValueError("Expected ONNX frame inputs shaped [batch, channels, height, width]")
        outputs = [
            self.session.run([self.output_name], {self.input_name: value[None]})[0][0]
            for value in values
        ]
        return np.stack(outputs).astype(np.float32, copy=False)

