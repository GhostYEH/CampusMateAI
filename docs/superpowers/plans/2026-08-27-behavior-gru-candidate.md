# MobileNetV3 + GRU Behavior Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and smoke-train an isolated four-class MobileNetV3 + GRU temporal behavior candidate from the three ordered YOLO frame sequences.

**Architecture:** Convert annotated detections into leak-free per-video tracks and fixed 16-frame windows. Encode frames with MobileNetV3-Small, aggregate embeddings with a GRU, and train a four-class head without modifying the current ONNX or Android assets.

**Tech Stack:** Python 3.13, PyTorch 2.13, torchvision 0.28, Pillow, PyYAML, pytest, CUDA 13

**Spec:** `docs/superpowers/specs/2026-08-27-behavior-gru-candidate-design.md`

## Global Constraints

- Preserve `ml/behavior_recognition/exports/v34-roi-seed-20260823/campusmate_behavior_v34_candidate.onnx` byte-for-byte.
- Preserve the canonical class order `READ`, `WRITE`, `PHONE_INTERACTION`, `NO_VISIBLE_STUDY`.
- Keep every four-digit source-video prefix wholly inside one split.
- Never modify files under `F:\数据集`.
- Treat the three-video result as exploratory and never promote it into Android assets.

---

### Task 1: Temporal track and window manifests

**Files:**
- Create: `ml/behavior_recognition/src/behavior_recognition/temporal_manifest.py`
- Create: `ml/behavior_recognition/tests/test_temporal_manifest.py`

**Interfaces:**
- Consumes: YOLO `images/{train,val}` and `labels/{train,val}` plus the existing source-class mapping.
- Produces: `build_temporal_manifests(dataset_root: Path, output_dir: Path, *, sequence_length: int, seed: int) -> TemporalManifestSummary` and split CSV files containing ordered crop metadata.

- [ ] **Step 1: Write failing grouping and split tests**

```python
def test_video_prefix_is_the_first_four_digits():
    assert video_id_from_stem("40010234") == "4001"

def test_source_video_never_crosses_splits(tmp_path):
    summary = build_temporal_manifests(make_tiny_source(tmp_path), tmp_path / "out", sequence_length=2, seed=7)
    owners = {(row.video_id, row.split) for row in summary.windows}
    assert all(sum(video == candidate for video, _ in owners) == 1 for candidate in {v for v, _ in owners})
```

- [ ] **Step 2: Run `python -m pytest tests/test_temporal_manifest.py -q` and verify failure because the module does not exist.**

- [ ] **Step 3: Implement deterministic frame parsing, IoU/center-distance matching, track expiry, stable-label windows, whole-video split allocation, CSV output, and diagnostic counts.**

- [ ] **Step 4: Run `python -m pytest tests/test_temporal_manifest.py -q` and verify all tests pass.**

- [ ] **Step 5: Commit `feat: build leak-free temporal behavior manifests`.**

### Task 2: Sequence dataset and GRU model

**Files:**
- Create: `ml/behavior_recognition/src/behavior_recognition/temporal_data.py`
- Create: `ml/behavior_recognition/src/behavior_recognition/temporal_models.py`
- Create: `ml/behavior_recognition/tests/test_temporal_data.py`
- Create: `ml/behavior_recognition/tests/test_temporal_models.py`

**Interfaces:**
- Consumes: temporal window CSV rows from Task 1.
- Produces: `TemporalBehaviorDataset`, `TemporalBehaviorModel`, `build_temporal_model`, `freeze_encoder`, and `unfreeze_encoder_tail`.

- [ ] **Step 1: Write failing tests for `[T,C,H,W]` dataset tensors, `[B,T,C,H,W] -> [B,4]` model output, GRU dimensions, and encoder freeze/unfreeze behavior.**
- [ ] **Step 2: Run the four targeted tests and verify imports or assertions fail.**
- [ ] **Step 3: Implement sequence-consistent crop loading and a MobileNetV3 feature encoder followed by one-layer GRU(256) and a four-class linear head.**
- [ ] **Step 4: Run `python -m pytest tests/test_temporal_data.py tests/test_temporal_models.py -q` and verify all tests pass.**
- [ ] **Step 5: Commit `feat: add temporal MobileNetV3 GRU model`.**

### Task 3: Two-phase trainer and CLI

**Files:**
- Create: `ml/behavior_recognition/src/behavior_recognition/temporal_train.py`
- Create: `ml/behavior_recognition/configs/mobilenet_v3_gru.yaml`
- Create: `ml/behavior_recognition/tests/test_temporal_train.py`
- Create: `ml/behavior_recognition/tests/test_temporal_cli.py`
- Modify: `ml/behavior_recognition/src/behavior_recognition/cli.py`

**Interfaces:**
- Consumes: Task 1 manifests, Task 2 dataset/model, optional current candidate ONNX path.
- Produces: `train_temporal_model(...) -> Path`, `temporal-manifest` CLI command, `temporal-train` CLI command, `best.pt`, `last.pt`, `history.csv`, and environment/config metadata.

- [ ] **Step 1: Write a failing tiny CPU training test that asserts a reloadable temporal checkpoint and phase metadata.**
- [ ] **Step 2: Run `python -m pytest tests/test_temporal_train.py -q` and verify failure.**
- [ ] **Step 3: Implement class-weighted two-phase training, AMP, clipping, deterministic loading, early stopping, and atomic best/last checkpoints. Record a clear initialization status; reject an incompatible requested ONNX import rather than silently falling back.**
- [ ] **Step 4: Add the two temporal CLI commands and the 16-frame GPU configuration.**
- [ ] **Step 5: Run `python -m pytest tests/test_temporal_train.py tests/test_temporal_cli.py -q` and verify all selected tests pass.**
- [ ] **Step 6: Commit `feat: train temporal behavior candidates`.**

### Task 4: Real manifest, smoke training, and verification

**Files:**
- Modify: `ml/behavior_recognition/README.md`
- Generate ignored artifacts under `ml/behavior_recognition/manifests_temporal/` and `ml/behavior_recognition/runs_temporal/`.

**Interfaces:**
- Consumes: real source `F:\数据集\0.671k_university_yolo_Dataset` and the committed temporal pipeline.
- Produces: audited manifests, a CUDA smoke checkpoint, history, and a concise reproducibility command.

- [ ] **Step 1: Generate real temporal manifests and verify video ownership, class counts, exclusions, and zero cross-split leakage.**
- [ ] **Step 2: Run a one-epoch limited CUDA smoke training and verify finite loss, non-empty validation predictions, checkpoint reload, and GPU metadata.**
- [ ] **Step 3: Run the full `ml/behavior_recognition` pytest suite.**
- [ ] **Step 4: Document exact commands and limitations without changing Android assets.**
- [ ] **Step 5: Run `git diff --check`, inspect scoped changes, confirm the production ONNX SHA-256 is unchanged, and commit `docs: document temporal behavior training`.**
