# CampusMateAI Behavior Recognition Offline Baseline

This package builds an auditable offline MobileNetV3-Small baseline from YOLO classroom annotations. It treats configured source dataset directories as read-only and does not replace the Android V3.2 production asset.

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
$repoRoot = (git rev-parse --show-toplevel).Trim()
Set-Location (Join-Path $repoRoot 'ml\behavior_recognition')
python -m pip install -e .
python -m pip install -r requirements.txt
```

For direct source execution:

```powershell
$env:PYTHONPATH = "src"
```

## Data sources

Copy `configs/sources.example.yaml` to the ignored local file `configs/sources.yaml`, then replace each placeholder with a local read-only dataset directory. Only the university dataset is marked training-ready because its six-class mapping is verified. The larger Handrise/Read/Write and Bow/Turn sets remain audit-only until their numeric label order is verified from authoritative metadata or a reviewed visual audit.

The university mapping is:

```text
0 Raise_hand          excluded
1 Read                READ
2 Write               WRITE
3 OnPhone             PHONE_INTERACTION
4 Bow_head            excluded from primary training
5 Leaning_over_table  NO_VISIBLE_STUDY
```

The source names and counts can be checked against Table III of the
[SCB-Dataset3 paper](https://arxiv.org/html/2310.02522). Source class 5 describes
leaning over the table; its mapped product label does not establish that a
student is asleep. The earlier `0.355k_university_yolo_Dataset` archive can
share the same classroom sequences with the frame-interpolated 671-image
archive. Audit its class mapping and frame overlap before using it; source
directory names do not establish independent videos or additional samples.

The university data contains only three video prefixes. Keep each complete
prefix in one split, including when frames occur in different original
train/validation folders. A three-way split therefore has just one video per
split and cannot support subject-independent or front-camera quality claims.
The ordered frames can support an offline temporal pilot, but frame labels
provide neither verified person tracks nor event onset/offset annotations.

Invalid boxes are rejected or clipped only in generated manifests. Original labels remain unchanged.

## Commands

When the V3.4 training checkpoint is unavailable, `onnx_finetune.OnnxBehaviorModel`
can reconstruct its existing fused inference graph as a differentiable module.
It retains the trained convolution/Gemm weights and classification head, and
supports only the operators in that graph. Before using it, verify both logits
and predicted classes against the original ONNX Runtime model on random and
real ROI inputs. Fused BatchNorm cannot recover its old running statistics;
fine-tuning updates the equivalent fused parameters. Save new checkpoints
separately with the original graph hash; this offline checkpoint type requires
the matching source graph and is not accepted by the standard baseline exporter.
Its `export_onnx` method writes updated tensors into the same graph and refuses
existing output paths. Verify exported logits before considering deployment.
It does not update deployment assets. Use the same preprocessing and fixed
video splits to compare the original and fine-tuned models, and do not describe
the re-split data as unseen by the inherited model without its old split manifest.

### Preserving existing weights with L2-SP

`l2sp_experiment` compares terminal-classifier-only fine-tuning, full fine-tuning,
and two full-network L2-SP strengths, all initialized from the same V3.4 ONNX.
The L2-SP term is `alpha * 0.5 * sum((weights - initial_weights)^2)` without
parameter-count normalization. This adapts the regularization idea from
[Li et al., ICML 2018](https://proceedings.mlr.press/v80/li18a.html) to the existing
four-class model; it is not a reproduction of the paper's datasets or numbers.
The terminal Gemm weight and bias retain their original values before training.
All arms share a seed, augmentation, loss and data splits. Full-network arms
also share their learning rate. Adam uses no ordinary weight decay, so the
L2-SP constraint is not confounded with an added zero-centered penalty.

```powershell
$env:PYTHONPATH = "src"
python -m behavior_recognition.l2sp_experiment `
  --source-onnx $env:CAMPUSMATE_BEHAVIOR_SOURCE_ONNX `
  --manifests $env:CAMPUSMATE_BEHAVIOR_MANIFESTS `
  --output-dir artifacts/l2sp_new_run --epochs 6 --workers 2
```

Choose a new output directory for every run. The plan records source and
manifest hashes before training, and rejects cross-split video/hash/sample
overlap. ROI expansion is 1.1 to match V3.4, with lossless PNG caching.
Candidate checkpoints are selected using validation only. An arm must improve
validation Macro-F1 and retain at least the original validation accuracy to
be eligible. The decision is saved before all locked candidates are evaluated
on test, including rejected candidates for an honest comparison. A selected
candidate is exported into the run directory and checked against its PyTorch
logits and classes on real ROIs; production assets are never modified.
The three-video benchmark and its previously reported test results support an
exploratory offline comparison, not independent generalization or deployment.

