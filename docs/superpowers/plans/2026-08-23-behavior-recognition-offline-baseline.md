# Behavior Recognition Offline Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, train, evaluate, calibrate, and export a reproducible MobileNetV3-Small student-behavior classifier that outperforms the packaged V3.2 model on a leakage-controlled offline test set.

**Architecture:** A standalone Python package under `ml/behavior_recognition` audits the read-only YOLO datasets on `F:\数据集`, creates deterministic source/group-aware manifests, lazily crops student ROIs, trains a four-class MobileNetV3-Small model, compares it with V3.2, calibrates rejection thresholds, and exports a candidate ONNX model. Generated data, checkpoints, and model binaries remain ignored local artifacts; the Android production asset is not replaced in this plan.

**Tech Stack:** Python 3.13, PyTorch 2.13, torchvision 0.28, CUDA 13.0, Pillow, NumPy, scikit-learn, PyYAML, ONNX, ONNX Runtime, pytest.

**Spec:** `docs/superpowers/specs/2026-08-23-behavior-recognition-offline-baseline-design.md`

## Global Constraints

- Treat every path under `F:\数据集` as read-only.
- Keep input shape exactly `1 x 3 x 224 x 224`, RGB, ImageNet normalization, float32 NCHW.
- Canonical output order is `READ`, `WRITE`, `PHONE_INTERACTION`, `NO_VISIBLE_STUDY`.
- `PHONE_INTERACTION` is an observable action, not a direct distraction judgment.
- Generate `UNCERTAIN` through calibration and rejection; do not train it as a synthetic class.
- Keep the existing V3.2 Android model and runtime selection unchanged.
- Do not load unknown `.pt`, pickle, or NumPy object-array files from downloaded archives.
- Do not claim mobile/front-camera improvement without later real-device evaluation.
- Use seed `20260823` for manifests, training, sampling, and evaluation.
- Commit source, tests, configs, summaries, and documentation only; ignore derived crops, manifests with absolute paths, checkpoints, runs, and ONNX binaries.

## File Structure

Create the following focused package:

```text
ml/behavior_recognition/
├─ pyproject.toml                 # package metadata
├─ requirements.txt              # pinned training/export dependencies
├─ pytest.ini                    # src-layout pytest configuration
├─ README.md                     # reproducible operator commands and limitations
├─ configs/
│  ├─ sources.yaml               # dataset roots and verified source label mappings
│  ├─ mobilenet_v3_small_roi.yaml# ROI training, augmentation and selection config
│  └─ mobilenet_v3_small_full.yaml# pure-label full-frame diagnostic config
├─ scripts/
│  └─ run_offline_baseline.ps1   # preflight → audit → train → evaluate → export
├─ src/behavior_recognition/
│  ├─ __init__.py
│  ├─ constants.py               # canonical labels and ImageNet preprocessing constants
│  ├─ records.py                 # typed source, box and manifest records
│  ├─ yolo.py                    # strict YOLO parser and box validation
│  ├─ audit.py                   # source integrity and anomaly reporting
│  ├─ manifest.py                # mapping, grouping, deduplication and deterministic split
│  ├─ data.py                    # lazy ROI/full-frame datasets and transforms
│  ├─ models.py                  # MobileNetV3-Small four-class builder
│  ├─ train.py                   # deterministic training and checkpoint selection
│  ├─ metrics.py                 # classification, calibration and rejection metrics
│  ├─ evaluate.py                # candidate and V3.2 offline comparison
│  ├─ calibrate.py               # temperature scaling and threshold search
│  ├─ export_onnx.py             # ONNX export and PyTorch/ORT parity
│  └─ cli.py                     # stable command-line entry points
└─ tests/
   ├─ conftest.py
   ├─ test_yolo.py
   ├─ test_audit.py
   ├─ test_manifest.py
   ├─ test_data.py
   ├─ test_models.py
   ├─ test_train.py
   ├─ test_metrics.py
   └─ test_export_onnx.py
```

