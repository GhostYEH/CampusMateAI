import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset

from expression_recognition import frozen_eval as fe
from expression_recognition import occlusion_ablation as oa


def _identifier(index: int) -> str:
    return hashlib.sha256(f"sample-{index}".encode("ascii")).hexdigest()


class _TinyDataset(Dataset):
    """Minimal stand-in for ManifestDataset that exposes manifest rows."""

    def __init__(self, images: torch.Tensor, labels: torch.Tensor, rows: list[dict]):
        self.images = images
        self.labels = labels
        self.rows = rows

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, index: int):
        return self.images[index], int(self.labels[index])


def _tiny_loader(count: int = 5, size: int = 8) -> DataLoader:
    images = torch.rand(count, 3, size, size)
    labels = torch.arange(count) % 7
    rows = [{"sha256": _identifier(index)} for index in range(count)]
    return DataLoader(_TinyDataset(images, labels, rows), batch_size=3, shuffle=False)


class _ConstantModel(nn.Module):
    """Returns a fixed logit vector so predictions are controllable in tests."""

    def __init__(self, logits: list[float]):
        super().__init__()
        self.register_buffer("logits", torch.tensor(logits, dtype=torch.float32))

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        return self.logits.unsqueeze(0).repeat(images.shape[0], 1)


# --------------------------------------------------------------------------- #
# Sample identity and pairing
# --------------------------------------------------------------------------- #
def test_stable_sample_ids_require_unique_content_hashes() -> None:
    rows = [{"sha256": _identifier(index)} for index in range(4)]
    assert fe.stable_sample_ids(rows) == [_identifier(index) for index in range(4)]
    with pytest.raises(ValueError):
        fe.stable_sample_ids([{"sha256": "abc"}])
    with pytest.raises(ValueError):
        fe.stable_sample_ids([{"sha256": _identifier(1)}, {"sha256": _identifier(1)}])


def test_verify_alignment_rejects_reordering_and_length_change() -> None:
    identifiers = [_identifier(index) for index in range(4)]
    fe.verify_alignment(identifiers, list(identifiers))
    with pytest.raises(ValueError):
        fe.verify_alignment(identifiers, identifiers[::-1])
    with pytest.raises(ValueError):
        fe.verify_alignment(identifiers, identifiers[:-1])


# --------------------------------------------------------------------------- #
# Mask determinism and metadata
# --------------------------------------------------------------------------- #
def test_build_views_keeps_clean_input_and_is_index_stable() -> None:
    images = torch.zeros(4, 3, 16, 16)
    before = images.clone()
    views = fe.resolve_views(["clean", "standard", "random_erasing"])
    built, regions = fe.build_views(images, mean=[0.5] * 3, std=[0.5] * 3, views=views)
    assert torch.equal(images, before)
    assert built["clean"] is images
    assert torch.equal(built["clean"], before)
    assert len(regions["standard"]) == 4
    assert regions["clean"] is None and regions["random_erasing"] is None
    # Same seed and offset reproduce the same masks, independent of batch grouping.
    single = []
    for index in range(4):
        one, one_regions = fe.build_views(
            images[index:index + 1], mean=[0.5] * 3, std=[0.5] * 3,
            views={"standard": views["standard"]}, first_index=index,
        )
        single.append(one["standard"])
        assert one_regions["standard"] == [regions["standard"][index]]
    assert torch.equal(torch.cat(single), built["standard"])


def test_mask_geometry_matches_the_mask_applied_to_real_pixels() -> None:
    views = fe.resolve_views(["standard", "severe", "random_erasing"])
    description = fe.describe_views(
        views, channels=3, height=32, width=32, count=6, mean=[0.5] * 3, std=[0.5] * 3,
    )
    for index in range(6):
        image = torch.rand(1, 3, 32, 32)
        built, _ = fe.build_views(
            image, mean=[0.5] * 3, std=[0.5] * 3, views=views, first_index=index,
        )
        for name in views:
            changed = (built[name] != image).any(dim=1)[0].numpy()
            box = description["per_sample"][name]["bbox"][index]
            assert box is not None
            left, top, width, height = box
            expected = np.zeros((32, 32), dtype=bool)
            expected[top:top + height, left:left + width] = True
            assert np.array_equal(changed, expected), name
            area = description["per_sample"][name]["area_fraction"][index]
            assert area == pytest.approx(changed.sum() / (32 * 32))
    # Repeated measurement must be identical: the mask depends only on (seed, index, shape).
    repeated = fe.describe_views(
        views, channels=3, height=32, width=32, count=6, mean=[0.5] * 3, std=[0.5] * 3,
    )
    assert repeated["per_sample"] == description["per_sample"]


