from __future__ import annotations

import argparse
import csv
import json
import platform
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import f1_score
from torch import nn
from torch.nn import functional as F
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from tqdm import tqdm

from .data import class_weights, create_loader
from .models import build_model, parameter_count
from .utils import load_config, save_json, seed_everything


class FocalLoss(nn.Module):
    """Focal loss with optional softened class weights for minority classes."""

    def __init__(self, gamma: float, class_weights_tensor: torch.Tensor | None = None):
        super().__init__()
        self.gamma = gamma
        if class_weights_tensor is not None:
            self.register_buffer("class_weights", class_weights_tensor)
        else:
            self.class_weights = None

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        log_probabilities = F.log_softmax(logits, dim=1)
        negative_log_likelihood = F.nll_loss(
            log_probabilities,
            targets,
            reduction="none",
        )
        probability = torch.exp(-negative_log_likelihood)
        focal = (1.0 - probability).pow(self.gamma) * negative_log_likelihood
        if self.class_weights is not None:
            focal = focal * self.class_weights[targets]
        return focal.mean()


def build_criterion(config: dict, targets: list[int], device: torch.device) -> nn.Module:
    loss_name = str(config.get("loss", "weighted_cross_entropy"))
    if loss_name == "focal":
        base_weights = class_weights(targets)
        power = float(config.get("focal_class_weight_power", 0.5))
        softened = base_weights.pow(power)
        softened = softened / softened.mean()
        return FocalLoss(
            gamma=float(config.get("focal_gamma", 2.0)),
            class_weights_tensor=softened.to(device),
        )
    if loss_name == "cross_entropy":
        return nn.CrossEntropyLoss(
            label_smoothing=float(config.get("label_smoothing", 0.0)),
        )
    if loss_name == "weighted_cross_entropy":
        return nn.CrossEntropyLoss(
            weight=class_weights(targets).to(device),
            label_smoothing=float(config.get("label_smoothing", 0.0)),
        )
    raise ValueError(f"Unsupported loss: {loss_name}")


def run_epoch(
    model: nn.Module,
    loader,
    criterion: nn.Module,
    device: torch.device,
    optimizer=None,
    scaler=None,
    gradient_clip_norm: float = 1.0,
    max_batches: int | None = None,
) -> dict[str, float]:
    training = optimizer is not None
    model.train(training)
    losses: list[float] = []
    predictions: list[int] = []
    targets: list[int] = []
    context = torch.enable_grad if training else torch.no_grad
    with context():
        progress = tqdm(loader, leave=False, desc="train" if training else "validation")
        for batch_index, (inputs, labels) in enumerate(progress):
            if max_batches is not None and batch_index >= max_batches:
                break
            inputs = inputs.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            if training:
                optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast(
                device_type=device.type,
                dtype=torch.float16,
                enabled=device.type == "cuda",
            ):
                logits = model(inputs)
                loss = criterion(logits, labels)
            if training:
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), gradient_clip_norm)
                scaler.step(optimizer)
                scaler.update()
            losses.append(float(loss.detach().cpu()))
            predictions.extend(logits.detach().argmax(1).cpu().tolist())
            targets.extend(labels.detach().cpu().tolist())
            progress.set_postfix(loss=f"{losses[-1]:.4f}")
    return {
        "loss": float(np.mean(losses)),
        "accuracy": float(np.mean(np.asarray(predictions) == np.asarray(targets))),
        "macro_f1": float(f1_score(targets, predictions, average="macro", zero_division=0)),
        "samples": len(targets),
    }


def save_checkpoint(
    path: Path,
    model: nn.Module,
    optimizer,
    scheduler,
    scaler,
    epoch: int,
    best_macro_f1: float,
    stale_epochs: int,
    config: dict,
    history: list[dict],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "model_state": model.state_dict(),
        "optimizer_state": optimizer.state_dict(),
        "scheduler_state": scheduler.state_dict(),
        "scaler_state": scaler.state_dict(),
        "epoch": epoch,
        "best_macro_f1": best_macro_f1,
        "stale_epochs": stale_epochs,
        "config": config,
        "history": history,
    }, path)


