from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import time
from collections import Counter
from pathlib import Path

import torch
import yaml
from sklearn.metrics import f1_score
from torch import nn
from torch.utils.data import DataLoader

from .constants import CLASS_NAMES
from .onnx_features import OnnxFrameFeatureEncoder, create_feature_model
from .temporal_data import TemporalBehaviorDataset
from .temporal_models import (
    TemporalBehaviorModel,
    TemporalGRUHead,
    freeze_encoder,
    unfreeze_encoder_tail,
)
from .train import _seed_worker, seed_everything


def _manifest_targets(path: Path) -> list[int]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [int(row["target_index"]) for row in csv.DictReader(handle)]


def _class_weights(targets: list[int]) -> torch.Tensor:
    counts = Counter(targets)
    total = len(targets)
    return torch.tensor(
        [total / (len(CLASS_NAMES) * max(1, counts[index])) for index in range(len(CLASS_NAMES))],
        dtype=torch.float32,
    )


def _run_epoch(model, loader, criterion, device, optimizer=None, amp=False):
    training = optimizer is not None
    model.train(training)
    losses = 0.0
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
        losses += float(loss.detach()) * labels.size(0)
        targets.extend(labels.detach().cpu().tolist())
        predictions.extend(logits.argmax(dim=1).detach().cpu().tolist())
    macro_f1 = f1_score(
        targets,
        predictions,
        labels=list(range(len(CLASS_NAMES))),
        average="macro",
        zero_division=0,
    )
    return losses / max(1, len(targets)), float(macro_f1)