Modify `.gitignore` only to exclude `ml/behavior_recognition/{artifacts,manifests,reports/generated,runs,exports,.torch-cache,.venv}/`.

---

### Task 1: Package scaffold and immutable behavior contract

**Files:**
- Create: `ml/behavior_recognition/pyproject.toml`
- Create: `ml/behavior_recognition/requirements.txt`
- Create: `ml/behavior_recognition/pytest.ini`
- Create: `ml/behavior_recognition/src/behavior_recognition/__init__.py`
- Create: `ml/behavior_recognition/src/behavior_recognition/constants.py`
- Create: `ml/behavior_recognition/src/behavior_recognition/records.py`
- Create: `ml/behavior_recognition/src/behavior_recognition/cli.py`
- Create: `ml/behavior_recognition/tests/test_models.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `CLASS_NAMES: tuple[str, ...]`, `CLASS_TO_INDEX: dict[str, int]`, `IMAGE_SIZE: int`, `IMAGENET_MEAN`, `IMAGENET_STD`.
- Produces: immutable `YoloBox`, `SourceSpec`, and `ManifestRecord` dataclasses used by all later tasks.
- Produces: an argparse command registry that later tasks extend with `audit`, `manifest`, `train`, `evaluate`, and `export` handlers.

- [ ] **Step 1: Write the contract test**

```python
from behavior_recognition.constants import CLASS_NAMES, CLASS_TO_INDEX, IMAGE_SIZE


def test_canonical_output_contract_is_stable():
    assert CLASS_NAMES == (
        "READ",
        "WRITE",
        "PHONE_INTERACTION",
        "NO_VISIBLE_STUDY",
    )
    assert CLASS_TO_INDEX == {name: index for index, name in enumerate(CLASS_NAMES)}
    assert IMAGE_SIZE == 224
```

- [ ] **Step 2: Run the test and verify the package is absent**

Run: `python -m pytest ml/behavior_recognition/tests/test_models.py -v`

Expected: collection fails with `ModuleNotFoundError: behavior_recognition`.

- [ ] **Step 3: Add the package files and immutable dataclasses**

```python
CLASS_NAMES = ("READ", "WRITE", "PHONE_INTERACTION", "NO_VISIBLE_STUDY")
CLASS_TO_INDEX = {name: index for index, name in enumerate(CLASS_NAMES)}
IMAGE_SIZE = 224
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
DEFAULT_SEED = 20260823
```

Define `YoloBox(class_id: int, center_x: float, center_y: float, width: float, height: float)`, `SourceSpec(name: str, root: Path, class_map: dict[int, str | None])`, and `ManifestRecord(sample_id, source, image_path, label_path, source_class_id, target_name, target_index, split, group_id, box)` as frozen dataclasses.

Use this dependency set in `requirements.txt`:

```text
torch==2.13.0
torchvision==0.28.0
numpy>=1.26,<3
pillow>=11.0
scikit-learn>=1.5
matplotlib>=3.9
PyYAML>=6.0
onnx>=1.17
onnxruntime>=1.20
pytest>=8.3
tqdm>=4.67
psutil>=6.1
```

Expose the CLI through `python -m behavior_recognition.cli`; with no subcommand it must print help and return exit code 2.

- [ ] **Step 4: Add local artifact ignores and run the test**

Run: `python -m pytest ml/behavior_recognition/tests/test_models.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the scaffold**

```powershell
git add -- .gitignore ml/behavior_recognition/pyproject.toml ml/behavior_recognition/requirements.txt ml/behavior_recognition/pytest.ini ml/behavior_recognition/src ml/behavior_recognition/tests/test_models.py
git commit -m "feat(ml): scaffold behavior recognition pipeline"
```

### Task 2: Strict YOLO parsing and source audit

**Files:**
- Create: `ml/behavior_recognition/src/behavior_recognition/yolo.py`
- Create: `ml/behavior_recognition/src/behavior_recognition/audit.py`
- Create: `ml/behavior_recognition/configs/sources.yaml`
- Create: `ml/behavior_recognition/tests/test_yolo.py`
- Create: `ml/behavior_recognition/tests/test_audit.py`
- Create: `ml/behavior_recognition/tests/conftest.py`
- Modify: `ml/behavior_recognition/src/behavior_recognition/cli.py`

