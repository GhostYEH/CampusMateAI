from __future__ import annotations

import csv
import json
import os
import platform
import random
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
import yaml
from sklearn.metrics import f1_score
from torch import nn
from torch.utils.data import DataLoader

from .constants import CLASS_NAMES
from .data import BehaviorDataset
from .models import build_model


def select_best_epoch(rows: list[dict]) -> int:
    if not rows:
        raise ValueError("No epoch results available")
    best = max(rows, key=lambda row: (row["val_macro_f1"], -row["val_loss"]))
    return int(best["epoch"])


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _seed_worker(worker_id: int) -> None:
    worker_seed = torch.initial_seed() % (2**32)
    random.seed(worker_seed)
    np.random.seed(worker_seed)


def _load_rows(path: Path, limit_per_class: int | None) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if limit_per_class is None:
        return rows
    counts: Counter[int] = Counter()
    limited = []
    for row in rows:
        label = int(row["target_index"])
        if counts[label] < limit_per_class:
            limited.append(row)
            counts[label] += 1
    return limited


def _class_weights(rows: list[dict[str, str]]) -> torch.Tensor:
    counts = Counter(int(row["target_index"]) for row in rows)
    total = sum(counts.values())
    return torch.tensor(
        [total / (len(CLASS_NAMES) * max(1, counts[index])) for index in range(len(CLASS_NAMES))],
        dtype=torch.float32,
    )


def _run_epoch(model, loader, criterion, device, optimizer=None, amp=False):
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    targets: list[int] = []
    predictions: list[int] = []
    for inputs, labels in loader:
        inputs = inputs.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)
        if training:
            optimizer.zero_grad(set_to_none=True)
        with torch.set_grad_enabled(training), torch.autocast(
            device_type=device.type, enabled=amp and device.type == "cuda"
        ):
            logits = model(inputs)
            loss = criterion(logits, labels)
        if training:
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        total_loss += float(loss.detach()) * labels.size(0)
        targets.extend(labels.detach().cpu().tolist())
        predictions.extend(logits.argmax(dim=1).detach().cpu().tolist())
    average_loss = total_loss / max(1, len(targets))
    macro_f1 = f1_score(
        targets, predictions, labels=list(range(len(CLASS_NAMES))), average="macro", zero_division=0
    )
    return average_loss, float(macro_f1)


def train_model(
    config_path: Path,
    manifest_dir: Path,
    run_dir: Path,
    max_epochs_override: int | None = None,
    limit_per_class: int | None = None,
    device_override: str | None = None,
) -> Path:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if max_epochs_override is not None:
        config["max_epochs"] = max_epochs_override
    seed = int(config.get("seed", 20260823))
    seed_everything(seed)
    device = torch.device(device_override or ("cuda" if torch.cuda.is_available() else "cpu"))
    train_rows = _load_rows(manifest_dir / "train.csv", limit_per_class)
    val_rows = _load_rows(manifest_dir / "val.csv", limit_per_class)
    if not train_rows or not val_rows:
        raise ValueError("Train and validation manifests must both contain samples")
    mode = str(config.get("input_mode", "roi"))
    train_dataset = BehaviorDataset(manifest_dir / "train.csv", mode, True, train_rows)
    val_dataset = BehaviorDataset(manifest_dir / "val.csv", mode, False, val_rows)
    generator = torch.Generator().manual_seed(seed)
    loader_kwargs = {
        "batch_size": int(config.get("batch_size", 64)),
        "num_workers": int(config.get("num_workers", 4)),
        "pin_memory": device.type == "cuda",
        "worker_init_fn": _seed_worker,
        "generator": generator,
        "persistent_workers": int(config.get("num_workers", 4)) > 0,
    }
    train_loader = DataLoader(train_dataset, shuffle=True, **loader_kwargs)
    val_loader = DataLoader(val_dataset, shuffle=False, **loader_kwargs)
    model = build_model(len(CLASS_NAMES), bool(config.get("pretrained", True))).to(device)
    criterion = nn.CrossEntropyLoss(
        weight=_class_weights(train_rows).to(device),
        label_smoothing=float(config.get("label_smoothing", 0.0)),
    )
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(config.get("learning_rate", 5e-4)),
        weight_decay=float(config.get("weight_decay", 1e-4)),
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "resolved_config.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
    )
    environment = {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "device": str(device),
        "cuda_available": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "pid": os.getpid(),
    }
    (run_dir / "environment.json").write_text(
        json.dumps(environment, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    history: list[dict] = []
    best_score = (-1.0, float("inf"))
    stale_epochs = 0
    best_path = run_dir / "best.pt"
    started = time.time()
    for epoch in range(1, int(config.get("max_epochs", 30)) + 1):
        train_loss, train_f1 = _run_epoch(
            model, train_loader, criterion, device, optimizer, bool(config.get("amp", True))
        )
        val_loss, val_f1 = _run_epoch(model, val_loader, criterion, device)
        row = {
            "epoch": epoch,
            "train_loss": train_loss,
            "train_macro_f1": train_f1,
            "val_loss": val_loss,
            "val_macro_f1": val_f1,
            "elapsed_seconds": round(time.time() - started, 3),
        }
        history.append(row)
        print(
            f"epoch={epoch} train_loss={train_loss:.4f} train_f1={train_f1:.4f} "
            f"val_loss={val_loss:.4f} val_f1={val_f1:.4f}",
            flush=True,
        )
        score = (val_f1, -val_loss)
        if score > best_score:
            best_score = score
            stale_epochs = 0
            temporary = run_dir / "best.pt.tmp"
            torch.save(
                {"epoch": epoch, "model_state": model.state_dict(), "config": config, "class_names": CLASS_NAMES},
                temporary,
            )
            temporary.replace(best_path)
        else:
            stale_epochs += 1
        if stale_epochs >= int(config.get("early_stopping_patience", 6)):
            break
    with (run_dir / "history.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(history[0]))
        writer.writeheader()
        writer.writerows(history)
    return best_path
