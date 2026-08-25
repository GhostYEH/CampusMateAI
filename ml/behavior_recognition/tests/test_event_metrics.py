import pytest

from behavior_recognition.metrics import EventInterval, event_classification_report


def test_event_metrics_count_false_phone_reminders_and_latency() -> None:
    reference = [
        EventInterval("PHONE_INTERACTION", 1_000, 5_000),
        EventInterval("STUDY_ACTIVITY", 10_000, 15_000),
    ]
    predicted = [
        EventInterval("PHONE_INTERACTION", 2_000, 5_000),
        EventInterval("PHONE_INTERACTION", 20_000, 23_000),
        EventInterval("STUDY_ACTIVITY", 10_500, 15_000),
    ]

    report = event_classification_report(reference, predicted, observed_duration_ms=3_600_000)

    assert report["per_class"]["PHONE_INTERACTION"]["precision"] == pytest.approx(0.5)
    assert report["per_class"]["PHONE_INTERACTION"]["recall"] == pytest.approx(1.0)
    assert report["false_reminders_per_hour"] == pytest.approx(1.0)
    assert report["phone_detection_p95_ms"] == pytest.approx(1_000)


def test_wrong_label_overlap_is_not_a_match() -> None:
    report = event_classification_report(
        [EventInterval("PHONE_INTERACTION", 0, 4_000)],
        [EventInterval("STUDY_ACTIVITY", 0, 4_000)],
        observed_duration_ms=3_600_000,
    )

    assert report["per_class"]["PHONE_INTERACTION"]["recall"] == 0.0
    assert report["per_class"]["STUDY_ACTIVITY"]["precision"] == 0.0
