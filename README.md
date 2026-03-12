# Farmease

Farmease is a smart greenhouse prototype that combines desktop monitoring, Telegram notifications, machine-learning-based prediction, and Arduino sensor or relay control in one repository.

## Overview

Current maturity: **Prototype / Early MVP**

Included today:
- Desktop dashboard with live serial telemetry processing
- Telegram alerting and bot command controls
- Model training and next-step prediction workflows
- Arduino firmware for greenhouse sensor and relay IO
- Optional local cloud ingest and web frontend demo
- Unit tests and CI checks for core Python paths

This repository was reorganized in Feb 2026 and keeps backward-compatible root launchers for the main Python entry points.

## Repository Layout

- `app/` - desktop dashboard application logic
- `integrations/` - Telegram integration and notifier code
- `ml/` - machine learning pipeline, training, and inference modules
- `firmware/` - Arduino / IoT firmware
- `cloud_backend/` - local demo ingest API and web frontend server
- `scripts/` - PowerShell and Python helper scripts
- `docs/` - setup and operations documentation
- `tests/` - unit and integration-style test coverage
- `data/` - generated local runtime data, ignored by git
- `models/` - generated model artifacts, ignored by git except committed source files

## Quick Start

From project root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-ml.txt
```

Run the main local workflows:

```powershell
python dashboard.py
python train_models.py
python predict_next.py
.\scripts\run_web_frontend.ps1
```

## Optional Cloud Demo

Start the local ingest API in one terminal:

```powershell
.\scripts\run_cloud_api.ps1
```

Start the web frontend in a second terminal:

```powershell
$env:FARMEASE_CLOUD_ENDPOINT="http://127.0.0.1:8787/ingest"
$env:FARMEASE_CLOUD_API_KEY="demo-key"
.\scripts\run_web_frontend.ps1
```

Then open `http://127.0.0.1:8080/`.

## Common Commands

Validation:

```powershell
python -m py_compile dashboard.py telegram_notifier.py
python -m unittest discover -s tests -p "test_*.py"
```

Generate evidence from the current local run data:

```powershell
python scripts/generate_event_evidence.py
```

Run the end-to-end rehearsal script:

```powershell
.\scripts\event_rehearsal.ps1
```

Optional cloud sync worker:

```powershell
.\scripts\run_cloud_sync.ps1
```

Optional local cloud ingest API:

```powershell
.\scripts\run_cloud_api.ps1
```

## Documentation

- `docs/TELEGRAM_SETUP.md` - Telegram alerts and bot command setup
- `docs/OPERATIONS.md` - startup, manual retraining, and validation workflow
- `docs/CLOUD_SYNC_PREP.md` - cloud sync worker configuration
- `docs/CLOUD_BACKEND_SETUP.md` - local ingest API and frontend setup

Generated local reports such as `docs/EVENT_EVIDENCE.md` and `docs/HEALTH_CHECK.md` are intentionally not committed.

## Environment Notes

The dashboard loads `.env` automatically if present.

Common optional keys:
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_ALERTS`, `TELEGRAM_COMMANDS`
- `TELEGRAM_ALERT_COOLDOWN`, `TELEGRAM_ALERT_TEMP_OFFSET`, `TELEGRAM_ALERT_SOIL_MARGIN`
- `TELEGRAM_FLAME_ACTIVE_VALUE`, `TELEGRAM_IR_ACTIVE_VALUE`
- `TELEGRAM_TEMP_FAULT_MIN_C`, `TELEGRAM_TEMP_FAULT_MAX_C`, `TELEGRAM_SOIL_FAULT_ADC_MAX`
- `TELEGRAM_STARTUP_BRIEFING`, `FARMEASE_MODE`
- `FARMEASE_CLOUD_SYNC`, `FARMEASE_CLOUD_ENDPOINT`, `FARMEASE_CLOUD_API_KEY`
- `FARMEASE_CLOUD_TIMEOUT_SECONDS`, `FARMEASE_CLOUD_POLL_SECONDS`, `FARMEASE_CLOUD_BATCH_SIZE`, `FARMEASE_DEVICE_ID`

## What Stays Out Of Git

The repository ignores machine-specific and generated outputs, including:
- local `.env` files and secret directories
- runtime CSV and JSONL data under `data/`
- trained model artifacts under `models/`
- generated operational reports under `docs/`

If you train models or run the dashboard locally, expect new artifacts to appear in `data/` and `models/` without being staged for commit.

## Direct Module Paths

- Dashboard core: `app/dashboard.py`
- Telegram notifier: `integrations/telegram_notifier.py`
- ML pipeline: `ml/ml_pipeline.py`
- Model training: `ml/train_models.py`
- Next-step prediction: `ml/predict_next.py`
- Firmware sketch: `firmware/iotf/iotf.ino`

## Near-Term Backlog

1. Add hardware-in-the-loop end-to-end tests for dashboard serial ingest and Telegram command handling.
2. Package the dashboard as a persistent service or installer for operator-friendly deployment.
