import json

import numpy as np
import pytest

from behavior_recognition.calibrate import search_rejection_thresholds
from behavior_recognition.cli import main
from behavior_recognition.offline_gate import OfflinePolicy, compare_offline_candidate


def evaluation_report(
    *,
    product_macro_f1: float,
    phone_auprc: float,
    ece: float,
    coverage: float,
) -> dict:
    return {
        "validation_product_calibrated": {
            "macro_f1": product_macro_f1,
            "phone_interaction_auprc": phone_auprc,
            "ece": ece,
        },
        "rejection": {"coverage": coverage},
        "test_product_calibrated": {"macro_f1": 1.0},
    }


def test_product_macro_gain_cannot_hide_phone_auprc_regression():
    """Catches advancing a candidate that improves only the majority study class."""
    baseline = evaluation_report(
        product_macro_f1=0.60,
        phone_auprc=0.70,
        ece=0.08,
        coverage=0.75,
    )
    candidate = evaluation_report(
        product_macro_f1=0.65,
        phone_auprc=0.67,
        ece=0.08,
        coverage=0.75,
    )

    decision = compare_offline_candidate(candidate, baseline)

    assert decision.advanced is False
    assert "phone_interaction_auprc" in decision.failed_checks
    assert decision.production_approved is False


def test_candidate_advances_only_as_an_offline_experiment():
    """Catches an offline frame comparison being represented as production approval."""
    baseline = evaluation_report(
        product_macro_f1=0.60,
        phone_auprc=0.70,
        ece=0.08,
        coverage=0.75,
    )
    candidate = evaluation_report(
        product_macro_f1=0.62,
        phone_auprc=0.70,
        ece=0.075,
        coverage=0.72,
    )

    decision = compare_offline_candidate(candidate, baseline)

    assert decision.advanced is True
    assert decision.failed_checks == []
    assert decision.production_approved is False
    assert decision.stage == "offline_experiment"
    assert decision.deltas["product_macro_f1"] == pytest.approx(0.02)


def test_candidate_below_rejection_coverage_does_not_advance():
    """Catches selective accuracy being improved by rejecting nearly every frame."""
    baseline = evaluation_report(
        product_macro_f1=0.60,
        phone_auprc=0.70,
        ece=0.08,
        coverage=0.75,
    )
    candidate = evaluation_report(
        product_macro_f1=0.64,
        phone_auprc=0.71,
        ece=0.07,
        coverage=0.50,
    )

    decision = compare_offline_candidate(
        candidate,
        baseline,
        policy=OfflinePolicy(minimum_rejection_coverage=0.70),
    )

    assert decision.advanced is False
    assert "rejection_coverage" in decision.failed_checks


def test_near_uniform_fallback_cannot_claim_coverage_to_advance():
    """Catches an all-rejected fallback being presented as eligible evidence."""
    probabilities = np.tile(
        [[0.26, 0.25, 0.25, 0.24]],
        (4, 1),
    )
    rejection = search_rejection_thresholds(
        probabilities,
        np.array([0, 1, 2, 3]),
        min_coverage=0.70,
    )
    baseline = evaluation_report(
        product_macro_f1=0.60,
        phone_auprc=0.70,
        ece=0.08,
        coverage=0.75,
    )
    candidate = evaluation_report(
        product_macro_f1=0.62,
        phone_auprc=0.70,
        ece=0.08,
        coverage=rejection["coverage"],
    )

    decision = compare_offline_candidate(candidate, baseline)

    assert decision.advanced is False
    assert "rejection_coverage" in decision.failed_checks


