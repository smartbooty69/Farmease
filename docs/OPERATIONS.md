# FarmEase Operations Runbook

## Goal

Provide repeatable startup, retraining, and validation for day-to-day operation.

## Prerequisites

- Python virtual environment exists at `.venv`
- Dependencies installed from `requirements-ml.txt`
- Optional `.env` configured for Telegram integration
- Arduino/serial device connected for live dashboard mode

## Start dashboard

From PowerShell:

```powershell
.\scripts\run_dashboard.ps1
```

This script validates key paths and starts `dashboard.py` with the project venv Python.

## Retrain models (manual)

Standard retraining:

```powershell
.\scripts\retrain_models.ps1
```

Stricter retraining gate:

```powershell
.\scripts\retrain_models.ps1 -StrictRelayQuality
```

The script runs:
1. `train_models.py` with configurable walk-forward splits
2. `predict_next.py` smoke check to verify artifacts load and infer

## Validation checklist

```powershell
python -m py_compile dashboard.py telegram_notifier.py
python -m unittest discover -s tests -p "test_*.py"
```

Review generated artifacts:
- `models/training_report.json`
- `models/light_forecast_model.joblib`
- `models/relay_light_model.joblib` (if quality gate passes)
- `models/feature_columns.json`

## Operational notes

- Generated logs under `data/` are local runtime artifacts and should stay untracked.
- If relay class balance degrades, retraining may skip relay classifier by design.
- Prefer walk-forward fold consistency over one-shot split metrics when selecting production models.