### SAV adaptation with four-class replay

`sav_replay_experiment` adapts the existing V3.4 single-frame branch using
official SAV keyframes and retains the four-output model contract. It pairs a
replay-only control with replay plus SAV, using identical old-data batches,
learning rate, seed, regularization, and a fixed equal epoch/step budget.
This paired experiment uses FP32 with TF32 disabled and aborts non-finite
gradients instead of silently skipping optimizer updates.
SAV adds a weighted set-label loss: read permits READ, take_notes permits WRITE,
and simultaneous read/take_notes permits their probability sum. This preserves
ambiguity in a mutually exclusive head; it does not learn simultaneous labels.
Other SAV actions produce no negative or NO_VISIBLE_STUDY labels.

The selected ten videos must have completed downloads and verified
`prepared_labels` JSON with timestamp 1 / frame 31, normalized boxes, and
original action IDs. Whole source videos from the same date stay together:
training uses 20181016, 20181017, 20200901; validation uses 20181018; test uses
20200902, 20200903. Student identities remain unknown. Pure WRITE is scarce
and no phone examples exist in SAV, so results cannot establish independent
WRITE accuracy, phone accuracy, or four-class precision on the new domain.

```powershell
$env:PYTHONPATH = "src"
python -m behavior_recognition.sav_replay_experiment `
  --source-onnx $env:CAMPUSMATE_BEHAVIOR_SOURCE_ONNX `
  --replay-manifests $env:CAMPUSMATE_BEHAVIOR_MANIFESTS `
  --replay-cache $env:CAMPUSMATE_BEHAVIOR_REPLAY_CACHE `
  --sav-root $env:CAMPUSMATE_SAV_ROOT `
  --output-dir artifacts/sav_new_run --epochs 6 --workers 2
```

The ROI cache must match the existing L2-SP plan's manifest hashes and
preprocessing. Source-image SHA256 and exact recomputed crop pixels are checked
before cache reuse. The SAV source-video counts must be 6/2/2 for train/val/test.
SAV uses full keyframes with ROI expansion 1.1. Validation must
retain original SCB accuracy, Macro-F1, all per-class F1, phone AUPRC and recall,
as well as SAV source-video-mean acceptable top-1 rate, while reducing SAV
source-video-mean set NLL. The choice is persisted before evaluating either
test. SAV scores describe recognition of positive set-labelled student ROIs,
not general four-class accuracy. SCB test remains an exposed diagnostic.
Checkpoints, comparison and parity records stay in the new run directory;
production assets are never replaced by this command.

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

### Paper-inspired local-region ablation (offline only)

Inspired by [CPViG-Net](https://doi.org/10.11896/jsjkx.250500100), the
`local_cue` variant shares a MobileNetV3 encoder between the full student
ROI and a lower-central crop where hands, books and a phone may appear. It is
an experimental image prior, not a phone detector or a deployment model.
Train it against the unchanged ROI baseline using the same manifests and seed:

```powershell
$env:PYTHONPATH = "src"
python -m behavior_recognition.cli train --config configs/mobilenet_v3_small_roi_paper_baseline.yaml --manifests manifests --run-dir runs/paper_full_roi
python -m behavior_recognition.cli train --config configs/mobilenet_v3_small_roi_local_cue.yaml --manifests manifests --run-dir runs/paper_local_cue
python -m behavior_recognition.local_cue_experiment --baseline runs/paper_full_roi/best.pt --local-cue runs/paper_local_cue/best.pt --manifests manifests --output reports/generated/local_cue_validation.json
```

The comparison uses validation only and reports four-class and product
Macro-F1, PHONE_INTERACTION AUPRC/precision/recall, and confusion matrices.
Both paper experiment configs use batch size 32 and the same training settings.
The existing ONNX export path supports only the single-view baseline.

### Temporal MobileNetV3 + GRU candidate

Build 16-frame windows from the three ordered university frame sequences. The builder merges the original image-level folders, tracks same-label boxes across adjacent frames, and assigns each complete four-digit video prefix to exactly one split:

```powershell
$env:PYTHONPATH = "src"
python -m behavior_recognition.cli temporal-manifest `
  --dataset-root $env:CAMPUSMATE_BEHAVIOR_DATASET_ROOT `
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
  --source-onnx "exports\v34-roi-seed-20260823\campusmate_behavior_v34_candidate.onnx"
