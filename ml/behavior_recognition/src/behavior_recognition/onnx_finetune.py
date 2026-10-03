"""Differentiable reconstruction of the packaged V3.4 inference graph.

This preserves fused convolution weights and the trained classification head.
It is intentionally restricted to the operators in this graph, and must pass
ONNX Runtime parity before fine-tuning. It is not a general ONNX converter.
"""
from __future__ import annotations

from pathlib import Path
from math import prod

import onnx
import torch
from onnx import numpy_helper
from torch import nn
from torch.nn import functional as F


class OnnxBehaviorModel(nn.Module):
    def __init__(self, source: str | Path):
        super().__init__()
        proto = onnx.load(str(source))
        self._source_graph_bytes = proto.SerializeToString()
        graph = proto.graph
        supported = {"Conv", "Gemm", "Relu", "HardSwish", "HardSigmoid", "GlobalAveragePool", "Mul", "Add", "Flatten"}
        unknown = {node.op_type for node in graph.node} - supported
        if unknown:
            raise ValueError(f"Unsupported fine-tune graph operators: {sorted(unknown)}")
        initializer_names = {item.name for item in graph.initializer}
        inputs = [item.name for item in graph.input if item.name not in initializer_names]
        if len(inputs) != 1 or len(graph.output) != 1:
            raise ValueError("Expected one graph input and one graph output")
        self.input_name = inputs[0]
        self.output_name = graph.output[0].name
        self.weights = nn.ParameterDict()
        self.tensor_keys = {}
        for index, item in enumerate(graph.initializer):
            tensor = torch.from_numpy(numpy_helper.to_array(item).copy())
            if tensor.dtype != torch.float32:
                raise ValueError(f"Expected float32 trained weights: {item.name}")
            key = f"tensor_{index}"
            self.tensor_keys[item.name] = key
            self.weights[key] = nn.Parameter(tensor)
        self.nodes = []
        available = set(inputs) | initializer_names
        for node in graph.node:
            if node.domain not in ("", "ai.onnx"):
                raise ValueError(f"Unsupported operator domain: {node.domain}")
            attrs = {attr.name: onnx.helper.get_attribute_value(attr) for attr in node.attribute}
            allowed = {"Conv": {"dilations", "group", "kernel_shape", "pads", "strides", "auto_pad"},
                       "Gemm": {"alpha", "beta", "transA", "transB"},
                       "HardSigmoid": {"alpha", "beta"}, "Flatten": {"axis"}}
            if set(attrs) - allowed.get(node.op_type, set()):
                raise ValueError(f"Unsupported {node.op_type} attributes: {set(attrs)}")
            if node.op_type == "Conv" and attrs.get("auto_pad", b"NOTSET") != b"NOTSET":
                raise ValueError("Automatic convolution padding is not supported")
            if len(node.output) != 1 or any(name and name not in available for name in node.input):
                raise ValueError("Expected a topologically ordered single-output graph")
            self.nodes.append((node.op_type, tuple(node.input), node.output[0], attrs))
            available.update(node.output)
        if self.output_name not in available:
            raise ValueError("Graph output is unresolved")

    def export_onnx(self, output: str | Path) -> None:
        """Save updated weights in the original graph; refuse any existing output."""
        proto = onnx.load_from_string(self._source_graph_bytes)
        for item in proto.graph.initializer:
            tensor = self.weights[self.tensor_keys[item.name]].detach().cpu().numpy()
            item.CopyFrom(numpy_helper.from_array(tensor, item.name))
        onnx.checker.check_model(proto)
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as handle:
            handle.write(proto.SerializeToString())

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        values = {name: self.weights[key] for name, key in self.tensor_keys.items()}
        values[self.input_name] = images
        for kind, names, output, attrs in self.nodes:
            inputs = [values[name] for name in names if name]
            x = inputs[0]
            if kind == "Conv":
                pads = attrs.get("pads", [0, 0, 0, 0])
                if len(pads) != 4:
                    raise ValueError("Only 2D convolution is supported")
                x = F.pad(x, (pads[1], pads[3], pads[0], pads[2]))
                result = F.conv2d(x, inputs[1], inputs[2] if len(inputs) > 2 else None,
                                  stride=attrs.get("strides", [1, 1]), dilation=attrs.get("dilations", [1, 1]),
                                  groups=attrs.get("group", 1))
            elif kind == "Gemm":
                a = x.transpose(0, 1) if attrs.get("transA", 0) else x
                b = inputs[1].transpose(0, 1) if attrs.get("transB", 0) else inputs[1]
                result = attrs.get("alpha", 1.0) * (a @ b)
                if len(inputs) > 2:
                    result = result + attrs.get("beta", 1.0) * inputs[2]
            elif kind == "Relu":
                result = F.relu(x)
            elif kind == "HardSwish":
                result = F.hardswish(x)
            elif kind == "HardSigmoid":
                result = (attrs.get("alpha", 0.2) * x + attrs.get("beta", 0.5)).clamp(0, 1)
            elif kind == "GlobalAveragePool":
                result = x.mean(dim=tuple(range(2, x.ndim)), keepdim=True)
            elif kind == "Mul":
                result = x * inputs[1]
            elif kind == "Add":
                result = x + inputs[1]
            elif kind == "Flatten":
                axis = attrs.get("axis", 1)
                if axis < 0:
                    axis += x.ndim
                result = x.reshape(prod(x.shape[:axis]), prod(x.shape[axis:]))
            values[output] = result
        return values[self.output_name]