def test_structured_view_geometry_follows_the_locked_ranges() -> None:
    summary = fe.describe_views(
        fe.resolve_views(["standard", "severe"]),
        channels=3, height=96, width=96, count=64, mean=[0.5] * 3, std=[0.5] * 3,
    )["views"]
    standard = summary["standard"]
    severe = summary["severe"]
    assert standard["empty_masks"] == 0 and severe["empty_masks"] == 0
    assert 0.04 <= standard["area_fraction_mean"] <= 0.16
    assert severe["area_fraction_mean"] > standard["area_fraction_mean"]
    assert sum(standard["region_counts"].values()) == 64


# --------------------------------------------------------------------------- #
# Candidate-data audit
# --------------------------------------------------------------------------- #
def _write_manifest(path: Path, rows: list[dict], fieldnames: list[str]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_audit_reports_missing_class_unresolved_labels_and_missing_files(tmp_path: Path) -> None:
    images = {}
    for index in range(3):
        image_path = tmp_path / f"img{index}.png"
        Image.new("L", (16, 16), color=index * 10).save(image_path)
        images[index] = image_path
    rows = [
        {"path": str(images[0]), "label": "happy", "split": "test", "status": "included",
         "sha256": _identifier(0)},
        {"path": str(images[1]), "label": "sad", "split": "test", "status": "included",
         "sha256": _identifier(1)},
        {"path": str(tmp_path / "absent.png"), "label": "happy", "split": "test",
         "status": "included", "sha256": _identifier(2)},
        {"path": str(images[2]), "label": "contempt", "split": "test", "status": "included",
         "sha256": _identifier(3)},
        {"path": str(images[2]), "label": "happy", "split": "test", "status": "excluded",
         "sha256": _identifier(4)},
    ]
    manifest = _write_manifest(
        tmp_path / "candidate.csv", rows, ["path", "label", "split", "status", "sha256"],
    )
    report = fe.audit_candidate_manifest(manifest, split="test")
    assert report["rows_selected"] == 4
    assert report["rows_excluded_by_status"] == 1
    assert report["rows_unresolved_label"] == 1
    assert report["unresolved_label_values"] == ["contempt"]
    assert report["rows_missing_file"] == 1
    assert report["rows_usable"] == 2
    assert report["classes_absent"] == ["angry", "disgust", "fear", "neutral", "surprise"]
    assert report["class_support"]["happy"] == 1
    assert report["usable_for_frozen_eval"] is False
    assert report["independence_verified"] is False
    assert report["group_columns"] == []


def test_audit_maps_numeric_labels_and_detects_reference_duplicates(tmp_path: Path) -> None:
    rows = []
    for index in range(3):
        image_path = tmp_path / f"num{index}.png"
        Image.new("L", (16, 16), color=index * 10).save(image_path)
        rows.append({"path": str(image_path), "label": str(index + 1), "sha256": _identifier(index)})
    manifest = _write_manifest(tmp_path / "candidate.csv", rows, ["path", "label", "sha256"])
    label_map = {str(index + 1): index for index in range(7)}
    reference = _write_manifest(
        tmp_path / "reference.csv",
        [{"sha256": _identifier(1)}, {"sha256": _identifier(9)}],
        ["sha256"],
    )
    report = fe.audit_candidate_manifest(
        manifest, reference_manifest=reference, label_map=label_map,
    )
    assert report["rows_unresolved_label"] == 0
    assert report["class_support"]["angry"] == 1
    assert report["class_support"]["disgust"] == 1
    assert report["class_support"]["fear"] == 1
    assert report["exact_duplicates_with_reference"] == 1
    assert report["duplicate_hashes_within_candidate"] == 0
    assert "exact duplicate" in " ".join(report["independence_reasons"])
    # Without a mapping the same numeric labels are refused rather than guessed.
    unmapped = fe.audit_candidate_manifest(manifest)
    assert unmapped["rows_unresolved_label"] == 3
    assert unmapped["rows_usable"] == 0


# --------------------------------------------------------------------------- #
# Probability contract and persistence
# --------------------------------------------------------------------------- #
def test_evaluate_views_returns_valid_probabilities_and_saves_roundtrip(tmp_path: Path) -> None:
    loader = _tiny_loader(count=5, size=8)
    model = _ConstantModel([0.1, 0.2, 3.0, 0.1, 0.1, 0.1, 0.1])
    config = {"normalization": {"mean": [0.5] * 3, "std": [0.5] * 3}}
    views = fe.resolve_views(["clean", "standard", "random_erasing"])
    result = fe.evaluate_views(model, loader, torch.device("cpu"), config, views)

    assert result["targets"].shape == (5,)
    assert result["sample_ids"] == [_identifier(index) for index in range(5)]
    for name in views:
        block = result["probabilities"][name]
        assert block.shape == (5, 7)
        assert np.isfinite(block).all()
        assert np.allclose(block.sum(axis=1), 1.0, atol=1e-6)
        assert np.array_equal(result["predictions"][name], block.argmax(axis=1))
        assert np.array_equal(result["logits"][name].argmax(axis=1), block.argmax(axis=1))
    assert set(result["regions"]["standard"].tolist()).issubset({0, 1, 2})
    assert (result["regions"]["clean"] == -1).all()

    path = tmp_path / "predictions.npz"
    fe.save_predictions(path, result, list(views))
    loaded = fe.load_predictions(path)
    assert loaded["views"] == list(views)
    assert loaded["sample_ids"] == result["sample_ids"]
    assert np.array_equal(loaded["predictions"]["standard"], result["predictions"]["standard"])
    assert np.array_equal(loaded["probabilities"]["standard"], result["probabilities"]["standard"])
    metrics = fe.metrics_from_predictions(result["predictions"], result["targets"])
    assert metrics["clean"]["samples"] == 5
    assert len(metrics["clean"]["per_class"]) == 7


def test_evaluate_views_rejects_a_manifest_order_change() -> None:
    loader = _tiny_loader(count=5, size=8)
    model = _ConstantModel([1.0] + [0.0] * 6)
    config = {"normalization": {"mean": [0.5] * 3, "std": [0.5] * 3}}
    with pytest.raises(ValueError):
        fe.evaluate_views(
            model, loader, torch.device("cpu"), config, fe.resolve_views(["clean"]),
            expected_ids=[_identifier(index) for index in range(4, -1, -1)],
        )


# --------------------------------------------------------------------------- #
# Paired error counts
# --------------------------------------------------------------------------- #
def test_paired_counts_reproduce_accuracy_delta_and_split_by_class() -> None:
    targets = np.array([0, 0, 1, 1, 2, 2], dtype=np.int64)
    reference = np.array([0, 1, 1, 2, 2, 2], dtype=np.int64)   # errors on index 1 and 3
    candidate = np.array([0, 0, 1, 1, 2, 0], dtype=np.int64)   # fixes 1 and 3, breaks 5
    counts = fe.paired_counts(reference, candidate, targets, name="C-R")
    assert counts["both_correct"] == 3
    assert counts["candidate_only_correct"] == 2
    assert counts["reference_only_correct"] == 1
    assert counts["both_wrong"] == 0
    assert counts["net_gain"] == 1
    assert counts["accuracy_delta"] == pytest.approx(1 / 6)
    assert counts["accuracy_delta"] == pytest.approx(
        counts["accuracy_delta_check"], abs=1e-12
    )
    assert counts["comparison"] == "C-R"
    assert counts["per_class"]["angry"]["candidate_only_correct"] == 1
    assert counts["per_class"]["angry"]["reference_only_correct"] == 0
    assert counts["per_class"]["fear"]["reference_only_correct"] == 1
    assert counts["per_class"]["sad"] == {"support": 0, "defined": False}
    assert sum(counts[cell] for cell in fe.PAIR_CELLS) == counts["samples"]


def test_paired_counts_handles_empty_subset_and_absent_class() -> None:
    with pytest.raises(ValueError):
        fe.paired_counts(np.array([], dtype=np.int64), np.array([], dtype=np.int64),
                         np.array([], dtype=np.int64))
    targets = np.array([0, 0, 1], dtype=np.int64)
    reference = np.array([0, 1, 1], dtype=np.int64)
    candidate = np.array([0, 0, 0], dtype=np.int64)
    counts = fe.paired_counts(reference, candidate, targets)
    assert counts["per_class"]["surprise"] == {"support": 0, "defined": False}
    assert counts["per_class"]["disgust"]["defined"] is True
    assert counts["per_class"]["disgust"]["support"] == 1


def test_example_pairs_are_sorted_and_include_both_directions() -> None:
    # Row order is deliberately not sorted by identifier, so the assertion below
    # proves the listing uses the identifier order rather than the row order.
    identifiers = [_identifier(1), _identifier(0), _identifier(2), _identifier(3)]
    targets = np.array([0, 0, 1, 1], dtype=np.int64)
    reference = np.array([1, 1, 1, 0], dtype=np.int64)   # wrong at 0,1; correct at 2,3
    candidate = np.array([0, 0, 0, 0], dtype=np.int64)   # fixed 0,1; broke 2
    examples = fe.example_pairs(reference, candidate, targets, identifiers, limit=5)
    expected_corrected = sorted([_identifier(0), _identifier(1)])
    assert [row["sample_id"] for row in examples["corrected"]] == expected_corrected
    assert [row["sample_id"] for row in examples["introduced"]] == [identifiers[2]]
    assert examples["corrected"][0]["true"] == "angry"
    assert examples["corrected"][0]["reference_prediction"] == "disgust"
    assert fe.example_pairs(reference, candidate, targets, identifiers, limit=1)["corrected"] == [
        examples["corrected"][0]
    ]


def test_summarize_seeds_reports_direction_counts() -> None:
    per_seed = {
        "20261022": {"net_gain": 5.0},
        "20261023": {"net_gain": -3.0},
        "20261024": {"net_gain": 5.0},
    }
    summary = fe.summarize_seeds(per_seed, ["net_gain"])
    assert summary["seeds"] == ["20261022", "20261023", "20261024"]
    cell = summary["cells"]["net_gain"]
    assert cell["mean"] == pytest.approx(7 / 3)
    assert cell["positive"] == 2 and cell["negative"] == 1
    assert cell["sample_std"] == pytest.approx(float(np.std([5.0, -3.0, 5.0], ddof=1)))


# --------------------------------------------------------------------------- #
# Reconciliation
# --------------------------------------------------------------------------- #
def test_compare_metrics_enforces_the_tolerance() -> None:
    current = {"checkpoints": {"final|C|1": {"metrics": {
        "clean": {"accuracy": 0.5, "macro_f1": 0.4, "balanced_accuracy": 0.45,
                  "samples": 10, "confusion_matrix": [[1]]},
    }}}}
    identical = json.loads(json.dumps(current))
    report = fe.compare_metrics(current, identical, tolerance=1e-6)
    assert report["passed"] is True
    assert report["max_abs_diff"] == 0.0

    shifted = json.loads(json.dumps(current))
    shifted["checkpoints"]["final|C|1"]["metrics"]["clean"]["macro_f1"] += 1e-5
    report = fe.compare_metrics(current, shifted, tolerance=1e-6)
    assert report["passed"] is False
    assert report["rows_exceeding_tolerance"] == 1

    missing = {"checkpoints": {"final|D|2": {"metrics": {}}}}
    report = fe.compare_metrics(current, missing, tolerance=1e-6)
    assert report["passed"] is False
    assert report["missing_entries"] == ["final|D|2"]


def test_synthetic_smoke_reports_placement_and_timing() -> None:
    model = _ConstantModel([0.0, 1.0] + [0.0] * 5)
    config = {
        "input_size": 16, "input_channels": 3,
        "normalization": {"mean": [0.5] * 3, "std": [0.5] * 3},
    }
    report = fe.synthetic_smoke(
        model, torch.device("cpu"), config, fe.resolve_views(["clean", "standard"]),
        batch_size=4, repeats=2, warmup=1,
    )
    assert report["placement"]["all_parameters_on_device"] is True
    assert report["placement"]["input_on_device"] is True
    assert report["view_shapes"]["standard"] == [4, 3, 16, 16]
    assert report["checks"]["clean"]["probabilities_sum_to_one"] is True
    assert report["checks"]["standard"]["logits_finite"] is True
    assert report["end_to_end_ms_per_iteration_mean"] > 0
    assert report["kernel_ms_per_view_mean"] is None
