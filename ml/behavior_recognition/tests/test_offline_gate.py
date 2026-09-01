import json

import pytest

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
