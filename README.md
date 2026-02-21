# Farmease

Smart greenhouse prototype with:
- desktop dashboard + live serial telemetry,
- Telegram alerts/controls,
- ML training and next-step prediction,
- Arduino firmware for sensor/relay IO.

This repository was reorganized (Feb 2026) and keeps backward-compatible root launchers.

## Project status

Current maturity: **Prototype / Early MVP**

Implemented:
- End-to-end data loop (sensor read -> dashboard -> CSV logs -> model training -> prediction)
- Telegram alerting and command controls
- Baseline training reports and model artifact persistence
- CI syntax + unit test checks
- Expanded ML pipeline/unit coverage (data prep, supervised shaping, split/gate utilities)
- Dashboard integration coverage for serial line processing and Telegram command dispatch
- Stability-aware model selection using walk-forward mean/std consistency
- Operations scripts/runbook for dashboard startup and retraining workflow
- Automated retraining workflow with generated health-check reports

Still pending for production readiness:
- Hardware-in-the-loop end-to-end tests (live serial device + dashboard UI + Telegram command loop)
- Rollout of scheduled retraining in deployment environments (task registration + threshold tuning)
- Installer/service packaging for non-developer environments

## Structure

- `app/` - desktop dashboard application logic
- `integrations/` - external integrations (Telegram notifier)
- `ml/` - machine learning pipeline, training, and inference scripts
- `firmware/` - Arduino/IoT firmware
- `cloud_backend/` - local demo ingest API for optional cloud sync
- `scripts/` - operational PowerShell/Python automation scripts
- `docs/` - setup and usage documentation
- `data/` - logged sensor/training CSVs (generated locally)
- `models/` - trained model artifacts and reports
- `tests/` - unit tests

## Quick start

From project root (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-ml.txt
```

Run apps/scripts:

```powershell
python dashboard.py
python train_models.py
python predict_next.py
.\scripts\run_web_frontend.ps1
```

Cloud + web dashboard quick start (two terminals):

Terminal 1:

```powershell
.\scripts\run_cloud_api.ps1
```

Terminal 2:

```powershell
$env:FARMEASE_CLOUD_ENDPOINT="http://127.0.0.1:8787/ingest"
$env:FARMEASE_CLOUD_API_KEY="demo-key"
.\scripts\run_web_frontend.ps1
```

Open: `http://127.0.0.1:8080/`

Telegram setup:
- See `docs/TELEGRAM_SETUP.md`

Operations runbook:
- See `docs/OPERATIONS.md`

Core documentation:
- `docs/TELEGRAM_SETUP.md` (alerts and bot command controls)
- `docs/OPERATIONS.md` (startup, retraining, validation)
- `docs/CLOUD_SYNC_PREP.md` (worker env + sync flow)
- `docs/CLOUD_BACKEND_SETUP.md` (local ingest API)
- `docs/EVENT_EVIDENCE.md` (generated evidence snapshot)
- `docs/HEALTH_CHECK.md` (generated retraining health report)

Optional cloud-sync prep:
- `docs/CLOUD_SYNC_PREP.md`
- `docs/CLOUD_BACKEND_SETUP.md`
- `.\scripts\run_cloud_sync.ps1`
- `.\scripts\run_cloud_api.ps1`
- `.\scripts\run_web_frontend.ps1`
- `cloud_backend/api_server.py`
- `cloud_backend/frontend_server.py`

## Validation commands

Local sanity checks:

```powershell
python -m py_compile dashboard.py telegram_notifier.py
python -m unittest discover -s tests -p "test_*.py"
```

Generate event evidence from current logs/models:

```powershell
python scripts/generate_event_evidence.py
```

Run full event rehearsal workflow:

```powershell
.\scripts\event_rehearsal.ps1
```

Run retraining + health check workflow:

```powershell
.\scripts\run_retraining_healthcheck.ps1 -FailOnHealthIssue
```

Install a daily scheduled retraining task (Windows):

```powershell
.\scripts\install_retraining_schedule.ps1 -DailyAt "02:00" -FailOnHealthIssue
```

Run optional cloud sync worker (future path):

```powershell
.\scripts\run_cloud_sync.ps1
```

Run optional local cloud ingest API:

```powershell
.\scripts\run_cloud_api.ps1
```

CI runs equivalent checks on each push/PR via:
- `.github/workflows/ci.yml`

## Environment quick reference

The dashboard loads `.env` automatically if present.

Common optional keys:
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_ALERTS`, `TELEGRAM_COMMANDS`
- `TELEGRAM_ALERT_COOLDOWN`, `TELEGRAM_ALERT_TEMP_OFFSET`, `TELEGRAM_ALERT_SOIL_MARGIN`
- `TELEGRAM_FLAME_ACTIVE_VALUE`, `TELEGRAM_IR_ACTIVE_VALUE`
- `TELEGRAM_TEMP_FAULT_MIN_C`, `TELEGRAM_TEMP_FAULT_MAX_C`, `TELEGRAM_SOIL_FAULT_ADC_MAX`
- `TELEGRAM_STARTUP_BRIEFING`, `FARMEASE_MODE`
- `FARMEASE_CLOUD_SYNC`, `FARMEASE_CLOUD_ENDPOINT`, `FARMEASE_CLOUD_API_KEY`
- `FARMEASE_CLOUD_TIMEOUT_SECONDS`, `FARMEASE_CLOUD_POLL_SECONDS`, `FARMEASE_CLOUD_BATCH_SIZE`, `FARMEASE_DEVICE_ID`

## Data and artifact policy

Generated runtime logs are intentionally git-ignored:
- `data/greenhouse_training_data.csv`
- `data/event_timeline.csv`
- `data/cloud_ingest.jsonl`
- `data/.cloud_sync_state.json`

ML artifacts are generated under `models/`.

## Direct module paths

- Dashboard core: `app/dashboard.py`
- Telegram notifier: `integrations/telegram_notifier.py`
- ML pipeline: `ml/ml_pipeline.py`
- Model training: `ml/train_models.py`
- Next-step prediction: `ml/predict_next.py`
- Firmware sketch: `firmware/iotf/iotf.ino`

## Near-term backlog (recommended)

1. Add hardware-in-the-loop end-to-end tests for dashboard serial ingest and Telegram command handling.
2. Automate retraining cadence (Task Scheduler/GitHub Actions schedule) with report checks.
3. Package dashboard as a persistent service/installer for operator-friendly deployment.