**Interfaces:**
- Consumes: `YoloBox`, `SourceSpec` from Task 1.
- Produces: `parse_yolo_line(line: str) -> YoloBox`.
- Produces: `sanitize_box(box: YoloBox) -> tuple[YoloBox | None, str | None]`.
- Produces: `audit_sources(specs: Sequence[SourceSpec], report_path: Path) -> dict`.

- [ ] **Step 1: Write parser failure and repair tests**

```python
import pytest
from behavior_recognition.yolo import parse_yolo_line, sanitize_box


def test_negative_width_is_rejected():
    box = parse_yolo_line("1 0.31 0.17 -0.03 0.07")
    fixed, reason = sanitize_box(box)
    assert fixed is None
    assert reason == "non_positive_extent"


def test_slight_coordinate_overflow_is_clipped():
    box = parse_yolo_line("0 1.007 0.25 0.12 0.14")
    fixed, reason = sanitize_box(box)
    assert fixed is not None
    assert 0.0 <= fixed.center_x <= 1.0
    assert reason == "clipped_to_image"


def test_wrong_column_count_raises():
    with pytest.raises(ValueError, match="five columns"):
        parse_yolo_line("1 0.5 0.5")
```

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `python -m pytest ml/behavior_recognition/tests/test_yolo.py -v`

Expected: FAIL because `behavior_recognition.yolo` does not exist.

- [ ] **Step 3: Implement strict parsing and non-destructive auditing**

The audit report must contain `source_counts`, `extension_counts`, `missing_labels`, `orphan_labels`, `empty_labels`, `invalid_lines`, `repaired_boxes`, `rejected_boxes`, and `class_box_counts`. Store source-relative paths in the committed summary; absolute paths remain only in ignored generated reports.

Register an `audit` CLI handler that loads `sources.yaml`, calls `audit_sources`, creates only the requested report parent directory, prints the anomaly summary, and exits nonzero when a source marked `required_for_training: true` is missing or lacks a verified mapping. Optional unresolved sources remain visible in the report but do not block the university baseline.

- [ ] **Step 4: Encode verified source mappings**

Use this university mapping exactly:

```yaml
university_0671:
  root: 'F:\数据集\0.671k_university_yolo_Dataset'
  required_for_training: true
  labels:
    0: null
    1: READ
    2: WRITE
    3: PHONE_INTERACTION
    4: null
    5: NO_VISIBLE_STUDY
handrise_read_write:
  root: 'F:\数据集\SCB5-Handrise-Read-write-2024-9-17'
  required_for_training: false
  labels: {0: null, 1: null, 2: null}
bow_turn_head:
  root: 'F:\数据集\SCB_BowTurnHead_20250509\SCB5-Turn-Bow-Head-2024-9-17'
  required_for_training: false
  labels: {0: null, 1: null}
```

The Handrise/Read/Write and Bow/Turn mappings must be confirmed from their official metadata or a reviewed visual audit before they can contribute training labels. Until confirmed, configure those source class IDs as `null` and still include them in integrity reporting.

- [ ] **Step 5: Run audit tests and the real read-only audit**

Run: `python -m pytest ml/behavior_recognition/tests/test_yolo.py ml/behavior_recognition/tests/test_audit.py -v`

Run: `python -m behavior_recognition.cli audit --sources configs/sources.yaml --output reports/generated/audit.json`

Expected: tests PASS; the real report identifies the two negative-width university boxes without changing source files.

- [ ] **Step 6: Commit the parser and audit**

```powershell
git add -- ml/behavior_recognition/configs/sources.yaml ml/behavior_recognition/src/behavior_recognition/yolo.py ml/behavior_recognition/src/behavior_recognition/audit.py ml/behavior_recognition/src/behavior_recognition/cli.py ml/behavior_recognition/tests
git commit -m "feat(ml): audit classroom behavior datasets"
```

