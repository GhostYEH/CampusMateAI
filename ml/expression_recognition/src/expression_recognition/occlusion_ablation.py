"""Controlled five-arm occlusion-training ablation for the seven-class ResNet18.

Arms (all start from the same existing checkpoint, same fixed train/validation
split, same optimizer / LR / number of optimizer updates):

    A  original checkpoint, no training (start reference)
    B  plain clean fine-tuning, no structured occlusion
    C  occluded-view supervision only
    E  clean + occluded supervision, no teacher (same two student forwards as D)
    D  clean + occluded supervision with a frozen clean-reference teacher (KD)

The E arm closes the attribution gap between C and D: E - C isolates adding
clean-view supervision, while D - E isolates teacher distillation under the same
two-view supervision and student forward count. D - C is only the effect of the
combined package, not of distillation alone.

This is a simplification of the CA-HOFT idea, not a reproduction of HardMix /
CA-HOFT numbers. Development experiment on already-exposed FER2013 data only.

Locked protocol decisions (fixed before any formal run, never tuned on results):
  * loss normalization: lambda_clean + lambda_masked = 1 (0.5 / 0.5 for D/E);
    E uses the same supervised term as D with the teacher/KL term removed;
    KD term is 0.5*(KL_clean + KL_masked), scaled by teacher_weight * T**2.
  * C supervises only the occluded view (lambda_clean = 0).
  * B supervises only the clean view.
  * validation masks fixed by `mask_seed = seed + 1_000_000`.
  * locked synthetic severe-occlusion stress test by `stress_seed = seed + 2_000_000`
    with a larger, untrained box geometry; used for reporting only, never for
    checkpoint selection.
  * checkpoint selection: mean(clean_macro_f1, occluded_macro_f1) on the fixed
    validation masks (same rule for every arm and seed).
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)
from torch import Tensor, nn
from torch.nn import functional as F
from torch.utils.data import DataLoader

from .constants import CLASS_NAMES
from .data import ManifestDataset, build_transforms
from .models import build_model
from .train import build_criterion
from .utils import save_json, seed_everything

# --- locked protocol constants -------------------------------------------------
DEFAULT_TEMPERATURE = 2.0
DEFAULT_TEACHER_WEIGHT = 0.5
DEFAULT_LAMBDA_CLEAN = 0.5
DEFAULT_LAMBDA_MASKED = 0.5
# standard occlusion geometry (mirrors expression_recognition.occlusion_experiment)
STD_BOX_WIDTH = (0.32, 0.54)
STD_BOX_HEIGHT = (0.15, 0.27)
# locked synthetic severe-occlusion stress geometry (never used for selection)
STRESS_BOX_WIDTH = (0.55, 0.80)
STRESS_BOX_HEIGHT = (0.30, 0.50)
REGION_NAMES = ["eyes", "mouth", "random"]
TRAIN_ARMS = ("B_plain", "C_hard_occlusion", "E_clean_occlusion", "D_clean_anchor")
TWO_VIEW_ARMS = ("E_clean_occlusion", "D_clean_anchor")
ALL_ARMS = ("A_baseline",) + TRAIN_ARMS


def _occlusion_params(rng: random.Random, width: int, height: int,
                      box_width_range: tuple[float, float],
                      box_height_range: tuple[float, float]):
    region = rng.randrange(3)
    box_width = max(1, round(width * rng.uniform(*box_width_range)))
    box_height = max(1, round(height * rng.uniform(*box_height_range)))
    if region == 0:      # eyes / eyebrows
        center_x, center_y = 0.5, 0.36
    elif region == 1:    # mouth / lower face
        center_x, center_y = 0.5, 0.73
    else:                # arbitrary region
        center_x = rng.uniform(0.25, 0.75)
        center_y = rng.uniform(0.30, 0.75)
    left = min(width - box_width, max(0, round(width * center_x - box_width / 2)))
    top = min(height - box_height, max(0, round(height * center_y - box_height / 2)))
    return region, left, top, box_width, box_height


def occlude_batch(
    images: Tensor,
    *,
    mean: list[float],
    std: list[float],
    seed: int,
    first_index: int = 0,
    box_width_range: tuple[float, float] = STD_BOX_WIDTH,
    box_height_range: tuple[float, float] = STD_BOX_HEIGHT,
) -> tuple[Tensor, list[int]]:
    """Cover one face region per image; never mutate the clean input.

    Returns the occluded batch and the per-sample region id (0 eyes, 1 mouth,
    2 random). Mask choice depends only on (seed, sample index), so it is fixed
    across arms, seeds-as-masks, and checkpoints.
    """
    if images.ndim != 4 or images.shape[1] != len(mean) or len(mean) != len(std):
        raise ValueError("Expected NCHW images with normalization matching channels")
    result = images.clone()
    _, channels, height, width = images.shape
    fill = images.new_tensor([-m / s for m, s in zip(mean, std)]).view(channels, 1, 1)
    regions: list[int] = []
    for index in range(images.shape[0]):
        rng = random.Random(seed + first_index + index)
        region, left, top, bw, bh = _occlusion_params(
            rng, width, height, box_width_range, box_height_range
        )
        result[index, :, top:top + bh, left:left + bw] = fill
        regions.append(region)
    return result, regions


def anchored_loss(
    student_clean: Tensor,
    student_occluded: Tensor,
    teacher_clean: Tensor,
    labels: Tensor,
    criterion: nn.Module,
    *,
    temperature: float = DEFAULT_TEMPERATURE,
    teacher_weight: float = DEFAULT_TEACHER_WEIGHT,
    lambda_clean: float = DEFAULT_LAMBDA_CLEAN,
    lambda_masked: float = DEFAULT_LAMBDA_MASKED,
) -> Tensor:
    """Normalized clean-anchored distillation loss (fixed a priori).

    Supervised part is a convex combination of the clean and occluded CE so its
    gradient scale matches the single-view arms; the KD term is the mean of the
    clean and occluded KL divergences scaled by teacher_weight * T**2.
    """
    if temperature <= 0 or teacher_weight < 0:
        raise ValueError("temperature must be positive and teacher_weight nonnegative")
    if lambda_clean < 0 or lambda_masked < 0 or abs(lambda_clean + lambda_masked - 1.0) > 1e-9:
        raise ValueError("lambda_clean + lambda_masked must equal 1")
    reference = F.softmax(teacher_clean.detach() / temperature, dim=1)
    clean_kl = F.kl_div(F.log_softmax(student_clean / temperature, dim=1), reference, reduction="batchmean")
    masked_kl = F.kl_div(F.log_softmax(student_occluded / temperature, dim=1), reference, reduction="batchmean")
    supervised = lambda_clean * criterion(student_clean, labels) + lambda_masked * criterion(student_occluded, labels)
    distillation = 0.5 * (clean_kl + masked_kl)
    return supervised + teacher_weight * temperature ** 2 * distillation


def supervised_two_view_loss(
    student_clean: Tensor,
    student_occluded: Tensor,
    labels: Tensor,
    criterion: nn.Module,
    *,
    lambda_clean: float = DEFAULT_LAMBDA_CLEAN,
    lambda_masked: float = DEFAULT_LAMBDA_MASKED,
) -> Tensor:
    """Convex clean/occluded supervision without a teacher (arm E)."""
    if lambda_clean < 0 or lambda_masked < 0 or abs(lambda_clean + lambda_masked - 1.0) > 1e-9:
        raise ValueError("lambda_clean + lambda_masked must equal 1")
    return (
        lambda_clean * criterion(student_clean, labels)
        + lambda_masked * criterion(student_occluded, labels)
    )


def arm_loss(name: str, model, clean, masked, teacher_clean, labels, criterion, config) -> Tensor:
    if name == "C_hard_occlusion":
        return criterion(model(masked), labels)
    if name == "B_plain":
        return criterion(model(clean), labels)
    if name == "E_clean_occlusion":
        return supervised_two_view_loss(
            model(clean), model(masked), labels, criterion,
            lambda_clean=float(config["distill_lambda_clean"]),
            lambda_masked=float(config["distill_lambda_masked"]),
        )
    if name == "D_clean_anchor":
        return anchored_loss(
            model(clean), model(masked), teacher_clean, labels, criterion,
            temperature=float(config["distill_temperature"]),
            teacher_weight=float(config["distill_teacher_weight"]),
            lambda_clean=float(config["distill_lambda_clean"]),
            lambda_masked=float(config["distill_lambda_masked"]),
        )
    raise ValueError(f"Unknown arm: {name}")


def _view_metrics(predictions: list[int], targets: list[int]) -> dict:
    labels = list(range(len(CLASS_NAMES)))
    p, r, f1, support = precision_recall_fscore_support(
        targets, predictions, labels=labels, zero_division=0
    )
    return {
        "samples": len(targets),
        "accuracy": float(accuracy_score(targets, predictions)),
        "macro_f1": float(f1_score(targets, predictions, labels=labels, average="macro", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(targets, predictions)),
        "per_class": {
            name: {
                "precision": float(p[i]),
                "recall": float(r[i]),
                "f1": float(f1[i]),
                "support": int(support[i]),
            }
            for i, name in enumerate(CLASS_NAMES)
        },
        "confusion_matrix": confusion_matrix(targets, predictions, labels=labels).tolist(),
    }


@torch.inference_mode()
def evaluate_model(model: nn.Module, loader: DataLoader, device: torch.device, config: dict,
                   mask_seed: int, stress_seed: int) -> dict:
    """Evaluate clean, standard-occluded, per-region, and locked severe stress views."""
    model.eval()
    mean = config["normalization"]["mean"]
    std = config["normalization"]["std"]
    clean_pred: list[int] = []
    occ_pred: list[int] = []
    stress_pred: list[int] = []
    targets: list[int] = []
    regions: list[int] = []
    offset = 0
    for clean, labels in loader:
        masked, batch_regions = occlude_batch(
            clean, mean=mean, std=std, seed=mask_seed, first_index=offset
        )
        stressed, _ = occlude_batch(
            clean, mean=mean, std=std, seed=stress_seed, first_index=offset,
            box_width_range=STRESS_BOX_WIDTH, box_height_range=STRESS_BOX_HEIGHT,
        )
        offset += len(labels)
        clean = clean.to(device, non_blocking=True)
        masked = masked.to(device, non_blocking=True)
        stressed = stressed.to(device, non_blocking=True)
        clean_pred.extend(model(clean).argmax(1).cpu().tolist())
        occ_pred.extend(model(masked).argmax(1).cpu().tolist())
        stress_pred.extend(model(stressed).argmax(1).cpu().tolist())
        targets.extend(labels.tolist())
        regions.extend(batch_regions)

    result = {
        "clean": _view_metrics(clean_pred, targets),
        "occluded": _view_metrics(occ_pred, targets),
        "occluded_stress_severe": _view_metrics(stress_pred, targets),
        "occluded_by_region": {},
    }
    regions_arr = np.asarray(regions)
    occ_arr = np.asarray(occ_pred)
    tgt_arr = np.asarray(targets)
    for region_id, region_name in enumerate(REGION_NAMES):
        mask = regions_arr == region_id
        if mask.any():
            result["occluded_by_region"][region_name] = _view_metrics(
                occ_arr[mask].tolist(), tgt_arr[mask].tolist()
            )
        else:
            result["occluded_by_region"][region_name] = {"samples": 0}
    result["region_counts"] = {REGION_NAMES[i]: int((regions_arr == i).sum()) for i in range(3)}
    return result


def _selection_score(metrics: dict) -> float:
    return 0.5 * (metrics["clean"]["macro_f1"] + metrics["occluded"]["macro_f1"])


def train_arm(
    name: str,
    initial_state: dict,
    teacher: nn.Module | None,
    train_dataset: ManifestDataset,
    validation_loader: DataLoader,
    config: dict,
    device: torch.device,
    arm_dir: Path,
    *,
    epochs: int,
    learning_rate: float,
    weight_decay: float,
    seed: int,
    mask_seed: int,
    stress_seed: int,
    max_train_batches: int | None,
    num_workers: int,
    batch_size: int,
) -> dict:
    seed_everything(seed)
    model = build_model(config, allow_download=False).to(device)
    model.load_state_dict(initial_state)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    criterion = build_criterion(config, train_dataset.targets, device)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    generator = torch.Generator().manual_seed(seed)
    loader_options = {
        "num_workers": num_workers,
        "persistent_workers": num_workers > 0,
        "pin_memory": device.type == "cuda",
    }
    mean = config["normalization"]["mean"]
    std = config["normalization"]["std"]

    history: list[dict] = []
    best_score = -1.0
    total_updates = 0
    total_views = 0
    peak_vram = 0.0
    started = time.perf_counter()

    # Built once so persistent workers survive across epochs; the generator keeps
    # producing a fresh shuffle each time the loader is re-iterated.
    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True, drop_last=True,
        generator=generator, **loader_options,
    )
    for epoch in range(epochs):
        model.train()
        epoch_losses: list[float] = []
        for batch_index, (clean, labels) in enumerate(train_loader):
            if max_train_batches is not None and batch_index >= max_train_batches:
                break
            # training occlusion seed is per-sample deterministic but changes each epoch
            masked, _ = occlude_batch(
                clean, mean=mean, std=std,
                seed=seed + epoch * 10_000_019 + batch_index * clean.shape[0],
            )
            clean = clean.to(device, non_blocking=True)
            masked = masked.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast(device_type=device.type, dtype=torch.float16,
                                    enabled=device.type == "cuda"):
                if name == "D_clean_anchor":
                    teacher_clean = teacher(clean).float()
                else:
                    teacher_clean = None
                loss = arm_loss(name, model, clean, masked, teacher_clean, labels, criterion, config)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), float(config.get("gradient_clip_norm", 1.0)))
            scaler.step(optimizer)
            scaler.update()
            epoch_losses.append(float(loss.detach().cpu()))
            total_updates += 1
            total_views += 2 if name in TWO_VIEW_ARMS else 1
            if device.type == "cuda":
                peak_vram = max(peak_vram, torch.cuda.max_memory_allocated() / 1e9)
        metrics = evaluate_model(model, validation_loader, device, config, mask_seed, stress_seed)
        score = _selection_score(metrics)
        row = {
            "epoch": epoch + 1,
            "train_loss": float(np.mean(epoch_losses)),
            "selection_score": score,
            "clean_macro_f1": metrics["clean"]["macro_f1"],
            "occluded_macro_f1": metrics["occluded"]["macro_f1"],
            "clean_accuracy": metrics["clean"]["accuracy"],
            "occluded_accuracy": metrics["occluded"]["accuracy"],
        }
        history.append(row)
        print(json.dumps({"arm": name, "seed": seed, **row}, ensure_ascii=False), flush=True)
        if score > best_score:
            best_score = score
            torch.save(
                {
                    "model_state": model.state_dict(),
                    "config": config,
                    "history": history,
                    "arm": name,
                    "seed": seed,
                    "selection_score": score,
                    "validation_mask_seed": mask_seed,
                },
                arm_dir / "best.pt",
            )
            save_json(arm_dir / "best_validation.json", metrics)

    save_json(arm_dir / "history.json", history)
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    run_info = {
        "arm": name,
        "seed": seed,
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "weight_decay": weight_decay,
        "optimizer_updates": total_updates,
        "views_processed": total_views,
        "views_per_update": 2 if name in TWO_VIEW_ARMS else 1,
        "two_view_supervision": name in TWO_VIEW_ARMS,
        "teacher_distillation": name == "D_clean_anchor",
        "wall_seconds": time.perf_counter() - started,
        "peak_vram_gb": peak_vram,
        "train_samples": len(train_dataset),
        "max_train_batches": max_train_batches,
    }
    save_json(arm_dir / "run_info.json", run_info)
    return {"run_info": run_info, "best": json.loads((arm_dir / "best_validation.json").read_text(encoding="utf-8"))}


def build_protocol_config(checkpoint_config: dict, *, seed: int, batch_size: int, num_workers: int,
                          temperature: float, teacher_weight: float,
                          lambda_clean: float, lambda_masked: float) -> dict:
    import copy
    config = copy.deepcopy(checkpoint_config)
    config["num_workers"] = num_workers
    config["batch_size"] = batch_size
    # disable stochastic occlusion augmentation so experimental occlusion is the only one
    config["augmentation"] = dict(config.get("augmentation", {}))
    config["augmentation"]["occlusion_probability"] = 0.0
    config.update({
        "distill_temperature": temperature,
        "distill_teacher_weight": teacher_weight,
        "distill_lambda_clean": lambda_clean,
        "distill_lambda_masked": lambda_masked,
    })
    return config


def run(args: argparse.Namespace) -> dict:
    if args.epochs < 1 or args.batch_size < 1 or args.learning_rate <= 0:
        raise ValueError("epochs, batch_size and learning_rate must be positive")
    if not args.checkpoint.is_file() or not args.manifest.is_file():
        raise FileNotFoundError("A seven-class checkpoint and included.csv manifest are required")
    requested = tuple(getattr(args, "arms", None) or ALL_ARMS)
    unknown = [name for name in requested if name not in ALL_ARMS]
    if unknown:
        raise ValueError(f"Unknown arm(s): {unknown}")
    if len(set(requested)) != len(requested):
        raise ValueError("Arms must be requested once each")
    resume = bool(getattr(args, "resume", False))
    seed = int(args.seed)
    mask_seed = seed + 1_000_000
    stress_seed = seed + 2_000_000
    seed_everything(seed)

    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    config = build_protocol_config(
        checkpoint["config"], seed=seed, batch_size=args.batch_size, num_workers=args.num_workers,
        temperature=args.temperature, teacher_weight=args.teacher_weight,
        lambda_clean=args.lambda_clean, lambda_masked=args.lambda_masked,
    )
    if config["model"] != "resnet18" or int(config["input_channels"]) != 3:
        raise ValueError("This experiment requires the existing three-channel ResNet18 checkpoint")

    train_dataset = ManifestDataset(args.manifest, "train", build_transforms(config, training=True))
    validation_dataset = ManifestDataset(args.manifest, "validation", build_transforms(config, training=False))
    if len(train_dataset) < args.batch_size:
        raise ValueError("Training split has fewer samples than batch_size")

    if args.output_dir.exists() and not args.overwrite and not resume:
        raise FileExistsError(f"Output dir already exists: {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    loader_options = {
        "num_workers": args.num_workers,
        "persistent_workers": args.num_workers > 0,
        "pin_memory": device.type == "cuda",
    }
    validation_loader = DataLoader(validation_dataset, batch_size=args.batch_size, shuffle=False, **loader_options)

    results_path = args.output_dir / "results.json"
    metadata = {
        "seed": seed,
        "mask_seed": mask_seed,
        "stress_seed": stress_seed,
        "checkpoint": str(args.checkpoint.resolve()),
        "manifest": str(args.manifest.resolve()),
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "temperature": args.temperature,
        "teacher_weight": args.teacher_weight,
        "lambda_clean": args.lambda_clean,
        "lambda_masked": args.lambda_masked,
        "smoke": args.max_train_batches is not None,
    }
    if resume and results_path.is_file():
        results = json.loads(results_path.read_text(encoding="utf-8"))
        for key, value in metadata.items():
            if key in results and results[key] != value:
                raise ValueError(f"Existing run has different {key}: {results[key]!r} != {value!r}")
    else:
        results = dict(metadata)
        results["arms"] = {}
    results.update(metadata)
    results["arms"] = dict(results.get("arms", {}))
    results["requested_arms"] = list(requested)
    results["resumed"] = resume

    # The frozen clean-reference teacher is only needed for A (same weights) and D.
    teacher = None
    if "A_baseline" in requested or "D_clean_anchor" in requested:
        teacher = build_model(config, allow_download=False).to(device)
        teacher.load_state_dict(checkpoint["model_state"])
        teacher.eval()
        for parameter in teacher.parameters():
            parameter.requires_grad_(False)

    # Arm A: original checkpoint, no training (start reference)
    if "A_baseline" in requested:
        if resume and "A_baseline" in results["arms"]:
            print(json.dumps({"arm": "A_baseline", "seed": seed, "status": "already recorded; skipped"},
                             ensure_ascii=False), flush=True)
        else:
            a_dir = args.output_dir / "A_baseline"
            a_dir.mkdir(exist_ok=True)
            results["arms"]["A_baseline"] = {
                "eval": evaluate_model(teacher, validation_loader, device, config, mask_seed, stress_seed)
            }
            save_json(a_dir / "metrics.json", results["arms"]["A_baseline"]["eval"])
            print(json.dumps({"arm": "A_baseline", "seed": seed,
                              "clean_macro_f1": results["arms"]["A_baseline"]["eval"]["clean"]["macro_f1"],
                              "occluded_macro_f1": results["arms"]["A_baseline"]["eval"]["occluded"]["macro_f1"]},
                             ensure_ascii=False), flush=True)

    for name in TRAIN_ARMS:
        if name not in requested:
            continue
        arm_dir = args.output_dir / name
        if resume and (arm_dir / "best.pt").is_file() and name in results["arms"]:
            print(json.dumps({"arm": name, "seed": seed, "status": "already recorded; skipped"},
                             ensure_ascii=False), flush=True)
            continue
        arm_dir.mkdir(exist_ok=True)
        if device.type == "cuda":
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
        out = train_arm(
            name, checkpoint["model_state"],
            teacher if name == "D_clean_anchor" else None,
            train_dataset, validation_loader, config, device, arm_dir,
            epochs=args.epochs, learning_rate=args.learning_rate,
            weight_decay=float(config["weight_decay"]), seed=seed,
            mask_seed=mask_seed, stress_seed=stress_seed,
            max_train_batches=args.max_train_batches, num_workers=args.num_workers,
            batch_size=args.batch_size,
        )
        results["arms"][name] = out

    save_json(results_path, results)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Controlled five-arm occlusion-training ablation.")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20261022)
    parser.add_argument("--arms", nargs="+", choices=ALL_ARMS, default=None,
                        help="Subset of arms to run (default: all). With --resume, add one arm without retraining the rest.")
    parser.add_argument("--resume", action="store_true",
                        help="Reuse an existing output dir and skip arms already recorded there. Never re-runs a recorded arm.")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--teacher-weight", type=float, default=DEFAULT_TEACHER_WEIGHT)
    parser.add_argument("--lambda-clean", type=float, default=DEFAULT_LAMBDA_CLEAN)
    parser.add_argument("--lambda-masked", type=float, default=DEFAULT_LAMBDA_MASKED)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--max-train-batches", type=int, help="Smoke run only; results not comparable")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--cpu", action="store_true")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
