"""Offline, paper-inspired clean-anchored occlusion experiment for ResNet18.

This is a controlled adaptation of CA-HOFT, not a reproduction of its RAF-DB
protocol. Both arms start from the same existing checkpoint and use identical
images, masks, optimizer settings, and validation examples.
"""

from __future__ import annotations

import argparse
import copy
import json
import random
from pathlib import Path

import torch
from sklearn.metrics import f1_score
from torch import Tensor, nn
from torch.nn import functional as F
from torch.utils.data import DataLoader

from .constants import CLASS_NAMES
from .data import ManifestDataset, build_transforms
from .models import build_model
from .train import build_criterion
from .utils import save_json, seed_everything


def occlude_batch(
    images: Tensor,
    *,
    mean: list[float],
    std: list[float],
    seed: int,
    first_index: int = 0,
) -> Tensor:
    """Cover one face region per image; never mutate the clean input.

    Mask choices approximate eye, mouth, and arbitrary obstructions. The seed
    and sample index fix validation masks across checkpoints and training arms.
    """
    if images.ndim != 4 or images.shape[1] != len(mean) or len(mean) != len(std):
        raise ValueError("Expected NCHW images with normalization matching channels")
    result = images.clone()
    _, channels, height, width = images.shape
    fill = images.new_tensor([-m / s for m, s in zip(mean, std)]).view(channels, 1, 1)
    for index in range(images.shape[0]):
        rng = random.Random(seed + first_index + index)
        region = rng.randrange(3)
        box_width = max(1, round(width * rng.uniform(0.32, 0.54)))
        box_height = max(1, round(height * rng.uniform(0.15, 0.27)))
        if region == 0:  # eyes / eyebrows
            center_x, center_y = 0.5, 0.36
        elif region == 1:  # mouth / lower face
            center_x, center_y = 0.5, 0.73
        else:
            center_x = rng.uniform(0.25, 0.75)
            center_y = rng.uniform(0.30, 0.75)
        left = min(width - box_width, max(0, round(width * center_x - box_width / 2)))
        top = min(height - box_height, max(0, round(height * center_y - box_height / 2)))
        result[index, :, top:top + box_height, left:left + box_width] = fill
    return result


def anchored_loss(
    student_clean: Tensor,
    student_occluded: Tensor,
    teacher_clean: Tensor,
    labels: Tensor,
    criterion: nn.Module,
    *,
    temperature: float = 2.0,
    teacher_weight: float = 0.5,
) -> Tensor:
    """Keep clean-label supervision while transferring a frozen clean reference."""
    if temperature <= 0 or teacher_weight < 0:
        raise ValueError("temperature must be positive and teacher_weight nonnegative")
    reference = F.softmax(teacher_clean.detach() / temperature, dim=1)
    clean_kl = F.kl_div(F.log_softmax(student_clean / temperature, dim=1), reference, reduction="batchmean")
    masked_kl = F.kl_div(F.log_softmax(student_occluded / temperature, dim=1), reference, reduction="batchmean")
    return (
        criterion(student_clean, labels)
        + criterion(student_occluded, labels)
        + teacher_weight * temperature**2 * (clean_kl + masked_kl)
    )


def evaluate_pair(model: nn.Module, loader: DataLoader, device: torch.device, config: dict, seed: int) -> dict:
    model.eval()
    clean_predictions: list[int] = []
    occluded_predictions: list[int] = []
    targets: list[int] = []
    offset = 0
    with torch.inference_mode():
        for clean, labels in loader:
            masked = occlude_batch(
                clean,
                mean=config["normalization"]["mean"],
                std=config["normalization"]["std"],
                seed=seed,
                first_index=offset,
            )
            offset += len(labels)
            clean = clean.to(device)
            masked = masked.to(device)
            clean_predictions.extend(model(clean).argmax(1).cpu().tolist())
            occluded_predictions.extend(model(masked).argmax(1).cpu().tolist())
            targets.extend(labels.tolist())
    labels = list(range(len(CLASS_NAMES)))
    return {
        "samples": len(targets),
        "clean_accuracy": sum(a == b for a, b in zip(clean_predictions, targets)) / len(targets),
        "occluded_accuracy": sum(a == b for a, b in zip(occluded_predictions, targets)) / len(targets),
        "clean_macro_f1": float(f1_score(targets, clean_predictions, labels=labels, average="macro", zero_division=0)),
        "occluded_macro_f1": float(f1_score(targets, occluded_predictions, labels=labels, average="macro", zero_division=0)),
        "clean_per_class_f1": dict(zip(CLASS_NAMES, f1_score(targets, clean_predictions, labels=labels, average=None, zero_division=0).tolist())),
        "occluded_per_class_f1": dict(zip(CLASS_NAMES, f1_score(targets, occluded_predictions, labels=labels, average=None, zero_division=0).tolist())),
    }


