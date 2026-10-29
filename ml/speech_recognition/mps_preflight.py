"""Probe this Mac's small MPS forward/backward workloads, without model downloads."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
from pathlib import Path


def check():
    automatic_fallback = os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK") == "1"
    report = {"architecture": platform.machine(), "macos": platform.mac_ver()[0],
              "automatic_operator_fallback_enabled": automatic_fallback}
    if platform.system() == "Darwin":
        report["unified_memory_gib"] = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"])) / 2**30
    try:
        import torch
    except ImportError:
        report.update(ready=False, reason="PyTorch is not installed in this interpreter")
        return report
    report.update(torch=torch.__version__, mps_built=torch.backends.mps.is_built(),
                  mps_available=torch.backends.mps.is_available())
    if not report["mps_available"]:
        report.update(ready=False, reason="MPS is unavailable in this interpreter/runtime")
        return report
    torch.manual_seed(73029)
    layer = torch.nn.Linear(12, 16, device="mps", dtype=torch.float32)
    features = torch.randn(32, 1, 12, device="mps")
    targets = torch.tensor([1, 2, 3], dtype=torch.long)
    lengths, target_lengths = torch.tensor([32]), torch.tensor([3])
    criterion = torch.nn.CTCLoss(blank=0, zero_infinity=True)

    def forward(cpu_loss):
        probabilities = layer(features).log_softmax(2)
        if cpu_loss:
            probabilities = probabilities.cpu()
        labels = targets if cpu_loss else targets.to("mps")
        return criterion(probabilities, labels, lengths, target_lengths)

    try:
        loss = forward(False)
        loss.backward()
        torch.mps.synchronize()
        report["ctc_native_forward_backward"] = None if automatic_fallback else True
        loss_device = str(loss.device)
    except (NotImplementedError, RuntimeError) as exc:
        report["ctc_native_forward_backward"] = False
        report["ctc_native_error_type"] = type(exc).__name__
        layer.zero_grad(set_to_none=True)
        try:
            loss = forward(True)
            loss.backward()
            torch.mps.synchronize()
            report["cpu_ctc_with_mps_gradients"] = True
            loss_device = "cpu"
        except (NotImplementedError, RuntimeError) as fallback_error:
            report.update(ready=False, cpu_ctc_with_mps_gradients=False,
                          fallback_error_type=type(fallback_error).__name__)
            return report
    gradient = layer.weight.grad
    finite = (gradient is not None and bool(torch.isfinite(gradient).all().item())
              and bool(gradient.abs().sum().item() > 0))
    report.update(ready=finite, gradient_device=str(gradient.device) if gradient is not None else None,
                  ctc_loss_device=loss_device, finite_loss=bool(torch.isfinite(loss).item()),
                  allocated_memory_bytes=torch.mps.current_allocated_memory(),
                  scope="Tiny synthetic CTC backward only; not a SenseVoice training or memory-capacity test")
    report["ready"] = report["ready"] and report["finite_loss"]
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = check()
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