### Task 3: Leakage-controlled manifest builder

**Files:**
- Create: `ml/behavior_recognition/src/behavior_recognition/manifest.py`
- Create: `ml/behavior_recognition/tests/test_manifest.py`
- Modify: `ml/behavior_recognition/src/behavior_recognition/cli.py`

**Interfaces:**
- Consumes: audited `SourceSpec` and sanitized boxes.
- Produces: `infer_group_id(source: str, stem: str) -> str`.
- Produces: `build_manifest(specs, output_dir: Path, seed: int) -> dict[str, list[ManifestRecord]]`.
- Produces: CSV files with exact columns defined by `ManifestRecord`.

- [ ] **Step 1: Write group isolation tests**

```python
from behavior_recognition.manifest import split_group_ids


def test_group_never_crosses_splits():
    grouped = {"scene_a": 20, "scene_b": 18, "scene_c": 12, "scene_d": 10}
    splits = split_group_ids(grouped, seed=20260823)
    owner = {}
    for split, groups in splits.items():
        for group in groups:
            assert group not in owner
            owner[group] = split
    assert set(owner) == set(grouped)
```

Add a test proving two identical image hashes cannot survive in different splits and a test proving conflicting target labels are quarantined.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest ml/behavior_recognition/tests/test_manifest.py -v`

Expected: FAIL because the manifest module is absent.

- [ ] **Step 3: Implement deterministic grouping, hashing, and split allocation**

Use source-aware filename prefixes and contiguous numeric sequences to form conservative scene groups. Allocate approximately 70%/15%/15% by group while preserving class coverage. Record `split_reason`, `sha256`, and `group_id` in generated manifests.

Register a `manifest` CLI handler that reruns the structural audit from the supplied source config and refuses to write manifests when required sources have unhandled structural errors. It may include repaired boxes but must exclude rejected boxes and unresolved class IDs.

- [ ] **Step 4: Run tests and build the first real manifest**

Run: `python -m pytest ml/behavior_recognition/tests/test_manifest.py -v`

Run: `python -m behavior_recognition.cli manifest --sources configs/sources.yaml --output manifests --seed 20260823`

Expected: PASS; no `group_id` or SHA-256 appears in more than one split.

- [ ] **Step 5: Commit manifest logic**

```powershell
git add -- ml/behavior_recognition/src/behavior_recognition/manifest.py ml/behavior_recognition/src/behavior_recognition/cli.py ml/behavior_recognition/tests/test_manifest.py
git commit -m "feat(ml): build grouped behavior manifests"
```

### Task 4: ROI dataset, transforms, and MobileNetV3 model

**Files:**
- Create: `ml/behavior_recognition/src/behavior_recognition/data.py`
- Create: `ml/behavior_recognition/src/behavior_recognition/models.py`
- Create: `ml/behavior_recognition/configs/mobilenet_v3_small_roi.yaml`
- Create: `ml/behavior_recognition/configs/mobilenet_v3_small_full.yaml`
- Create: `ml/behavior_recognition/tests/test_data.py`
- Modify: `ml/behavior_recognition/tests/test_models.py`

**Interfaces:**
- Consumes: manifest CSV records from Task 3.
- Produces: `BehaviorDataset(manifest_path: Path, mode: str, training: bool)`.
- Produces: `build_model(num_classes: int = 4, pretrained: bool = True) -> nn.Module`.
- Produces: `build_transforms(training: bool, mode: str) -> Callable`.

- [ ] **Step 1: Write ROI and output-shape tests**

```python
import torch
from behavior_recognition.models import build_model


def test_mobilenet_output_matches_contract():
    model = build_model(num_classes=4, pretrained=False).eval()
    output = model(torch.zeros(2, 3, 224, 224))
    assert output.shape == (2, 4)
