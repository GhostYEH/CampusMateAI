import tempfile
import unittest
from pathlib import Path

from classroom_attention.annotations import (
    cohen_kappa,
    load_adjudications,
    load_annotations,
    merge,
)
from classroom_attention.synthetic import generate
from classroom_attention.windows import load_dataset


class AnnotationMergeTest(unittest.TestCase):
    def test_perfect_kappa(self):
        self.assertEqual(1.0, cohen_kappa(["on_task", "off_task"], ["on_task", "off_task"]))

    def test_kappa_is_not_undefined_for_single_class(self):
        self.assertIsNone(cohen_kappa(["on_task", "on_task"], ["on_task", "on_task"]))

    def test_synthetic_merge_reports_reliability_and_unresolved(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = generate(Path(temp))
            sessions, report = load_dataset(paths.manifest)
            a = load_annotations(paths.annotator_a, "A01", sessions=sessions)
            b = load_annotations(paths.annotator_b, "A02", sessions=sessions)
            adjudications = load_adjudications(paths.adjudication, sessions=sessions)
            rows, merge_report = merge(sessions, ("A01", a), ("A02", b), adjudications)
            self.assertEqual(240, merge_report.windows)
            self.assertGreater(merge_report.agreed, 200)
            self.assertGreater(merge_report.adjudicated, 0)
            self.assertEqual(1, merge_report.unresolved)
            self.assertIsNotNone(merge_report.kappa)
            self.assertGreater(merge_report.kappa, 0.6)
            self.assertLess(merge_report.kappa, 1.0)
            self.assertIn("note_taking", merge_report.context_counts)
            unresolved = [row for row in rows if row["status"] == "unresolved"]
            self.assertEqual(1, len(unresolved))
            self.assertIsNone(unresolved[0]["label"])

    def test_merge_is_blind_and_keeps_raw_labels(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = generate(Path(temp))
            sessions, _ = load_dataset(paths.manifest)
            a = load_annotations(paths.annotator_a, "A01", sessions=sessions)
            b = load_annotations(paths.annotator_b, "A02", sessions=sessions)
            rows, _ = merge(sessions, ("A01", a), ("A02", b), {})
            self.assertTrue(all("label_a" in row and "label_b" in row for row in rows))
            self.assertTrue(all(row["label"] is None or row["label"] in ("on_task", "off_task", "unobservable") for row in rows))

    def test_bad_label_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = generate(Path(temp))
            sessions, _ = load_dataset(paths.manifest)
            bad = Path(temp) / "bad.csv"
            bad.write_text(
                "participant_id,session_id,window_index,label\n"
                "P001,S001,0,focused\n",
                encoding="utf-8",
            )
            with self.assertRaises(Exception):
                load_annotations(bad, "A01", sessions=sessions)


if __name__ == "__main__":
    unittest.main()
