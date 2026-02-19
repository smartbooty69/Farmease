import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class HealthReportScriptTests(unittest.TestCase):
    def setUp(self):
        self.workspace_root = Path(__file__).resolve().parents[1]
        self.script_path = self.workspace_root / "scripts" / "generate_health_report.py"

    def _write_sample_training_report(self, models_dir: Path, rows_used: int = 1200, mae: float = 300.0, f1: float = 0.6, folds: int = 4):
        report = {
            "rows_used": rows_used,
            "walk_forward": {
                "generated_folds": folds,
                "regression": {
                    "metrics": {
                        "mae": {
                            "mean": mae,
                        }
                    }
                },
                "classification": {
                    "metrics": {
                        "f1": {
                            "mean": f1,
                        }
                    }
                },
            },
        }
        (models_dir / "training_report.json").write_text(json.dumps(report), encoding="utf-8")
        (models_dir / "light_forecast_model.joblib").write_text("ok", encoding="utf-8")
        (models_dir / "feature_columns.json").write_text(json.dumps(["temp_c"]), encoding="utf-8")

    def _write_training_data(self, data_dir: Path):
        (data_dir / "greenhouse_training_data.csv").write_text(
            "timestamp,temp_c\n2026-02-20T00:00:00,26.0\n",
            encoding="utf-8",
        )

    def test_health_report_passes_with_good_inputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            models_dir = temp_root / "models"
            data_dir = temp_root / "data"
            docs_dir = temp_root / "docs"
            models_dir.mkdir(parents=True, exist_ok=True)
            data_dir.mkdir(parents=True, exist_ok=True)
            docs_dir.mkdir(parents=True, exist_ok=True)

            self._write_sample_training_report(models_dir)
            self._write_training_data(data_dir)

            result = subprocess.run(
                [
                    sys.executable,
                    str(self.script_path),
                    "--project-root",
                    str(temp_root),
                    "--fail-on-health-issue",
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)

            output_json = models_dir / "health_check_report.json"
            output_md = docs_dir / "HEALTH_CHECK.md"

            self.assertTrue(output_json.exists())
            self.assertTrue(output_md.exists())

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["overall_status"], "pass")

    def test_health_report_fails_on_threshold_violation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            models_dir = temp_root / "models"
            data_dir = temp_root / "data"
            docs_dir = temp_root / "docs"
            models_dir.mkdir(parents=True, exist_ok=True)
            data_dir.mkdir(parents=True, exist_ok=True)
            docs_dir.mkdir(parents=True, exist_ok=True)

            self._write_sample_training_report(models_dir, rows_used=100, mae=2500.0, f1=0.1, folds=1)
            self._write_training_data(data_dir)

            result = subprocess.run(
                [
                    sys.executable,
                    str(self.script_path),
                    "--project-root",
                    str(temp_root),
                    "--fail-on-health-issue",
                    "--min-rows-used",
                    "500",
                    "--max-regression-mae",
                    "1000",
                    "--min-classification-f1",
                    "0.4",
                    "--min-walk-forward-folds",
                    "3",
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 1)

            output_json = models_dir / "health_check_report.json"
            self.assertTrue(output_json.exists())
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["overall_status"], "fail")


if __name__ == "__main__":
    unittest.main()
