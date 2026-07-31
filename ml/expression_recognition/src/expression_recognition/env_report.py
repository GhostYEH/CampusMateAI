from __future__ import annotations

import argparse
import json
import platform
import subprocess
from pathlib import Path

import torch
import torchvision

from .utils import save_json


def command_output(command: list[str]) -> str:
    try:
        return subprocess.run(
            command, check=False, capture_output=True, text=True, encoding="utf-8"
        ).stdout.strip()
    except OSError as error:
        return f"unavailable: {error}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cuda_available = torch.cuda.is_available()
    report = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "torch": torch.__version__,
        "torchvision": torchvision.__version__,
        "cuda_available": cuda_available,
        "cuda_runtime": torch.version.cuda,
        "cudnn": torch.backends.cudnn.version(),
        "nvidia_smi": command_output(["nvidia-smi"]),
        "pip_freeze": command_output([platform.sys.executable, "-m", "pip", "freeze"]),
    }
    if cuda_available:
        properties = torch.cuda.get_device_properties(0)
        tensor = torch.randn(512, 512, device="cuda")
        cuda_result = (tensor @ tensor).mean()
        with torch.amp.autocast("cuda", dtype=torch.float16):
            amp_result = (tensor @ tensor).mean()
        report["gpu"] = {
            "name": properties.name,
            "total_memory_bytes": properties.total_memory,
            "compute_capability": f"{properties.major}.{properties.minor}",
            "cuda_tensor_result": float(cuda_result.cpu()),
            "amp_tensor_result": float(amp_result.cpu()),
        }
    save_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
