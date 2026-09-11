# Learner State Evaluation

This package defines a deterministic offline contract for evaluating CampusMateAI misconception predictions. It accepts strict JSONL annotations and predictions, then emits machine-readable binary and calibration metrics without reading application databases.

The checked-in `c-misconception-synthetic-v1` dataset contains 100 curated synthetic contract cases across five C-language misconception codes. It is explicitly marked `synthetic_curated` and `decision_eligible=false`. Its scores must not be presented as real student, production-model, or competition effectiveness results. A separately authorized and reviewed human dataset is still required for such claims.

## Reproduce

From this directory:

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
python -m learner_state_evaluation.dataset
python -m learner_state_evaluation.cli validate-dataset `
  --annotations datasets/c_language_misconception_v1.jsonl `
  --manifest datasets/c_language_misconception_v1.manifest.json `
  --output reports/generated/dataset-validation.json
```

Evaluate a future candidate whose prediction JSONL contains exactly one row per annotation:

```powershell
python -m learner_state_evaluation.cli evaluate `
  --annotations datasets/c_language_misconception_v1.jsonl `
  --manifest datasets/c_language_misconception_v1.manifest.json `
  --predictions path/to/predictions.jsonl `
  --output reports/generated/evaluation.json
```

Annotation rows contain only stable codes, boolean labels, bounded evidence counts, quality/decision enums, and explicit privacy metadata. Prediction rows contain only `sample_id`, boolean `predicted_label`, positive-class `score`, `model_version`, and `prediction_source`. Unknown fields are rejected so names, raw code, answers, compiler output, credentials, and free text cannot silently enter this dataset.

Reports include TP/FP/TN/FN, Precision, Recall, F1, ROC AUC when both classes exist, Brier score, ECE, per-hypothesis metrics, and unsupported-assertion rate. Output has no wall-clock timestamp, so identical inputs produce identical bytes.
