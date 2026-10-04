"""Validation-only selection of original/SAV weight and probability blends."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from torch.utils.data import DataLoader

from .l2sp_experiment import (CachedDataset, audit_splits, score, verify_parity,
                              verify_prepared_cache, write_json)
from .metrics import softmax
from .onnx_finetune import OnnxBehaviorModel
from .sav_data import build_sav_records
from .sav_replay_experiment import (SavDataset, set_report, validation_eligible,
                                    validation_rank, verify_replay_pixels)

# Declared before inspecting any new blend metrics; never refine from test.
ALPHAS = (0.0, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0)
LIMITATIONS = (
    "Both SCB and SAV tests were reported in the preceding experiment and are "
    "now exposed diagnostics. Blend parameters are selected from validation "
    "only; validation is also reused and has very few independent source videos. "
    "SAV scores cover positive READ/WRITE sets, not four-class accuracy or phone "
    "precision. Probability fusion requires two model forwards; parameter "
    "interpolation preserves the original graph and one forward. This is an "
    "offline comparison; production assets and thresholds are unchanged."
)


def check_alpha(alpha: float) -> None:
    if not np.isfinite(alpha) or not 0 <= alpha <= 1:
        raise ValueError("Blend weight must be finite and in [0,1]")


def blend_state(original: dict, adapted: dict, alpha: float) -> dict:
    """Interpolate matching fused weights; preserve exact endpoints and inputs."""
    check_alpha(alpha)
    if original.keys() != adapted.keys():
        raise ValueError("Blend state keys disagree")
    result = {}
    for key, base in original.items():
        candidate = adapted[key]
        if (base.shape != candidate.shape or base.dtype != candidate.dtype
                or not base.is_floating_point() or not torch.isfinite(base).all()
                or not torch.isfinite(candidate).all()):
            raise ValueError("Blend tensors must match and be finite floating point")
        result[key] = (base.clone() if alpha == 0 else candidate.clone() if alpha == 1
                       else torch.lerp(base, candidate, alpha))
    return result


def probability_blend_logits(original: np.ndarray, adapted: np.ndarray, alpha: float) -> np.ndarray:
    """Log of a convex probability mixture, compatible with existing scorers."""
    check_alpha(alpha)
    if (original.shape != adapted.shape or original.ndim != 2 or original.shape[1] != 4
            or not np.isfinite(original).all() or not np.isfinite(adapted).all()):
        raise ValueError("Expected matching finite four-class logits")
    if alpha == 0:
        return original.copy()
    if alpha == 1:
        return adapted.copy()
    probabilities = (1 - alpha) * softmax(original).astype(np.float64) + alpha * softmax(adapted)
    return np.log(np.maximum(probabilities, np.finfo(np.float64).tiny))


def choose_blend(candidates: dict, baseline: dict) -> str:
    eligible = [key for key, value in candidates.items()
                if value["alpha"] > 0 and validation_eligible(value["validation"], baseline)]
    if not eligible:
        return "original"
    # Equal validation quality prefers a single forward, then less adaptation.
    return max(eligible, key=lambda key: (
        validation_rank(candidates[key]["validation"], baseline),
        candidates[key]["method"] == "weights", -candidates[key]["alpha"],
    ))


def collect_logits(model, loader, device):
    outputs = []
    model.eval()
    with torch.inference_mode():
        for images, _ in loader:
            outputs.append(model(images.to(device, non_blocking=True)).cpu().numpy())
    result = np.concatenate(outputs)
    if not np.isfinite(result).all():
        raise ValueError("Nonfinite inference logits")
    return result


def verify_sav_provenance(rows: dict, prior: dict) -> dict:
    """Bind saved ROI labels/splits to the fingerprinted official annotations."""
    if any(not rows.get(split) for split in ("train", "val", "test")):
        raise ValueError("Missing prior SAV split rows")
    # Saved paths have the verified structure root/frames/clip/img_000031.jpg.
    first_image = Path(rows["train"][0]["image_path"])
    rebuilt, audit = build_sav_records(first_image.parents[2], prior["plan"]["split_dates"])
    saved_audit = prior["plan"]["sav_audit"]
    # Legacy runs can be reverified without training: exact rebuilt rows prove
    # that their saved masks agree with the now-fingerprinted official map.
    comparable_audit = audit if "label_provenance" in saved_audit else {
        key: value for key, value in audit.items() if key != "label_provenance"
    }
    if comparable_audit != saved_audit or rebuilt != rows:
        raise ValueError("Prior SAV rows or annotation fingerprints changed")
    return {"samples": sum(map(len, rows.values())),
            "label_provenance": audit["label_provenance"],
            "method": "exact rebuilt rows and original annotation SHA256 audit"}


def run(args):
    started = time.perf_counter()
    if args.workers < 0:
        raise ValueError("Workers must be nonnegative")
    source, root, previous = args.source_onnx.resolve(), args.output_dir.resolve(), args.sav_run.resolve()
    if root.exists():
        raise FileExistsError("Choose a new output directory")
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    prior = json.loads((previous / "comparison.json").read_text(encoding="utf-8"))
    checkpoint_path = previous / "replay_plus_sav" / "best.pt"
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    if (prior["plan"]["source_sha256"] != source_sha
            or checkpoint["source_sha256"] != source_sha
            or checkpoint["arm"] != "replay_plus_sav"
            or checkpoint["epoch"] != prior["candidates"]["replay_plus_sav"]["best_epoch"]):
        raise ValueError("Prior run/checkpoint source or epoch mismatch")
    old_rows, fingerprints, sav_rows = {}, {}, {}
    for split in ("train", "val", "test"):
        manifest = args.replay_manifests / f"{split}.csv"
        with manifest.open(encoding="utf-8-sig", newline="") as handle:
            old_rows[split] = list(csv.DictReader(handle))
        fingerprints[split] = hashlib.sha256(manifest.read_bytes()).hexdigest()
        sav_rows[split] = json.loads((previous / f"sav_{split}.json").read_text(encoding="utf-8"))
    if fingerprints != prior["plan"]["replay_manifest_sha256"]:
        raise ValueError("Replay manifests differ from preceding experiment")
    audit_splits(old_rows)
    verify_prepared_cache(args.replay_cache, old_rows, fingerprints)
    old_pixels = verify_replay_pixels(args.replay_cache, old_rows)
    sav_provenance = verify_sav_provenance(sav_rows, prior)
    sav_pixels = verify_replay_pixels(previous, sav_rows)
    root.mkdir(parents=True)
    plan = {"source_sha256": source_sha,
            "checkpoint_sha256": hashlib.sha256(checkpoint_path.read_bytes()).hexdigest(),
            "prior_comparison_sha256": hashlib.sha256((previous / "comparison.json").read_bytes()).hexdigest(),
            "replay_manifest_sha256": fingerprints,
            "sav_manifest_sha256": {s: hashlib.sha256((previous / f"sav_{s}.json").read_bytes()).hexdigest() for s in sav_rows},
            "alphas": list(ALPHAS), "methods": ["weights", "probabilities"],
            "selection": prior["plan"]["selection"], "old_pixels": old_pixels, "sav_pixels": sav_pixels,
            "sav_provenance": sav_provenance,
            "tie_break": "exact rank tie: one forward, then smaller alpha",
            "precision": "FP32, TF32 disabled", "labels": prior["plan"]["labels"],
            "test_status": "Both tests previously exposed; do not use for blend selection",
            "limitations": LIMITATIONS}
    write_json(root / "plan.json", plan)
    torch.set_num_threads(2)
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cuda.matmul.allow_tf32 = False
    device = torch.device(args.device)

    def loader(dataset):
        return DataLoader(dataset, batch_size=64, num_workers=args.workers,
                          pin_memory=device.type == "cuda", persistent_workers=args.workers > 0)

    # Test loaders and predictions are constructed after the choice is frozen.
    val_loaders = {"scb": loader(CachedDataset(args.replay_cache, old_rows["val"], False)),
                   "sav": loader(SavDataset(previous, sav_rows["val"], False))}

    def predict(model, loaders):
        return {key: collect_logits(model, value, device) for key, value in loaders.items()}

    def report(logits, split):
        labels = np.asarray([int(row["target_index"]) for row in old_rows[split]])
        return {"scb": score(logits["scb"], labels), "sav": set_report(logits["sav"], sav_rows[split])}

    original = OnnxBehaviorModel(source).to(device)
    original_state = {k: v.detach().cpu().clone() for k, v in original.state_dict().items()}
    adapted_state = checkpoint["model_state"]
    # Validate all shapes/finite weights even before collecting the endpoints.
    blend_state(original_state, adapted_state, 1)
    options = ort.SessionOptions(); options.intra_op_num_threads = 2
    session = ort.InferenceSession(str(source), sess_options=options, providers=["CPUExecutionProvider"])
    write_json(root / "original_parity.json", verify_parity(
        original, session, CachedDataset(args.replay_cache, old_rows["train"], False), device))
    val_original = predict(original, val_loaders)
    baseline = report(val_original, "val")
    if (baseline["scb"]["accuracy"] != prior["original_validation"]["scb"]["accuracy"]
            or baseline["scb"]["macro_f1"] != prior["original_validation"]["scb"]["macro_f1"]):
        raise ValueError("Original validation no longer matches preceding experiment")
    model = OnnxBehaviorModel(source).to(device)
    model.load_state_dict(adapted_state, strict=True)
    val_adapted = predict(model, val_loaders)
    candidates = {}
    for alpha in ALPHAS:
        endpoints = val_original if alpha == 0 else val_adapted if alpha == 1 else None
        for method in plan["methods"]:
            if endpoints is not None:
                logits = endpoints
            elif method == "probabilities":
                logits = {key: probability_blend_logits(val_original[key], val_adapted[key], alpha)
                          for key in val_original}
            else:
                model.load_state_dict(blend_state(original_state, adapted_state, alpha), strict=True)
                logits = predict(model, val_loaders)
            measured = report(logits, "val")
            key = f"{method}_{alpha:g}"
            candidates[key] = {"method": method, "alpha": alpha, "validation": measured,
                               "eligible": alpha > 0 and validation_eligible(measured, baseline)}
            print("BLEND", json.dumps({"key": key, "eligible": candidates[key]["eligible"],
                  "scb_accuracy": measured["scb"]["accuracy"], "scb_macro_f1": measured["scb"]["macro_f1"],
                  "sav_hit": measured["sav"]["acceptable_top1_rate"]}), flush=True)
        write_json(root / "validation_grid.json", candidates)
    selected = choose_blend(candidates, baseline)
    write_json(root / "selection.json", {"selected": selected, "baseline": baseline,
                                        "candidates": candidates, "criterion": plan["selection"]})
    test_loaders = {"scb": loader(CachedDataset(args.replay_cache, old_rows["test"], False)),
                    "sav": loader(SavDataset(previous, sav_rows["test"], False))}
    test_original = predict(original, test_loaders)
    model.load_state_dict(adapted_state, strict=True)
    test_adapted = predict(model, test_loaders)
    tests = {"original": report(test_original, "test"), "adapted": report(test_adapted, "test")}
    artifact = None
    if selected != "original":
        choice = candidates[selected]
        if choice["method"] == "weights":
            model.load_state_dict(blend_state(original_state, adapted_state, choice["alpha"]), strict=True)
            selected_logits = predict(model, test_loaders)
            output = root / "selected_weight_blend.onnx"
            model.export_onnx(output)
            exported = ort.InferenceSession(str(output), sess_options=options, providers=["CPUExecutionProvider"])
            write_json(root / "export_parity.json", verify_parity(
                model, exported, SavDataset(previous, sav_rows["train"], False), device))
            artifact = output.name
        else:
            selected_logits = {key: probability_blend_logits(test_original[key], test_adapted[key], choice["alpha"])
                               for key in test_original}
            artifact = "probability_blend_recipe.json"
            write_json(root / artifact, {"alpha": choice["alpha"], "source_sha256": source_sha,
                                        "checkpoint_sha256": plan["checkpoint_sha256"],
                                        "formula": "(1-alpha)*softmax(original_logits)+alpha*softmax(adapted_logits)",
                                        "labels": plan["labels"], "model_forwards": 2, "production_approved": False})
        tests["selected_blend"] = report(selected_logits, "test")
    else:
        tests["selected_blend"] = tests["original"]
    if hashlib.sha256(source.read_bytes()).hexdigest() != source_sha:
        raise RuntimeError("Production source model changed")
    comparison = {"plan": plan, "baseline_validation": baseline, "selected_on_validation": selected,
                  "selected_validation": baseline if selected == "original" else candidates[selected]["validation"],
                  "diagnostic_tests": tests, "candidate_artifact": artifact, "assets_replaced": False,
                  "elapsed_seconds": time.perf_counter() - started, "limitations": LIMITATIONS}
    write_json(root / "comparison.json", comparison)
    print("COMPLETE", json.dumps({"selected": selected, "seconds": comparison["elapsed_seconds"]}), flush=True)
    return comparison


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source-onnx", "sav-run", "replay-manifests", "replay-cache", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
