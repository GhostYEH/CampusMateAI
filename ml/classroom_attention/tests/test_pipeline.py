import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from classroom_attention.annotations import (
    load_adjudications,
    load_annotations,
    merge,
    read_merged,
    read_merged_contexts,
    write_merged,
)
from classroom_attention.dataset import build_rows, dataset_summary
from classroom_attention.model import load_model, predict_logit, predict_probability, save_model
from classroom_attention.schema import ContractError
from classroom_attention.synthetic import generate
from classroom_attention.train import compare_feature_sets, train_and_evaluate
from classroom_attention.windows import load_dataset


class PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.paths = generate(Path(cls.temp.name), seed=20261124)
        cls.sessions, cls.import_report = load_dataset(cls.paths.manifest)
        cls.a = load_annotations(cls.paths.annotator_a, "A01", sessions=cls.sessions)
        cls.b = load_annotations(cls.paths.annotator_b, "A02", sessions=cls.sessions)
        cls.adjudication = load_adjudications(cls.paths.adjudication, sessions=cls.sessions)
        cls.merged_rows, cls.merge_report = merge(
            cls.sessions, ("A01", cls.a), ("A02", cls.b), cls.adjudication
        )
        write_merged(cls.paths.merged, cls.merged_rows)
        cls.dataset_rows = build_rows(
            cls.sessions,
            read_merged(cls.paths.merged),
            read_merged_contexts(cls.paths.merged),
        )
        cls.result = compare_feature_sets(
            cls.dataset_rows,
            seed=20261124,
            model_version_prefix="unit",
            data_source="synthetic",
            annotation_kappa=cls.merge_report.kappa,
        )

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_dataset_has_no_media_or_identity_fields(self):
        summary = dataset_summary(self.dataset_rows)
        self.assertEqual(240, summary["windows"])
        self.assertEqual(12, summary["participants"])
        self.assertGreater(summary["observable_coverage"], 0.95)
        forbidden = ("frame", "image", "photo", "video", "title", "email", "student_id")
        for row in self.dataset_rows:
            for key in row:
                self.assertNotIn(key.lower(), forbidden)

    def test_merge_reports_disagreement_and_kappa(self):
        self.assertIsNotNone(self.merge_report.kappa)
        self.assertEqual(1, self.merge_report.unresolved)
        self.assertGreater(len(self.merge_report.disagreements), 0)
        self.assertIn("note_taking", self.merge_report.context_counts)

    def test_lopo_reports_required_metrics_for_both_feature_sets(self):
        for feature_set in ("baseline", "headpose"):
            run = self.result[feature_set]
            self.assertEqual(12, len(run["per_participant"]))
            self.assertEqual(12, len(run["participants"]))
            pooled = run["pooled"]
            self.assertGreater(pooled["observation_coverage"], 0.95)
            self.assertIsNotNone(pooled["macro_f1"])
            self.assertIsNotNone(pooled["off_task_recall"])
            self.assertIsNotNone(pooled["auprc"])
            self.assertIsNotNone(pooled["ece"])
            self.assertIsNotNone(pooled["false_alerts_per_hour"])
            self.assertIsNotNone(pooled["delay_median_seconds"])
            self.assertIn("glasses", run["groups"])
            self.assertIn("lighting", run["groups"])
            self.assertIn("device", run["groups"])
            self.assertIn("context", run["groups"])
            self.assertFalse(run["release"]["eligible"])
            self.assertIn("synthetic", run["release"]["reason"])
            self.assertIsNone(run["release_evaluation"])
            self.assertEqual(
                pooled["tp"], sum(fold["tp"] for fold in run["per_participant"].values())
            )
            self.assertEqual(
                pooled["false_alerts"],
                sum(fold["false_alerts"] for fold in run["per_participant"].values()),
            )
            self.assertGreaterEqual(run["reporting_threshold"], 0.2)
            self.assertLessEqual(run["reporting_threshold"], 0.9)

    def test_headpose_fold_uses_more_features_than_baseline(self):
        baseline = load_model_from_run(self.result["baseline"]["model"])
        headpose = load_model_from_run(self.result["headpose"]["model"])
        self.assertLessEqual(len(baseline["feature_order"]), 9)
        self.assertGreaterEqual(len(headpose["feature_order"]), len(baseline["feature_order"]))
        self.assertFalse(
            set(baseline["feature_order"])
            & {"yaw_mean", "yaw_std", "yaw_range", "pitch_mean", "pitch_std", "pitch_range"}
        )
        self.assertTrue(
            set(headpose["feature_order"])
            & {"yaw_mean", "yaw_std", "yaw_range", "pitch_mean", "pitch_std", "pitch_range"}
        )
        self.assertIsNotNone(self.result["comparison"]["macro_f1_delta"])
        self.assertIn("headpose_incremental", self.result["comparison"])

    def test_golden_fixture_matches_python_inference(self):
        model = load_model_from_run(self.result["headpose"]["model"])
        cases = []
        for row in self.dataset_rows[:6]:
            features = {name: row["features"].get(name) for name in model["feature_order"]}
            logit = predict_logit(
                features,
                model["feature_order"],
                model["impute"],
                model["normalization"],
                model["coefficients"],
                model["intercept"],
            )
            probability = predict_probability(logit, model["calibration"])
            cases.append((features, logit, probability))
        for features, expected_logit, expected_probability in cases:
            again = predict_logit(
                features,
                model["feature_order"],
                model["impute"],
                model["normalization"],
                model["coefficients"],
                model["intercept"],
            )
            self.assertAlmostEqual(expected_logit, again, places=12)
            self.assertAlmostEqual(
                expected_probability, predict_probability(again, model["calibration"]), places=12
            )

    def test_full_pipeline_artifacts_are_serializable(self):
        model = load_model_from_run(self.result["headpose"]["model"])
        payload = json.dumps(model, sort_keys=True)
        self.assertIn("decision_threshold", payload)
        self.assertIn("missing_policy", payload)
        self.assertEqual(model["missing_policy"], "median_impute")


