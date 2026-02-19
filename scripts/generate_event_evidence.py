from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
DOCS_DIR = PROJECT_ROOT / "docs"

TRAINING_DATA_FILE = DATA_DIR / "greenhouse_training_data.csv"
EVENT_LOG_FILE = DATA_DIR / "event_timeline.csv"
TRAINING_REPORT_FILE = MODELS_DIR / "training_report.json"

EVENT_EVIDENCE_JSON = DOCS_DIR / "event_evidence.json"
EVENT_EVIDENCE_MD = DOCS_DIR / "EVENT_EVIDENCE.md"


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def parse_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


def parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except Exception:
        return None


@dataclass
class SensorLogSummary:
    rows_total: int
    rows_complete: int
    start_time: datetime | None
    end_time: datetime | None
    duration_minutes: float
    median_sampling_seconds: float | None
    pump_on_ratio: float | None
    irrigation_runtime_avoided_pct: float | None
    light_on_ratio: float | None


@dataclass
class EventLogSummary:
    events_total: int
    event_type_counts: dict[str, int]
    severity_counts: dict[str, int]
    source_counts: dict[str, int]
    startup_events: int
    sensor_fault_events: int
    control_events: int
    critical_alerts: int


def summarize_sensor_log(rows: list[dict[str, str]]) -> SensorLogSummary:
    timestamps: list[datetime] = []
    pump_values: list[int] = []
    light_values: list[int] = []
    complete_rows = 0

    required = ("temp_c", "humidity_pct", "soil_adc", "light_lux")

    for row in rows:
        ts = parse_iso(row.get("timestamp"))
        if ts is not None:
            timestamps.append(ts)

        if all((row.get(col) or "") != "" for col in required):
            complete_rows += 1

        pump = parse_int(row.get("relay_pump"))
        if pump is not None:
            pump_values.append(pump)

        light = parse_int(row.get("relay_light"))
        if light is not None:
            light_values.append(light)

    timestamps.sort()
    duration_minutes = 0.0
    median_sampling_seconds = None
    if len(timestamps) >= 2:
        deltas = [
            (timestamps[idx] - timestamps[idx - 1]).total_seconds()
            for idx in range(1, len(timestamps))
            if (timestamps[idx] - timestamps[idx - 1]).total_seconds() >= 0
        ]
        if deltas:
            median_sampling_seconds = float(median(deltas))
        duration_minutes = (timestamps[-1] - timestamps[0]).total_seconds() / 60.0

    pump_on_ratio = None
    irrigation_runtime_avoided_pct = None
    if pump_values:
        pump_on_ratio = sum(1 for value in pump_values if value == 1) / len(pump_values)
        irrigation_runtime_avoided_pct = (1.0 - pump_on_ratio) * 100.0

    light_on_ratio = None
    if light_values:
        light_on_ratio = sum(1 for value in light_values if value == 1) / len(light_values)

    return SensorLogSummary(
        rows_total=len(rows),
        rows_complete=complete_rows,
        start_time=timestamps[0] if timestamps else None,
        end_time=timestamps[-1] if timestamps else None,
        duration_minutes=duration_minutes,
        median_sampling_seconds=median_sampling_seconds,
        pump_on_ratio=pump_on_ratio,
        irrigation_runtime_avoided_pct=irrigation_runtime_avoided_pct,
        light_on_ratio=light_on_ratio,
    )


def summarize_event_log(rows: list[dict[str, str]]) -> EventLogSummary:
    event_types = Counter((row.get("event_type") or "unknown").strip() for row in rows)
    severities = Counter((row.get("severity") or "unknown").strip() for row in rows)
    sources = Counter((row.get("source") or "unknown").strip() for row in rows)

    return EventLogSummary(
        events_total=len(rows),
        event_type_counts=dict(event_types),
        severity_counts=dict(severities),
        source_counts=dict(sources),
        startup_events=event_types.get("startup", 0),
        sensor_fault_events=event_types.get("sensor", 0),
        control_events=event_types.get("control", 0),
        critical_alerts=severities.get("critical", 0),
    )


