from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def count_csv_rows(file_path: Path) -> int:
    if not file_path.exists():
        return 0

    with file_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.reader(csv_file)
        next(reader, None)
        return sum(1 for _ in reader)


def summarize_event_severity(file_path: Path) -> dict[str, int]:
    summary = {"info": 0, "warning": 0, "critical": 0, "other": 0}
    if not file_path.exists():
        return summary

    with file_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            severity = str(row.get("severity", "")).strip().lower()
            if severity in summary:
                summary[severity] += 1
            else:
                summary["other"] += 1

    return summary


def read_training_report(file_path: Path) -> dict[str, Any]:
    if not file_path.exists():
        return {}

    with file_path.open("r", encoding="utf-8") as report_file:
        data = json.load(report_file)
        if not isinstance(data, dict):
            return {}
        return data


def format_metric(value: Any, digits: int = 4) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.{digits}f}"
    return "N/A"


def build_markdown(report: dict[str, Any], training_rows: int, event_rows: int, severity_summary: dict[str, int]) -> str:
    best_models = report.get("best_models", {}) if isinstance(report.get("best_models"), dict) else {}
    walk_forward = report.get("walk_forward", {}) if isinstance(report.get("walk_forward"), dict) else {}

    regression_metrics = {}
    classification_metrics = {}
    if isinstance(walk_forward.get("regression"), dict):
        regression_metrics = walk_forward["regression"].get("metrics", {}) if isinstance(walk_forward["regression"].get("metrics"), dict) else {}
    if isinstance(walk_forward.get("classification"), dict):
        classification_metrics = walk_forward["classification"].get("metrics", {}) if isinstance(walk_forward["classification"].get("metrics"), dict) else {}

    reg_mae = regression_metrics.get("mae", {}) if isinstance(regression_metrics.get("mae"), dict) else {}
    cls_f1 = classification_metrics.get("f1", {}) if isinstance(classification_metrics.get("f1"), dict) else {}

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    return "\n".join(
        [
            "# Event Evidence",
            "",
            f"Generated at (UTC): **{generated_at}**",
            "",
            "## Run Summary",
            "",
            f"- Training rows available: **{training_rows}**",
            f"- Event log rows available: **{event_rows}**",
            f"- Selected light forecast model: **{best_models.get('light_forecast', 'N/A')}**",
            f"- Selected relay model: **{best_models.get('relay_light', 'N/A')}**",
            "",
            "## Walk-Forward Metrics",
            "",
            f"- Regression MAE (mean): **{format_metric(reg_mae.get('mean'))}**",
            f"- Regression MAE (std): **{format_metric(reg_mae.get('std'))}**",
            f"- Classification F1 (mean): **{format_metric(cls_f1.get('mean'))}**",
            f"- Classification F1 (std): **{format_metric(cls_f1.get('std'))}**",
            "",
            "## Event Severity Counts",
            "",
            f"- Info: **{severity_summary['info']}**",
            f"- Warning: **{severity_summary['warning']}**",
            f"- Critical: **{severity_summary['critical']}**",
            f"- Other: **{severity_summary['other']}**",
            "",
            "## Artifacts Checked",
            "",
            "- `models/training_report.json`",
            "- `models/light_forecast_model.joblib`",
            "- `models/relay_light_model.joblib` (if class balance gate passed)",
            "- `models/feature_columns.json`",
            "- `data/greenhouse_training_data.csv`",
            "- `data/event_timeline.csv`",
            "",
        ]
    )


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]

    training_data_path = project_root / "data" / "greenhouse_training_data.csv"
    event_log_path = project_root / "data" / "event_timeline.csv"
    training_report_path = project_root / "models" / "training_report.json"
    output_path = project_root / "docs" / "EVENT_EVIDENCE.md"

    report = read_training_report(training_report_path)
    training_rows = count_csv_rows(training_data_path)
    event_rows = count_csv_rows(event_log_path)
    severity_summary = summarize_event_severity(event_log_path)

    markdown = build_markdown(report, training_rows, event_rows, severity_summary)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")

    print(f"Event evidence written to: {output_path}")


if __name__ == "__main__":
    main()
