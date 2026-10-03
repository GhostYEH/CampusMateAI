from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import pytest
import torch
from onnx import helper, numpy_helper

from behavior_recognition.onnx_finetune import OnnxBehaviorModel


def test_reconstructed_fused_graph_preserves_logits_and_trained_head_then_has_gradients(tmp_path):
    rng = np.random.default_rng(7)
    arrays = {"w": rng.normal(size=(3, 3, 3, 3)).astype(np.float32),
              "b": rng.normal(size=3).astype(np.float32),
              "head": rng.normal(size=(4, 3)).astype(np.float32),
              "bias": rng.normal(size=4).astype(np.float32)}
    nodes = [helper.make_node("Conv", ["input", "w", "b"], ["conv"], pads=[1, 2, 0, 1]),
             helper.make_node("HardSwish", ["conv"], ["activation"]),
             helper.make_node("GlobalAveragePool", ["activation"], ["pooled"]),
             helper.make_node("Flatten", ["pooled"], ["flat"]),
             helper.make_node("Gemm", ["flat", "head", "bias"], ["output"], transB=1, alpha=0.7, beta=0.2)]
    graph = helper.make_graph(nodes, "fused", [helper.make_tensor_value_info("input", onnx.TensorProto.FLOAT, [1, 3, 8, 8])],
                              [helper.make_tensor_value_info("output", onnx.TensorProto.FLOAT, [1, 4])],
                              [numpy_helper.from_array(array, name) for name, array in arrays.items()])
    proto = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)], ir_version=10)
    path = tmp_path / "source.onnx"
    onnx.save(proto, path)
    original = path.read_bytes()
    model = OnnxBehaviorModel(path)
    sample = torch.from_numpy(rng.normal(size=(1, 3, 8, 8)).astype(np.float32))
    expected = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"]).run(None, {"input": sample.numpy()})[0]
    actual = model(sample)
    np.testing.assert_allclose(actual.detach().numpy(), expected, rtol=1e-5, atol=1e-5)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.001)
    actual.square().sum().backward()
    assert all(parameter.grad is not None and torch.isfinite(parameter.grad).all() for parameter in model.parameters())
    optimizer.step()
    assert not torch.equal(model(sample), actual)
    exported = tmp_path / "candidate.onnx"
    model.export_onnx(exported)
    exported_logits = ort.InferenceSession(str(exported), providers=["CPUExecutionProvider"]).run(None, {"input": sample.numpy()})[0]
    np.testing.assert_allclose(exported_logits, model(sample).detach().numpy(), rtol=1e-5, atol=1e-5)
    with pytest.raises(FileExistsError):
        model.export_onnx(path)
    with pytest.raises(FileExistsError):
        model.export_onnx(exported)
    assert path.read_bytes() == original


def test_unknown_operator_fails_before_training(tmp_path):
    graph = helper.make_graph([helper.make_node("Softmax", ["input"], ["output"])], "unsupported",
                              [helper.make_tensor_value_info("input", onnx.TensorProto.FLOAT, [1, 4])],
                              [helper.make_tensor_value_info("output", onnx.TensorProto.FLOAT, [1, 4])])
    path = tmp_path / "unsupported.onnx"
    onnx.save(helper.make_model(graph), path)
    with pytest.raises(ValueError, match="Unsupported"):
        OnnxBehaviorModel(path)


def test_packaged_v34_full_graph_matches_onnx_and_supports_batching():
    source = Path(__file__).resolve().parents[3] / "android/app/src/main/assets/models/behavior/campusmate_behavior_v34.onnx"
    model = OnnxBehaviorModel(source).eval()
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    session = ort.InferenceSession(str(source), sess_options=options, providers=["CPUExecutionProvider"])
    generator = torch.Generator().manual_seed(20261003)
    samples = torch.randn(2, 3, 224, 224, generator=generator)
    with torch.inference_mode():
        actual = model(samples).numpy()
    expected = np.concatenate([session.run(None, {session.get_inputs()[0].name: sample.numpy()[None]})[0]
                               for sample in samples])
    np.testing.assert_allclose(actual, expected, rtol=1e-4, atol=1e-4)
    np.testing.assert_array_equal(actual.argmax(1), expected.argmax(1))
