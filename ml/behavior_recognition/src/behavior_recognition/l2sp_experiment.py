"""Bounded L2-SP comparisons from existing V3.4 weights, without deployment."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset

from .constants import CLASS_NAMES, PRODUCT_CLASS_NAMES
from .data import build_transforms, crop_normalized_box
from .finetune_regularization import configure_trainable, l2_sp_penalty, sp_reference
from .metrics import classification_report, project_product_probabilities, softmax
from .onnx_finetune import OnnxBehaviorModel
from .train import _class_weights, _seed_worker, seed_everything

LIMITATION = (
    "Only three source videos. The inherited model's old training split is "
    "unavailable and may overlap this benchmark. Previous experiments have "
    "already reported this test set. Results are exploratory offline comparisons, "
    "not independent subject/front-camera validation or deployment approval."
)


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def audit_splits(rows: dict[str, list[dict]]) -> dict:
    """Reject cross-split sample, video, or source-image hash overlap."""
    seen_ids = set()
    sets = {}
    for split, records in rows.items():
        if not records:
            raise ValueError(f"Empty {split} manifest")
        sets[split] = {"groups": set(), "hashes": set()}
        for record in records:
            if record["sample_id"] in seen_ids:
                raise ValueError("Duplicate sample_id across manifests")
            seen_ids.add(record["sample_id"])
            if record["split"] != split:
                raise ValueError("Manifest split field disagrees with filename")
            label = int(record["target_index"])
            if label not in range(len(CLASS_NAMES)) or record["target_name"] != CLASS_NAMES[label]:
                raise ValueError("Class label contract mismatch")
            if not record["group_id"] or not record["sha256"]:
                raise ValueError("Missing video group or source hash")
            sets[split]["groups"].add(record["group_id"])
            sets[split]["hashes"].add(record["sha256"])
    splits = list(sets)
    for index, left in enumerate(splits):
        for right in splits[index + 1:]:
            for key in ("groups", "hashes"):
                if sets[left][key] & sets[right][key]:
                    raise ValueError(f"Cross-split {key} overlap: {left}/{right}")
    return {
        split: {"samples": len(records),
                "class_counts": dict(Counter(r["target_name"] for r in records)),
                "video_groups": sorted(sets[split]["groups"])}
        for split, records in rows.items()
    }


def eligible(validation: dict, baseline: dict) -> bool:
    return (validation["macro_f1"] > baseline["macro_f1"] + 1e-12
            and validation["accuracy"] >= baseline["accuracy"] - 1e-12)


def select_arm(validations: dict[str, dict], baseline: dict) -> str:
    options = [name for name, result in validations.items() if eligible(result, baseline)]
    if not options:
        return "original"
    return max(options, key=lambda name: (validations[name]["macro_f1"],
                                          validations[name]["accuracy"]))


def checkpoint_rank(validation: dict, baseline: dict) -> tuple:
    # Prefer eligible epochs before ranking Macro-F1; otherwise a later F1 gain
    # with an accuracy regression could overwrite an earlier valid checkpoint.
    return (eligible(validation, baseline), validation["macro_f1"], validation["accuracy"])


def cache_path(root: Path, record: dict) -> Path:
    key = hashlib.sha256(record["sample_id"].encode()).hexdigest()
    return root / "roi_cache" / f"{key}.png"


def prepare_cache(root: Path, records: list[dict], workers: int) -> None:
    (root / "roi_cache").mkdir()
    grouped = defaultdict(list)
    for record in records:
        grouped[record["image_path"]].append(record)

    def process(pair):
        image_path, image_records = pair
        with Image.open(image_path) as opened:
            image = opened.convert("RGB")
            for record in image_records:
                crop = crop_normalized_box(
                    image, *(float(record[k]) for k in
                             ("center_x", "center_y", "width", "height")),
                    expansion=1.1,
                ).resize((224, 224), Image.Resampling.BILINEAR)
                crop.save(cache_path(root, record), compress_level=1)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        list(executor.map(process, grouped.items()))


def verify_prepared_cache(root: Path, rows: dict, fingerprints: dict) -> None:
    metadata = json.loads((root / "plan.json").read_text(encoding="utf-8"))
    if (metadata.get("manifest_sha256") != fingerprints
            or metadata.get("roi_expansion") != 1.1
            or metadata.get("labels") != list(CLASS_NAMES)):
        raise ValueError("Prepared ROI cache contract mismatch")
    for records in rows.values():
        for row in records:
            path = cache_path(root, row)
            if not path.is_file():
                raise ValueError("Prepared ROI cache is incomplete")
            try:
                with Image.open(path) as image:
                    if image.format != "PNG" or image.size != (224, 224) or image.mode != "RGB":
                        raise ValueError("Prepared ROI cache image contract mismatch")
                    image.verify()
            except (OSError, SyntaxError) as error:
                raise ValueError("Prepared ROI cache image is corrupt") from error


class CachedDataset(Dataset):
    def __init__(self, root: Path, rows: list[dict], training: bool):
        self.root, self.rows = root, rows
        self.transform = build_transforms(training)

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        with Image.open(cache_path(self.root, row)) as opened:
            image = self.transform(opened.convert("RGB"))
        return image, int(row["target_index"])


def score(logits: np.ndarray, labels: np.ndarray) -> dict:
    probabilities = softmax(logits)
    result = classification_report(labels, probabilities, CLASS_NAMES)
    product_labels, product_probabilities = project_product_probabilities(
        labels, probabilities, CLASS_NAMES
    )
    product = classification_report(product_labels, product_probabilities, PRODUCT_CLASS_NAMES)
    result.update(samples=len(labels), product_accuracy=product["accuracy"],
                  product_macro_f1=product["macro_f1"])
    return result


def evaluate(model, loader, device) -> dict:
    model.eval()
    outputs, labels = [], []
    # FP32 matches the original inference contract; AMP is training-only.
    with torch.inference_mode():
        for images, targets in loader:
            outputs.append(model(images.to(device, non_blocking=True)).cpu().numpy())
            labels.append(targets.numpy())
    return score(np.concatenate(outputs), np.concatenate(labels))


def verify_parity(model, session, dataset, device, count=12) -> dict:
    errors, predictions = [], []
    model.eval()
    with torch.inference_mode():
        for index in np.linspace(0, len(dataset) - 1, count, dtype=int):
            sample, _ = dataset[int(index)]
            sample = sample.unsqueeze(0)
            expected = session.run(None, {session.get_inputs()[0].name: sample.numpy()})[0]
            actual = model(sample.to(device)).cpu().numpy()
            np.testing.assert_allclose(actual, expected, rtol=1e-4, atol=1e-4)
            predictions.append(bool(np.array_equal(actual.argmax(1), expected.argmax(1))))
            errors.append(float(abs(actual - expected).max()))
    if not all(predictions):
        raise ValueError("Original ONNX prediction mismatch")
    return {"samples": count, "max_logit_error": max(errors), "argmax_agreement": 1.0}


def run_experiment(args) -> dict:
    if args.epochs < 1 or args.epochs > 6 or args.patience < 1 or args.workers < 0 or args.batch_size < 1:
        raise ValueError("Invalid training bounds")
    if any(value < 0 or not np.isfinite(value) for value in args.sp_alphas):
        raise ValueError("L2-SP strengths must be finite and nonnegative")
    if any(not np.isfinite(value) or value <= 0 for value in (args.head_lr, args.full_lr)):
        raise ValueError("Learning rates must be finite and positive")
    if len(args.sp_alphas) != len(set(args.sp_alphas)):
        raise ValueError("Duplicate L2-SP arms")
    started = time.perf_counter()
    source, root = args.source_onnx.resolve(), args.output_dir.resolve()
    source_bytes = source.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    rows = {}
    fingerprints = {}
    for split in ("train", "val", "test"):
        path = args.manifests / f"{split}.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            rows[split] = list(csv.DictReader(handle))
        fingerprints[split] = hashlib.sha256(path.read_bytes()).hexdigest()
    audit = audit_splits(rows)
    if root.exists():
        raise FileExistsError("Choose a new output directory")
    root.mkdir(parents=True)
    arms = [
        {"name": "head_only", "scope": "head", "lr": args.head_lr, "alpha": 0.0},
        {"name": "full_plain", "scope": "all", "lr": args.full_lr, "alpha": 0.0},
        *[{"name": f"full_l2sp_{alpha:g}", "scope": "all",
           "lr": args.full_lr, "alpha": alpha} for alpha in args.sp_alphas],
    ]
    device = torch.device(args.device)
    torch.set_num_threads(2)
    # TF32 convolution is enabled by default and fails strict original-graph parity.
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cuda.matmul.allow_tf32 = False
    plan = {
        "source_sha256": source_sha, "manifest_sha256": fingerprints,
        "seed": args.seed, "epochs_max": args.epochs, "early_stop_patience": args.patience,
        "arms": arms, "batch_size": args.batch_size, "workers": args.workers,
        "roi_expansion": 1.1, "labels": list(CLASS_NAMES), "split_audit": audit,
        "loss": "sqrt inverse-frequency weighted CE with label smoothing 0.05",
        "l2_sp": "alpha * 0.5 * sum((trainable weights - original weights)^2)",
        "optimizer": "Adam, no ordinary weight decay",
        "evaluation": "FP32 with convolution/matmul TF32 disabled",
        "selection": "validation Macro-F1 increase AND accuracy >= original; no test selection",
        "paper": "https://proceedings.mlr.press/v80/li18a.html",
        "limitation": LIMITATION,
    }
    write_json(root / "plan.json", plan)
    cache_root = args.prepared_cache_dir.resolve() if args.prepared_cache_dir else root
    if args.prepared_cache_dir:
        verify_prepared_cache(cache_root, rows, fingerprints)
    else:
        prepare_cache(root, sum(rows.values(), []), max(1, min(6, args.workers or 1)))
    print("CACHE_READY", flush=True)
    eval_loaders = {
        split: DataLoader(CachedDataset(cache_root, records, False), batch_size=args.batch_size,
                          num_workers=args.workers, pin_memory=device.type == "cuda",
                          persistent_workers=args.workers > 0, worker_init_fn=_seed_worker)
        for split, records in rows.items() if split != "train"
    }
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    session = ort.InferenceSession(str(source), sess_options=options, providers=["CPUExecutionProvider"])
    original = OnnxBehaviorModel(source).to(device)
    parity = verify_parity(original, session, CachedDataset(cache_root, rows["train"], False), device)
    write_json(root / "original_parity.json", parity)
    baseline = evaluate(original, eval_loaders["val"], device)
    write_json(root / "original_validation.json", baseline)
    print("BASELINE", json.dumps({k: baseline[k] for k in ("accuracy", "macro_f1")}), flush=True)
    del original, session
    results = {}
    for arm in arms:
        seed_everything(args.seed)
        arm_root = root / arm["name"]
        arm_root.mkdir()
        model = OnnxBehaviorModel(source).to(device)
        trainability = configure_trainable(model, arm["scope"])
        reference = sp_reference(model) if arm["alpha"] else None
        train_loader = DataLoader(
            CachedDataset(cache_root, rows["train"], True), batch_size=args.batch_size,
            shuffle=True, generator=torch.Generator().manual_seed(args.seed),
            num_workers=args.workers, pin_memory=device.type == "cuda",
            persistent_workers=args.workers > 0, worker_init_fn=_seed_worker,
        )
        trainable = [p for p in model.parameters() if p.requires_grad]
        optimizer = torch.optim.Adam(trainable, lr=arm["lr"])
        scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
        criterion = torch.nn.CrossEntropyLoss(
            weight=_class_weights(rows["train"]).sqrt().to(device), label_smoothing=0.05
        )
        best, best_epoch, stale = None, 0, 0
        history = []
        arm_started = time.perf_counter()
        for epoch in range(1, args.epochs + 1):
            epoch_started = time.perf_counter()
            model.train()
            ce_sum, sp_sum, n = 0.0, 0.0, 0
            for images, targets in train_loader:
                images, targets = images.to(device, non_blocking=True), targets.to(device, non_blocking=True)
                optimizer.zero_grad(set_to_none=True)
                with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
                    ce = criterion(model(images), targets)
                penalty = l2_sp_penalty(model, reference) if reference is not None else ce.new_zeros(())
                loss = ce.float() + arm["alpha"] * penalty
                if not torch.isfinite(loss):
                    raise RuntimeError("Nonfinite loss")
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(trainable, 1.0)
                scaler.step(optimizer)
                scaler.update()
                ce_sum += float(ce.detach()) * len(targets)
                sp_sum += float(penalty.detach()) * len(targets)
                n += len(targets)
            validation = evaluate(model, eval_loaders["val"], device)
            row = {"epoch": epoch, "ce_batch_mean": ce_sum / n, "sp_batch_mean": sp_sum / n,
                   "seconds": time.perf_counter() - epoch_started, "validation": validation}
            history.append(row)
            write_json(arm_root / "history.json", history)
            print("EPOCH", json.dumps({"arm": arm["name"], "epoch": epoch,
                                      "accuracy": validation["accuracy"], "macro_f1": validation["macro_f1"],
                                      "seconds": row["seconds"]}), flush=True)
            rank = checkpoint_rank(validation, baseline)
            if best is None or rank > checkpoint_rank(best, baseline):
                best, best_epoch, stale = validation, epoch, 0
                torch.save({"model_state": {k: v.detach().cpu() for k, v in model.state_dict().items()},
                            "source_sha256": source_sha, "epoch": epoch, "arm": arm,
                            "trainability": trainability}, arm_root / "best.pt")
            else:
                stale += 1
            if stale >= args.patience:
                break
        results[arm["name"]] = {
            "config": arm, "best_epoch": best_epoch, "epochs_completed": len(history),
            "validation": best, "eligible": eligible(best, baseline),
            "trainability": trainability, "seconds": time.perf_counter() - arm_started,
        }
        write_json(arm_root / "result.json", results[arm["name"]])
        del train_loader, optimizer, model, reference
        if device.type == "cuda":
            torch.cuda.empty_cache()
    selected = select_arm({name: value["validation"] for name, value in results.items()}, baseline)
    # Persist the choice BEFORE evaluating test, even when all trained arms regress.
    write_json(root / "selection.json", {"selected": selected, "original_validation": baseline,
                                        "candidates": results, "criterion": plan["selection"]})
    original = OnnxBehaviorModel(source).to(device)
    test_original = evaluate(original, eval_loaders["test"], device)
    del original
    for arm in arms:
        checkpoint = torch.load(root / arm["name"] / "best.pt", map_location="cpu", weights_only=True)
        if checkpoint["source_sha256"] != source_sha:
            raise ValueError("Checkpoint source mismatch")
        model = OnnxBehaviorModel(source).to(device)
        model.load_state_dict(checkpoint["model_state"], strict=True)
        test = evaluate(model, eval_loaders["test"], device)
        results[arm["name"]]["test"] = test
        results[arm["name"]]["test_accuracy_delta_pp"] = 100 * (test["accuracy"] - test_original["accuracy"])
        results[arm["name"]]["test_macro_f1_delta_pp"] = 100 * (test["macro_f1"] - test_original["macro_f1"])
        if arm["name"] == selected:
            exported = root / "selected_candidate.onnx"
            model.export_onnx(exported)
            exported_session = ort.InferenceSession(str(exported), sess_options=options,
                                                    providers=["CPUExecutionProvider"])
            export_parity = verify_parity(model, exported_session,
                                          CachedDataset(cache_root, rows["train"], False), device)
            export_parity["sha256"] = hashlib.sha256(exported.read_bytes()).hexdigest()
            write_json(root / "export_parity.json", export_parity)
        del model
    if source.read_bytes() != source_bytes:
        raise RuntimeError("Original model changed")
    report = {"plan": plan, "original_validation": baseline, "original_test": test_original,
              "candidates": results, "selected_on_validation": selected,
              "exported_candidate": selected != "original", "assets_replaced": False,
              "elapsed_seconds": time.perf_counter() - started, "limitation": LIMITATION}
    write_json(root / "comparison.json", report)
    print("COMPLETE", json.dumps({"selected": selected, "original_test_accuracy": test_original["accuracy"],
                                 "seconds": report["elapsed_seconds"]}), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-onnx", type=Path, required=True)
    parser.add_argument("--manifests", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--prepared-cache-dir", type=Path,
                        help="Reuse a prior run's verified plan.json and completed ROI cache")
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--patience", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20261003)
    parser.add_argument("--head-lr", type=float, default=1e-5)
    parser.add_argument("--full-lr", type=float, default=2e-6)
    parser.add_argument("--sp-alphas", type=float, nargs="+", default=[100.0, 1000.0])
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    run_experiment(parser.parse_args())


if __name__ == "__main__":
    main()