```

Create a synthetic 100x80 image and assert that an expanded normalized box produces a non-empty 224x224 tensor. Assert validation transforms are deterministic.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `python -m pytest ml/behavior_recognition/tests/test_data.py ml/behavior_recognition/tests/test_models.py -v`

Expected: FAIL because the modules are absent.

- [ ] **Step 3: Implement lazy crops and ImageNet-compatible transforms**

Use an ROI expansion factor of `1.25`, preserve head/hands/table context, clip to image bounds, then resize to 224x224. Training augmentation may use brightness/contrast, JPEG-like blur, small rotation/translation, scale jitter, and random erasing; validation/test use deterministic resize and normalization only.

For `mode: full`, include only images whose mapped behavior boxes agree on one canonical target. Exclude mixed-label multi-student frames so the same full image is never presented with contradictory class labels. Report the number of retained pure-label frames; this diagnostic dataset must not replace ROI as the primary experiment.

- [ ] **Step 4: Implement MobileNetV3-Small and config**

```yaml
model: mobilenet_v3_small
seed: 20260823
input_size: 224
input_mode: roi
pretrained: true
pretrained_weights: IMAGENET1K_V1
batch_size: 64
num_workers: 4
max_epochs: 30
early_stopping_patience: 6
learning_rate: 0.0005
weight_decay: 0.0001
label_smoothing: 0.05
loss: weighted_cross_entropy
amp: true
selection_metric: macro_f1
```

Create `mobilenet_v3_small_full.yaml` with the same values except `input_mode: full`. The full-frame manifest filter is deterministic and preserves the same group ownership as the ROI split.

- [ ] **Step 5: Run all dataset/model tests**

Run: `python -m pytest ml/behavior_recognition/tests/test_data.py ml/behavior_recognition/tests/test_models.py -v`

Expected: PASS.

- [ ] **Step 6: Commit the dataset and model**

```powershell
git add -- ml/behavior_recognition/configs/mobilenet_v3_small_roi.yaml ml/behavior_recognition/configs/mobilenet_v3_small_full.yaml ml/behavior_recognition/src/behavior_recognition/data.py ml/behavior_recognition/src/behavior_recognition/models.py ml/behavior_recognition/tests
git commit -m "feat(ml): add behavior ROI classifier"
```

### Task 5: Deterministic training and checkpoint selection

**Files:**
- Create: `ml/behavior_recognition/src/behavior_recognition/train.py`
- Create: `ml/behavior_recognition/tests/test_train.py`
- Modify: `ml/behavior_recognition/src/behavior_recognition/cli.py`

**Interfaces:**
- Consumes: YAML config, train/validation manifests, `BehaviorDataset`, and `build_model`.
- Produces: `train_model(config_path, manifest_dir, run_dir) -> Path` returning the best checkpoint.
- Produces: `run_dir/{resolved_config.yaml,history.csv,best.pt,environment.json}`.

- [ ] **Step 1: Write loss and checkpoint tests**

```python
from behavior_recognition.train import select_best_epoch


def test_checkpoint_selection_uses_macro_f1_then_loss():
    rows = [
        {"epoch": 1, "val_macro_f1": 0.61, "val_loss": 0.8},
        {"epoch": 2, "val_macro_f1": 0.64, "val_loss": 0.9},
        {"epoch": 3, "val_macro_f1": 0.64, "val_loss": 0.7},
    ]
    assert select_best_epoch(rows) == 3
