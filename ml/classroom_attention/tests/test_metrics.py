import unittest

from classroom_attention.metrics import simulate_alerts


class AlertReplayTest(unittest.TestCase):
    def test_alert_uses_window_end_and_cooldown_from_prompt_time(self) -> None:
        rows = [
            {
                "participant_id": "P001",
                "session_id": "S001",
                "index": index,
                "start_offset_ms": index * 10_000,
                "duration_ms": 10_000,
                "observable": True,
                "dominant_stage": "slide",
                "label": "off_task",
            }
            for index in range(16)
        ]
        predictions = [{"probability": 0.9} for _ in rows]

        alerts = simulate_alerts(rows, predictions, threshold=0.5)

        self.assertEqual([1, 13], [alert["window_index"] for alert in alerts])
        self.assertEqual(20_000, alerts[0]["alert_offset_ms"])
        self.assertEqual(140_000, alerts[1]["alert_offset_ms"])


if __name__ == "__main__":
    unittest.main()
