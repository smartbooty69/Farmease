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

## Retraining + health check (automated workflow)

Run the full automation flow manually:

```powershell
.\scripts\run_retraining_healthcheck.ps1 -FailOnHealthIssue
```

This workflow runs:
1. Model retraining
2. Prediction smoke check
3. Event evidence generation (`docs/EVENT_EVIDENCE.md`)
4. Health check generation (`models/health_check_report.json`, `docs/HEALTH_CHECK.md`)

Install a daily scheduled task on Windows:

```powershell
.\scripts\install_retraining_schedule.ps1 -DailyAt "02:00" -FailOnHealthIssue
```

Useful scheduled-task commands:

```powershell
Start-ScheduledTask -TaskName "FarmEase-RetrainingHealthcheck"
Get-ScheduledTask -TaskName "FarmEase-RetrainingHealthcheck"
Unregister-ScheduledTask -TaskName "FarmEase-RetrainingHealthcheck" -Confirm:$false
```

## Validation checklist

```powershell
python -m py_compile dashboard.py telegram_notifier.py
python -m unittest discover -s tests -p "test_*.py"
```

Generate event evidence summary:

```powershell
python scripts/generate_event_evidence.py
```

## Event-day rehearsal (recommended)

Run the complete pre-event sequence in one command:

```powershell
.\scripts\event_rehearsal.ps1
```

This sequence executes:
1. Syntax checks (`py_compile`)
2. Unit tests
3. Retraining + prediction smoke check
4. Event evidence generation (`docs/EVENT_EVIDENCE.md`)

For 4-8 hour stability proof, use:
- `docs/EVENT_RELIABILITY_LOG_TEMPLATE.md`

## Optional cloud-sync worker

Cloud sync is optional and does not replace local control.

Start demo cloud ingest API (optional):

```powershell
.\scripts\run_cloud_api.ps1
```

```powershell
.\scripts\run_cloud_sync.ps1
```

Setup notes:
- `docs/CLOUD_SYNC_PREP.md`
- `docs/CLOUD_BACKEND_SETUP.md`

Review generated artifacts:
- `models/training_report.json`
- `models/light_forecast_model.joblib`
- `models/relay_light_model.joblib` (if quality gate passes)
- `models/feature_columns.json`
- `docs/EVENT_EVIDENCE.md`

## Operational notes

- Generated logs under `data/` are local runtime artifacts and should stay untracked.
- If relay class balance degrades, retraining may skip relay classifier by design.
- Prefer walk-forward fold consistency over one-shot split metrics when selecting production models.