@pytest.mark.parametrize(
    ("baseline_value", "candidate_value", "metric"),
    [
        (0.70, 0.69, "phone_auprc"),
        (0.12, 0.13, "ece"),
    ],
)
def test_exact_metric_regression_tolerance_boundary_is_allowed(
    baseline_value,
    candidate_value,
    metric,
):
    """Catches binary-float noise rejecting a candidate at the configured boundary."""
    baseline = evaluation_report(
        product_macro_f1=0.60,
        phone_auprc=baseline_value if metric == "phone_auprc" else 0.70,
        ece=baseline_value if metric == "ece" else 0.08,
        coverage=0.75,
    )
    candidate = evaluation_report(
        product_macro_f1=0.62,
        phone_auprc=candidate_value if metric == "phone_auprc" else 0.70,
        ece=candidate_value if metric == "ece" else 0.08,
        coverage=0.75,
    )

    decision = compare_offline_candidate(candidate, baseline)

    assert decision.advanced is True
    assert decision.failed_checks == []


@pytest.mark.parametrize(
    "path",
    [
        ("validation_product_calibrated", "macro_f1"),
        ("validation_product_calibrated", "phone_interaction_auprc"),
        ("validation_product_calibrated", "ece"),
        ("rejection", "coverage"),
    ],
)
def test_boolean_metric_is_rejected(path):
    """Catches JSON booleans being coerced into numeric offline evidence."""
    candidate = evaluation_report(
        product_macro_f1=0.62,
        phone_auprc=0.70,
        ece=0.08,
        coverage=0.75,
    )
    candidate[path[0]][path[1]] = True

    with pytest.raises(ValueError, match="metric must be numeric"):
        compare_offline_candidate(
            candidate,
            evaluation_report(
                product_macro_f1=0.60,
                phone_auprc=0.70,
                ece=0.08,
                coverage=0.75,
            ),
        )


def test_missing_validation_metrics_fail_loudly():
    """Catches silently falling back to locked test metrics."""
    with pytest.raises(ValueError, match="validation_product_calibrated"):
        compare_offline_candidate(
            {"test_product_calibrated": {"macro_f1": 1.0}},
            evaluation_report(
                product_macro_f1=0.60,
                phone_auprc=0.70,
                ece=0.08,
                coverage=0.75,
            ),
        )


def test_offline_compare_cli_writes_non_production_decision(tmp_path):
    """Catches the comparison gate existing only as an unrepeatable Python call."""
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    output_path = tmp_path / "decision.json"
    baseline_path.write_text(
        json.dumps(evaluation_report(
            product_macro_f1=0.60,
            phone_auprc=0.70,
            ece=0.08,
            coverage=0.75,
        )),
        encoding="utf-8",
    )
    candidate_path.write_text(
        json.dumps(evaluation_report(
            product_macro_f1=0.62,
            phone_auprc=0.70,
            ece=0.075,
            coverage=0.72,
        )),
        encoding="utf-8",
    )

    exit_code = main([
        "offline-compare",
        "--baseline", str(baseline_path),
        "--candidate", str(candidate_path),
        "--output", str(output_path),
    ])

    decision = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert decision["advanced"] is True
    assert decision["production_approved"] is False


@pytest.mark.parametrize("aliased_input", ("baseline", "candidate"))
def test_offline_compare_cli_rejects_output_that_aliases_an_input(tmp_path, aliased_input):
    """Catches a report comparison overwriting the evidence it just read."""
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    for path, report in (
        (
            baseline_path,
            evaluation_report(
                product_macro_f1=0.60,
                phone_auprc=0.70,
                ece=0.08,
                coverage=0.75,
            ),
        ),
        (
            candidate_path,
            evaluation_report(
                product_macro_f1=0.62,
                phone_auprc=0.70,
                ece=0.08,
                coverage=0.75,
            ),
        ),
    ):
        path.write_text(json.dumps(report), encoding="utf-8")
    aliased_path = baseline_path if aliased_input == "baseline" else candidate_path
    original_bytes = aliased_path.read_bytes()

    with pytest.raises(SystemExit) as error:
        main([
            "offline-compare",
            "--baseline", str(baseline_path),
            "--candidate", str(candidate_path),
            "--output", str(aliased_path),
        ])

    assert aliased_path.read_bytes() == original_bytes
    assert error.value.code != 0
