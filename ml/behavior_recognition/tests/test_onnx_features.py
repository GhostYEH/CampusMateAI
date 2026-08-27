from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper

from behavior_recognition.onnx_features import OnnxFrameFeatureEncoder, create_feature_model


def _write_tiny_model(path: Path) -> None:
    input_info = helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 3, 2, 2])
    output_info = helper.make_tensor_value_info("logits", TensorProto.FLOAT, [1, 3])
    nodes = [
        helper.make_node("GlobalAveragePool", ["input"], ["pooled"]),
        helper.make_node("Flatten", ["pooled"], ["features"], axis=1),
        helper.make_node("Identity", ["features"], ["logits"]),
    ]
    graph = helper.make_graph(nodes, "tiny", [input_info], [output_info])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 10
    onnx.save(model, path)


def test_onnx_encoder_exposes_and_batches_intermediate_features(tmp_path: Path):
    source = tmp_path / "source.onnx"
    derived = tmp_path / "features.onnx"
    _write_tiny_model(source)

    create_feature_model(source, derived, "features", feature_size=3)
    derived_graph = onnx.load(derived).graph
    assert derived_graph.input[0].type.tensor_type.shape.dim[0].dim_param == "batch"
    assert derived_graph.output[-1].type.tensor_type.shape.dim[0].dim_param == "batch"
    encoder = OnnxFrameFeatureEncoder(derived, "features")
    inputs = np.arange(24, dtype=np.float32).reshape(2, 3, 2, 2)
    features = encoder.encode(inputs)

    assert features.shape == (2, 3)
    np.testing.assert_allclose(features, inputs.mean(axis=(2, 3)), rtol=1e-6)
