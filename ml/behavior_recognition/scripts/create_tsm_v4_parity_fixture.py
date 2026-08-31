"""Create deterministic TSM V4 ONNX input/output files for MindSpore benchmark."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import onnxruntime as ort


INPUT_NAME = "frames"
OUTPUT_NAME = "logits"
INPUT_SHAPE = (1, 8, 3, 224, 224)
PARITY_SEED = 20260830


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    args.output_directory.mkdir(parents=True, exist_ok=True)

    sample = np.random.default_rng(PARITY_SEED).uniform(0, 255, INPUT_SHAPE).astype(np.float32)
    session = ort.InferenceSession(str(args.model), providers=["CPUExecutionProvider"])
    logits = session.run([OUTPUT_NAME], {INPUT_NAME: sample})[0].reshape(-1)
    sample.tofile(args.output_directory / "input.bin")
    calibration = "logits 2 1 5\n" + " ".join(f"{float(value):.9g}" for value in logits) + "\n"
    (args.output_directory / "expected.txt").write_text(calibration, encoding="ascii")


if __name__ == "__main__":
    main()
