from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class CheckResult:
    name: str
    status: str
    message: str
    value: Any = None
    threshold: Any = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate FarmEase retraining health report.")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--training-report", type=Path, default=Path("models") / "training_report.json")
    parser.add_argument("--training-data", type=Path, default=Path("data") / "greenhouse_training_data.csv")
    parser.add_argument("--output-json", type=Path, default=Path("models") / "health_check_report.json")
    parser.add_argument("--output-md", type=Path, default=Path("docs") / "HEALTH_CHECK.md")
    parser.add_argument("--max-training-age-hours", type=float, default=48.0)
    parser.add_argument("--min-rows-used", type=int, default=500)
    parser.add_argument("--min-walk-forward-folds", type=int, default=3)
    parser.add_argument("--min-classification-f1", type=float, default=0.40)
    parser.add_argument("--max-regression-mae", type=float, default=1000.0)
    parser.add_argument("--fail-on-health-issue", action="store_true", default=False)
    parser.add_argument("--fail-on-warning", action="store_true", default=False)
    return parser.parse_args()


def _resolve(base: Path, maybe_relative: Path) -> Path:
    return maybe_relative if maybe_relative.is_absolute() else base / maybe_relative


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        next(reader, None)
        return sum(1 for _ in reader)


def training_age_hours(path: Path) -> float:
    modified_utc = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    age = datetime.now(timezone.utc) - modified_utc
    return age.total_seconds() / 3600.0


def add_check(results: list[CheckResult], name: str, condition: bool, pass_message: str, fail_message: str, value: Any = None, threshold: Any = None) -> None:
    if condition:
        results.append(CheckResult(name=name, status="pass", message=pass_message, value=value, threshold=threshold))
    else:
        results.append(CheckResult(name=name, status="fail", message=fail_message, value=value, threshold=threshold))


def evaluate_health(args: argparse.Namespace) -> tuple[dict[str, Any], list[CheckResult]]:
    project_root = args.project_root.resolve()
    report_path = _resolve(project_root, args.training_report)
    data_path = _resolve(project_root, args.training_data)

    output_json_path = _resolve(project_root, args.output_json)
    output_md_path = _resolve(project_root, args.output_md)

    checks: list[CheckResult] = []

    add_check(
        checks,
        name="training_report_exists",
        condition=report_path.exists(),
        pass_message="Training report found",
        fail_message="Training report missing; run retraining workflow",
    )

    report: dict[str, Any] = {}
    if report_path.exists():
        report = read_json(report_path)

    rows_used = int(report.get("rows_used", 0) or 0)
    add_check(
        checks,
        name="rows_used_minimum",
        condition=rows_used >= args.min_rows_used,
        pass_message="Rows used meets minimum",
        fail_message="Rows used below minimum",
        value=rows_used,
        threshold=args.min_rows_used,
    )

    folds_generated = int((report.get("walk_forward") or {}).get("generated_folds", 0) or 0)
    add_check(
        checks,
        name="walk_forward_folds",
        condition=folds_generated >= args.min_walk_forward_folds,
        pass_message="Walk-forward folds meet minimum",
        fail_message="Walk-forward folds below minimum",
        value=folds_generated,
        threshold=args.min_walk_forward_folds,
    )

    regression_mae = (((report.get("walk_forward") or {}).get("regression") or {}).get("metrics") or {}).get("mae", {}).get("mean")
    regression_mae_value = float(regression_mae) if isinstance(regression_mae, (int, float)) else None
    add_check(
        checks,
        name="regression_mae",
        condition=regression_mae_value is not None and regression_mae_value <= args.max_regression_mae,
        pass_message="Regression MAE within threshold",
        fail_message="Regression MAE above threshold or unavailable",
        value=regression_mae_value,
        threshold=args.max_regression_mae,
    )

    classification_f1 = (((report.get("walk_forward") or {}).get("classification") or {}).get("metrics") or {}).get("f1", {}).get("mean")
    classification_f1_value = float(classification_f1) if isinstance(classification_f1, (int, float)) else None
    add_check(
        checks,
        name="classification_f1",
        condition=classification_f1_value is not None and classification_f1_value >= args.min_classification_f1,
        pass_message="Classification F1 meets threshold",
        fail_message="Classification F1 below threshold or unavailable",
        value=classification_f1_value,
        threshold=args.min_classification_f1,
    )

    model_dir = report_path.parent if report_path.parent.exists() else _resolve(project_root, Path("models"))
    required_artifacts = [
        model_dir / "light_forecast_model.joblib",
        model_dir / "feature_columns.json",
    ]
    for artifact in required_artifacts:
        add_check(
            checks,
            name=f"artifact:{artifact.name}",
            condition=artifact.exists(),
            pass_message=f"Artifact present: {artifact.name}",
            fail_message=f"Artifact missing: {artifact.name}",
        )

    if report_path.exists():
        age_hours = training_age_hours(report_path)
        add_check(
            checks,
            name="training_report_freshness",
            condition=age_hours <= args.max_training_age_hours,
            pass_message="Training report freshness within threshold",
            fail_message="Training report is stale",
            value=round(age_hours, 2),
            threshold=args.max_training_age_hours,
        )
    else:
        age_hours = None

    data_rows = count_csv_rows(data_path)
    add_check(
        checks,
        name="training_data_available",
        condition=data_rows > 0,
        pass_message="Training dataset has rows",
        fail_message="Training dataset has no rows or is missing",
        value=data_rows,
        threshold=1,
    )

    check_payload = [
        {
            "name": item.name,
            "status": item.status,
            "message": item.message,
            "value": item.value,
            "threshold": item.threshold,
        }
        for item in checks
    ]

    failed = [item for item in checks if item.status == "fail"]
    overall_status = "pass" if not failed else "fail"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "overall_status": overall_status,
        "project_root": str(project_root),
        "inputs": {
            "training_report": str(report_path),
            "training_data": str(data_path),
            "output_json": str(output_json_path),
            "output_md": str(output_md_path),
        },
        "thresholds": {
            "max_training_age_hours": args.max_training_age_hours,
            "min_rows_used": args.min_rows_used,
            "min_walk_forward_folds": args.min_walk_forward_folds,
            "min_classification_f1": args.min_classification_f1,
            "max_regression_mae": args.max_regression_mae,
        },
        "snapshot": {
            "rows_used": rows_used,
            "walk_forward_folds": folds_generated,
            "regression_mae_mean": regression_mae_value,
            "classification_f1_mean": classification_f1_value,
            "training_report_age_hours": age_hours,
            "training_data_rows": data_rows,
        },
        "checks": check_payload,
    }

    return payload, checks