def load_csv(file_path: Path) -> list[dict[str, str]]:
    if not file_path.exists():
        return []
    with file_path.open("r", encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def load_json(file_path: Path) -> dict[str, Any]:
    if not file_path.exists():
        return {}
    with file_path.open("r", encoding="utf-8") as source:
        return json.load(source)


def format_pct(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def format_float(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def write_outputs(sensor: SensorLogSummary, events: EventLogSummary, report: dict[str, Any]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    regression = report.get("metrics", {}).get("regression", {}).get("xgboost", {})
    classification = report.get("metrics", {}).get("classification", {}).get("xgboost", {})

    summary_json: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_files": {
            "training_data": str(TRAINING_DATA_FILE.relative_to(PROJECT_ROOT)),
            "event_log": str(EVENT_LOG_FILE.relative_to(PROJECT_ROOT)),
            "training_report": str(TRAINING_REPORT_FILE.relative_to(PROJECT_ROOT)),
        },
        "sensor_log": {
            "rows_total": sensor.rows_total,
            "rows_complete": sensor.rows_complete,
            "start_time": sensor.start_time.isoformat() if sensor.start_time else None,
            "end_time": sensor.end_time.isoformat() if sensor.end_time else None,
            "duration_minutes": round(sensor.duration_minutes, 2),
            "median_sampling_seconds": sensor.median_sampling_seconds,
            "pump_on_ratio": sensor.pump_on_ratio,
            "irrigation_runtime_avoided_pct": sensor.irrigation_runtime_avoided_pct,
            "light_on_ratio": sensor.light_on_ratio,
        },
        "event_log": {
            "events_total": events.events_total,
            "event_type_counts": events.event_type_counts,
            "severity_counts": events.severity_counts,
            "source_counts": events.source_counts,
            "startup_events": events.startup_events,
            "sensor_fault_events": events.sensor_fault_events,
            "control_events": events.control_events,
            "critical_alerts": events.critical_alerts,
        },
        "model_metrics": {
            "rows_total": report.get("rows_total"),
            "rows_used": report.get("rows_used"),
            "regression": {
                "mae": regression.get("mae"),
                "rmse": regression.get("rmse"),
                "r2": regression.get("r2"),
            },
            "classification": {
                "accuracy": classification.get("accuracy"),
                "precision": classification.get("precision"),
                "recall": classification.get("recall"),
                "f1": classification.get("f1"),
                "roc_auc": classification.get("roc_auc"),
            },
            "quality_gate": report.get("quality_gate", {}).get("relay_light", {}),
        },
    }

    with EVENT_EVIDENCE_JSON.open("w", encoding="utf-8") as destination:
        json.dump(summary_json, destination, indent=2)

    md_lines = [
        "# FarmEase Event Evidence",
        "",
        f"Generated: {summary_json['generated_at']}",
        "",
        "## Measured impact",
        f"- Logged telemetry rows: {sensor.rows_total}",
        f"- Complete sensor rows: {sensor.rows_complete}",
        f"- Data collection window: {format_float(sensor.duration_minutes)} minutes",
        f"- Median sampling interval: {format_float(sensor.median_sampling_seconds)} seconds",
        f"- Pump ON ratio: {format_pct(sensor.pump_on_ratio)}",
        (
            f"- Estimated irrigation runtime avoided vs always-on baseline: "
            f"{format_float(sensor.irrigation_runtime_avoided_pct)}%"
        ),
        "",
        "## Reliability evidence",
        f"- Total timeline events captured: {events.events_total}",
        f"- Startup events logged: {events.startup_events}",
        f"- Sensor fault events captured: {events.sensor_fault_events}",
        f"- Control command events captured: {events.control_events}",
        f"- Critical alerts captured: {events.critical_alerts}",
        "",
        "## Model evidence",
        f"- Training rows used: {report.get('rows_used')} / {report.get('rows_total')}",
        f"- Light forecast MAE: {regression.get('mae')}",
        f"- Light forecast RMSE: {regression.get('rmse')}",
        f"- Relay classifier F1: {classification.get('f1')}",
        f"- Relay classifier ROC-AUC: {classification.get('roc_auc')}",
        f"- Relay quality gate passed: {report.get('quality_gate', {}).get('relay_light', {}).get('passed')}",
        "",
        "## Notes",
        "- Irrigation runtime avoided is a proxy metric from `relay_pump` duty-cycle.",
        "- Re-run this script before your final presentation to refresh numbers.",
    ]

    with EVENT_EVIDENCE_MD.open("w", encoding="utf-8") as destination:
        destination.write("\n".join(md_lines) + "\n")


def main() -> None:
    training_rows = load_csv(TRAINING_DATA_FILE)
    event_rows = load_csv(EVENT_LOG_FILE)
    training_report = load_json(TRAINING_REPORT_FILE)

    sensor_summary = summarize_sensor_log(training_rows)
    event_summary = summarize_event_log(event_rows)

    write_outputs(sensor_summary, event_summary, training_report)

    print(f"Generated {EVENT_EVIDENCE_JSON.relative_to(PROJECT_ROOT)}")
    print(f"Generated {EVENT_EVIDENCE_MD.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
