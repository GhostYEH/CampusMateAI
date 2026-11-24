import json
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from classroom_attention.model import (
    build_model,
    fit_platt,
    load_model,
    predict_logit,
    predict_probability,
    save_model,
)


class ModelTest(unittest.TestCase):
    def test_logistic_regression_separates_simple_data(self):
        rows = []
        for index in range(40):
            features = {
                "face_visible_ratio": 0.95 if index < 20 else 0.4,
                "valid_coverage": 1.0,
                "no_face_ratio": 0.05 if index < 20 else 0.6,
                "invalid_ratio": 0.0,
                "manual_page_turns": 1.0 if index < 20 else 0.0,
                "quiz_submissions": 0.0,
                "questions": 0.0,
                "stage_quiz": 0.0,
                "stage_lecture": 0.0,
                "yaw_mean": 0.0 if index < 20 else 30.0,
                "yaw_std": 4.0,
                "yaw_range": 8.0,
                "pitch_mean": 0.0,
                "pitch_std": 4.0,
                "pitch_range": 8.0,
            }
            rows.append(
                {
                    "participant_id": f"P{index % 8 + 1:03d}",
                    "session_id": "S001",
                    "index": index,
                    "label": "on_task" if index < 20 else "off_task",
                    "observable": True,
                    "features": features,
                }
            )
        model = build_model(
            rows,
            feature_set="headpose",
            model_version="test",
            calibration=(1.0, 0.0),
            threshold=0.5,
            training_metadata={},
            release={},
        )
        self.assertIn("face_visible_ratio", model["feature_order"])
        self.assertEqual(len(model["feature_order"]), len(model["coefficients"]))
        on_task_probability = predict_probability(
            predict_logit(
                rows[0]["features"],
                model["feature_order"],
                model["impute"],
                model["normalization"],
                model["coefficients"],
                model["intercept"],
            ),
            model["calibration"],
        )
        off_task_probability = predict_probability(
            predict_logit(
                rows[-1]["features"],
                model["feature_order"],
                model["impute"],
                model["normalization"],
                model["coefficients"],
                model["intercept"],
            ),
            model["calibration"],
        )
        self.assertLess(on_task_probability, 0.3)
        self.assertGreater(off_task_probability, 0.7)

    def test_median_impute_is_used_for_missing_head_pose(self):
        rows = []
        for index in range(10):
            rows.append(
                {
                    "participant_id": "P001",
                    "session_id": "S001",
                    "index": index,
                    "label": "on_task" if index < 5 else "off_task",
                    "observable": True,
                    "features": {
                        "face_visible_ratio": 0.8,
                        "valid_coverage": 0.9,
                        "no_face_ratio": 0.2,
                        "invalid_ratio": 0.0,
                        "manual_page_turns": 0.0,
                        "quiz_submissions": 0.0,
                        "questions": 0.0,
                        "stage_quiz": 0.0,
                        "stage_lecture": 0.0,
                        "yaw_mean": None if index % 2 else 0.0,
                        "yaw_std": None,
                        "yaw_range": None,
                        "pitch_mean": None,
                        "pitch_std": None,
                        "pitch_range": None,
                    },
                    "duration_ms": 10_000,
                }
            )
        model = build_model(
            rows,
            feature_set="headpose",
            model_version="test",
            calibration=(1.0, 0.0),
            threshold=0.5,
            training_metadata={},
            release={},
        )
        self.assertIn("yaw_mean", model["impute"])
        self.assertTrue(math.isfinite(model["impute"]["yaw_mean"]))

    def test_artifact_round_trip(self):
        model = {
            "schema_version": 1,
            "model_version": "unit-test",
            "feature_set": "baseline",
            "feature_order": ["face_visible_ratio"],
            "feature_labels": {"face_visible_ratio": "人脸可见比例"},
            "missing_policy": "median_impute",
            "impute": {"face_visible_ratio": 0.5},
            "normalization": {"face_visible_ratio": {"mean": 0.5, "std": 0.1}},
            "coefficients": [1.2],
            "intercept": -0.3,
            "calibration": {"type": "platt", "a": 1.0, "b": 0.0},
            "decision_threshold": 0.6,
            "coverage_gate": {"min_valid_coverage": 0.5, "min_face_visible_ratio": 0.2},
            "release": {"eligible": False, "reason": "synthetic"},
        }
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "model.json"
            save_model(path, model)
            loaded = load_model(path)
            self.assertEqual(model["model_version"], loaded["model_version"])
            logit = predict_logit(
                {"face_visible_ratio": 0.8},
                loaded["feature_order"],
                loaded["impute"],
                loaded["normalization"],
                loaded["coefficients"],
                loaded["intercept"],
            )
            self.assertAlmostEqual(1.2 * 3.0 - 0.3, logit, places=6)

    def test_platt_calibration_returns_finite_parameters(self):
        logits = np.linspace(-3, 3, 20)
        labels = (logits > 0).astype(float)
        a, b = fit_platt(logits, labels)
        self.assertTrue(math.isfinite(a))
        self.assertTrue(math.isfinite(b))
        self.assertGreater(a, 0)


if __name__ == "__main__":
    unittest.main()
