# Classroom Attention (interactive classroom native player)

Offline research pipeline for the Android「互动课堂」原生播放器的课堂投入识别。
This package consumes only the window-level CSV/JSON facts that the player
already exports; raw camera frames never leave the device, and no names, account
IDs or device identifiers are imported.

The pipeline is deliberately separate from the existing production observation
bar: unless a model passes the pre-registered release gate on **real consented
pilot data**, the Android player keeps showing facts/「无法判断」 and does not
show a student-facing reminder.

## What it does

1. **Import + validate** the existing `ClassroomObservationExport` formats:
   - CSV header produced by `exportCSV` (`window_index` … `unavailable_reason_counts`);
   - JSON `version=1` window arrays.
   Strict checks reject unknown fields, media/identity fields, impossible
   sample counts, inconsistent ratios, illegal reason codes, duplicate window
   indexes, non-monotonic offsets, and path traversal in the manifest.
2. **Align anonymous participants/sessions** through `manifest.csv`
   (`P001`-style participant IDs, `S001`-style session IDs, group labels only).
3. **Merge two independent annotations** with a blind protocol:
   `on_task` / `off_task` / `unobservable`, optional context
   (`quiet_listening`, `note_taking`, `checking_materials`, `clear_off_task`).
   Agreement, Cohen's κ, per-class confusion, disagreement list, and
   adjudication are reported. Unresolved windows are excluded from supervised
   training.
4. **Build the evaluation dataset** with per-window features:
   visibility, valid coverage, invalid ratio, page turns, quiz submissions,
   questions, stage indicators, and optional yaw/pitch statistics.
5. **Train and evaluate** a deterministic logistic regression with
   leave-one-participant-out (LOPO). Standardization, feature selection,
   Platt calibration, and the reminder threshold are fit **inside each training
   fold only**; all windows of a participant stay on one side.
6. **Export a model artifact** with schema version, feature order, median
   imputation, normalization, coefficients, calibration and threshold for
   Android inference. A golden fixture makes Python and Kotlin numbers
   comparable.
7. **Compare** `baseline` (visibility + classroom interactions) and `headpose`
   (+ yaw/pitch) under the same data/participant split and the **same coverage
   gate**. Pooled LOPO metrics use the decision from each participant's
   held-out fold. `comparison.json` reports median fold thresholds for
   reference and the false-alert rates from those fold decisions.

## Reproduce

From `ml/classroom_attention`:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

Full synthetic pipeline (fixture generation → import → merge → dataset →
LOPO comparison → export → golden inference):

```powershell
$env:PYTHONPATH = "src"
python -m classroom_attention.cli run-synthetic `
  --workdir datasets/synthetic_v1 --seed 20261124
```

Step-by-step:

```powershell
$env:PYTHONPATH = "src"
python -m classroom_attention.cli generate-synthetic --output-dir datasets/synthetic_v2 --seed 20261124
python -m classroom_attention.cli validate --manifest datasets/synthetic_v2/manifest.csv --report datasets/synthetic_v2/validation.json
python -m classroom_attention.cli merge --manifest datasets/synthetic_v2/manifest.csv `
  --annotator-a "A01:datasets/synthetic_v2/annotations/A01.csv" `
  --annotator-b "A02:datasets/synthetic_v2/annotations/A02.csv" `
  --adjudication datasets/synthetic_v2/annotations/adjudication.csv `
  --output datasets/synthetic_v2/merged.jsonl --report datasets/synthetic_v2/merge-report.json
python -m classroom_attention.cli build-dataset --manifest datasets/synthetic_v2/manifest.csv `
  --merged datasets/synthetic_v2/merged.jsonl --output datasets/synthetic_v2/dataset.jsonl `
  --report datasets/synthetic_v2/dataset-summary.json
python -m classroom_attention.cli train --dataset datasets/synthetic_v2/dataset.jsonl `
  --output-dir artifacts/synthetic_v2 --feature-set compare --data-source synthetic `
  --annotation-kappa 0.79
python -m classroom_attention.cli golden --dataset datasets/synthetic_v2/dataset.jsonl `
  --model artifacts/synthetic_v2/model-headpose.json --output artifacts/synthetic_v2/golden_inference.json
```

For a real pilot, use separate participant cohorts for training and release
evaluation. Validate, merge and build a dataset for each cohort with the steps
above. Use the same anonymous code for each participant across both sets.
The release check scores the independent dataset with the exported model and
its exact threshold. The independent data stays out of training, calibration
and threshold selection.

```powershell
$trainKappa = (Get-Content datasets/pilot_v1/merge-report.json -Raw | ConvertFrom-Json).kappa
$releaseKappa = (Get-Content datasets/pilot_release_v1/merge-report.json -Raw | ConvertFrom-Json).kappa
python -m classroom_attention.cli train --dataset datasets/pilot_v1/dataset.jsonl `
  --output-dir datasets/pilot_v1/artifacts --feature-set compare --data-source real `
  --annotation-kappa $trainKappa --release-dataset datasets/pilot_release_v1/dataset.jsonl `
  --release-annotation-kappa $releaseKappa