def train(args: argparse.Namespace) -> Path:
    config = load_config(args.config)
    seed_everything(int(config["seed"]))
    if not torch.cuda.is_available() and not args.allow_cpu:
        raise RuntimeError("CUDA is unavailable; pass --allow-cpu only for an intentional CPU smoke test.")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    smoke = bool(args.smoke)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = args.run_dir or (
        Path(args.output_root) / f"{'smoke_' if smoke else ''}{config['model']}_{timestamp}"
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    resolved_config = dict(config)
    resolved_config.update({
        "manifest": str(Path(args.manifest).resolve()),
        "device": str(device),
        "smoke": smoke,
        "started_at": datetime.now().isoformat(),
        "command_arguments": vars(args),
    })
    save_json(run_dir / "resolved_config.json", resolved_config)

    train_dataset, train_loader = create_loader(args.manifest, "train", config, True)
    _, validation_loader = create_loader(args.manifest, "validation", config, False)
    model = build_model(config).to(device)
    criterion = build_criterion(config, train_dataset.targets, device)
    optimizer = AdamW(
        model.parameters(),
        lr=float(config["learning_rate"]),
        weight_decay=float(config["weight_decay"]),
    )
    max_epochs = 1 if smoke else int(args.max_epochs or config["max_epochs"])
    scheduler = CosineAnnealingLR(optimizer, T_max=max_epochs, eta_min=1e-6)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    start_epoch = 0
    best_macro_f1 = -1.0
    stale_epochs = 0
    history: list[dict] = []

    if args.resume:
        checkpoint = torch.load(args.resume, map_location=device, weights_only=False)
        model.load_state_dict(checkpoint["model_state"])
        optimizer.load_state_dict(checkpoint["optimizer_state"])
        scheduler.load_state_dict(checkpoint["scheduler_state"])
        scaler.load_state_dict(checkpoint["scaler_state"])
        start_epoch = int(checkpoint["epoch"]) + 1
        best_macro_f1 = float(checkpoint["best_macro_f1"])
        stale_epochs = int(checkpoint.get("stale_epochs", 0))
        history = list(checkpoint.get("history", []))

    environment = {
        "python": platform.python_version(),
        "pytorch": torch.__version__,
        "cuda_runtime": torch.version.cuda,
        "cudnn": torch.backends.cudnn.version(),
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
        "device_memory_bytes": (
            torch.cuda.get_device_properties(0).total_memory if torch.cuda.is_available() else None
        ),
        "parameter_count": parameter_count(model),
        "train_samples": len(train_dataset),
        "validation_samples": len(validation_loader.dataset),
    }
    save_json(run_dir / "environment.json", environment)
    max_batches = args.max_batches if smoke else None
    patience = int(config["early_stopping_patience"])
    started = time.perf_counter()

    for epoch in range(start_epoch, max_epochs):
        epoch_started = time.perf_counter()
        train_metrics = run_epoch(
            model, train_loader, criterion, device, optimizer, scaler,
            float(config["gradient_clip_norm"]), max_batches,
        )
        validation_metrics = run_epoch(
            model, validation_loader, criterion, device, max_batches=max_batches,
        )
        scheduler.step()
        row = {
            "epoch": epoch,
            "learning_rate": optimizer.param_groups[0]["lr"],
            "train_loss": train_metrics["loss"],
            "train_accuracy": train_metrics["accuracy"],
            "train_macro_f1": train_metrics["macro_f1"],
            "validation_loss": validation_metrics["loss"],
            "validation_accuracy": validation_metrics["accuracy"],
            "validation_macro_f1": validation_metrics["macro_f1"],
            "duration_seconds": time.perf_counter() - epoch_started,
        }
        history.append(row)
        print(json.dumps(row, ensure_ascii=False))
        with (run_dir / "history.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

        improved = validation_metrics["macro_f1"] > best_macro_f1 + 1e-4
        if improved:
            best_macro_f1 = validation_metrics["macro_f1"]
            stale_epochs = 0
            save_checkpoint(
                run_dir / "best.pt", model, optimizer, scheduler, scaler, epoch,
                best_macro_f1, stale_epochs, config, history,
            )
        else:
            stale_epochs += 1
        save_checkpoint(
            run_dir / "last.pt", model, optimizer, scheduler, scaler, epoch,
            best_macro_f1, stale_epochs, config, history,
        )
        if not smoke and stale_epochs >= patience:
            print(f"Early stopping at epoch {epoch}; best validation macro-F1={best_macro_f1:.6f}")
            break

    with (run_dir / "history.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(history[0].keys()))
        writer.writeheader()
        writer.writerows(history)
    summary = {
        "best_validation_macro_f1": best_macro_f1,
        "completed_epochs": len(history),
        "total_duration_seconds": time.perf_counter() - started,
        "best_checkpoint": str((run_dir / "best.pt").resolve()),
        "last_checkpoint": str((run_dir / "last.pt").resolve()),
    }
    save_json(run_dir / "training_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Train an expression model.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("runs"))
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--max-epochs", type=int)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--max-batches", type=int, default=4)
    parser.add_argument("--allow-cpu", action="store_true")
    args = parser.parse_args()
    train(args)


if __name__ == "__main__":
    main()