```

Add a CPU-only tiny-dataset smoke test that completes one epoch and reloads the saved state dict.

- [ ] **Step 2: Run the tests and verify failure**

Run: `python -m pytest ml/behavior_recognition/tests/test_train.py -v`

Expected: FAIL because the training module is absent.

- [ ] **Step 3: Implement seeded AMP training**

Seed Python, NumPy, PyTorch, CUDA, and DataLoader workers. Use weighted cross entropy, gradient clipping at `1.0`, early stopping by validation Macro-F1, and atomic checkpoint writes. Record CUDA device, package versions, resolved configuration, manifest hashes, and elapsed time.

- [ ] **Step 4: Run the smoke test and a real two-epoch smoke run**

Run: `python -m pytest ml/behavior_recognition/tests/test_train.py -v`

Run: `python -m behavior_recognition.cli train --config configs/mobilenet_v3_small_roi.yaml --manifests manifests --run-dir runs/smoke --max-epochs 2 --limit-per-class 64`

Expected: PASS; CUDA device is `NVIDIA GeForce RTX 5060 Laptop GPU`; `runs/smoke/best.pt` is created.

- [ ] **Step 5: Commit training support**

```powershell
git add -- ml/behavior_recognition/src/behavior_recognition/train.py ml/behavior_recognition/src/behavior_recognition/cli.py ml/behavior_recognition/tests/test_train.py
git commit -m "feat(ml): train behavior classifier reproducibly"
```

### Task 6: Metrics, V3.2 comparison, calibration, and rejection

**Files:**
- Create: `ml/behavior_recognition/src/behavior_recognition/metrics.py`
- Create: `ml/behavior_recognition/src/behavior_recognition/evaluate.py`
- Create: `ml/behavior_recognition/src/behavior_recognition/calibrate.py`
- Create: `ml/behavior_recognition/tests/test_metrics.py`
- Modify: `ml/behavior_recognition/src/behavior_recognition/cli.py`

**Interfaces:**
- Produces: `classification_report(y_true, probabilities, class_names) -> dict`.
- Produces: `fit_temperature(logits, y_true) -> float`.
- Produces: `apply_rejection(probabilities, thresholds, margin_threshold) -> np.ndarray` where rejected predictions are `-1`.
- Produces: `evaluate_checkpoint(...) -> dict` and V3.2 diagnostic results on the identical test manifest.

- [ ] **Step 1: Write metric and rejection tests**

```python
import numpy as np
from behavior_recognition.metrics import apply_rejection


def test_low_margin_prediction_is_rejected():
    probabilities = np.array([[0.36, 0.34, 0.20, 0.10]], dtype=np.float32)
    result = apply_rejection(
        probabilities,
        thresholds=np.array([0.4, 0.4, 0.4, 0.4]),
        margin_threshold=0.08,
    )
    assert result.tolist() == [-1]
```

Add deterministic tests for confusion matrix, Macro-F1, Balanced Accuracy, PHONE_INTERACTION AUPRC, ECE, and Brier score.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest ml/behavior_recognition/tests/test_metrics.py -v`

Expected: FAIL because metric functions are absent.

- [ ] **Step 3: Implement metrics and temperature scaling**

Fit temperature on validation logits only. Search per-class probability thresholds and margin threshold against validation Macro-F1 with a minimum accepted coverage recorded in the resolved config. Never tune against test.

- [ ] **Step 4: Implement comparable V3.2 diagnostics**

Run the packaged V3.2 ONNX with Android-aligned RGB resize and ImageNet normalization. Report its binary behavior performance separately because its output space differs from the four-class candidate; do not mislabel binary Accuracy as four-class Accuracy.

- [ ] **Step 5: Run tests and smoke evaluation**

Run: `python -m pytest ml/behavior_recognition/tests/test_metrics.py -v`

Run: `python -m behavior_recognition.cli evaluate --checkpoint runs/smoke/best.pt --manifests manifests --output reports/generated/smoke-evaluation.json --compare-v32 ../../android/app/src/main/assets/models/behavior/campusmate_visible_study_v32.onnx`

Expected: tests PASS; report includes uncalibrated, calibrated, rejected-coverage, per-class, and V3.2 diagnostic sections.

- [ ] **Step 6: Commit evaluation support**

```powershell
git add -- ml/behavior_recognition/src/behavior_recognition/metrics.py ml/behavior_recognition/src/behavior_recognition/evaluate.py ml/behavior_recognition/src/behavior_recognition/calibrate.py ml/behavior_recognition/src/behavior_recognition/cli.py ml/behavior_recognition/tests/test_metrics.py
git commit -m "feat(ml): evaluate and calibrate behavior model"
```

### Task 7: ONNX export, parity validation, and model card

**Files:**
- Create: `ml/behavior_recognition/src/behavior_recognition/export_onnx.py`
- Create: `ml/behavior_recognition/tests/test_export_onnx.py`
- Modify: `ml/behavior_recognition/src/behavior_recognition/cli.py`

