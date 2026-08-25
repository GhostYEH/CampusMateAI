from behavior_recognition.promotion_gate import evaluate_promotion


PASSING = {
    "event_macro_f1": 0.72,
    "phone_precision": 0.82,
    "phone_recall": 0.78,
    "no_visible_study_f1": 0.68,
    "false_reminders_per_hour": 0.7,
    "phone_detection_p95_ms": 2800,
    "quality_coverage": 0.75,
}


def test_high_frame_accuracy_cannot_hide_excess_false_reminders() -> None:
    metrics = dict(PASSING, frame_accuracy=0.95, false_reminders_per_hour=1.4)

    decision = evaluate_promotion(metrics)

    assert decision.approved is False
    assert "false_reminders_per_hour" in decision.failed_gates


def test_all_event_gates_and_device_groups_must_pass() -> None:
    decision = evaluate_promotion(
        PASSING,
        device_groups={
            "android": {"phone_precision": 0.80},
            "harmony": {"phone_precision": 0.74},
        },
    )

    assert decision.approved is False
    assert "device_group:harmony:phone_precision" in decision.failed_gates


def test_candidate_is_approved_only_when_every_gate_passes() -> None:
    decision = evaluate_promotion(
        PASSING,
        device_groups={
            "android": {"phone_precision": 0.81},
            "harmony": {"phone_precision": 0.79},
        },
    )

    assert decision.approved is True
    assert decision.failed_gates == []
