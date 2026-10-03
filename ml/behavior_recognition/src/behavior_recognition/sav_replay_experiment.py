"""Paired V3.4 adaptation with grouped SAV set labels and four-class replay."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset

from .constants import CLASS_NAMES
from .data import build_transforms, crop_normalized_box
from .finetune_regularization import configure_trainable, l2_sp_penalty, sp_reference
from .l2sp_experiment import (CachedDataset, audit_splits, cache_path, evaluate,
                              prepare_cache, verify_parity, verify_prepared_cache,
                              write_json)
from .metrics import softmax
from .onnx_finetune import OnnxBehaviorModel
from .sav_data import build_sav_records
from .train import _class_weights, _seed_worker, seed_everything

SPLIT_DATES = {"train": ["20181016", "20181017", "20200901"],
               "val": ["20181018"], "test": ["20200902", "20200903"]}
LIMITATIONS = (
    "SAV contains only ten selected source videos, no phone label, and very few "
    "write-only examples. Dates and source videos are disjoint, but student "
    "identities are unknown. Set-label accuracy/NLL on positive SAV examples "
    "does not measure class precision or general four-class accuracy. The old "
    "SCB test is previously exposed, and the inherited training split is unknown. "
    "This adapts the single-frame V3.4 branch using official annotated keyframes; "
    "it does not train a temporal model or modify production assets."
)


def partial_label_loss(logits: torch.Tensor, masks: torch.Tensor) -> torch.Tensor:
    """Negative log probability of the permitted mutually-exclusive class set."""
    if logits.ndim != 2 or logits.shape != masks.shape or logits.shape[1] != 4:
        raise ValueError("Expected matching [batch,4] logits and set masks")
    if not len(logits) or masks.dtype != torch.bool or not masks.any(dim=1).all():
        raise ValueError("Set labels must be nonempty boolean masks")
    log_probabilities = logits.float().log_softmax(dim=1)
    return -log_probabilities.masked_fill(~masks, -torch.inf).logsumexp(dim=1).mean()


def set_report(logits: np.ndarray, rows: list[dict]) -> dict:
    if np.shape(logits) != (len(rows), 4) or not len(rows):
        raise ValueError("SAV score input mismatch")
    probabilities = softmax(logits)
    masks = np.asarray([row["class_mask"] for row in rows], dtype=bool)
    hits = masks[np.arange(len(rows)), probabilities.argmax(axis=1)]
    nll = -np.log(np.maximum((probabilities * masks).sum(axis=1), 1e-12))
    groups = defaultdict(list)
    for index, row in enumerate(rows):
        groups[row["source_video_key"]].append(index)
    by_source = {
        key: {"samples": len(indices), "acceptable_top1_rate": float(hits[indices].mean()),
              "partial_nll": float(nll[indices].mean())}
        for key, indices in groups.items()
    }
    return {"samples": len(rows), "acceptable_top1_rate": float(hits.mean()),
            "partial_nll": float(nll.mean()), "by_source_video": by_source,
            "source_mean_acceptable_top1_rate": float(np.mean([r["acceptable_top1_rate"] for r in by_source.values()])),
            "source_mean_partial_nll": float(np.mean([r["partial_nll"] for r in by_source.values()])),
            "read_only_samples": int(((masks[:, 0]) & ~masks[:, 1]).sum()),
            "write_only_samples": int(((masks[:, 1]) & ~masks[:, 0]).sum()),
            "read_or_write_samples": int((masks[:, 0] & masks[:, 1]).sum()),
            "metric_scope": "positive set-labelled READ/WRITE ROI recognition; not four-class accuracy"}


class SavDataset(Dataset):
    def __init__(self, root: Path, rows: list[dict], training: bool):
        self.root, self.rows = root, rows
        self.transform = build_transforms(training)

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        with Image.open(cache_path(self.root, row)) as image:
            tensor = self.transform(image.convert("RGB"))
        return tensor, torch.tensor(row["class_mask"], dtype=torch.bool)


def evaluate_sav(model, loader, rows, device):
    model.eval()
    outputs = []
    with torch.inference_mode():
        for images, _ in loader:
            outputs.append(model(images.to(device, non_blocking=True)).cpu().numpy())
    return set_report(np.concatenate(outputs), rows)


def validation_eligible(value: dict, original: dict) -> bool:
    old, base = value["scb"], original["scb"]
    guarded = (old["accuracy"] >= base["accuracy"] - 1e-12
               and old["macro_f1"] >= base["macro_f1"] - 1e-12
               and old["phone_interaction_auprc"] >= base["phone_interaction_auprc"] - 1e-12
               and all(old["per_class"][name]["f1"] >= base["per_class"][name]["f1"] - 1e-12 for name in CLASS_NAMES)
               and old["per_class"]["PHONE_INTERACTION"]["recall"] >= base["per_class"]["PHONE_INTERACTION"]["recall"] - 1e-12)
    new, initial = value["sav"], original["sav"]
    return bool(guarded
                and new["source_mean_acceptable_top1_rate"] >= initial["source_mean_acceptable_top1_rate"] - 1e-12
                and new["source_mean_partial_nll"] < initial["source_mean_partial_nll"] - 1e-12)


def validation_rank(value: dict, original: dict) -> tuple:
    return (validation_eligible(value, original),
            -value["sav"]["source_mean_partial_nll"],
            value["scb"]["macro_f1"], value["scb"]["accuracy"])


def next_sav_batch(loader, iterator):
    try:
        return next(iterator), iterator
    except StopIteration:
        iterator = iter(loader)
        return next(iterator), iterator


def verify_replay_pixels(root: Path, rows: dict, workers: int = 2) -> dict:
    """Check cached ROIs against fingerprinted source images before reuse."""
    grouped = defaultdict(list)
    for records in rows.values():
        for row in records:
            grouped[row["image_path"]].append(row)

    def verify(pair):
        image_path, records = pair
        source = Path(image_path)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if any(row["sha256"] != digest for row in records):
            raise ValueError("Replay source image fingerprint mismatch")
        with Image.open(source) as opened:
            image = opened.convert("RGB")
            for row in records:
                expected = crop_normalized_box(
                    image, *(float(row[key]) for key in
                             ("center_x", "center_y", "width", "height")), expansion=1.1,
                ).resize((224, 224), Image.Resampling.BILINEAR)
                with Image.open(cache_path(root, row)) as cached:
                    if not np.array_equal(np.asarray(expected), np.asarray(cached)):
                        raise ValueError("Replay cached ROI pixels mismatch")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        list(executor.map(verify, grouped.items()))
    return {"source_images": len(grouped), "verified_rois": sum(map(len, rows.values())),
            "method": "source SHA256 and exact decoded crop pixel equality"}


def run(args):
    if not 1 <= args.epochs <= 6 or args.workers < 1:
        raise ValueError("Invalid bounded training settings")
    if not args.lr > 0 or not np.isfinite(args.lr) or not np.isfinite(args.sav_weight) or args.sav_weight <= 0:
        raise ValueError("Invalid optimization settings")
    started = time.perf_counter()
    source, root = args.source_onnx.resolve(), args.output_dir.resolve()
    source_bytes = source.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    old_rows, fingerprints = {}, {}
    for split in ("train", "val", "test"):
        path = args.replay_manifests / f"{split}.csv"
        with path.open(encoding="utf-8-sig", newline="") as handle:
            old_rows[split] = list(csv.DictReader(handle))
        fingerprints[split] = hashlib.sha256(path.read_bytes()).hexdigest()
    old_audit = audit_splits(old_rows)
    verify_prepared_cache(args.replay_cache, old_rows, fingerprints)
    replay_pixels = verify_replay_pixels(args.replay_cache, old_rows, min(args.workers, 2))
    sav_rows, sav_audit = build_sav_records(args.sav_root, SPLIT_DATES)
    if any(len(sav_audit[split]["source_videos"]) != count
           for split, count in (("train", 6), ("val", 2), ("test", 2))):
        raise ValueError("Expected SAV source video split counts 6/2/2")
    # Check overlap across both sources, allowing repeated students on a frame within a split.
    split_hashes = {s: {r["sha256"] for r in old_rows[s] + sav_rows[s]} for s in old_rows}
    for left, right in (("train", "val"), ("train", "test"), ("val", "test")):
        if split_hashes[left] & split_hashes[right]:
            raise ValueError("Cross-source image hash leakage")
    if root.exists():
        raise FileExistsError("Choose a new output directory")
    root.mkdir(parents=True)
    plan = {"source_sha256": source_sha, "replay_manifest_sha256": fingerprints,
            "seed": args.seed, "epochs": args.epochs, "schedule": "fixed equal epochs and optimizer steps in both arms",
            "arms": ["replay_only", "replay_plus_sav"], "lr": args.lr,
            "old_batch_size": 48, "sav_batch_size": 16, "sav_loss_weight": args.sav_weight,
            "l2sp_alpha": 1000.0, "l2sp_definition": "0.5 * unnormalized sum squared parameter distance from original",
            "old_loss": "sqrt inverse frequency CE; smoothing=0.05",
            "new_loss": "set-label -log(sum softmax of permitted READ/WRITE classes); no unlabeled negatives",
            "old_audit": old_audit, "replay_pixels": replay_pixels,
            "sav_audit": sav_audit, "split_dates": SPLIT_DATES,
            "selection": "all original SCB val accuracy/macroF1/per-classF1/phoneAUPRC/phoneRecall retained; SAV source-mean acceptable rate retained and set NLL improves; rank by source-mean SAV NLL",
            "roi_expansion": 1.1, "labels": list(CLASS_NAMES),
            "training_precision": "FP32, TF32 disabled; nonfinite gradients abort rather than skip paired updates",
            "evaluation": "FP32; TF32 disabled; frozen selection before test", "limitations": LIMITATIONS}
    write_json(root / "plan.json", plan)
    for split, records in sav_rows.items():
        write_json(root / f"sav_{split}.json", records)
    prepare_cache(root, sum(sav_rows.values(), []), max(1, min(args.workers, 2)))
    device = torch.device(args.device)
    torch.set_num_threads(2)
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cuda.matmul.allow_tf32 = False

    def loader(dataset, batch_size, training=False, seed_offset=0):
        return DataLoader(dataset, batch_size=batch_size, shuffle=training,
                          generator=torch.Generator().manual_seed(args.seed + seed_offset),
                          num_workers=args.workers, pin_memory=device.type == "cuda",
                          persistent_workers=args.workers > 0, worker_init_fn=_seed_worker)

    old_eval = {s: loader(CachedDataset(args.replay_cache, old_rows[s], False), 64) for s in ("val", "test")}
    sav_eval = {s: loader(SavDataset(root, sav_rows[s], False), 64) for s in ("val", "test")}

    def validation(model):
        return {"scb": evaluate(model, old_eval["val"], device),
                "sav": evaluate_sav(model, sav_eval["val"], sav_rows["val"], device)}

    options = ort.SessionOptions(); options.intra_op_num_threads = 2
    session = ort.InferenceSession(str(source), sess_options=options, providers=["CPUExecutionProvider"])
    original = OnnxBehaviorModel(source).to(device)
    parity = verify_parity(original, session, CachedDataset(args.replay_cache, old_rows["train"], False), device)
    sav_parity_data = SavDataset(root, sav_rows["train"], False)
    parity["sav"] = verify_parity(original, session, sav_parity_data, device)
    write_json(root / "original_parity.json", parity)
    baseline = validation(original)
    write_json(root / "original_validation.json", baseline)
    print("BASELINE", json.dumps(baseline), flush=True)
    del original, session
    results = {}
    for name in plan["arms"]:
        seed_everything(args.seed)
        arm_root = root / name; arm_root.mkdir()
        model = OnnxBehaviorModel(source).to(device)
        trainability = configure_trainable(model, "all")
        reference = sp_reference(model)
        old_train = loader(CachedDataset(args.replay_cache, old_rows["train"], True), 48, True)
        # Identical replay batches/augmentation seeds/optimizer steps in both arms.
        sav_train = loader(SavDataset(root, sav_rows["train"], True), 16, True, 100)
        optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
        criterion = torch.nn.CrossEntropyLoss(weight=_class_weights(old_rows["train"]).sqrt().to(device), label_smoothing=0.05)
        best, best_epoch, steps = None, 0, 0
        history = []
        for epoch in range(1, args.epochs + 1):
            epoch_start = time.perf_counter(); model.train()
            sums = defaultdict(float); batches = 0
            sav_iterator = iter(sav_train) if name == "replay_plus_sav" else None
            for images, targets in old_train:
                optimizer.zero_grad(set_to_none=True)
                images, targets = images.to(device, non_blocking=True), targets.to(device, non_blocking=True)
                ce = criterion(model(images), targets)
                additional = ce.new_zeros(())
                if name == "replay_plus_sav":
                    (sav_images, masks), sav_iterator = next_sav_batch(sav_train, sav_iterator)
                    additional = partial_label_loss(model(sav_images.to(device, non_blocking=True)), masks.to(device, non_blocking=True))
                penalty = l2_sp_penalty(model, reference)
                loss = ce.float() + args.sav_weight * additional.float() + 1000 * penalty
                if not torch.isfinite(loss):
                    raise RuntimeError("Nonfinite training loss")
                loss.backward()
                norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                if not torch.isfinite(norm):
                    raise RuntimeError("Nonfinite gradients; paired update aborted")
                optimizer.step()
                for key, value in (("old_ce", ce), ("sav_set_nll", additional), ("l2sp_penalty", penalty), ("gradient_norm_before_clip", norm)):
                    sums[key] += float(value.detach())
                batches += 1; steps += 1
            measured = validation(model)
            row = {"epoch": epoch, "validation": measured, "steps": steps,
                   "seconds": time.perf_counter() - epoch_start,
                   "loss_batch_means": {key: value / batches for key, value in sums.items()}}
            history.append(row); write_json(arm_root / "history.json", history)
            print("EPOCH", json.dumps({"arm": name, "epoch": epoch,
                  "old_accuracy": measured["scb"]["accuracy"], "old_macro_f1": measured["scb"]["macro_f1"],
                  "sav_source_nll": measured["sav"]["source_mean_partial_nll"], "eligible": validation_eligible(measured, baseline),
                  "seconds": row["seconds"]}), flush=True)
            if best is None or validation_rank(measured, baseline) > validation_rank(best, baseline):
                best, best_epoch = measured, epoch
                torch.save({"model_state": {k: v.detach().cpu() for k, v in model.state_dict().items()},
                            "epoch": epoch, "source_sha256": source_sha, "arm": name,
                            "trainability": trainability}, arm_root / "best.pt")
        results[name] = {"validation": best, "best_epoch": best_epoch,
                         "epochs_completed": len(history), "steps": steps,
                         "eligible": validation_eligible(best, baseline)}
        del old_train, sav_train, sav_iterator, model, optimizer, reference
        if device.type == "cuda":
            torch.cuda.empty_cache()
    options_names = [name for name, result in results.items() if result["eligible"]]
    selected = max(options_names, key=lambda n: validation_rank(results[n]["validation"], baseline)) if options_names else "original"
    write_json(root / "selection.json", {"selected": selected, "baseline": baseline, "candidates": results,
                                        "criterion": plan["selection"]})
    # Both test sets are read only after all epoch and arm choices are frozen.
    test_reports = {}
    for name in ["original", *plan["arms"]]:
        model = OnnxBehaviorModel(source).to(device)
        if name != "original":
            checkpoint = torch.load(root / name / "best.pt", map_location="cpu", weights_only=False)
            if checkpoint["source_sha256"] != source_sha:
                raise ValueError("Checkpoint source graph mismatch")
            model.load_state_dict(checkpoint["model_state"], strict=True)
        test_reports[name] = {"scb_exposed_test_diagnostic": evaluate(model, old_eval["test"], device),
                              "sav_heldout_test": evaluate_sav(model, sav_eval["test"], sav_rows["test"], device)}
        if name == selected and name != "original":
            exported = root / "selected_candidate.onnx"; model.export_onnx(exported)
            export_session = ort.InferenceSession(str(exported), sess_options=options, providers=["CPUExecutionProvider"])
            export_parity = verify_parity(model, export_session, sav_parity_data, device)
            export_parity["sha256"] = hashlib.sha256(exported.read_bytes()).hexdigest()
            write_json(root / "export_parity.json", export_parity)
        del model
    if source.read_bytes() != source_bytes:
        raise RuntimeError("Production source model changed")
    report = {"plan": plan, "original_validation": baseline, "candidates": results,
              "selected_on_validation": selected, "tests": test_reports, "assets_replaced": False,
              "elapsed_seconds": time.perf_counter() - started, "limitations": LIMITATIONS}
    write_json(root / "comparison.json", report)
    print("COMPLETE", json.dumps({"selected": selected, "seconds": report["elapsed_seconds"]}), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source-onnx", "replay-manifests", "replay-cache", "sav-root", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20261003)
    parser.add_argument("--lr", type=float, default=2e-6)
    parser.add_argument("--sav-weight", type=float, default=0.2)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