class ReleaseEvaluationTest(unittest.TestCase):
    def cohort(self, prefix: str, probability: float) -> list[dict]:
        return [
            {
                "participant_id": f"{prefix}{participant:03}",
                "session_id": "S001",
                "index": index,
                "start_offset_ms": index * 10_000,
                "duration_ms": 10_000,
                "observable": True,
                "dominant_stage": "slide",
                "label": label,
                "probability": probability if label == "off_task" else 0.1,
            }
            for participant in range(5)
            for index, label in enumerate(("on_task", "off_task", "off_task"))
        ]

    def test_release_replays_exported_threshold_on_independent_participants(self) -> None:
        def train_fold(_rows, *, model_version, **_kwargs):
            return {"decision_threshold": 0.30 if "-fold-" in model_version else 0.70}

        def predict_rows(model, rows):
            threshold = model["decision_threshold"]
            return [
                {
                    "participant_id": row["participant_id"],
                    "session_id": row["session_id"],
                    "window_index": row["index"],
                    "probability": row["probability"],
                    "predicted": "off_task" if row["probability"] >= threshold else "on_task",
                }
                for row in rows
            ]

        with (
            patch("classroom_attention.train.train_fold", side_effect=train_fold),
            patch("classroom_attention.train.predict_rows", side_effect=predict_rows),
        ):
            for probability, eligible in ((0.60, False), (0.80, True)):
                with self.subTest(holdout_probability=probability):
                    result = train_and_evaluate(
                        self.cohort("P", 0.60), feature_set="headpose", seed=20261124,
                        model_version="test", data_source="real", annotation_kappa=0.80,
                        release_rows=self.cohort("H", probability), release_annotation_kappa=0.80,
                    )
                    self.assertEqual(1.0, result["pooled"]["off_task_segment_recall"])
                    evaluation = result["release_evaluation"]
                    self.assertEqual(0.70, evaluation["threshold"])
                    self.assertEqual(result["model"]["decision_threshold"], evaluation["threshold"])
                    self.assertEqual(0.0, evaluation["metrics"]["false_alerts_per_hour"])
                    self.assertEqual(float(eligible), evaluation["metrics"]["off_task_segment_recall"])
                    self.assertEqual(eligible, result["model"]["release"]["eligible"])
                    if not eligible:
                        self.assertIn("off_task_segment_recall_below_0.50", result["release"]["reason"])

    def test_participant_overlap_blocks_release_evaluation_before_training(self) -> None:
        with self.assertRaisesRegex(ContractError, "参与者必须完全分离"):
            train_and_evaluate(
                self.cohort("P", 0.60), feature_set="headpose", seed=20261124,
                model_version="test", data_source="real", annotation_kappa=0.80,
                release_rows=self.cohort("P", 0.80), release_annotation_kappa=0.80,
            )


def load_model_from_run(model: dict):
    return model


if __name__ == "__main__":
    unittest.main()