def _run_onnx_epoch(model, encoder, loader, criterion, device, optimizer=None, amp=False):
    training = optimizer is not None
    model.train(training)
    losses = 0.0
    targets: list[int] = []
    predictions: list[int] = []
    for inputs, labels in loader:
        batch, time, channels, height, width = inputs.shape
        flattened = inputs.reshape(batch * time, channels, height, width).numpy()
        encoded = encoder.encode(flattened).reshape(batch, time, -1)
        features = torch.from_numpy(encoded).to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)
        if training:
            optimizer.zero_grad(set_to_none=True)
        with torch.set_grad_enabled(training), torch.autocast(
            device_type=device.type, enabled=amp and device.type == "cuda"
        ):
            logits = model(features)
            loss = criterion(logits, labels)
        if training:
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        losses += float(loss.detach()) * labels.size(0)
        targets.extend(labels.detach().cpu().tolist())
        predictions.extend(logits.argmax(dim=1).detach().cpu().tolist())
    macro_f1 = f1_score(
        targets,
        predictions,
        labels=list(range(len(CLASS_NAMES))),
        average="macro",
        zero_division=0,
    )
    return losses / max(1, len(targets)), float(macro_f1)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def train_temporal_model(
    config_path: Path,
    manifest_dir: Path,
    run_dir: Path,
    *,
    max_epochs_override: int | None = None,
    source_onnx_override: Path | None = None,
    device_override: str | None = None,
) -> Path:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    seed = int(config.get("seed", 20260827))
    seed_everything(seed)
    device = torch.device(device_override or ("cuda" if torch.cuda.is_available() else "cpu"))
    train_path = manifest_dir / "train.csv"
    val_path = manifest_dir / "val.csv"
    targets = _manifest_targets(train_path)
    if not targets or not _manifest_targets(val_path):
        raise ValueError("Temporal train and validation manifests must be non-empty")

    train_dataset = TemporalBehaviorDataset(train_path, training=True)
    val_dataset = TemporalBehaviorDataset(val_path, training=False)
    workers = int(config.get("num_workers", 4))
    common = {
        "batch_size": int(config.get("batch_size", 4)),
        "num_workers": workers,
        "pin_memory": device.type == "cuda",
        "persistent_workers": workers > 0,
        "worker_init_fn": _seed_worker,
        "generator": torch.Generator().manual_seed(seed),
    }
    train_loader = DataLoader(train_dataset, shuffle=True, **common)
    val_loader = DataLoader(val_dataset, shuffle=False, **common)
    encoder_mode = str(config.get("encoder_mode", "pytorch"))
    onnx_encoder = None
    source_onnx_sha256 = ""
    if encoder_mode == "onnx_frozen":
        source_onnx = source_onnx_override or Path(str(config.get("source_onnx", "")))
        if not source_onnx.is_file():
            raise FileNotFoundError(f"Frozen ONNX encoder not found: {source_onnx}")
        feature_output = str(config["onnx_feature_output"])
        feature_size = int(config["onnx_feature_size"])
        derived_model = run_dir / "frame_features.onnx"
        create_feature_model(
            source_onnx, derived_model, feature_output, feature_size=feature_size
        )
        onnx_encoder = OnnxFrameFeatureEncoder(derived_model, feature_output)
        model = TemporalGRUHead(
            feature_size,
            hidden_size=int(config.get("hidden_size", 256)),
            num_classes=len(CLASS_NAMES),
        ).to(device)
        architecture = "mobilenet_v3_small_onnx_gru"
        source_onnx_sha256 = _sha256(source_onnx)
    elif encoder_mode == "pytorch":
        model = TemporalBehaviorModel(
            len(CLASS_NAMES),
            hidden_size=int(config.get("hidden_size", 256)),
            pretrained=bool(config.get("pretrained", True)),
        ).to(device)
        architecture = "mobilenet_v3_small_gru"
    else:
        raise ValueError(f"Unsupported temporal encoder mode: {encoder_mode}")
    criterion = nn.CrossEntropyLoss(
        weight=_class_weights(targets).to(device),
        label_smoothing=float(config.get("label_smoothing", 0.05)),
    )
    phase1_epochs = int(config.get("phase1_epochs", 3))
    phase2_epochs = 0 if encoder_mode == "onnx_frozen" else int(config.get("phase2_epochs", 12))
    if max_epochs_override is not None:
        phase1_epochs = min(phase1_epochs, max_epochs_override)
        phase2_epochs = min(phase2_epochs, max(0, max_epochs_override - phase1_epochs))
    phases = (("frozen_encoder", phase1_epochs), ("fine_tune", phase2_epochs))

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
    best_path = run_dir / "best.pt"
    epoch = 0
    started = time.time()
    for phase, phase_epochs in phases:
        if phase_epochs < 1:
            continue
        if phase == "frozen_encoder":
            if encoder_mode == "pytorch":
                freeze_encoder(model)
            learning_rate = float(config.get("learning_rate", 5e-4))
        else:
            unfreeze_encoder_tail(model, int(config.get("unfreeze_blocks", 2)))
            learning_rate = float(config.get("fine_tune_learning_rate", 1e-4))
        optimizer = torch.optim.AdamW(
            (parameter for parameter in model.parameters() if parameter.requires_grad),
            lr=learning_rate,
            weight_decay=float(config.get("weight_decay", 1e-4)),
        )
        for _ in range(phase_epochs):
            epoch += 1
            epoch_runner = _run_onnx_epoch if onnx_encoder is not None else _run_epoch
            runner_prefix = (model, onnx_encoder) if onnx_encoder is not None else (model,)
            train_loss, train_f1 = epoch_runner(
                *runner_prefix,
                train_loader,
                criterion,
                device,
                optimizer,
                bool(config.get("amp", True)),
            )
            val_loss, val_f1 = epoch_runner(
                *runner_prefix, val_loader, criterion, device
            )
            row = {
                "epoch": epoch,
                "phase": phase,
                "train_loss": train_loss,
                "train_macro_f1": train_f1,
                "val_loss": val_loss,
                "val_macro_f1": val_f1,
                "elapsed_seconds": round(time.time() - started, 3),
            }
            history.append(row)
            payload = {
                "epoch": epoch,
                "phase": phase,
                "architecture": architecture,
                "model_state": model.state_dict(),
                "config": config,
                "class_names": CLASS_NAMES,
                "metrics": row,
                "source_onnx_sha256": source_onnx_sha256,
            }
            temporary = run_dir / "last.pt.tmp"
            torch.save(payload, temporary)
            temporary.replace(run_dir / "last.pt")
            if (val_f1, -val_loss) > best_score:
                best_score = (val_f1, -val_loss)
                best_temporary = run_dir / "best.pt.tmp"
                torch.save(payload, best_temporary)
                best_temporary.replace(best_path)
            print(
                f"epoch={epoch} phase={phase} train_loss={train_loss:.4f} "
                f"train_f1={train_f1:.4f} val_loss={val_loss:.4f} val_f1={val_f1:.4f}",
                flush=True,
            )
    if not history:
        raise ValueError("At least one temporal training epoch is required")
    with (run_dir / "history.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(history[0]))
        writer.writeheader()
        writer.writerows(history)
    return best_path
