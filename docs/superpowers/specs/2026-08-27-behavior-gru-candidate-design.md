# MobileNetV3 + GRU Behavior Candidate Design

## Objective

Build an independent temporal behavior-recognition candidate without replacing the existing single-frame ONNX model or any Android production asset. The candidate consumes ordered person crops and predicts the existing four classes: `READ`, `WRITE`, `PHONE_INTERACTION`, and `NO_VISIBLE_STUDY`.

## Data constraints

The current training source contains 671 annotated frames from three numeric sequences: `4001`, `4002`, and `4003`. Individual frames contain multiple YOLO boxes but no persistent person identifier. The existing image-level train/validation folders mix frames from the same source sequence, so they must not be reused as temporal split boundaries.

For this first candidate, each four-digit filename prefix is treated as one independent source video. All derived tracks and windows from a source video stay in one split. Two videos are used for training and one for validation, selected deterministically to retain the best feasible four-class coverage. This three-video experiment is a development baseline only; it cannot satisfy the existing production promotion gate or establish subject-independent generalization.

## Architecture

The model has three explicit parts:

1. A MobileNetV3-Small frame encoder produces one feature vector per crop.
2. A single-layer unidirectional GRU with hidden size 256 consumes the ordered frame embeddings.
3. A linear classifier maps the final valid GRU state to the existing four output classes in their current order.

The input contract is `[batch, time, 3, 224, 224]` plus sequence lengths. Initial windows contain 16 frames. The encoder runs on the flattened batch-time dimension so each frame is processed exactly once.

The current single-frame candidate ONNX remains immutable. The implementation first attempts to import its MobileNetV3 feature weights into the PyTorch encoder and verifies numerical agreement at the single-frame logits boundary. If reliable import is not possible, training stops with an actionable error instead of silently claiming to reuse the current model. An explicit ImageNet fallback may be added later, but is not part of this approved run.

## Track construction

Frames are ordered numerically within each source video. Person detections are associated across adjacent frames using deterministic bipartite matching over IoU and normalized center displacement. A match is accepted only when class continuity and geometry thresholds pass. Unmatched detections start new tracks; tracks expire after a small configurable frame gap.

Only the four mapped source classes are retained. A window must have a stable target label and enough observed frames. Ambiguous transitions, label conflicts, and tracks shorter than the configured minimum are excluded and reported. Crops use the same expansion and normalization contract as the single-frame baseline. Spatial augmentation is sampled once per sequence where geometry must remain consistent; color augmentation may vary by frame.

## Training

Training has two phases:

1. Freeze the frame encoder and train the GRU and classifier.
2. Unfreeze the final MobileNetV3 feature blocks and jointly fine-tune them with a lower encoder learning rate.

Class-weighted cross entropy, gradient clipping, AMP, deterministic seeds, early stopping, and Macro-F1 checkpoint selection follow the existing baseline conventions. The first execution is a small GPU smoke run that proves data loading, forward/backward passes, checkpoint persistence, and validation. Full training starts only after the smoke run passes.

Generated manifests, track diagnostics, checkpoints, and histories live under ignored `ml/behavior_recognition` artifact directories. No raw dataset files are modified.

## Evaluation and safety

The candidate is compared with the current single-frame model using validation Macro-F1, per-class precision/recall, confusion matrix, prediction-switch rate, and event stability. Because only three source videos exist, results are labeled exploratory and are not used to replace the production model.

The existing ONNX asset and Android integration are out of scope. Promotion requires additional independently recorded continuous front-camera videos, subject-isolated train/validation/test splits, event-level evaluation, device latency testing, and the existing reminder-safety gates.

## Tests

Tests cover deterministic video grouping, leak-free split ownership, track association, label-transition rejection, fixed-length window sampling, tensor shapes, variable sequence lengths, encoder freezing, checkpoint reload, and a tiny CPU training pass. The implementation follows red-green-refactor cycles and runs the existing `ml/behavior_recognition` test suite before any completion claim.
