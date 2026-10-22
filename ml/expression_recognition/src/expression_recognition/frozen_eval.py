"""Frozen-checkpoint per-sample evaluation, candidate-data audit and paired error analysis.

This module never trains, tunes, adapts or calibrates a model. It re-runs already
locked checkpoints on an existing manifest, keeps per-sample probabilities, and
compares two frozen methods sample by sample so that corrected errors and newly
introduced errors are counted separately instead of being inferred from a net
Macro-F1 difference.

Scope limits that the tooling encodes rather than hides:

* Metrics always use the fixed seven-class label set, so a candidate set that
  lacks a class reports ``support == 0`` for it instead of silently shrinking the
  Macro-F1 denominator.
* Exact duplicate detection uses SHA-256 only. Near duplicates are reported as
  ``unresolved``; a clean hash check is not evidence of independence.
* The audit cannot establish which images a checkpoint was trained on, so
  ``independence_verified`` stays false unless the caller supplies explicit
  exposure evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import torch
from torch.utils.data import DataLoader

from .constants import CLASS_NAMES, CLASS_TO_INDEX, NUM_CLASSES
from .data import ManifestDataset, build_transforms
from .models import build_model
from .occlusion_ablation import (
    STRESS_BOX_HEIGHT,
    STRESS_BOX_WIDTH,
    build_protocol_config,
    occlude_batch,
    random_erasing_batch,
)
from .utils import save_json

VIEW_ORDER = ("clean", "standard", "severe", "random_erasing")
# Locked evaluation views of the existing occlusion experiments. The seeds are
# the ones used by the ten-epoch common-mask re-evaluation.
DEFAULT_VIEWS: dict[str, dict[str, Any]] = {
    "clean": {"kind": "clean"},
    "standard": {"kind": "structured", "geometry": "standard", "seed": 880001},
    "severe": {"kind": "structured", "geometry": "severe", "seed": 880002},
    "random_erasing": {"kind": "random_erasing", "seed": 880003},
}
PAIR_CELLS = ("both_correct", "candidate_only_correct", "reference_only_correct", "both_wrong")


# --------------------------------------------------------------------------- #
# Views and mask metadata
# --------------------------------------------------------------------------- #
def parse_view_seeds(items: Sequence[str] | None) -> dict[str, int]:
    """Parse ``name=seed`` overrides without touching the locked defaults."""
    seeds: dict[str, int] = {}
    for item in items or ():
        name, separator, value = item.partition("=")
        if not separator or not name.strip():
            raise ValueError(f"Expected name=seed, got {item!r}")
        if name not in DEFAULT_VIEWS or DEFAULT_VIEWS[name]["kind"] == "clean":
            raise ValueError(f"View {name!r} takes no mask seed")
        seeds[name] = int(value)
    return seeds


def resolve_views(names: Sequence[str] | None = None,
                  seeds: Mapping[str, int] | None = None) -> dict[str, dict[str, Any]]:
    """Return an ordered view spec, optionally restricted to a subset of names."""
    requested = tuple(names or VIEW_ORDER)
    unknown = [name for name in requested if name not in DEFAULT_VIEWS]
    if unknown:
        raise ValueError(f"Unknown view(s): {unknown}")
    if len(set(requested)) != len(requested):
        raise ValueError("Views must be requested once each")
    resolved: dict[str, dict[str, Any]] = {}
    for name in requested:
        spec = dict(DEFAULT_VIEWS[name])
        if seeds and name in seeds:
            spec["seed"] = int(seeds[name])
        resolved[name] = spec
    return resolved


def build_views(images: torch.Tensor, *, mean: list[float], std: list[float],
                views: Mapping[str, Mapping[str, Any]],
                first_index: int = 0) -> tuple[dict[str, torch.Tensor], dict[str, list[int] | None]]:
    """Build every requested view of a batch; the clean input is never mutated."""
    built: dict[str, torch.Tensor] = {}
    regions: dict[str, list[int] | None] = {}
    for name, spec in views.items():
        kind = spec["kind"]
        if kind == "clean":
            built[name] = images
            regions[name] = None
        elif kind == "structured":
            geometry = spec.get("geometry", "standard")
            if geometry == "severe":
                masked, ids = occlude_batch(
                    images, mean=mean, std=std, seed=int(spec["seed"]), first_index=first_index,
                    box_width_range=STRESS_BOX_WIDTH, box_height_range=STRESS_BOX_HEIGHT,
                )
            elif geometry == "standard":
                masked, ids = occlude_batch(
                    images, mean=mean, std=std, seed=int(spec["seed"]), first_index=first_index,
                )
            else:
                raise ValueError(f"Unknown occlusion geometry: {geometry!r}")
            built[name] = masked
            regions[name] = ids
        elif kind == "random_erasing":
            built[name] = random_erasing_batch(
                images, mean=mean, std=std, seed=int(spec["seed"]), first_index=first_index,
            )
            regions[name] = None
        else:
            raise ValueError(f"Unknown view kind: {kind!r}")
    return built, regions


def _bbox(mask: np.ndarray) -> list[int] | None:
    rows = np.flatnonzero(mask.any(axis=1))
    columns = np.flatnonzero(mask.any(axis=0))
    if rows.size == 0 or columns.size == 0:
        return None
    top, bottom = int(rows[0]), int(rows[-1])
    left, right = int(columns[0]), int(columns[-1])
    return [left, top, right - left + 1, bottom - top + 1]


def describe_views(views: Mapping[str, Mapping[str, Any]], *, channels: int, height: int,
                   width: int, count: int, mean: list[float], std: list[float],
                   chunk: int = 512) -> dict[str, dict[str, Any]]:
    """Measure the real mask geometry on a zero tensor.

    The mask depends only on ``(seed, sample index, tensor shape)``, never on
    pixel content, so measuring a zero tensor reproduces exactly the boxes that
    will be applied to real images. Area and position are therefore auditable
    without a second copy of the masking code.
    """
    if count <= 0:
        raise ValueError("count must be positive")
    records: dict[str, dict[str, Any]] = {
        name: {"area_fraction": [], "changed_pixels": [], "bbox": [], "region": []} for name in views
    }
    for start in range(0, count, chunk):
        size = min(chunk, count - start)
        zeros = torch.zeros(size, channels, height, width)
        built, regions = build_views(zeros, mean=mean, std=std, views=views, first_index=start)
        for name in views:
            masked = built[name]
            if views[name]["kind"] == "clean":
                for _ in range(size):
                    records[name]["area_fraction"].append(0.0)
                    records[name]["changed_pixels"].append(0)
                    records[name]["bbox"].append(None)
                    records[name]["region"].append(None)
                continue
            changed = (masked != zeros).any(dim=1).numpy()
            for index in range(size):
                mask = changed[index]
                pixels = int(mask.sum())
                records[name]["changed_pixels"].append(pixels)
                records[name]["area_fraction"].append(pixels / float(height * width))
                records[name]["bbox"].append(_bbox(mask))
                records[name]["region"].append(
                    int(regions[name][index]) if regions[name] is not None else None
                )
    summary: dict[str, dict[str, Any]] = {}
    for name, values in records.items():
        areas = np.asarray(values["area_fraction"], dtype=np.float64)
        summary[name] = {
            "kind": views[name]["kind"],
            "seed": views[name].get("seed"),
            "geometry": views[name].get("geometry"),
            "samples": int(areas.size),
            "area_fraction_mean": float(areas.mean()),
            "area_fraction_std": float(areas.std()),
            "area_fraction_min": float(areas.min()),
            "area_fraction_max": float(areas.max()),
            "area_fraction_p10": float(np.quantile(areas, 0.10)),
            "area_fraction_p50": float(np.quantile(areas, 0.50)),
            "area_fraction_p90": float(np.quantile(areas, 0.90)),
            "region_counts": (
                {str(region): int(sum(1 for value in values["region"] if value == region))
                 for region in sorted({v for v in values["region"] if v is not None})}
                if views[name]["kind"] == "structured" else {}
            ),
            "empty_masks": int(sum(1 for pixels in values["changed_pixels"] if pixels == 0)),
        }
    return {"views": summary, "per_sample": records}


# --------------------------------------------------------------------------- #
# Sample identity
# --------------------------------------------------------------------------- #
def stable_sample_ids(rows: Sequence[Mapping[str, str]]) -> list[str]:
    """Return the manifest SHA-256 as the sample identity, rejecting ambiguity.

    Row order alone is not an identity: two prediction files may be produced by
    different manifests or different split filters. The hash is content-derived,
    so a mismatch is detected instead of silently joining unrelated samples.
    """
    identifiers: list[str] = []
    for position, row in enumerate(rows):
        value = (row.get("sha256") or "").strip().lower()
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError(f"Row {position} has no usable sha256 sample id: {value!r}")
        identifiers.append(value)
    if len(set(identifiers)) != len(identifiers):
        duplicates = len(identifiers) - len(set(identifiers))
        raise ValueError(f"Sample ids are not unique: {duplicates} duplicate row(s)")
    return identifiers


def verify_alignment(reference_ids: Sequence[str], candidate_ids: Sequence[str]) -> None:
    """Raise when two prediction files do not describe the same samples in order."""
    if len(reference_ids) != len(candidate_ids):
        raise ValueError(
            f"Sample count mismatch: {len(reference_ids)} != {len(candidate_ids)}"
        )
    for index, (left, right) in enumerate(zip(reference_ids, candidate_ids)):
        if left != right:
            raise ValueError(f"Sample id mismatch at position {index}: {left} != {right}")


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def hash_image(path: Path) -> str:
    """Hash decoded pixel data so a re-encode of identical pixels still matches."""
    from PIL import Image

    with Image.open(path) as image:
        image.load()
        array = np.asarray(image.convert("L"), dtype=np.uint8)
    digest = hashlib.sha256()
    digest.update(f"{array.shape}".encode("ascii"))
    digest.update(array.tobytes())
    return digest.hexdigest()


# --------------------------------------------------------------------------- #
# Candidate-data audit
# --------------------------------------------------------------------------- #
def _resolve_label(raw: str, label_map: Mapping[str, int] | None) -> int | None:
    value = (raw or "").strip()
    if not value:
        return None
    lowered = value.lower()
    if lowered in CLASS_TO_INDEX:
        return CLASS_TO_INDEX[lowered]
    if label_map is not None and value in label_map:
        return int(label_map[value])
    return None


def audit_candidate_manifest(
    manifest: Path,
    *,
    reference_manifest: Path | None = None,
    split: str | None = None,
    label_map: Mapping[str, int] | None = None,
    hash_images: bool = False,
    max_hash: int | None = None,
    authorization_record: Path | None = None,
    exposure_evidence: Path | None = None,
) -> dict[str, Any]:
    """Audit whether a candidate manifest can support a frozen external evaluation.

    The audit is deliberately conservative: it reports what can be verified from
    files and marks everything else as unresolved instead of inferring
    independence from a directory name or a dataset title.
    """
    manifest = Path(manifest)
    if not manifest.is_file():
        raise FileNotFoundError(manifest)
    with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"Manifest is empty: {manifest}")

    path_column = "source_path" if "source_path" in rows[0] else "path"
    label_column = "label" if "label" in rows[0] else "raw_label"
    if path_column not in rows[0] or label_column not in rows[0]:
        raise ValueError("Manifest needs a path/source_path column and a label/raw_label column")

    selected = [
        row for row in rows
        if (row.get("status", "included") or "included") == "included"
        and (split is None or (row.get("split") or split) == split)
    ]
    excluded_status = len(rows) - len(selected)

    unresolved: list[str] = []
    missing_files: list[str] = []
    resolved_rows: list[dict[str, Any]] = []
    for row in selected:
        raw_label = row.get(label_column, "")
        index = _resolve_label(raw_label, label_map)
        if index is None:
            unresolved.append(raw_label)
            continue
        raw_path = (row.get(path_column) or "").strip()
        resolved_rows.append({
            "raw_path": raw_path,
            "path": Path(raw_path),
            "label_index": index,
            "raw_label": raw_label,
            "sha256": (row.get("sha256") or "").strip().lower(),
        })

    for entry in resolved_rows:
        if not entry["path"].is_file():
            missing_files.append(entry["raw_path"])

    usable = [entry for entry in resolved_rows if entry["path"].is_file()]

    hash_source = "not_computed"
    hashes: list[str] = []
    if usable and usable[0]["sha256"]:
        hash_source = "manifest_sha256_column"
        hashes = [entry["sha256"] for entry in usable if entry["sha256"]]
    elif usable and hash_images:
        hash_source = "decoded_pixels"
        limit = len(usable) if max_hash is None else min(max_hash, len(usable))
        hashes = [hash_image(entry["path"]) for entry in usable[:limit]]
    hashed_count = len(hashes)

    duplicate_hashes = len(hashes) - len(set(hashes)) if hashes else 0

    reference_hashes: set[str] = set()
    reference_count = 0
    if reference_manifest is not None and Path(reference_manifest).is_file():
        with Path(reference_manifest).open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                value = (row.get("sha256") or "").strip().lower()
                if value:
                    reference_hashes.add(value)
        reference_count = len(reference_hashes)
    cross_overlap = len(set(hashes) & reference_hashes) if hashes and reference_hashes else None

    support = {name: 0 for name in CLASS_NAMES}
    for entry in usable:
        support[CLASS_NAMES[entry["label_index"]]] += 1
    present = [name for name, count in support.items() if count > 0]
    absent = [name for name, count in support.items() if count == 0]

    group_columns = [name for name in ("subject_id", "session_id", "video_id", "movie_id")
                     if name in rows[0]]

    authorization = None
    if authorization_record is not None:
        record = Path(authorization_record)
        authorization = {
            "path": str(record),
            "exists": record.is_file(),
            "sha256": hash_file(record) if record.is_file() else None,
        }

    exposure = None
    if exposure_evidence is not None:
        evidence = Path(exposure_evidence)
        exposure = {
            "path": str(evidence),
            "exists": evidence.is_file(),
            "sha256": hash_file(evidence) if evidence.is_file() else None,
        }

    reasons: list[str] = []
    if not usable:
        reasons.append("no usable sample: every candidate row is unresolved or missing")
    if unresolved:
        reasons.append(f"{len(unresolved)} row(s) have labels outside the seven-class mapping")
    if missing_files:
        reasons.append(f"{len(missing_files)} declared file(s) are absent on disk")
    if cross_overlap:
        reasons.append(f"{cross_overlap} exact duplicate(s) already exist in the reference manifest")
    if absent:
        reasons.append(f"classes without support: {absent}")
    if not group_columns:
        reasons.append("no subject/session identifier, so person-independent generalisation cannot be claimed")
    if hashes and reference_hashes and cross_overlap == 0:
        reasons.append("near duplicates are not detectable by hash; the check is unresolved, not passed")
    if authorization is None or not authorization["exists"]:
        reasons.append("no authorisation record supplied")
    if exposure is None or not exposure["exists"]:
        reasons.append("training exposure of the starting checkpoint cannot be established from local files")

    return {
        "manifest": str(manifest),
        "manifest_sha256": hash_file(manifest),
        "split_filter": split,
        "rows_total": len(rows),
        "rows_selected": len(selected),
        "rows_excluded_by_status": excluded_status,
        "rows_unresolved_label": len(unresolved),
        "unresolved_label_values": sorted({value for value in unresolved})[:20],
        "rows_missing_file": len(missing_files),
        "rows_usable": len(usable),
        "label_map_supplied": dict(label_map) if label_map else None,
        "class_support": support,
        "classes_present": present,
        "classes_absent": absent,
        "group_columns": group_columns,
        "hash_source": hash_source,
        "hashed_rows": hashed_count,
        "duplicate_hashes_within_candidate": duplicate_hashes,
        "reference_manifest": str(reference_manifest) if reference_manifest else None,
        "reference_unique_hashes": reference_count,
        "exact_duplicates_with_reference": cross_overlap,
        "authorization_record": authorization,
        "exposure_evidence": exposure,
        "usable_for_frozen_eval": bool(usable) and not missing_files and not unresolved,
        "independence_verified": False,
        "independence_reasons": reasons,
        "verdict": (
            "eligible for a frozen diagnostic evaluation; independence is NOT verified"
            if usable and not missing_files and not unresolved and not cross_overlap
            else "not eligible for an external evaluation claim"
        ),
    }


# --------------------------------------------------------------------------- #
# Frozen inference
# --------------------------------------------------------------------------- #
def collect_environment(device: torch.device, *, batch_size: int, dtype: str) -> dict[str, Any]:
    import torchvision

    info: dict[str, Any] = {
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "torch": torch.__version__,
        "torchvision": torchvision.__version__,
        "cuda_available": torch.cuda.is_available(),
        "torch_cuda": torch.version.cuda,
        "cudnn_version": torch.backends.cudnn.version(),
        "cudnn_enabled": torch.backends.cudnn.enabled,
        "cudnn_benchmark": torch.backends.cudnn.benchmark,
        "cudnn_deterministic": torch.backends.cudnn.deterministic,
        "tf32_matmul": torch.backends.cuda.matmul.allow_tf32,
        "tf32_cudnn": torch.backends.cudnn.allow_tf32,
        "device": str(device),
        "dtype": dtype,
        "batch_size": batch_size,
    }
    if torch.cuda.is_available():
        properties = torch.cuda.get_device_properties(0)
        info["gpu"] = {
            "name": properties.name,
            "total_memory_gb": round(properties.total_memory / 1024 ** 3, 2),
            "compute_capability": f"{properties.major}.{properties.minor}",
            "device_count": torch.cuda.device_count(),
        }
    return info


def _same_device(tensor_device: torch.device, device: torch.device) -> bool:
    """Compare devices without treating ``cuda`` and ``cuda:0`` as different."""
    if tensor_device.type != device.type:
        return False
    return device.index is None or tensor_device.index == device.index


def assert_on_device(model: torch.nn.Module, tensor: torch.Tensor, device: torch.device) -> dict[str, Any]:
    tensors = list(model.parameters()) + list(model.buffers())
    if not tensors:
        raise ValueError("Model exposes no parameters or buffers to place")
    parameter_devices = {str(value.device) for value in tensors}
    return {
        "parameter_devices": sorted(parameter_devices),
        "input_device": str(tensor.device),
        "all_parameters_on_device": all(_same_device(value.device, device) for value in tensors),
        "input_on_device": _same_device(tensor.device, device),
        "parameter_dtype": str(tensors[0].dtype),
        "input_dtype": str(tensor.dtype),
    }


@torch.inference_mode()
def evaluate_views(
    model: torch.nn.Module,
    loader: DataLoader,
    device: torch.device,
    config: dict[str, Any],
    views: Mapping[str, Mapping[str, Any]],
    *,
    expected_ids: Sequence[str] | None = None,
    verify_regions: Mapping[str, Sequence[int]] | None = None,
) -> dict[str, Any]:
    """Run every view over the whole split and return per-sample outputs."""
    model.eval()
    mean = config["normalization"]["mean"]
    std = config["normalization"]["std"]
    names = list(views)
    total = len(loader.dataset)
    probabilities = {name: np.zeros((total, NUM_CLASSES), dtype=np.float32) for name in names}
    logits_store = {name: np.zeros((total, NUM_CLASSES), dtype=np.float32) for name in names}
    predictions = {name: np.zeros(total, dtype=np.int16) for name in names}
    targets = np.zeros(total, dtype=np.int16)
    region_store: dict[str, np.ndarray] = {
        name: np.full(total, -1, dtype=np.int8) for name in names
    }

    offset = 0
    for clean, labels in loader:
        batch_views, regions = build_views(
            clean, mean=mean, std=std, views=views, first_index=offset,
        )
        size = int(labels.shape[0])
        if offset + size > total:
            raise ValueError("Loader yielded more samples than the dataset length")
        for name in names:
            tensor = batch_views[name].to(device, non_blocking=True)
            output = model(tensor).float()
            if output.shape != (size, NUM_CLASSES):
                raise ValueError(f"Unexpected logit shape {tuple(output.shape)} for view {name}")
            # One host transfer per view: every extra device-side reduction would
            # force its own synchronisation and slow the pass down for no gain.
            combined = torch.cat((output, torch.softmax(output, dim=1)), dim=1).cpu().numpy()
            logits_store[name][offset:offset + size] = combined[:, :NUM_CLASSES]
            probabilities[name][offset:offset + size] = combined[:, NUM_CLASSES:]
            predictions[name][offset:offset + size] = (
                combined[:, :NUM_CLASSES].argmax(axis=1).astype(np.int16)
            )
            ids = regions.get(name)
            if ids is not None:
                region_store[name][offset:offset + size] = np.asarray(ids, dtype=np.int8)
        targets[offset:offset + size] = labels.numpy().astype(np.int16)
        offset += size

    if offset != total:
        raise ValueError(f"Evaluated {offset} samples but the dataset declares {total}")
    for name in names:
        block = probabilities[name]
        if block.shape != (total, NUM_CLASSES) or not np.isfinite(block).all():
            raise ValueError(f"Invalid probability block for view {name}")
        if not np.isfinite(logits_store[name]).all():
            raise ValueError(f"Non-finite logits for view {name}")
        if not np.allclose(block.sum(axis=1), 1.0, atol=1e-5):
            raise ValueError(f"Probabilities for view {name} do not sum to one")
        if region_store[name].max() > 2:
            raise ValueError(f"Unexpected region id for view {name}")

    dataset_rows = getattr(loader.dataset, "rows", None)
    identifiers = stable_sample_ids(dataset_rows) if dataset_rows is not None else []
    if expected_ids is not None:
        verify_alignment(expected_ids, identifiers)
    if verify_regions is not None:
        for name, reference in verify_regions.items():
            actual = region_store[name][region_store[name] >= 0]
            reference_array = np.asarray(reference, dtype=np.int8)
            reference_array = reference_array[reference_array >= 0]
            # Mask ids are index-based, so a shorter run must reproduce the prefix
            # of the recorded masks; sample identity is checked separately above.
            if reference_array.size < actual.size or not np.array_equal(
                actual, reference_array[:actual.size]
            ):
                raise ValueError(f"Mask region ids changed for view {name}")

    return {
        "sample_ids": identifiers,
        "targets": targets,
        "probabilities": probabilities,
        "logits": logits_store,
        "predictions": predictions,
        "regions": region_store,
    }


def metrics_from_predictions(predictions: Mapping[str, np.ndarray],
                             targets: np.ndarray) -> dict[str, dict[str, Any]]:
    """Reuse the existing seven-class metric payload so old and new values match."""
    from .occlusion_ablation import _view_metrics

    target_list = targets.tolist()
    return {
        name: _view_metrics(values.tolist(), target_list) for name, values in predictions.items()
    }


def save_predictions(path: Path, result: Mapping[str, Any], views: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "view_order": np.asarray(list(views)),
        "sample_ids": np.asarray(result["sample_ids"]),
        "targets": result["targets"],
    }
    for name in views:
        payload[f"probs__{name}"] = result["probabilities"][name]
        payload[f"logits__{name}"] = result["logits"][name]
        payload[f"pred__{name}"] = result["predictions"][name]
        payload[f"region__{name}"] = result["regions"][name]
    np.savez_compressed(path, **payload)


def load_predictions(path: Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as archive:
        views = [str(name) for name in archive["view_order"].tolist()]
        loaded = {
            "views": views,
            "sample_ids": [str(value) for value in archive["sample_ids"].tolist()],
            "targets": archive["targets"],
            "probabilities": {name: archive[f"probs__{name}"] for name in views},
            "logits": {name: archive[f"logits__{name}"] for name in views},
            "predictions": {name: archive[f"pred__{name}"] for name in views},
            "regions": {name: archive[f"region__{name}"] for name in views},
        }
    return loaded


# --------------------------------------------------------------------------- #
# Paired error analysis
# --------------------------------------------------------------------------- #
def paired_counts(
    reference: np.ndarray,
    candidate: np.ndarray,
    targets: np.ndarray,
    *,
    name: str = "",
) -> dict[str, Any]:
    """Count the four paired outcomes for ``candidate`` versus ``reference``.

    ``candidate_only_correct`` are errors the candidate fixed;
    ``reference_only_correct`` are errors the candidate introduced. Their
    difference explains the accuracy delta only; it does not decompose Macro-F1.
    """
    reference = np.asarray(reference).astype(np.int64)
    candidate = np.asarray(candidate).astype(np.int64)
    targets = np.asarray(targets).astype(np.int64)
    if not (reference.shape == candidate.shape == targets.shape):
        raise ValueError(
            f"Shape mismatch: reference {reference.shape}, candidate {candidate.shape}, "
            f"targets {targets.shape}"
        )
    if reference.size == 0:
        raise ValueError("Paired analysis needs at least one sample")
    reference_correct = reference == targets
    candidate_correct = candidate == targets
    counts = {
        "both_correct": int((reference_correct & candidate_correct).sum()),
        "candidate_only_correct": int((candidate_correct & ~reference_correct).sum()),
        "reference_only_correct": int((~candidate_correct & reference_correct).sum()),
        "both_wrong": int((~reference_correct & ~candidate_correct).sum()),
    }
    total = int(targets.size)
    counts["samples"] = total
    counts["candidate_accuracy"] = float(candidate_correct.mean())
    counts["reference_accuracy"] = float(reference_correct.mean())
    counts["net_gain"] = counts["candidate_only_correct"] - counts["reference_only_correct"]
    counts["accuracy_delta"] = counts["net_gain"] / total
    counts["accuracy_delta_check"] = counts["candidate_accuracy"] - counts["reference_accuracy"]
    if abs(counts["accuracy_delta"] - counts["accuracy_delta_check"]) > 1e-12:
        raise AssertionError("Paired counts do not reproduce the accuracy difference")
    if sum(counts[cell] for cell in PAIR_CELLS) != total:
        raise AssertionError("Paired cells do not add up to the sample count")
    per_class: dict[str, Any] = {}
    for index, label in enumerate(CLASS_NAMES):
        selected = targets == index
        support = int(selected.sum())
        if support == 0:
            per_class[label] = {"support": 0, "defined": False}
            continue
        subset_reference = reference_correct[selected]
        subset_candidate = candidate_correct[selected]
        per_class[label] = {
            "support": support,
            "defined": True,
            "both_correct": int((subset_reference & subset_candidate).sum()),
            "candidate_only_correct": int((subset_candidate & ~subset_reference).sum()),
            "reference_only_correct": int((~subset_candidate & subset_reference).sum()),
            "both_wrong": int((~subset_reference & ~subset_candidate).sum()),
            "candidate_accuracy": float(subset_candidate.mean()),
            "reference_accuracy": float(subset_reference.mean()),
            "net_gain": int((subset_candidate & ~subset_reference).sum())
            - int((~subset_candidate & subset_reference).sum()),
        }
    counts["per_class"] = per_class
    if name:
        counts["comparison"] = name
    return counts


def example_pairs(
    reference: np.ndarray,
    candidate: np.ndarray,
    targets: np.ndarray,
    sample_ids: Sequence[str],
    *,
    limit: int = 5,
) -> dict[str, list[dict[str, Any]]]:
    """List corrected and introduced samples using a fixed identifier order."""
    reference = np.asarray(reference).astype(np.int64)
    candidate = np.asarray(candidate).astype(np.int64)
    targets = np.asarray(targets).astype(np.int64)
    order = sorted(range(len(sample_ids)), key=lambda index: sample_ids[index])

    def build(indices: Iterable[int]) -> list[dict[str, Any]]:
        return [
            {
                "sample_id": sample_ids[index],
                "true": CLASS_NAMES[int(targets[index])],
                "reference_prediction": CLASS_NAMES[int(reference[index])],
                "candidate_prediction": CLASS_NAMES[int(candidate[index])],
            }
            for index in indices
        ]

    corrected = [index for index in order if candidate[index] == targets[index] != reference[index]]
    introduced = [index for index in order if reference[index] == targets[index] != candidate[index]]
    return {
        "corrected": build(corrected[:limit]),
        "introduced": build(introduced[:limit]),
    }


def summarize_seeds(per_seed: Mapping[str, Mapping[str, Any]], cells: Sequence[str]) -> dict[str, Any]:
    """Mean, sample standard deviation and sign counts across training seeds."""
    seeds = sorted(per_seed)
    if not seeds:
        raise ValueError("No seed to summarise")
    summary: dict[str, Any] = {"seeds": seeds, "cells": {}}
    for cell in cells:
        values = [float(per_seed[seed][cell]) for seed in seeds]
        array = np.asarray(values, dtype=np.float64)
        summary["cells"][cell] = {
            "values": values,
            "mean": float(array.mean()),
            "sample_std": float(array.std(ddof=1)) if array.size > 1 else 0.0,
            "positive": int((array > 0).sum()),
            "negative": int((array < 0).sum()),
            "zero": int((array == 0).sum()),
        }
    return summary


# --------------------------------------------------------------------------- #
# Reconciliation against a previous evaluation
# --------------------------------------------------------------------------- #
def compare_metrics(current: Mapping[str, Any], reference: Mapping[str, Any],
                    *, tolerance: float = 1e-6,
                    keys: Sequence[str] | None = None) -> dict[str, Any]:
    """Compare re-computed metrics with a previous run at a fixed tolerance.

    ``keys`` restricts the comparison to the checkpoints that were actually
    re-collected. Reference entries outside that scope are reported as
    ``not_compared`` instead of being counted as failures.
    """
    rows: list[dict[str, Any]] = []
    worst = 0.0
    failures = 0
    missing: list[str] = []
    current_checkpoints = current.get("checkpoints", {})
    reference_checkpoints = reference.get("checkpoints", {})
    selected = list(keys) if keys is not None else list(reference_checkpoints)
    not_compared = [key for key in reference_checkpoints if key not in selected]
    for key in selected:
        entry = reference_checkpoints.get(key)
        if entry is None:
            missing.append(key)
            continue
        if key not in current_checkpoints:
            missing.append(key)
            continue
        for view, old in entry.get("metrics", {}).items():
            new = current_checkpoints[key].get("metrics", {}).get(view)
            if new is None:
                missing.append(f"{key}|{view}")
                continue
            for metric in ("accuracy", "macro_f1", "balanced_accuracy"):
                difference = abs(float(new[metric]) - float(old[metric]))
                worst = max(worst, difference)
                rows.append({
                    "checkpoint": key, "view": view, "metric": metric,
                    "reference": float(old[metric]), "current": float(new[metric]),
                    "abs_diff": difference,
                })
            if int(new["samples"]) != int(old["samples"]):
                failures += 1
                rows.append({
                    "checkpoint": key, "view": view, "metric": "samples",
                    "reference": old["samples"], "current": new["samples"],
                    "abs_diff": None, "mismatch": "sample count",
                })
            if new["confusion_matrix"] != old["confusion_matrix"]:
                failures += 1
                rows.append({
                    "checkpoint": key, "view": view, "metric": "confusion_matrix",
                    "reference": "archived", "current": "recomputed",
                    "abs_diff": None, "mismatch": "confusion matrix differs",
                })
    exceeded = [row for row in rows if row["abs_diff"] is not None and row["abs_diff"] > tolerance]
    return {
        "tolerance": tolerance,
        "checkpoints_compared": len(selected) - len(missing),
        "checkpoints_not_compared": not_compared,
        "missing_entries": missing,
        "metric_rows": len(rows),
        "max_abs_diff": worst,
        "rows_exceeding_tolerance": len(exceeded),
        "mismatches": failures,
        "passed": not exceeded and not failures and not missing,
        "examples_exceeding": exceeded[:10],
    }


# --------------------------------------------------------------------------- #
# GPU smoke
# --------------------------------------------------------------------------- #
@torch.inference_mode()
def synthetic_smoke(model: torch.nn.Module, device: torch.device, config: dict[str, Any],
                    views: Mapping[str, Mapping[str, Any]], *, batch_size: int,
                    repeats: int = 10, warmup: int = 3) -> dict[str, Any]:
    """Verify device placement, shapes and timing on synthetic input only.

    Recognition accuracy on synthetic noise is meaningless and is never used to
    choose a method. End-to-end time is reported next to CUDA kernel time; both
    are measured after warmup with explicit synchronisation and say nothing
    about phone energy.
    """
    model.eval()
    mean = config["normalization"]["mean"]
    std = config["normalization"]["std"]
    channels = int(config["input_channels"])
    size = int(config["input_size"])
    generator = torch.Generator().manual_seed(20261022)
    images = torch.rand(batch_size, channels, size, size, generator=generator)
    images = (images - 0.5) / 0.25

    placement = assert_on_device(model, images.to(device), device)
    built, _ = build_views(images, mean=mean, std=std, views=views, first_index=0)
    view_shapes = {name: list(tensor.shape) for name, tensor in built.items()}

    def forward_once(name: str) -> torch.Tensor:
        return model(built[name].to(device, non_blocking=True)).float()

    for _ in range(warmup):
        for name in views:
            forward_once(name)
    if device.type == "cuda":
        torch.cuda.synchronize()

    kernel_ms: dict[str, list[float]] = {name: [] for name in views}
    end_to_end: list[float] = []
    for _ in range(repeats):
        start_event = torch.cuda.Event(enable_timing=True) if device.type == "cuda" else None
        end_event = torch.cuda.Event(enable_timing=True) if device.type == "cuda" else None
        wall_start = time.perf_counter()
        for name in views:
            if start_event is not None:
                start_event.record()
            output = forward_once(name)
            if end_event is not None:
                end_event.record()
                end_event.synchronize()
                kernel_ms[name].append(start_event.elapsed_time(end_event))
        if device.type == "cuda":
            torch.cuda.synchronize()
        end_to_end.append(time.perf_counter() - wall_start)

    # Correctness checks run once, outside the timed loop: device-side reductions
    # each force a synchronisation and would otherwise dominate the measurement.
    checks: dict[str, dict[str, Any]] = {}
    for name in views:
        output = forward_once(name)
        probabilities = torch.softmax(output, dim=1)
        checks[name] = {
            "logit_shape": list(output.shape),
            "logits_finite": bool(torch.isfinite(output).all().item()),
            "probabilities_sum_to_one": bool(
                torch.allclose(
                    probabilities.sum(dim=1),
                    torch.ones(output.shape[0], device=output.device),
                    atol=1e-5,
                )
            ),
        }

    peak_memory = float(torch.cuda.max_memory_allocated() / 1024 ** 3) if device.type == "cuda" else None
    return {
        "synthetic_input": {
            "batch_size": batch_size,
            "shape": [batch_size, channels, size, size],
            "note": "uniform noise; recognition accuracy is meaningless and not reported",
        },
        "placement": placement,
        "view_shapes": view_shapes,
        "checks": checks,
        "views_per_iteration": len(views),
        "repeats": repeats,
        "warmup": warmup,
        "end_to_end_ms_per_iteration_mean": float(np.mean(end_to_end) * 1000),
        "end_to_end_ms_per_view_mean": float(np.mean(end_to_end) * 1000 / len(views)),
        "kernel_ms_per_view_mean": (
            {name: float(np.mean(values)) for name, values in kernel_ms.items()}
            if device.type == "cuda" else None
        ),
        "kernel_ms_per_view_std": (
            {name: float(np.std(values)) for name, values in kernel_ms.items()}
            if device.type == "cuda" else None
        ),
        "peak_memory_gb": peak_memory,
        "timing_note": (
            "End-to-end includes host-to-device copies and Python overhead; kernel time is "
            "CUDA-event time around the forward pass only. Neither measures phone latency or energy."
        ),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _checkpoint_path(root: Path, seed: int, arm: str, filename: str) -> Path:
    return root / f"seed_{seed}" / arm / filename


def run_masks(args: argparse.Namespace) -> dict[str, Any]:
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    config = build_protocol_config(
        checkpoint["config"], seed=int(args.seed), batch_size=args.batch_size,
        num_workers=0, temperature=2.0, teacher_weight=0.5,
        lambda_clean=0.5, lambda_masked=0.5,
    )
    views = resolve_views(args.views, parse_view_seeds(args.view_seeds))
    description = describe_views(
        views, channels=int(config["input_channels"]), height=int(config["input_size"]),
        width=int(config["input_size"]), count=args.count,
        mean=config["normalization"]["mean"], std=config["normalization"]["std"],
    )
    payload = {
        "views": views,
        "count": args.count,
        "input_size": int(config["input_size"]),
        "input_channels": int(config["input_channels"]),
        "summary": description["views"],
        "per_sample": description["per_sample"],
    }
    save_json(Path(args.output_dir) / "view_masks.json", payload)
    np.savez_compressed(
        Path(args.output_dir) / "view_masks.npz",
        **{
            f"{name}__area": np.asarray(values["area_fraction"], dtype=np.float32)
            for name, values in description["per_sample"].items()
        },
        **{
            f"{name}__region": np.asarray(
                [-1 if value is None else value for value in values["region"]], dtype=np.int8
            )
            for name, values in description["per_sample"].items()
        },
    )
    return payload["summary"]


def run_evaluate(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir)
    # The directory may already hold the protocol lock, mask audit and smoke
    # report; only a previous collection must never be overwritten.
    if (output_dir / "metrics.json").exists() and not args.overwrite:
        raise FileExistsError(f"A collection already exists in: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    config = build_protocol_config(
        checkpoint["config"], seed=int(args.seeds[0]), batch_size=args.batch_size,
        num_workers=args.num_workers, temperature=2.0, teacher_weight=0.5,
        lambda_clean=0.5, lambda_masked=0.5,
    )
    if config["model"] != "resnet18" or int(config["input_channels"]) != 3:
        raise ValueError("This evaluation requires the existing three-channel ResNet18 contract")
    views = resolve_views(args.views, parse_view_seeds(args.view_seeds))

    device = torch.device("cpu" if args.cpu else ("cuda" if torch.cuda.is_available() else "cpu"))
    dataset = ManifestDataset(args.manifest, args.split, build_transforms(config, training=False))
    loader = DataLoader(
        dataset, batch_size=args.batch_size, shuffle=False,
        num_workers=args.num_workers, persistent_workers=args.num_workers > 0,
        pin_memory=device.type == "cuda",
    )
    identifiers = stable_sample_ids(dataset.rows)

    environment = collect_environment(device, batch_size=args.batch_size, dtype="float32")
    environment["manifest"] = str(args.manifest)
    environment["manifest_sha256"] = hash_file(Path(args.manifest))
    environment["split"] = args.split
    environment["samples"] = len(dataset)
    environment["views"] = views
    save_json(output_dir / "environment.json", environment)

    expected_regions: dict[str, list[int]] = {}
    mask_file = Path(args.mask_file) if args.mask_file else None
    if mask_file is not None and mask_file.is_file():
        with np.load(mask_file, allow_pickle=False) as archive:
            for name in views:
                key = f"{name}__region"
                if key in archive:
                    expected_regions[name] = archive[key].tolist()

    results: dict[str, Any] = {
        "mask_seeds": {name: spec.get("seed") for name, spec in views.items()},
        "eval_batch_size": args.batch_size,
        "validation_samples": len(dataset),
        "device": str(device),
        "dtype": "float32",
        "checkpoints": {},
        "timings": {},
    }
    arms = {
        "B_plain": Path(args.baseline_root),
        "R_random_erasing": Path(args.baseline_root),
        "C_hard_occlusion": Path(args.duration_root),
        "D_clean_anchor": Path(args.duration_root),
    }
    requested = tuple(args.arms or arms)
    unknown = [name for name in requested if name not in arms]
    if unknown:
        raise ValueError(f"Unknown arm(s): {unknown}")
    predictions_dir = output_dir / "predictions"
    predictions_dir.mkdir(exist_ok=True)

    for seed in args.seeds:
        for arm in requested:
            path = _checkpoint_path(arms[arm], int(seed), arm, args.checkpoint_name)
            if not path.is_file():
                raise FileNotFoundError(path)
            state = torch.load(path, map_location="cpu", weights_only=False)
            model = build_model(config, allow_download=False).to(device)
            model.load_state_dict(state["model_state"])
            model.eval()

            if device.type == "cuda":
                torch.cuda.synchronize()
            started = time.perf_counter()
            result = evaluate_views(
                model, loader, device, config, views,
                expected_ids=identifiers, verify_regions=expected_regions or None,
            )
            if device.type == "cuda":
                torch.cuda.synchronize()
            elapsed = time.perf_counter() - started

            save_predictions(predictions_dir / f"seed_{seed}_{arm}.npz", result, list(views))
            metrics = metrics_from_predictions(result["predictions"], result["targets"])
            key = f"final|{arm}|{seed}"
            results["checkpoints"][key] = {
                "arm": arm,
                "seed": int(seed),
                "role": "final",
                "epoch": int(state.get("epoch", -1)),
                "selection_score": float(state.get("selection_score", float("nan"))),
                "checkpoint_sha256": hash_file(path),
                "source": str(path),
                "metrics": metrics,
            }
            results["timings"][key] = {
                "seconds": elapsed,
                "samples": len(dataset),
                "views": len(views),
                "views_per_second": len(dataset) * len(views) / elapsed if elapsed else None,
            }
            print(json.dumps({
                "checkpoint": key,
                "epoch": int(state.get("epoch", -1)),
                **{name: metrics[name]["macro_f1"] for name in views},
                "seconds": round(elapsed, 2),
            }, ensure_ascii=False), flush=True)
            del model
            if device.type == "cuda":
                torch.cuda.empty_cache()

    save_json(output_dir / "metrics.json", results)
    return results


def run_audit(args: argparse.Namespace) -> dict[str, Any]:
    label_map = None
    if args.label_map:
        label_map = json.loads(Path(args.label_map).read_text(encoding="utf-8"))
    report = audit_candidate_manifest(
        Path(args.manifest),
        reference_manifest=Path(args.reference_manifest) if args.reference_manifest else None,
        split=args.split,
        label_map=label_map,
        hash_images=args.hash_images,
        max_hash=args.max_hash,
        authorization_record=Path(args.authorization_record) if args.authorization_record else None,
        exposure_evidence=Path(args.exposure_evidence) if args.exposure_evidence else None,
    )
    save_json(Path(args.output), report)
    return report


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    config = build_protocol_config(
        checkpoint["config"], seed=20261022, batch_size=args.batch_size, num_workers=0,
        temperature=2.0, teacher_weight=0.5, lambda_clean=0.5, lambda_masked=0.5,
    )
    views = resolve_views(args.views, parse_view_seeds(args.view_seeds))
    device = torch.device("cpu" if args.cpu else ("cuda" if torch.cuda.is_available() else "cpu"))
    model = build_model(config, allow_download=False).to(device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    report = synthetic_smoke(
        model, device, config, views, batch_size=args.batch_size,
        repeats=args.repeats, warmup=args.warmup,
    )
    report["environment"] = collect_environment(device, batch_size=args.batch_size, dtype="float32")
    save_json(Path(args.output), report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Frozen per-sample evaluation, candidate-data audit and paired error analysis.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="Audit a candidate manifest before any external claim")
    audit.add_argument("--manifest", required=True)
    audit.add_argument("--reference-manifest")
    audit.add_argument("--split")
    audit.add_argument("--label-map", help="JSON object mapping raw labels to seven-class indices")
    audit.add_argument("--hash-images", action="store_true")
    audit.add_argument("--max-hash", type=int)
    audit.add_argument("--authorization-record")
    audit.add_argument("--exposure-evidence")
    audit.add_argument("--output", required=True)
    audit.set_defaults(func=run_audit)

    masks = sub.add_parser("masks", help="Record the exact mask geometry of the locked views")
    masks.add_argument("--checkpoint", required=True)
    masks.add_argument("--output-dir", required=True)
    masks.add_argument("--count", type=int, required=True)
    masks.add_argument("--seed", type=int, default=20261022)
    masks.add_argument("--batch-size", type=int, default=128)
    masks.add_argument("--views", nargs="+")
    masks.add_argument("--view-seeds", nargs="+")
    masks.set_defaults(func=run_masks)

    evaluate = sub.add_parser("evaluate", help="Run frozen checkpoints and keep per-sample output")
    evaluate.add_argument("--checkpoint", required=True, help="Checkpoint that defines model config")
    evaluate.add_argument("--manifest", required=True)
    evaluate.add_argument("--split", default="validation")
    evaluate.add_argument("--baseline-root", required=True, help="Root holding B_plain / R_random_erasing")
    evaluate.add_argument("--duration-root", required=True, help="Root holding C/D arms")
    evaluate.add_argument("--output-dir", required=True)
    evaluate.add_argument("--checkpoint-name", default="last.pt")
    evaluate.add_argument("--seeds", nargs="+", type=int, default=[20261022, 20261023, 20261024])
    evaluate.add_argument("--arms", nargs="+")
    evaluate.add_argument("--views", nargs="+")
    evaluate.add_argument("--view-seeds", nargs="+")
    evaluate.add_argument("--mask-file")
    evaluate.add_argument("--batch-size", type=int, default=128)
    evaluate.add_argument("--num-workers", type=int, default=4)
    evaluate.add_argument("--cpu", action="store_true")
    evaluate.add_argument("--overwrite", action="store_true")
    evaluate.set_defaults(func=run_evaluate)

    smoke = sub.add_parser("smoke", help="Synthetic-input device and timing check")
    smoke.add_argument("--checkpoint", required=True)
    smoke.add_argument("--output", required=True)
    smoke.add_argument("--views", nargs="+")
    smoke.add_argument("--view-seeds", nargs="+")
    smoke.add_argument("--batch-size", type=int, default=128)
    smoke.add_argument("--repeats", type=int, default=10)
    smoke.add_argument("--warmup", type=int, default=3)
    smoke.add_argument("--cpu", action="store_true")
    smoke.set_defaults(func=run_smoke)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
