# CampusMateAI Behavior Recognition Offline Baseline

This package builds an auditable offline MobileNetV3-Small baseline from YOLO classroom annotations. It never edits `F:\数据集` and it does not replace the Android V3.2 production asset.

## Output contract

The candidate ONNX output order is fixed:

```text
0 READ
1 WRITE
2 PHONE_INTERACTION
3 NO_VISIBLE_STUDY
```

`PHONE_INTERACTION` is observable phone handling, not proof of distraction. Low-confidence or conflicting outputs are rejected as `UNCERTAIN` by calibrated thresholds rather than trained as a fifth class.

## Environment

The verified machine environment at implementation time was Python 3.13, PyTorch 2.13, torchvision 0.28, CUDA 13.0, and an NVIDIA GeForce RTX 5060 Laptop GPU.

Install the package only when the existing environment does not already provide the requirements:

```powershell
Set-Location D:\File\demo1\.worktrees\behavior-recognition-v34\ml\behavior_recognition
python -m pip install -e .
python -m pip install -r requirements.txt
```

For direct source execution:

```powershell
$env:PYTHONPATH = "src"
```

## Data sources

`configs/sources.yaml` currently treats only `F:\数据集\0.671k_university_yolo_Dataset` as training-ready because its six-class mapping is verified. The larger Handrise/Read/Write and Bow/Turn sets remain audit-only until their numeric label order is verified from authoritative metadata or a reviewed visual audit.

The university mapping is:

```text
0 Raise_hand          excluded
1 Read                READ
2 Write               WRITE
3 OnPhone             PHONE_INTERACTION
4 Bow_head            excluded from primary training
5 Sleep               NO_VISIBLE_STUDY
```

Invalid boxes are rejected or clipped only in generated manifests. Original labels remain unchanged.

## Commands

Run tests:

```powershell
python -m pytest -q
```

Run a two-epoch smoke pipeline:

```powershell
./scripts/run_offline_baseline.ps1 -RunName smoke-seed-20260823 -MaxEpochs 2 -SkipFullTraining
```

Run full training:

```powershell
./scripts/run_offline_baseline.ps1 -RunName v34-roi-seed-20260823 -MaxEpochs 30
```

The pipeline performs environment preflight, data audit, grouped manifest creation, tests, ROI cache generation, training, calibration, V3.2 comparison, and ONNX parity export.

### Temporal MobileNetV3 + GRU candidate

Build 16-frame windows from the three ordered university frame sequences. The builder merges the original image-level folders, tracks same-label boxes across adjacent frames, and assigns each complete four-digit video prefix to exactly one split:

```powershell
$env:PYTHONPATH = "src"
python -m behavior_recognition.cli temporal-manifest `
  --dataset-root "F:\数据集\0.671k_university_yolo_Dataset" `
  --output manifests_temporal `
  --sequence-length 16 `
  --stride 8
```

Train the GRU from the current single-frame candidate's frozen 1024-dimensional ONNX features:

```powershell
python -m behavior_recognition.cli temporal-train `
  --config configs\mobilenet_v3_gru.yaml `
  --manifests manifests_temporal `
  --run-dir runs_temporal\full-current-onnx-20260827 `
  --source-onnx "D:\File\demo1\ml\behavior_recognition\exports\v34-roi-seed-20260823\campusmate_behavior_v34_candidate.onnx"
```

Fuse the original frame encoder and the trained GRU into one fixed-shape ONNX model:

```powershell
python -m behavior_recognition.cli temporal-export `
  --checkpoint runs_temporal\full-current-onnx-20260827\best.pt `
  --source-onnx "D:\File\demo1\ml\behavior_recognition\exports\v34-roi-seed-20260823\campusmate_behavior_v34_candidate.onnx" `
  --output exports_temporal\full-current-onnx-20260827
```

The fused model accepts `frames` with shape `[1, 16, 3, 224, 224]` and returns four `logits`. Export fails if the source ONNX SHA-256 differs from the model used during GRU training or if fused-vs-two-stage parity exceeds `1e-4`.

This route preserves and actually executes the current ONNX frame encoder; it does not substitute ImageNet weights under the same name. Because the original PyTorch checkpoint is unavailable, the encoder remains frozen and only the GRU and four-class head train. The three-video split is suitable for pipeline development but not production promotion or subject-independent accuracy claims.

## Local artifacts

Generated content is ignored by Git:

```text
artifacts/roi-cache/       derived 224x224 student crops
manifests/                 absolute-path train/val/test manifests
runs/                      checkpoints and histories
manifests_temporal/        leak-free temporal window manifests
runs_temporal/             GRU checkpoints, logs, and derived feature ONNX
exports_temporal/          fused temporal ONNX, parity, labels, and model card
reports/generated/         machine-readable audit/evaluation reports
exports/                   candidate ONNX, labels, parity, and model card
```

Interrupted training can be restarted safely. Existing ROI cache files and downloaded torchvision weights are reused; the training run itself starts from a new optimizer state unless explicit resume support is added in a later approved design.

## Interpretation and limits

- Compare candidate four-class Macro-F1, Balanced Accuracy, per-class metrics, and PHONE_INTERACTION AUPRC.
- Treat V3.2 results as a separate binary diagnostic; its Accuracy is not comparable to four-class Accuracy.
- Validation selects checkpoints, temperature, and rejection thresholds. Test is reserved for the locked candidate.
- The public dataset contains distant multi-student classroom views. Offline gains do not establish front-camera or real-device gains.
- Do not copy the candidate ONNX into Android assets until real front-camera evaluation, device latency, temperature, power, and reminder replay all pass the project route criteria.

## Target front-camera event workflow

New front-camera annotations use `configs/target_front_camera.yaml` and
`event_manifest.build_event_manifest`. The builder requires explicit consent,
keeps each subject in one split, rejects duplicated videos attributed to
different subjects, and excludes overlapping contradictory labels.

Product evaluation folds READ/WRITE into `STUDY_ACTIVITY`; `UNCERTAIN` remains
an abstention state and is never a trainable class. Frame outputs pass through
`temporal.BehaviorEventAggregator`, which applies phone-entry duration, exit
hysteresis, and reminder cooldown. Promotion is decided by
`promotion_gate.evaluate_promotion`, using event Macro-F1, PHONE event
Precision/Recall, false reminders per hour, p95 detection latency, coverage,
and per-device precision. Frame Accuracy alone cannot approve a candidate.