def render_markdown(payload: dict[str, Any]) -> str:
    checks = payload.get("checks", [])
    lines = [
        "# Retraining Health Check",
        "",
        f"Generated at (UTC): **{payload.get('generated_at_utc', 'N/A')}**",
        f"Overall status: **{str(payload.get('overall_status', 'unknown')).upper()}**",
        "",
        "## Snapshot",
        "",
        f"- Rows used: **{payload.get('snapshot', {}).get('rows_used', 'N/A')}**",
        f"- Walk-forward folds: **{payload.get('snapshot', {}).get('walk_forward_folds', 'N/A')}**",
        f"- Regression MAE mean: **{payload.get('snapshot', {}).get('regression_mae_mean', 'N/A')}**",
        f"- Classification F1 mean: **{payload.get('snapshot', {}).get('classification_f1_mean', 'N/A')}**",
        f"- Training report age (hours): **{payload.get('snapshot', {}).get('training_report_age_hours', 'N/A')}**",
        f"- Training data rows: **{payload.get('snapshot', {}).get('training_data_rows', 'N/A')}**",
        "",
        "## Checks",
        "",
    ]

    for check in checks:
        status = str(check.get("status", "unknown")).upper()
        name = str(check.get("name", "check"))
        message = str(check.get("message", ""))
        value = check.get("value")
        threshold = check.get("threshold")

        suffix_parts: list[str] = []
        if value is not None:
            suffix_parts.append(f"value={value}")
        if threshold is not None:
            suffix_parts.append(f"threshold={threshold}")

        suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""
        lines.append(f"- [{status}] {name}: {message}{suffix}")

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    payload, checks = evaluate_health(args)

    project_root = args.project_root.resolve()
    output_json_path = _resolve(project_root, args.output_json)
    output_md_path = _resolve(project_root, args.output_md)

    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_md_path.parent.mkdir(parents=True, exist_ok=True)

    output_json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    output_md_path.write_text(render_markdown(payload), encoding="utf-8")

    print(f"Health report written to: {output_json_path}")
    print(f"Health summary markdown written to: {output_md_path}")
    print(f"Overall health status: {str(payload['overall_status']).upper()}")

    has_failures = any(item.status == "fail" for item in checks)
    has_warnings = any(item.status == "warn" for item in checks)

    if args.fail_on_warning and (has_failures or has_warnings):
        raise SystemExit(1)

    if args.fail_on_health_issue and has_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
