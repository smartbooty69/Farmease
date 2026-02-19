import unittest

import pandas as pd

from ml.ml_pipeline import build_feature_frame, make_supervised_data, prepare_dataframe
from ml.predict_next import align_columns
from ml.train_models import (
    build_walk_forward_folds,
    evaluate_relay_quality_gate,
    stability_adjusted_classification_score,
    stability_adjusted_regression_loss,
)


class MlPipelineTrainingTests(unittest.TestCase):
    def test_prepare_dataframe_sorts_deduplicates_and_coerces(self):
        raw = pd.DataFrame(
            {
                "timestamp": ["2026-01-01 00:00:02", "2026-01-01 00:00:01", "2026-01-01 00:00:01"],
                "temp_c": ["29.5", "bad", "30.0"],
                "relay_light": [2, 1, 0],
            }
        )

        prepared = prepare_dataframe(raw)

        self.assertEqual(len(prepared), 2)
        self.assertLess(prepared.loc[0, "timestamp"], prepared.loc[1, "timestamp"])
        self.assertEqual(int(prepared.loc[0, "relay_light"]), 0)
        self.assertEqual(int(prepared.loc[1, "relay_light"]), 1)

    def test_make_supervised_data_requires_positive_horizon(self):
        frame = pd.DataFrame(
            {
                "timestamp": pd.date_range("2026-01-01", periods=3, freq="min"),
                "light_lux": [100.0, 110.0, 120.0],
                "relay_light": [0, 1, 1],
            }
        )

        with self.assertRaises(ValueError):
            make_supervised_data(frame, horizon_steps=0)

    def test_make_supervised_data_shapes_and_targets(self):
        frame = pd.DataFrame(
            {
                "timestamp": pd.date_range("2026-01-01", periods=6, freq="min"),
                "temp_c": [25, 25, 26, 27, 28, 29],
                "humidity_pct": [50, 50, 51, 52, 53, 54],
                "soil_adc": [2000, 1990, 1985, 1980, 1975, 1970],
                "light_lux": [100, 110, 120, 130, 140, 150],
                "relay_light": [0, 0, 1, 1, 0, 0],
                "automation_on": [1, 1, 1, 1, 1, 1],
            }
        )
        engineered = build_feature_frame(frame)
        features, y_light, y_relay = make_supervised_data(engineered, horizon_steps=1)

        self.assertEqual(len(features), 5)
        self.assertEqual(len(y_light), 5)
        self.assertEqual(len(y_relay), 5)
        self.assertNotIn("timestamp", features.columns)

    def test_align_columns_adds_missing_and_reorders(self):
        input_frame = pd.DataFrame({"b": [2], "a": [1]})
        aligned = align_columns(input_frame, ["a", "b", "c"])

        self.assertEqual(list(aligned.columns), ["a", "b", "c"])
        self.assertEqual(aligned.iloc[0]["a"], 1)
        self.assertTrue(pd.isna(aligned.iloc[0]["c"]))

    def test_build_walk_forward_folds_returns_expected_count(self):
        folds = build_walk_forward_folds(total_rows=220, n_splits=4, min_train_rows=80, min_valid_rows=20)

        self.assertEqual(len(folds), 4)
        first_train, first_valid = folds[0]
        self.assertEqual(first_train.start, 0)
        self.assertEqual(first_train.stop, 80)
        self.assertEqual(first_valid.start, 80)

    def test_relay_quality_gate_detects_imbalanced_splits(self):
        train_y = pd.Series([0] * 12 + [1] * 3)
        valid_y = pd.Series([0] * 8 + [1] * 1)

        passed, issues, summary = evaluate_relay_quality_gate(train_y, valid_y, min_class_count=5)

        self.assertFalse(passed)
        self.assertGreaterEqual(len(issues), 1)
        self.assertFalse(summary["passed"])

    def test_stability_adjusted_scores(self):
        reg_loss = stability_adjusted_regression_loss({"mae": {"mean": 10.0, "std": 2.0}})
        cls_score = stability_adjusted_classification_score({"f1": {"mean": 0.8, "std": 0.1}})

        self.assertAlmostEqual(reg_loss, 10.5)
        self.assertAlmostEqual(cls_score, 0.79)


if __name__ == "__main__":
    unittest.main()