**Interfaces:**
- Produces: `export_candidate(checkpoint, config, output_dir) -> Path`.
- Produces: `exports/<run>/campusmate_behavior_v34_candidate.onnx`, `labels.json`, `model_card.json`, and `parity.json` as ignored local artifacts.

- [ ] **Step 1: Write an ONNX parity test**

```python
def test_exported_onnx_matches_pytorch(tmp_path):
    onnx_path, parity = export_test_model(tmp_path, seed=20260823)
    assert onnx_path.exists()
    assert parity["top1_match"] is True
    assert parity["max_abs_error"] <= 1e-4
```

- [ ] **Step 2: Run the test and verify failure**

Run: `python -m pytest ml/behavior_recognition/tests/test_export_onnx.py -v`

Expected: FAIL because the export module is absent.

- [ ] **Step 3: Implement export with a fixed deployment contract**

Use input name `input`, output name `logits`, opset 17, static batch 1, float32 NCHW, and output order from `CLASS_NAMES`. Validate at least 32 fixed test samples through PyTorch and ONNX Runtime.

- [ ] **Step 4: Run tests and export the smoke candidate**

Run: `python -m pytest ml/behavior_recognition/tests/test_export_onnx.py -v`

Run: `python -m behavior_recognition.cli export --checkpoint runs/smoke/best.pt --config configs/mobilenet_v3_small_roi.yaml --output exports/smoke`

Expected: PASS; maximum absolute logit error is at most `1e-4`; every parity sample has matching Top-1.

- [ ] **Step 5: Commit export support**

```powershell
git add -- ml/behavior_recognition/src/behavior_recognition/export_onnx.py ml/behavior_recognition/src/behavior_recognition/cli.py ml/behavior_recognition/tests/test_export_onnx.py
git commit -m "feat(ml): export behavior candidate to ONNX"
```

### Task 8: Reproducible orchestration and operator documentation

**Files:**
- Create: `ml/behavior_recognition/scripts/run_offline_baseline.ps1`
- Create: `ml/behavior_recognition/README.md`

**Interfaces:**
- Consumes: CLI commands from Tasks 2–7.
- Produces: one PowerShell entry point with `-Sources`, `-RunName`, `-MaxEpochs`, and `-SkipFullTraining` parameters.

- [ ] **Step 1: Implement fail-fast environment preflight**

The script must print Python, PyTorch, torchvision, CUDA availability, GPU name, free disk space, and source-path existence. It must stop before training when a required path is missing or CUDA was explicitly required but unavailable.

- [ ] **Step 2: Chain audit, manifest, tests, smoke training, full training, evaluation, and export**

```powershell
python -m pytest -q
python -m behavior_recognition.cli audit --sources $Sources --output reports/generated/audit.json
python -m behavior_recognition.cli manifest --sources $Sources --output manifests --seed 20260823
python -m behavior_recognition.cli train --config configs/mobilenet_v3_small_roi.yaml --manifests manifests --run-dir "runs/$RunName"
python -m behavior_recognition.cli evaluate --checkpoint "runs/$RunName/best.pt" --manifests manifests --output "reports/generated/$RunName.json" --compare-v32 $V32Model
python -m behavior_recognition.cli export --checkpoint "runs/$RunName/best.pt" --config configs/mobilenet_v3_small_roi.yaml --output "exports/$RunName"
```

- [ ] **Step 3: Document exact setup and limitations**

Document editable install, commands, source mappings, output locations, recovery after interruption, metric interpretation, the read-only data guarantee, and the fact that the candidate does not replace V3.2 or prove front-camera improvement.

- [ ] **Step 4: Run PowerShell syntax validation and help output**

Run: `powershell -NoProfile -Command "[scriptblock]::Create((Get-Content -Raw 'ml/behavior_recognition/scripts/run_offline_baseline.ps1')) | Out-Null"`

Run: `powershell -NoProfile -File ml/behavior_recognition/scripts/run_offline_baseline.ps1 -Help`

