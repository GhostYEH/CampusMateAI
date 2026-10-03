import json

import numpy as np
import onnx
import pytest
import torch
from onnx import helper, numpy_helper

from behavior_recognition.finetune_regularization import (
    configure_trainable,
    l2_sp_penalty,
    sp_reference,
)
from behavior_recognition.onnx_finetune import OnnxBehaviorModel


def _tiny_model(tmp_path):
    arrays = {
        "backbone_weight": np.array([[1.0, 0.5], [0.4, 1.0], [0.2, 0.8]], dtype=np.float32),
        "backbone_bias": np.array([0.1, 0.1, 0.1], dtype=np.float32),
        "head_weight": np.array([[0.5, -0.3, 0.2], [-0.1, 0.4, 0.3]], dtype=np.float32),
        "head_bias": np.array([0.05, -0.05], dtype=np.float32),
    }
    nodes = [
        helper.make_node(
            "Gemm", ["features", "backbone_weight", "backbone_bias"], ["hidden"], transB=1
        ),
        helper.make_node("Relu", ["hidden"], ["activated"]),
        helper.make_node(
            "Gemm", ["activated", "head_weight", "head_bias"], ["logits"], transB=1
        ),
    ]
    graph = helper.make_graph(
        nodes,
        "tiny_finetune",
        [helper.make_tensor_value_info("features", onnx.TensorProto.FLOAT, ["batch", 2])],
        [helper.make_tensor_value_info("logits", onnx.TensorProto.FLOAT, ["batch", 2])],
        [numpy_helper.from_array(array, name) for name, array in arrays.items()],
    )
    proto = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)], ir_version=10)
    path = tmp_path / "tiny.onnx"
    onnx.save(proto, path)
    return OnnxBehaviorModel(path)


def _head_parameter_names(model):
    return {
        f"weights.{model.tensor_keys[name]}"
        for name in ("head_weight", "head_bias")
    }


def test_head_scope_freezes_backbone_and_single_step_updates_only_head(tmp_path):
    model = _tiny_model(tmp_path)
    before = {name: parameter.detach().clone() for name, parameter in model.named_parameters()}
    metadata = configure_trainable(model, scope="head")

    assert set(metadata["trainable_parameters"]) == _head_parameter_names(model)
    assert set(metadata["frozen_parameters"]) == set(before) - _head_parameter_names(model)
    assert metadata["trainable_numel"] == sum(
        before[name].numel() for name in _head_parameter_names(model)
    )
    json.dumps(metadata)
    for name, parameter in model.named_parameters():
        torch.testing.assert_close(parameter, before[name], rtol=0, atol=0)
        assert parameter.requires_grad is (name in _head_parameter_names(model))

    optimizer = torch.optim.SGD(model.parameters(), lr=0.05)
    features = torch.tensor([[1.0, 2.0], [2.0, 1.0]])
    targets = torch.tensor([0, 1])
    optimizer.zero_grad()
    torch.nn.functional.cross_entropy(model(features), targets).backward()
    optimizer.step()

    for name, parameter in model.named_parameters():
        if name in _head_parameter_names(model):
            assert not torch.equal(parameter, before[name])
        else:
            torch.testing.assert_close(parameter, before[name], rtol=0, atol=0)


def test_all_scope_and_l2_sp_penalty_scale_gradient_and_reference_detachment(tmp_path):
    model = _tiny_model(tmp_path)
    all_metadata = configure_trainable(model, scope="all")
    assert set(all_metadata["trainable_parameters"]) == set(dict(model.named_parameters()))
    assert all(parameter.requires_grad for parameter in model.parameters())

    configure_trainable(model, scope="head")
    reference = sp_reference(model)
    reference_before = {name: value.clone() for name, value in reference.items()}
    assert set(reference) == _head_parameter_names(model)
    assert all(not value.requires_grad for value in reference.values())
    torch.testing.assert_close(l2_sp_penalty(model, reference), torch.tensor(0.0))

    changed_name = sorted(reference)[0]
    with torch.no_grad():
        dict(model.named_parameters())[changed_name].add_(0.5)
    penalty = l2_sp_penalty(model, reference)
    expected = 0.5 * 0.5**2 * reference[changed_name].numel()
    assert penalty.item() == pytest.approx(expected)
    penalty.backward()

    for name, parameter in model.named_parameters():
        if name == changed_name:
            torch.testing.assert_close(parameter.grad, torch.full_like(parameter, 0.5))
        elif name in reference:
            torch.testing.assert_close(parameter.grad, torch.zeros_like(parameter))
        else:
            assert parameter.grad is None
    for name, value in reference.items():
        assert value.grad is None
        torch.testing.assert_close(value, reference_before[name], rtol=0, atol=0)


def test_invalid_scope_missing_trainables_and_reference_mismatches_raise(tmp_path):
    model = _tiny_model(tmp_path)
    with pytest.raises(ValueError, match="scope must"):
        configure_trainable(model, scope="classifier")
    with pytest.raises(ValueError, match="scope must"):
        configure_trainable(model, scope=None)

    configure_trainable(model, scope="head")
    reference = sp_reference(model)
    with pytest.raises(ValueError, match="keys do not match"):
        l2_sp_penalty(model, {next(iter(reference)): next(iter(reference.values()))})

    wrong_shape = dict(reference)
    first_name = next(iter(wrong_shape))
    wrong_shape[first_name] = torch.zeros(1, dtype=reference[first_name].dtype)
    with pytest.raises(ValueError, match="shape mismatch"):
        l2_sp_penalty(model, wrong_shape)

    for parameter in model.parameters():
        parameter.requires_grad_(False)
    with pytest.raises(ValueError, match="no trainable parameters"):
        sp_reference(model)
    with pytest.raises(ValueError, match="no trainable parameters"):
        l2_sp_penalty(model, reference)

    with pytest.raises(ValueError, match="no parameters to train"):
        configure_trainable(torch.nn.Module(), scope="all")
