import csv
import json
import tempfile
import unittest
from pathlib import Path

from classroom_attention.windows import load_dataset, read_window_file


class WindowImportTest(unittest.TestCase):
    def test_synthetic_manifest_loads_and_counts(self):
        from classroom_attention.synthetic import generate

        with tempfile.TemporaryDirectory() as temp:
            paths = generate(Path(temp))
            sessions, report = load_dataset(paths.manifest)
            self.assertTrue(report.ok, report.summary())
            self.assertEqual(24, report.sessions)
            self.assertEqual(240, report.windows)
            self.assertEqual(234, report.observable)
            self.assertEqual(6, report.unobservable)
            self.assertEqual(240, sum(len(session.windows) for session in sessions))

    def test_missing_reason_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rows = [
                {
                    "window_index": 0,
                    "start_offset_ms": 0,
                    "end_offset_ms": 10000,
                    "complete": "true",
                    "valid_samples": 40,
                    "invalid_samples": 0,
                    "face_visible_samples": 0,
                    "face_visible_ratio": "0.000",
                    "yaw_mean_deg": "",
                    "yaw_std_deg": "",
                    "yaw_min_deg": "",
                    "yaw_max_deg": "",
                    "yaw_samples": "",
                    "pitch_mean_deg": "",
                    "pitch_std_deg": "",
                    "pitch_min_deg": "",
                    "pitch_max_deg": "",
                    "pitch_samples": "",
                    "dominant_stage": "slide",
                    "stage_counts": "slide:40",
                    "manual_page_turns": "0",
                    "quiz_submissions": "0",
                    "questions": "0",
                    "verdict": "unobservable",
                    "unavailable_reason": "",
                    "unavailable_reason_counts": "no_face:40",
                }
            ]
            path = root / "bad.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaises(Exception):
                read_window_file(path)

    def test_json_rejects_unknown_media_field(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "windows.json"
            payload = {
                "version": 1,
                "windows": [
                    {
                        "index": 0,
                        "startOffsetMs": 0,
                        "endOffsetMs": 10000,
                        "complete": True,
                        "validSampleCount": 40,
                        "invalidSampleCount": 0,
                        "faceVisibleSampleCount": 40,
                        "faceVisibleRatio": 1.0,
                        "yaw": None,
                        "pitch": None,
                        "stageCounts": {"slide": 40},
                        "dominantStage": "slide",
                        "manualPageTurns": 0,
                        "quizSubmissions": 0,
                        "questions": 0,
                        "verdict": "observable",
                        "unavailableReason": None,
                        "unavailableReasonCounts": {},
                        "rawFrame": "frame-data",
                    }
                ],
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(Exception):
                read_window_file(path)

    def test_invalid_participant_code_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "one.csv").write_text(
                "window_index,start_offset_ms,end_offset_ms,complete,valid_samples,"
                "invalid_samples,face_visible_samples,face_visible_ratio,dominant_stage,"
                "stage_counts,manual_page_turns,quiz_submissions,questions,verdict,"
                "unavailable_reason,unavailable_reason_counts\n",
                encoding="utf-8",
            )
            manifest = root / "manifest.csv"
            manifest.write_text(
                "participant_id,session_id,file\n"
                "student@example.com,S001,one.csv\n",
                encoding="utf-8",
            )
            with self.assertRaises(Exception):
                load_dataset(manifest, strict=False)

    def test_manifest_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = root / "manifest.csv"
            manifest.write_text(
                "participant_id,session_id,file\nP001,S001,../outside.csv\n",
                encoding="utf-8",
            )
            with self.assertRaises(Exception):
                load_dataset(manifest, strict=False)


if __name__ == "__main__":
    unittest.main()