def run_arm(
    name: str,
    initial_state: dict,
    teacher: nn.Module,
    train_loader: DataLoader,
    validation_loader: DataLoader,
    config: dict,
    device: torch.device,
    output_dir: Path,
    *,
    epochs: int,
    learning_rate: float,
    seed: int,
    max_train_batches: int | None,
) -> dict:
    seed_everything(seed)
    model = build_model(config, allow_download=False).to(device)
    model.load_state_dict(initial_state)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=float(config["weight_decay"]))
    criterion = build_criterion(config, train_loader.dataset.targets, device)
    history: list[dict] = []
    best_score = -1.0
    arm_dir = output_dir / name
    arm_dir.mkdir()
    for epoch in range(epochs):
        model.train()
        losses: list[float] = []
        for batch_index, (clean, labels) in enumerate(train_loader):
            if max_train_batches is not None and batch_index >= max_train_batches:
                break
            masked = occlude_batch(
                clean,
                mean=config["normalization"]["mean"],
                std=config["normalization"]["std"],
                seed=seed + epoch * len(train_loader.dataset) + batch_index * clean.shape[0],
            )
            clean, masked, labels = clean.to(device), masked.to(device), labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            if name == "hard_occlusion":
                loss = criterion(model(masked), labels)
            else:
                with torch.no_grad():
                    teacher_clean = teacher(clean)
                loss = anchored_loss(model(clean), model(masked), teacher_clean, labels, criterion)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
        metrics = evaluate_pair(model, validation_loader, device, config, seed + 1_000_000)
        row = {"epoch": epoch + 1, "train_loss": sum(losses) / len(losses), **metrics}
        history.append(row)
        print(json.dumps({"arm": name, **row}, ensure_ascii=False), flush=True)
        score = (metrics["clean_macro_f1"] + metrics["occluded_macro_f1"]) / 2
        if score > best_score:
            best_score = score
            torch.save({
                "model_state": model.state_dict(),
                "config": config,
                "history": history,
                "experiment": name,
                "validation_mask_seed": seed + 1_000_000,
            }, arm_dir / "best.pt")
            save_json(arm_dir / "best_validation.json", row)
    save_json(arm_dir / "history.json", history)
    return json.loads((arm_dir / "best_validation.json").read_text(encoding="utf-8"))


def run_experiment(args: argparse.Namespace) -> dict:
    if args.epochs < 1 or args.batch_size < 1 or args.learning_rate <= 0:
        raise ValueError("epochs, batch_size and learning_rate must be positive")
    if args.max_train_batches is not None and args.max_train_batches < 1:
        raise ValueError("max_train_batches must be positive")
    if not args.checkpoint.is_file() or not args.manifest.is_file():
        raise FileNotFoundError("A trained expression checkpoint and included.csv manifest are required")
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    config = copy.deepcopy(checkpoint["config"])
    if config["model"] != "resnet18" or int(config["input_channels"]) != 3:
        raise ValueError("This experiment requires the existing three-channel ResNet18 checkpoint")
    config["augmentation"]["occlusion_probability"] = 0.0
    config["num_workers"] = args.num_workers
    seed = int(config["seed"])
    seed_everything(seed)
    train_dataset = ManifestDataset(args.manifest, "train", build_transforms(config, training=True))
    validation_dataset = ManifestDataset(args.manifest, "validation", build_transforms(config, training=False))
    if len(train_dataset) < args.batch_size:
        raise ValueError("Training split has fewer samples than batch_size")
    if args.output_dir.exists():
        raise FileExistsError(f"Experiment output already exists: {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    teacher = build_model(config, allow_download=False).to(device)
    teacher.load_state_dict(checkpoint["model_state"])
    teacher.eval()
    for parameter in teacher.parameters():
        parameter.requires_grad_(False)
    validation_loader = DataLoader(validation_dataset, batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers)
    baseline = evaluate_pair(teacher, validation_loader, device, config, seed + 1_000_000)
    save_json(args.output_dir / "baseline_validation.json", baseline)
    results = {"baseline": baseline, "smoke": args.max_train_batches is not None, "arms": {}}
    for name in ("hard_occlusion", "clean_anchor"):
        generator = torch.Generator().manual_seed(seed)
        train_loader = DataLoader(
            train_dataset, batch_size=args.batch_size, shuffle=True, drop_last=True,
            num_workers=args.num_workers, generator=generator,
        )
        results["arms"][name] = run_arm(
            name, checkpoint["model_state"], teacher, train_loader, validation_loader,
            config, device, args.output_dir, epochs=args.epochs,
            learning_rate=args.learning_rate, seed=seed,
            max_train_batches=args.max_train_batches,
        )
    save_json(args.output_dir / "comparison.json", results)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare clean-anchored and hard-only occlusion fine-tuning.")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--max-train-batches", type=int, help="Smoke run only; results are not comparable")
    parser.add_argument("--cpu", action="store_true")
    args = parser.parse_args()
    run_experiment(args)


if __name__ == "__main__":
    main()