```

`metrics-headpose.json` and `metrics-baseline.json` include the
`release_evaluation` threshold and replay metrics. Keep the release cohort
fixed during acceptance. If its results are used to tune the model, use a
fresh cohort for acceptance.

## Labels and annotation protocol

| Label | Operational definition |
| --- | --- |
| `on_task` | Visible behaviour consistent with the current classroom task: quiet listening, looking at the slide, writing notes, consulting in-class material. Head down for note-taking is **not** off-task by itself. |
| `off_task` | Clearly observable disengagement from the current task: sustained looking away at a phone/another window, leaving the seat, unrelated activity visible in frame. Single ambiguous head pose is insufficient. |
| `unobservable` | Cannot judge: no face, severe occlusion, low light, multiple faces, frozen frame, sampling interruption, or the annotator cannot determine the task context. |

Two annotators label independently from the classroom task plus visible
behaviour. They do not see each other's labels or model output during
annotation. Disagreements go to a third adjudicator; unresolved items stay out
of training and are counted in the report. Target reliability is Cohen's
κ ≥ 0.70.

The device export does not carry a note-taking/course-material tag; those
contexts live only in the annotation CSV and are reported descriptively
(`context` groups). Never infer identity or psychological state from a label.

## Metrics and release gate

Reported per pooled LOPO view and per participant:

- valid observation coverage (`observation_coverage`);
- macro-F1 over `on_task` / `off_task` on covered labelled windows;
- off-task Precision / Recall;
- AUPRC, Brier score and ECE (10 bins);
- false alerts per hour, off-task segment recall, missed segments and
  median/P90 reminder delay;
- groups: glasses, lighting, device, annotation context (descriptive when
  fewer than 3 participants).

Release requires real, consented pilot data with Cohen κ ≥ 0.70 in both
cohorts, and an independent evaluation cohort with at least five labelled
participants. That cohort must contain observable on-task windows and
labelled off-task segments. With the final model and the Android reminder
policy, the pilot thresholds are at least 80% observation coverage, at most
one false alert per hour and at least 50% off-task segment recall.

Segment recall counts each contiguous, labelled off-task episode once, even
if the model abstains. A hit must occur inside the episode at the end of an
off-task window. Replay uses two consecutive complete windows, suppression
during lectures and quizzes, and a 120-second cooldown. Partial, repeated or
missing windows cannot supply consecutive evidence. Delay is measured from the
start of an episode to the end of the window where the reminder is emitted.

## Android handoff

Use the exported artifact directly with `ClassroomAttentionModel.kt`. Copy the
model into the main assets after the independent replay produces
`release.eligible=true`. Android also checks that eligible artifacts declare
real pilot data and the independent release requirements.

```powershell
# Release candidate after metrics-headpose.json reports eligibility
$assets = '..\..\android\app\src\main\assets\classroom_attention'
New-Item -ItemType Directory -Path $assets -Force | Out-Null
Copy-Item datasets/pilot_v1/artifacts/model-headpose.json (Join-Path $assets 'model.json')

# Development preview: used by Debug only when the main asset is absent.
Copy-Item datasets/synthetic_v1/artifacts/model-headpose.json `
  ..\..\android\app\src\debug\assets\classroom_attention\model-preview.json

# Golden fixture for the Kotlin parity test.
Copy-Item datasets/synthetic_v1/artifacts/golden_inference.json `
  ..\..\android\app\src\test\resources\classroom_attention\golden_inference.json
```

Run the Kotlin checks from `android/` with JDK 21:

```powershell
.\gradlew.bat :app:testDebugUnitTest --tests "*ClassroomAttention*"
```

Roll back by deleting `android/app/src/main/assets/classroom_attention/model.json`
or by keeping `release.eligible=false`; a missing or incompatible artifact falls
back to fact-only observation without changing the UI code.

## Files

- `src/classroom_attention/schema.py` — strict window/manifest contracts;
- `src/classroom_attention/windows.py` — CSV/JSON import and validation;
- `src/classroom_attention/annotations.py` — blind dual merge, κ, adjudication;
- `src/classroom_attention/features.py` — window features and observability gate;
- `src/classroom_attention/model.py` — logistic regression, Platt calibration,
  artifact schema and Python inference;
- `src/classroom_attention/metrics.py` — selective classification, AUPRC, ECE,
  alert episodes, delays, per-participant/group summaries;
- `src/classroom_attention/train.py` — LOPO, threshold selection, B/C comparison,
  release conditions;
- `src/classroom_attention/synthetic.py` — deterministic fixture;

## Synthetic fixture caveat

`datasets/synthetic_v1` is generated. Its metrics verify code and numeric
consistency only; they are not evidence about real students. The comparison
shows whether the pipeline can detect an incremental head-pose effect, not
whether such an effect exists in a real classroom.

## Known limitations

- No consented real pilot windows are in this repository; every release gate
  remains closed.
- Raw frames are device-memory only; this pipeline cannot inspect video or
  verify annotation against footage.
- The device export has no note-taking/course-material tag; those contexts are
  annotation-only and self-report is not used as ground truth.
- Glasses/lighting/device subgroups are small in the synthetic fixture and
  must be re-estimated on real data; do not generalize the numbers.
- Real device camera behaviour (permissions, background, rotation, thermal and
  battery effects) is outside this offline package.
