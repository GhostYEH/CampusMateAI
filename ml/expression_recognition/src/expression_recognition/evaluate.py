from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch
from torch.nn import functional as F

from .constants import CLASS_NAMES
from .data import create_loader
from .metrics import compute_classification_metrics
from .models import build_model, parameter_count
from .utils import save_json


def collect_predictions(model, loader, device) -> tuple[np.ndarray, np.ndarray, float]:
    model.eval()
    probabilities = []
    targets = []
    losses = []
    with torch.no_grad():
        for inputs, labels in loader:
            inputs = inputs.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            logits = model(inputs)
            losses.append(float(F.cross_entropy(logits, labels).cpu()))
            probabilities.append(torch.softmax(logits, dim=1).cpu().numpy())
            targets.append(labels.cpu().numpy())
    return np.concatenate(probabilities), np.concatenate(targets), float(np.mean(losses))


def benchmark_model(model, config: dict, device: torch.device) -> dict:
    model.eval()
    result = {}
    for batch_size in (1, 32):
        sample = torch.randn(
            batch_size,
            int(config["input_channels"]),
            int(config["input_size"]),
            int(config["input_size"]),
            device=device,
        )
        with torch.no_grad():
            for _ in range(20):
                model(sample)
            if device.type == "cuda":
                torch.cuda.synchronize()
            timings = []
            iterations = 100 if batch_size == 1 else 40
            for _ in range(iterations):
                started = time.perf_counter()
                model(sample)
                if device.type == "cuda":
                    torch.cuda.synchronize()
                timings.append((time.perf_counter() - started) * 1000)
        result[f"batch_{batch_size}"] = {
            "mean_latency_ms": float(np.mean(timings)),
            "p50_latency_ms": float(np.percentile(timings, 50)),
            "p95_latency_ms": float(np.percentile(timings, 95)),
            "throughput_samples_per_second": float(batch_size / (np.mean(timings) / 1000)),
        }
    return result


def plot_confusion(matrix: np.ndarray, output: Path) -> None:
    fig, axis = plt.subplots(figsize=(8, 7))
    image = axis.imshow(matrix, cmap="Blues")
    fig.colorbar(image, ax=axis)
    axis.set_xticks(range(len(CLASS_NAMES)), CLASS_NAMES, rotation=45, ha="right")
    axis.set_yticks(range(len(CLASS_NAMES)), CLASS_NAMES)
    axis.set_xlabel("Predicted")
    axis.set_ylabel("True")
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            axis.text(column, row, str(matrix[row, column]), ha="center", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_history(history: list[dict], output: Path) -> None:
    if not history:
        return
    epochs = [row["epoch"] for row in history]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].plot(epochs, [row["train_loss"] for row in history], label="train")
    axes[0].plot(epochs, [row["validation_loss"] for row in history], label="validation")
    axes[0].set_title("Loss")
    axes[0].legend()
    axes[1].plot(epochs, [row["train_macro_f1"] for row in history], label="train")
    axes[1].plot(epochs, [row["validation_macro_f1"] for row in history], label="validation")
    axes[1].set_title("Macro-F1")
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def evaluate(args: argparse.Namespace) -> dict:
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    config = checkpoint["config"]
    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    model = build_model(config, allow_download=False)
    model.load_state_dict(checkpoint["model_state"])
    model.to(device)
    _, loader = create_loader(
        args.manifest, args.split, config, training=False,
        batch_size_override=args.batch_size,
    )
    probabilities, targets, loss = collect_predictions(model, loader, device)
    metrics = compute_classification_metrics(probabilities, targets)
    checkpoint_size = Path(args.checkpoint).stat().st_size
    metrics.update({
        "split": args.split,
        "loss": loss,
        "model": config["model"],
        "input_size": config["input_size"],
        "input_channels": config["input_channels"],
        "normalization": config["normalization"],
        "parameter_count": parameter_count(model),
        "checkpoint_size_bytes": checkpoint_size,
        "pytorch_benchmark": benchmark_model(model, config, device),
        "benchmark_device": str(device),
        "checkpoint": str(Path(args.checkpoint).resolve()),
    })
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    save_json(output_dir / f"{args.split}_metrics.json", metrics)
    np.savez_compressed(
        output_dir / f"{args.split}_predictions.npz",
        probabilities=probabilities,
        targets=targets,
    )
    report = metrics["classification_report"]
    with (output_dir / f"{args.split}_per_class.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        fieldnames = ["class", "precision", "recall", "f1-score", "support"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for label in CLASS_NAMES:
            writer.writerow({"class": label, **report[label]})
    plot_confusion(
        np.asarray(metrics["confusion_matrix"]),
        output_dir / f"{args.split}_confusion_matrix.png",
    )
    plot_history(checkpoint.get("history", []), output_dir / "training_curves.png")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a trained expression classifier.")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", choices=["validation", "test"], required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--cpu", action="store_true")
    args = parser.parse_args()
    evaluate(args)


if __name__ == "__main__":
    main()