Expected: both commands exit 0 and the second prints parameter usage without starting training.

- [ ] **Step 5: Commit orchestration and docs**

```powershell
git add -- ml/behavior_recognition/scripts/run_offline_baseline.ps1 ml/behavior_recognition/README.md
git commit -m "docs(ml): document behavior training workflow"
```

### Task 9: Full offline training and evidence report

**Files:**
- Generate, ignored: `ml/behavior_recognition/manifests/*`
- Generate, ignored: `ml/behavior_recognition/runs/v34-roi-seed-20260823/*`
- Generate, ignored: `ml/behavior_recognition/reports/generated/v34-roi-seed-20260823.json`
- Generate, ignored: `ml/behavior_recognition/exports/v34-roi-seed-20260823/*`
- Create: `ml/behavior_recognition/reports/v34-roi-seed-20260823-summary.md`

**Interfaces:**
- Consumes: the complete pipeline.
- Produces: a human-readable, source-backed decision report and an ignored candidate ONNX artifact.

- [ ] **Step 1: Run the complete test suite**

Run: `python -m pytest ml/behavior_recognition/tests -q`

Expected: all tests PASS.

- [ ] **Step 2: Run the two-epoch GPU smoke pipeline**

Run from `ml/behavior_recognition`:

```powershell
./scripts/run_offline_baseline.ps1 -Sources configs/sources.yaml -RunName smoke-seed-20260823 -MaxEpochs 2 -SkipFullTraining
```

Expected: audit, manifest, training, evaluation, and ONNX parity complete without modifying `F:\数据集`.

- [ ] **Step 3: Run full MobileNetV3-Small ROI training**

```powershell
./scripts/run_offline_baseline.ps1 -Sources configs/sources.yaml -RunName v34-roi-seed-20260823 -MaxEpochs 30
```

Expected: early stopping selects `best.pt` by validation Macro-F1 and produces the candidate ONNX.

- [ ] **Step 4: Run the pure-label full-frame diagnostic**

```powershell
python -m behavior_recognition.cli train --config configs/mobilenet_v3_small_full.yaml --manifests manifests --run-dir runs/v34-full-seed-20260823
python -m behavior_recognition.cli evaluate --checkpoint runs/v34-full-seed-20260823/best.pt --manifests manifests --input-mode full --output reports/generated/v34-full-seed-20260823.json --compare-v32 ../../android/app/src/main/assets/models/behavior/campusmate_visible_study_v32.onnx
```

Expected: the report states how many pure-label frames were retained and compares full-frame and ROI results without mixing their sample definitions.

- [ ] **Step 5: Review leakage and metric gates**

Reject the candidate if any group/hash crosses splits, ONNX parity fails, PHONE_INTERACTION performance collapses, or the test metrics do not clearly improve over the comparable V3.2 diagnostic. Record both positive and negative results without selecting thresholds on test.

- [ ] **Step 6: Write the evidence summary**

The committed summary must include dataset counts, anomaly counts, class distribution, split/group statistics, environment, training duration, best epoch, full per-class metrics, Macro-F1, Balanced Accuracy, PHONE_INTERACTION AUPRC, calibration/rejection coverage, V3.2 comparison, ONNX parity, limitations, and the decision `promising_offline_candidate` or `rejected_offline_candidate`.

- [ ] **Step 7: Commit only the compact evidence summary**

```powershell
git add -- ml/behavior_recognition/reports/v34-roi-seed-20260823-summary.md
git commit -m "docs(ml): report behavior baseline results"
```

## Completion Gate

Before claiming completion:

1. Confirm `F:\数据集` source hashes/counts did not change during the run.
2. Confirm all behavior-recognition tests pass.
3. Confirm manifest group/hash isolation.
4. Confirm candidate metrics and V3.2 diagnostics are reported separately.
5. Confirm ONNX Top-1 parity and maximum absolute error.
6. Confirm no generated dataset, checkpoint, or ONNX binary is accidentally staged.
7. Confirm the Android V3.2 asset and runtime selection remain unchanged.
