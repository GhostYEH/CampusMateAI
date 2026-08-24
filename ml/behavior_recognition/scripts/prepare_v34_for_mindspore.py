"""Rewrite ONNX HardSwish nodes into equivalent MindSpore Lite 2.1 primitives."""

from __future__ import annotations

import argparse
from pathlib import Path

import onnx
from onnx import helper


def rewrite_hard_swish(source: Path, destination: Path) -> int:
    model = onnx.load(source)
    rewritten = []
    count = 0
    for node in model.graph.node:
        if node.op_type != "HardSwish":
            rewritten.append(node)
            continue
        count += 1
        intermediate = f"{node.output[0]}__hard_sigmoid"
        rewritten.append(
            helper.make_node(
                "HardSigmoid",
                [node.input[0]],
                [intermediate],
                name=f"{node.name}__hard_sigmoid",
                alpha=1.0 / 6.0,
                beta=0.5,
            )
        )
        rewritten.append(
            helper.make_node(
                "Mul",
                [node.input[0], intermediate],
                list(node.output),
                name=f"{node.name}__mul",
            )
        )
    del model.graph.node[:]
    model.graph.node.extend(rewritten)
    onnx.checker.check_model(model)
    destination.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, destination)
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    count = rewrite_hard_swish(args.source, args.destination)
    if count == 0:
        raise RuntimeError("Expected at least one HardSwish node")
    print(f"Rewrote {count} HardSwish nodes")


if __name__ == "__main__":
    main()
