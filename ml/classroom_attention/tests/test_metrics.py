import unittest

from classroom_attention.metrics import alert_metrics, simulate_alerts


class AlertReplayTest(unittest.TestCase):
    def window(self, index: int, **overrides) -> dict:
        return {
            "participant_id": "P001",
            "session_id": "S001",
            "index": index,
            "start_offset_ms": index * 10_000,
            "duration_ms": 10_000,
            "observable": True,
            "dominant_stage": "slide",
            "label": "off_task",
            **overrides,
        }

    def test_alert_uses_window_end_and_cooldown_from_prompt_time(self) -> None:
        rows = [self.window(index) for index in range(16)]
        predictions = [{"probability": 0.9} for _ in rows]

        alerts = simulate_alerts(rows, predictions, threshold=0.5)

        self.assertEqual([1, 13], [alert["window_index"] for alert in alerts])
        self.assertEqual(20_000, alerts[0]["alert_offset_ms"])
        self.assertEqual(140_000, alerts[1]["alert_offset_ms"])
        metrics = alert_metrics(rows, predictions, threshold=0.5)
        self.assertEqual(2, metrics["true_alerts"])
        self.assertEqual(1, metrics["off_task_segments"])
        self.assertEqual(1.0, metrics["off_task_segment_recall"])

    def test_partial_duplicate_and_missing_windows_do_not_build_evidence(self) -> None:
        rows = [
            self.window(0),
            self.window(0),
            self.window(1, complete=False),
            self.window(2),
            self.window(3),
        ]
        alerts = simulate_alerts(rows, [{"probability": 0.9} for _ in rows], threshold=0.5)
        self.assertEqual([3], [alert["window_index"] for alert in alerts])

    def test_early_false_alert_cannot_cover_an_unobservable_off_task_segment(self) -> None:
        rows = [
            self.window(0, label="on_task"),
            self.window(1, label="on_task"),
            self.window(2, observable=False),
        ]
        metrics = alert_metrics(rows, [{"probability": 0.9} for _ in rows], threshold=0.5)
        self.assertEqual(1, metrics["false_alerts"])
        self.assertEqual(1, metrics["missed_off_task_segments"])
        self.assertEqual(0.0, metrics["off_task_segment_recall"])


if __name__ == "__main__":
    unittest.main()
