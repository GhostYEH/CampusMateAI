"""Parameter selection and L2-SP regularization for ONNX fine-tuning."""
from __future__ import annotations

from collections.abc import Mapping

import torch
from torch import nn


def _named_parameters(model: nn.Module) -> dict[str, nn.Parameter]:
    if not isinstance(model, nn.Module):
        raise TypeError("model must be a torch.nn.Module")
    parameters = dict(model.named_parameters())
    if not parameters:
        raise ValueError("model has no parameters to train")
    return parameters


def configure_trainable(model: nn.Module, scope: str = "head") -> dict[str, object]:
    """Freeze model parameters except the requested fine-tuning scope.

    ``head`` selects only initializer-backed weight and optional bias tensors
    for the Gemm node that produces ``model.output_name``. ``all`` makes every
    model parameter trainable. Parameter values are left untouched.

    The returned dictionary contains only JSON-serializable names and counts.
    """
    if not isinstance(scope, str) or scope not in {"head", "all"}:
        raise ValueError("scope must be 'head' or 'all'")

    parameters = _named_parameters(model)
    if scope == "all":
        trainable_names = set(parameters)
    else:
        tensor_keys = getattr(model, "tensor_keys", None)
        nodes = getattr(model, "nodes", None)
        output_name = getattr(model, "output_name", None)
        if not isinstance(tensor_keys, Mapping) or nodes is None or not output_name:
            raise ValueError("head scope requires an ONNX fine-tune model")

        terminal_gemms = [node for node in nodes if node[0] == "Gemm" and node[2] == output_name]
        if not terminal_gemms:
            raise ValueError("head scope requires a terminal Gemm producing model.output_name")

        trainable_names: set[str] = set()
        for _, inputs, _, _ in terminal_gemms:
            if len(inputs) < 2 or not inputs[1]:
                raise ValueError("terminal Gemm has no initializer-backed weight")
            head_tensors = [inputs[1]]
            if len(inputs) >= 3 and inputs[2]:
                head_tensors.append(inputs[2])
            for tensor_name in head_tensors:
                parameter_key = tensor_keys.get(tensor_name)
                parameter_name = f"weights.{parameter_key}" if parameter_key is not None else None
                if parameter_name not in parameters:
                    raise ValueError(
                        f"terminal Gemm tensor {tensor_name!r} is not a model parameter"
                    )
                trainable_names.add(parameter_name)
        if not trainable_names:
            raise ValueError("head scope selected no trainable parameters")

    for name, parameter in parameters.items():
        parameter.requires_grad_(name in trainable_names)

    selected = [name for name in parameters if name in trainable_names]
    frozen = [name for name in parameters if name not in trainable_names]
    return {
        "scope": scope,
        "trainable_parameters": selected,
        "frozen_parameters": frozen,
        "trainable_numel": sum(parameters[name].numel() for name in selected),
        "frozen_numel": sum(parameters[name].numel() for name in frozen),
    }


def sp_reference(model: nn.Module) -> dict[str, torch.Tensor]:
    """Snapshot trainable parameters for an L2-SP penalty."""
    parameters = _named_parameters(model)
    trainable = {
        name: parameter
        for name, parameter in parameters.items()
        if parameter.requires_grad
    }
    if not trainable:
        raise ValueError("model has no trainable parameters for an L2-SP reference")
    return {name: parameter.detach().clone() for name, parameter in trainable.items()}


def l2_sp_penalty(
    model: nn.Module, reference: Mapping[str, torch.Tensor]
) -> torch.Tensor:
    """Return ``0.5 * sum((parameter - reference) ** 2)`` over trainable tensors.

    The sum is unnormalized: it is not divided by the number of tensors or
    elements. Reference tensors are detached so gradients flow only to the
    current model parameters.
    """
    parameters = _named_parameters(model)
    trainable = {
        name: parameter
        for name, parameter in parameters.items()
        if parameter.requires_grad
    }
    if not trainable:
        raise ValueError("model has no trainable parameters for an L2-SP penalty")
    if not isinstance(reference, Mapping):
        raise TypeError("reference must be a mapping of parameter names to tensors")

    expected_keys = set(trainable)
    reference_keys = set(reference)
    if reference_keys != expected_keys:
        missing = sorted(expected_keys - reference_keys)
        unexpected = sorted(map(repr, reference_keys - expected_keys))
        raise ValueError(
            f"reference parameter keys do not match trainable parameters "
            f"(missing={missing}, unexpected={unexpected})"
        )

    penalty = next(iter(trainable.values())).new_zeros(())
    for name, parameter in trainable.items():
        reference_tensor = reference[name]
        if not isinstance(reference_tensor, torch.Tensor):
            raise TypeError(f"reference[{name!r}] must be a torch.Tensor")
        if reference_tensor.shape != parameter.shape:
            raise ValueError(
                f"reference shape mismatch for {name}: expected {tuple(parameter.shape)}, "
                f"got {tuple(reference_tensor.shape)}"
            )
        if reference_tensor.dtype != parameter.dtype or reference_tensor.device != parameter.device:
            raise ValueError(f"reference dtype/device mismatch for {name}")
        penalty = penalty + (parameter - reference_tensor.detach()).square().sum()
    return penalty * 0.5
