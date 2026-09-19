# Learner State Evaluation

This package defines a deterministic offline contract for evaluating CampusMateAI learner state predictions and planning safety. It accepts strict JSONL annotations and predictions, then emits machine-readable binary and calibration metrics without reading application databases.

## Reproduce

From this directory:

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
```

Annotation rows contain only stable codes, boolean labels, bounded evidence counts, quality/decision enums, and explicit privacy metadata. Prediction rows contain only `sample_id`, boolean `predicted_label`, positive-class `score`, `model_version`, and `prediction_source`. Unknown fields are rejected so names, raw code, answers, compiler output, credentials, and free text cannot silently enter this dataset.

Reports include TP/FP/TN/FN, Precision, Recall, F1, ROC AUC when both classes exist, Brier score, ECE, per-hypothesis metrics, and unsupported-assertion rate. Output has no wall-clock timestamp, so identical inputs produce identical bytes.

The same evaluator also contains a separate, fully synthetic planning safety benchmark (120 cases by default). Reproduce it offline with:

```powershell
python -m learner_state_evaluation.cli evaluate-planning `
  --output path/to/planning-evaluation.json
```

It reports priority agreement, deadline/evidence coverage, invalid recommendation rate, stale-plan detection, deterministic fallback, idempotent execution, unauthorized-action, and schema-validity metrics. It contains no learner identifiers, task text, event payloads, credentials, or raw course material.

## Phase 8A/8B — truthful CampusMate-LM benchmark

Only a successful, schema-valid response from the explicitly configured
OpenAI-compatible client may claim `REAL_MODEL`. The input-only
`DETERMINISTIC_BASELINE` never reads `expected_output` and is comparison-only;
fixtures, oracle references, and fallbacks are never promotion evidence.

The repository currently contains no authorized CampusMate-LM weights. Asset
inventory recognizes a non-empty GGUF file or a bounded Hugging Face-style
directory containing config, tokenizer metadata, and weights. Local assets
still require an authorized serving runtime. The executable route today is an
explicitly enabled OpenAI-compatible CampusMate-LM service. Configuration alone
does not prove inference: only valid observed responses count. Production and
Canary remain disabled.

Reproduce the safe local checks from this directory:

```powershell
$env:PYTHONPATH = "src"
$dataset = "datasets/campusmate_lm_shadow_v1.jsonl"
python -m learner_state_evaluation.model_shadow.real_benchmark inventory
python -m learner_state_evaluation.model_shadow.real_benchmark preflight --dataset $dataset
python -m learner_state_evaluation.model_shadow.real_benchmark run-baseline `
  --dataset $dataset --output-dir (Join-Path $env:TEMP "campusmate-phase8-baseline")
python -m learner_state_evaluation.model_shadow.real_benchmark run-blocked `
  --dataset $dataset --output-dir (Join-Path $env:TEMP "campusmate-phase8-blocked") `
  --reason MODEL_RUNTIME_UNAVAILABLE
```

For an authorized service, set placeholders only in the current shell and never
commit their values:

```powershell
$env:CAMPUSMATE_LM_SHADOW_ENABLED = "true"
$env:CAMPUSMATE_LM_BASE_URL = "<authorized-openai-compatible-url>"
$env:CAMPUSMATE_LM_MODEL = "<authorized-model-id>"
$env:CAMPUSMATE_LM_API_KEY = "<runtime-secret>"
python -m learner_state_evaluation.model_shadow.real_benchmark preflight --dataset $dataset
python -m learner_state_evaluation.model_shadow.real_benchmark run-real `
  --dataset $dataset --output-dir (Join-Path $env:TEMP "campusmate-phase8-real") `
  --model-version "<authorized-model-version>" --temperature 0 --max-tokens 512
```

Inference is limited to the held-out `test` split (52 rows: KC 18, error 14,
summary 10, tool routing 10). Reports distinguish complete real coverage,
mixed fallback, and total fallback per capability. Missing token, device,
memory, or cost measurements stay `null`, never zero. Use `evaluate` for an
external prediction file and `compare` for generated reports. Never commit
weights, caches, predictions, reports, logs, secrets, URLs, or machine paths.

## Student World Model and adaptive closed-loop evaluation

The repository also contains a deterministic, offline research harness. Its
fixture is explicitly `synthetic`; replay inputs must be labelled
`anonymized_replay`, and real-study data is not shipped here. The harness does
not claim educational or causal effectiveness.

Run the four comparable baselines from the repository root:

```powershell
$env:PYTHONPATH = "ml/learner_state_evaluation/src"
python -m learner_state_evaluation.cli validate-dataset `
  --dataset ml/learner_state_evaluation/datasets/adaptive_closed_loop_v1.json `
  --output artifacts/results/adaptive-validate.json
python -m learner_state_evaluation.cli run `
  --dataset ml/learner_state_evaluation/datasets/adaptive_closed_loop_v1.json `
  --modes STATIC_PLAN,PROFILE_ONLY,STATE_DRIVEN,CLOSED_LOOP `
  --seed 20260918 --output artifacts/results/adaptive-run
python -m learner_state_evaluation.cli compare `
  --results artifacts/results/adaptive-run/result.json `
  --output artifacts/results/adaptive-compare.json
python -m learner_state_evaluation.cli summarize `
  --result artifacts/results/adaptive-run/result.json
```

`STATIC_PLAN` uses only goal and time budget; `PROFILE_ONLY` adds the static
profile; `STATE_DRIVEN` delegates state analysis and finite strategy selection
to the existing backend policies without feedback replanning; `CLOSED_LOOP`
adds the existing deterministic replan policy. All modes share the same
scenario, as-of time, seed, versions, and input digest. Results contain state
coverage/availability, policy safety and determinism, closed-loop recovery and
oscillation metrics, and a reproducibility manifest. Outputs are ignored under
`artifacts/`.

### Reading the numbers

The harness reports **measured** values only. Two conventions matter when
citing these tables:

- `table5_ablation` comes from actually re-running each variant and diffing it
  against `full_system`. `changed_vs_full_system: false` means the ablated
  capability had no measurable effect on this dataset — that is a coverage
  finding about the synthetic scenarios, not evidence that the capability is
  unnecessary. The comparison includes `decision_chain`, because feedback
  changes the successor strategy rather than the current decision.
- Any metric the offline adapter cannot observe is `null`, never `0` or `1.0`,
  and appears in `metrics.unmeasured` with a reason. `null` means "not
  measured"; it must not be read as a zero. Likewise
  `replan_recovery_success_rate` is measured (REPLAN decisions whose successor
  actually differs from the pre-decision strategy), and it is `null` when no
  REPLAN occurred.

Every row carries `data_source_type: synthetic`. These are offline engineering
results and say nothing about real student outcomes.

The replay evaluator uses a simulated clock and returns lineage, evidence
references, plan summaries, outcomes, decisions, and warning codes. It accepts
no repository writer, creates no task, sends no notification, and makes no
external model call. Participant assignment is opt-in only, stable by salted
hash, and supports exit and deletion; safety rules apply to every group.