```

Fuse the original frame encoder and the trained GRU into one fixed-shape ONNX model:

```powershell
python -m behavior_recognition.cli temporal-export `
  --checkpoint runs_temporal\full-current-onnx-20260827\best.pt `
  --source-onnx "exports\v34-roi-seed-20260823\campusmate_behavior_v34_candidate.onnx" `
  --output exports_temporal\full-current-onnx-20260827
```

The fused model accepts `frames` with shape `[1, 16, 3, 224, 224]` and returns four `logits`. Export fails if the source ONNX SHA-256 differs from the model used during GRU training or if fused-vs-two-stage parity exceeds `1e-4`. A successful export writes an immutable artifact set under `generations/<content-id>/` and atomically updates `current.json`; consumers should resolve the model path from that pointer.

This route preserves and actually executes the current ONNX frame encoder; it does not substitute ImageNet weights under the same name. Because the original PyTorch checkpoint is unavailable, the encoder remains frozen and only the GRU and four-class head train. The three-video split is suitable for pipeline development but not production promotion or subject-independent accuracy claims.

Audit a temporal artifact without modifying it:

```powershell
$repoRoot = (git rev-parse --show-toplevel).Trim()
python -m behavior_recognition.cli temporal-audit `
  --model (Join-Path $repoRoot 'android\app\src\main\assets\models\behavior\campusmate_tsm_mobilenetv2_v4.onnx') `
  --model-card (Join-Path $repoRoot 'harmony\entry\src\main\resources\rawfile\models\behavior\model_card.json') `
  --output reports\generated\v4-temporal-audit.json
```

The audit verifies the source hash, ONNX input/output metadata, label order, and training provenance. The currently packaged V4 records conversion parity but its ONNX graph exposes symbolic input/output dimensions while the model card declares fixed shapes, and it has no `training_provenance` block. These are reproducibility/contract failures; the audit does not invent missing dataset, checkpoint, or code-revision values.

## Local artifacts

Generated content is ignored by Git:

```text
artifacts/roi-cache/       derived 224x224 student crops
manifests/                 absolute-path train/val/test manifests
runs/                      checkpoints and histories
manifests_temporal/        leak-free temporal window manifests
runs_temporal/             GRU checkpoints, logs, and derived feature ONNX
exports_temporal/          atomic pointer plus versioned fused temporal artifacts
reports/generated/         machine-readable audit/evaluation reports
exports/                   candidate ONNX, labels, parity, and model card
```

Interrupted training can be restarted safely. Existing ROI cache files and downloaded torchvision weights are reused; the training run itself starts from a new optimizer state unless explicit resume support is added in a later approved design.

CUDA float16 training uses a persistent gradient scaler, unscales before
gradient clipping, and skips non-finite optimizer updates. Epoch loss is the
global weighted cross-entropy mean (including label smoothing), so changing
validation batch size does not change the reported loss. Frozen temporal
encoder blocks keep BatchNorm statistics and dropout in evaluation mode;
only explicitly unfrozen tail blocks return to training mode. Checkpoint
evaluation restores the configured single-view or local-cue model without
downloading pretrained weights.

## Interpretation and limits

- Compare candidate four-class Macro-F1, Balanced Accuracy, per-class metrics, and PHONE_INTERACTION AUPRC.
- Evaluation also reports the product space `STUDY_ACTIVITY`, `PHONE_INTERACTION`, and `NO_VISIBLE_STUDY`. It sums READ/WRITE probabilities before selecting the product prediction; it does not collapse an already selected four-class label.
- Treat V3.2 results as a separate binary diagnostic; its Accuracy is not comparable to four-class Accuracy.
- Validation selects checkpoints, temperature, and rejection thresholds. Test is reserved for the locked candidate.
- The public dataset contains distant multi-student classroom views. Offline gains do not establish front-camera or real-device gains.
- Do not copy the candidate ONNX into Android assets until real front-camera evaluation, device latency, temperature, power, and reminder replay all pass the project route criteria.

Compare two evaluation reports using validation metrics only:

```powershell
python -m behavior_recognition.cli offline-compare `
  --baseline reports\generated\baseline.json `
  --candidate reports\generated\candidate.json `
  --output reports\generated\offline-decision.json
```

The command checks product Macro-F1, PHONE_INTERACTION AUPRC, calibration error, and rejection coverage. `advanced=true` means only that the candidate merits another offline experiment. The output always records `production_approved=false`; production approval remains the target-domain event gate below.

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
